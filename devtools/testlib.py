# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""this module contains base classes and utilities for cubicweb tests"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import os
import sys
import re
import urlparse
from os.path import dirname, join, abspath
from urllib import unquote
from math import log
from contextlib import contextmanager
from warnings import warn

import yams.schema

from logilab.common.testlib import TestCase, InnerTest, Tags
from logilab.common.pytest import nocoverage, pause_tracing, resume_tracing
from logilab.common.debugger import Debugger
from logilab.common.umessage import message_from_string
from logilab.common.decorators import cached, classproperty, clear_cache
from logilab.common.deprecation import deprecated, class_deprecated
from logilab.common.shellutils import getlogin

from cubicweb import ValidationError, NoSelectableObject, AuthenticationError
from cubicweb import cwconfig, devtools, web, server
from cubicweb.dbapi import ProgrammingError, DBAPISession, repo_connect
from cubicweb.sobjects import notification
from cubicweb.web import Redirect, application
from cubicweb.server.session import security_enabled
from cubicweb.server.hook import SendMailOp
from cubicweb.devtools import SYSTEM_ENTITIES, SYSTEM_RELATIONS, VIEW_VALIDATORS
from cubicweb.devtools import BASE_URL, fake, htmlparser
from cubicweb.utils import json

# low-level utilities ##########################################################

class CubicWebDebugger(Debugger):
    """special debugger class providing a 'view' function which saves some
    html into a temporary file and open a web browser to examinate it.
    """
    def do_view(self, arg):
        import webbrowser
        data = self._getval(arg)
        file('/tmp/toto.html', 'w').write(data)
        webbrowser.open('file:///tmp/toto.html')

def line_context_filter(line_no, center, before=3, after=None):
    """return true if line are in context

    if after is None: after = before
    """
    if after is None:
        after = before
    return center - before <= line_no <= center + after

def unprotected_entities(schema, strict=False):
    """returned a set of each non final entity type, excluding "system" entities
    (eg CWGroup, CWUser...)
    """
    if strict:
        protected_entities = yams.schema.BASE_TYPES
    else:
        protected_entities = yams.schema.BASE_TYPES.union(SYSTEM_ENTITIES)
    return set(schema.entities()) - protected_entities

def refresh_repo(repo, resetschema=False, resetvreg=False):
    for pool in repo.pools:
        pool.close(True)
    repo.system_source.shutdown()
    devtools.reset_test_database(repo.config)
    for pool in repo.pools:
        pool.reconnect()
    repo._type_source_cache = {}
    repo._extid_cache = {}
    repo.querier._rql_cache = {}
    for source in repo.sources:
        source.reset_caches()
    if resetschema:
        repo.set_schema(repo.config.load_schema(), resetvreg=resetvreg)


# email handling, to test emails sent by an application ########################

MAILBOX = []

class Email:
    """you'll get instances of Email into MAILBOX during tests that trigger
    some notification.

    * `msg` is the original message object

    * `recipients` is a list of email address which are the recipients of this
      message
    """
    def __init__(self, recipients, msg):
        self.recipients = recipients
        self.msg = msg

    @property
    def message(self):
        return message_from_string(self.msg)

    @property
    def subject(self):
        return self.message.get('Subject')

    @property
    def content(self):
        return self.message.get_payload(decode=True)

    def __repr__(self):
        return '<Email to %s with subject %s>' % (','.join(self.recipients),
                                                  self.message.get('Subject'))

# the trick to get email into MAILBOX instead of actually sent: monkey patch
# cwconfig.SMTP object
class MockSMTP:
    def __init__(self, server, port):
        pass
    def close(self):
        pass
    def sendmail(self, helo_addr, recipients, msg):
        MAILBOX.append(Email(recipients, msg))

cwconfig.SMTP = MockSMTP


class TestCaseConnectionProxy(object):
    """thin wrapper around `cubicweb.dbapi.Connection` context-manager
    used in CubicWebTC (cf. `cubicweb.devtools.testlib.CubicWebTC.login` method)

    It just proxies to the default connection context manager but
    restores the original connection on exit.
    """
    def __init__(self, testcase, cnx):
        self.testcase = testcase
        self.cnx = cnx

    def __getattr__(self, attrname):
        return getattr(self.cnx, attrname)

    def __enter__(self):
        return self.cnx.__enter__()

    def __exit__(self, exctype, exc, tb):
        try:
            return self.cnx.__exit__(exctype, exc, tb)
        finally:
            self.cnx.close()
            self.testcase.restore_connection()

# base class for cubicweb tests requiring a full cw environments ###############

class CubicWebTC(TestCase):
    """abstract class for test using an apptest environment

    attributes:

    * `vreg`, the vregistry
    * `schema`, self.vreg.schema
    * `config`, cubicweb configuration
    * `cnx`, dbapi connection to the repository using an admin user
    * `session`, server side session associated to `cnx`
    * `app`, the cubicweb publisher (for web testing)
    * `repo`, the repository object
    * `admlogin`, login of the admin user
    * `admpassword`, password of the admin user
    * `shell`, create and use shell environment
    """
    appid = 'data'
    configcls = devtools.ApptestConfiguration
    reset_schema = reset_vreg = False # reset schema / vreg between tests
    tags = TestCase.tags | Tags('cubicweb', 'cw_repo')

    @classproperty
    def config(cls):
        """return the configuration object

        Configuration is cached on the test class.
        """
        try:
            return cls.__dict__['_config']
        except KeyError:
            home = abspath(join(dirname(sys.modules[cls.__module__].__file__), cls.appid))
            config = cls._config = cls.configcls(cls.appid, apphome=home)
            config.mode = 'test'
            return config

    @classmethod
    def init_config(cls, config):
        """configuration initialization hooks.

        You may only want to override here the configuraton logic.

        Otherwise, consider to use a different :class:`ApptestConfiguration`
        defined in the `configcls` class attribute"""
        source = config.sources()['system']
        cls.admlogin = unicode(source['db-user'])
        cls.admpassword = source['db-password']
        # uncomment the line below if you want rql queries to be logged
        #config.global_set_option('query-log-file',
        #                         '/tmp/test_rql_log.' + `os.getpid()`)
        config.global_set_option('log-file', None)
        # set default-dest-addrs to a dumb email address to avoid mailbox or
        # mail queue pollution
        config.global_set_option('default-dest-addrs', ['whatever'])
        send_to =  '%s@logilab.fr' % getlogin()
        config.global_set_option('sender-addr', send_to)
        config.global_set_option('default-dest-addrs', send_to)
        config.global_set_option('sender-name', 'cubicweb-test')
        config.global_set_option('sender-addr', 'cubicweb-test@logilab.fr')
        # default_base_url on config class isn't enough for TestServerConfiguration
        config.global_set_option('base-url', config.default_base_url())
        # web resources
        try:
            config.global_set_option('embed-allowed', re.compile('.*'))
        except: # not in server only configuration
            pass

    @classmethod
    def _init_repo(cls):
        """init the repository and connection to it.

        Repository and connection are cached on the test class. Once
        initialized, we simply reset connections and repository caches.
        """
        if not 'repo' in cls.__dict__:
            cls._build_repo()
        else:
            try:
                cls.cnx.rollback()
            except ProgrammingError:
                pass
            cls._refresh_repo()

    @classmethod
    def _build_repo(cls):
        cls.repo, cls.cnx = devtools.init_test_database(config=cls.config)
        cls.init_config(cls.config)
        cls.repo.hm.call_hooks('server_startup', repo=cls.repo)
        cls.vreg = cls.repo.vreg
        cls.websession = DBAPISession(cls.cnx, cls.admlogin)
        cls._orig_cnx = (cls.cnx, cls.websession)
        cls.config.repository = lambda x=None: cls.repo

    @classmethod
    def _refresh_repo(cls):
        refresh_repo(cls.repo, cls.reset_schema, cls.reset_vreg)

    # global resources accessors ###############################################

    @property
    def schema(self):
        """return the application schema"""
        return self.vreg.schema

    @property
    def session(self):
        """return current server side session (using default manager account)"""
        session = self.repo._sessions[self.cnx.sessionid]
        session.set_pool()
        return session

    @property
    def adminsession(self):
        """return current server side session (using default manager account)"""
        return self.repo._sessions[self._orig_cnx[0].sessionid]

    def shell(self):
        """return a shell session object"""
        from cubicweb.server.migractions import ServerMigrationHelper
        return ServerMigrationHelper(None, repo=self.repo, cnx=self.cnx,
                                     interactive=False,
                                     # hack so it don't try to load fs schema
                                     schema=1)

    def set_option(self, optname, value):
        self.config.global_set_option(optname, value)

    def set_debug(self, debugmode):
        server.set_debug(debugmode)

    def debugged(self, debugmode):
        return server.debugged(debugmode)

    # default test setup and teardown #########################################

    def setUp(self):
        # monkey patch send mail operation so emails are sent synchronously
        self._old_mail_postcommit_event = SendMailOp.postcommit_event
        SendMailOp.postcommit_event = SendMailOp.sendmails
        pause_tracing()
        previous_failure = self.__class__.__dict__.get('_repo_init_failed')
        if previous_failure is not None:
            self.skipTest('repository is not initialised: %r' % previous_failure)
        try:
            self._init_repo()
        except Exception, ex:
            self.__class__._repo_init_failed = ex
            raise
        resume_tracing()
        self._cnxs = []
        self.setup_database()
        self.commit()
        MAILBOX[:] = [] # reset mailbox

    def tearDown(self):
        if not self.cnx._closed:
            self.cnx.rollback()
        for cnx in self._cnxs:
            if not cnx._closed:
                cnx.close()
        SendMailOp.postcommit_event = self._old_mail_postcommit_event

    def setup_database(self):
        """add your database setup code by overriding this method"""

    # user / session management ###############################################

    def user(self, req=None):
        """return the application schema"""
        if req is None:
            req = self.request()
            return self.cnx.user(req)
        else:
            return req.user

    def create_user(self, login, groups=('users',), password=None, req=None,
                    commit=True, **kwargs):
        """create and return a new user entity"""
        if password is None:
            password = login.encode('utf8')
        if req is None:
            req = self._orig_cnx[0].request()
        user = req.create_entity('CWUser', login=unicode(login),
                                 upassword=password, **kwargs)
        req.execute('SET X in_group G WHERE X eid %%(x)s, G name IN(%s)'
                    % ','.join(repr(str(g)) for g in groups),
                    {'x': user.eid})
        user.cw_clear_relation_cache('in_group', 'subject')
        if commit:
            req.cnx.commit()
        return user

    def login(self, login, **kwargs):
        """return a connection for the given login/password"""
        if login == self.admlogin:
            self.restore_connection()
            # definitly don't want autoclose when used as a context manager
            return self.cnx
        autoclose = kwargs.pop('autoclose', True)
        if not kwargs:
            kwargs['password'] = str(login)
        self.cnx = repo_connect(self.repo, unicode(login), **kwargs)
        self.websession = DBAPISession(self.cnx)
        self._cnxs.append(self.cnx)
        if login == self.vreg.config.anonymous_user()[0]:
            self.cnx.anonymous_connection = True
        if autoclose:
            return TestCaseConnectionProxy(self, self.cnx)
        return self.cnx

    def restore_connection(self):
        if not self.cnx is self._orig_cnx[0]:
            if not self.cnx._closed:
                self.cnx.close()
            try:
                self._cnxs.remove(self.cnx)
            except ValueError:
                pass
        self.cnx, self.websession = self._orig_cnx

    # db api ##################################################################

    @nocoverage
    def cursor(self, req=None):
        return self.cnx.cursor(req or self.request())

    @nocoverage
    def execute(self, rql, args=None, eidkey=None, req=None):
        """executes <rql>, builds a resultset, and returns a couple (rset, req)
        where req is a FakeRequest
        """
        if eidkey is not None:
            warn('[3.8] eidkey is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        req = req or self.request(rql=rql)
        return req.execute(unicode(rql), args)

    @nocoverage
    def commit(self):
        try:
            return self.cnx.commit()
        finally:
            self.session.set_pool() # ensure pool still set after commit

    @nocoverage
    def rollback(self):
        try:
            self.cnx.rollback()
        except ProgrammingError:
            pass # connection closed
        finally:
            self.session.set_pool() # ensure pool still set after commit

    # # server side db api #######################################################

    def sexecute(self, rql, args=None, eid_key=None):
        if eid_key is not None:
            warn('[3.8] eid_key is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        self.session.set_pool()
        return self.session.execute(rql, args)

    # other utilities #########################################################

    def grant_permission(self, entity, group, pname, plabel=None):
        """insert a permission on an entity. Will have to commit the main
        connection to be considered
        """
        pname = unicode(pname)
        plabel = plabel and unicode(plabel) or unicode(group)
        e = entity.eid
        with security_enabled(self.session, False, False):
            peid = self.execute(
            'INSERT CWPermission X: X name %(pname)s, X label %(plabel)s,'
            'X require_group G, E require_permission X '
            'WHERE G name %(group)s, E eid %(e)s',
            locals())[0][0]
        return peid

    @contextmanager
    def temporary_appobjects(self, *appobjects):
        self.vreg._loadedmods.setdefault(self.__module__, {})
        for obj in appobjects:
            self.vreg.register(obj)
        try:
            yield
        finally:
            for obj in appobjects:
                self.vreg.unregister(obj)

    def assertModificationDateGreater(self, entity, olddate):
        entity.cw_attr_cache.pop('modification_date', None)
        self.failUnless(entity.modification_date > olddate)


    # workflow utilities #######################################################

    def assertPossibleTransitions(self, entity, expected):
        transitions = entity.cw_adapt_to('IWorkflowable').possible_transitions()
        self.assertListEqual(sorted(tr.name for tr in transitions),
                             sorted(expected))


    # views and actions registries inspection ##################################

    def pviews(self, req, rset):
        return sorted((a.__regid__, a.__class__)
                      for a in self.vreg['views'].possible_views(req, rset=rset))

    def pactions(self, req, rset,
                 skipcategories=('addrelated', 'siteactions', 'useractions',
                                 'footer', 'manage')):
        return [(a.__regid__, a.__class__)
                for a in self.vreg['actions'].poss_visible_objects(req, rset=rset)
                if a.category not in skipcategories]

    def pactions_by_cats(self, req, rset, categories=('addrelated',)):
        return [(a.__regid__, a.__class__)
                for a in self.vreg['actions'].poss_visible_objects(req, rset=rset)
                if a.category in categories]

    def pactionsdict(self, req, rset,
                     skipcategories=('addrelated', 'siteactions', 'useractions',
                                     'footer', 'manage')):
        res = {}
        for a in self.vreg['actions'].poss_visible_objects(req, rset=rset):
            if a.category not in skipcategories:
                res.setdefault(a.category, []).append(a.__class__)
        return res

    def action_submenu(self, req, rset, id):
        return self._test_action(self.vreg['actions'].select(id, req, rset=rset))

    def _test_action(self, action):
        class fake_menu(list):
            @property
            def items(self):
                return self
        class fake_box(object):
            def action_link(self, action, **kwargs):
                return (action.title, action.url())
        submenu = fake_menu()
        action.fill_menu(fake_box(), submenu)
        return submenu

    def list_views_for(self, rset):
        """returns the list of views that can be applied on `rset`"""
        req = rset.req
        only_once_vids = ('primary', 'secondary', 'text')
        req.data['ex'] = ValueError("whatever")
        viewsvreg = self.vreg['views']
        for vid, views in viewsvreg.items():
            if vid[0] == '_':
                continue
            if rset.rowcount > 1 and vid in only_once_vids:
                continue
            views = [view for view in views
                     if view.category != 'startupview'
                     and not issubclass(view, notification.NotificationView)
                     and not isinstance(view, class_deprecated)]
            if views:
                try:
                    view = viewsvreg._select_best(views, req, rset=rset)
                    if view.linkable():
                        yield view
                    else:
                        not_selected(self.vreg, view)
                    # else the view is expected to be used as subview and should
                    # not be tested directly
                except NoSelectableObject:
                    continue

    def list_actions_for(self, rset):
        """returns the list of actions that can be applied on `rset`"""
        req = rset.req
        for action in self.vreg['actions'].possible_objects(req, rset=rset):
            yield action

    def list_boxes_for(self, rset):
        """returns the list of boxes that can be applied on `rset`"""
        req = rset.req
        for box in self.vreg['ctxcomponents'].possible_objects(req, rset=rset):
            yield box

    def list_startup_views(self):
        """returns the list of startup views"""
        req = self.request()
        for view in self.vreg['views'].possible_views(req, None):
            if view.category == 'startupview':
                yield view.__regid__
            else:
                not_selected(self.vreg, view)

    # web ui testing utilities #################################################

    @property
    @cached
    def app(self):
        """return a cubicweb publisher"""
        publisher = application.CubicWebPublisher(self.config, vreg=self.vreg)
        def raise_error_handler(*args, **kwargs):
            raise
        publisher.error_handler = raise_error_handler
        return publisher

    requestcls = fake.FakeRequest
    def request(self, rollbackfirst=False, **kwargs):
        """return a web ui request"""
        req = self.requestcls(self.vreg, form=kwargs)
        if rollbackfirst:
            self.websession.cnx.rollback()
        req.set_session(self.websession)
        return req

    def remote_call(self, fname, *args):
        """remote json call simulation"""
        dump = json.dumps
        args = [dump(arg) for arg in args]
        req = self.request(fname=fname, pageid='123', arg=args)
        ctrl = self.vreg['controllers'].select('json', req)
        return ctrl.publish(), req

    def app_publish(self, req, path='view'):
        return self.app.publish(path, req)

    def ctrl_publish(self, req, ctrl='edit'):
        """call the publish method of the edit controller"""
        ctrl = self.vreg['controllers'].select(ctrl, req, appli=self.app)
        try:
            result = ctrl.publish()
            req.cnx.commit()
        except web.Redirect:
            req.cnx.commit()
            raise
        return result

    def req_from_url(self, url):
        """parses `url` and builds the corresponding CW-web request

        req.form will be setup using the url's query string
        """
        req = self.request()
        if isinstance(url, unicode):
            url = url.encode(req.encoding) # req.setup_params() expects encoded strings
        querystring = urlparse.urlparse(url)[-2]
        params = urlparse.parse_qs(querystring)
        req.setup_params(params)
        return req

    def url_publish(self, url):
        """takes `url`, uses application's app_resolver to find the
        appropriate controller, and publishes the result.

        This should pretty much correspond to what occurs in a real CW server
        except the apache-rewriter component is not called.
        """
        req = self.req_from_url(url)
        ctrlid, rset = self.app.url_resolver.process(req, req.relative_path(False))
        return self.ctrl_publish(req, ctrlid)

    def expect_redirect(self, callback, req):
        """call the given callback with req as argument, expecting to get a
        Redirect exception
        """
        try:
            callback(req)
        except Redirect, ex:
            try:
                path, params = ex.location.split('?', 1)
            except ValueError:
                path = ex.location
                params = {}
            else:
                cleanup = lambda p: (p[0], unquote(p[1]))
                params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
            if path.startswith(req.base_url()): # may be relative
                path = path[len(req.base_url()):]
            return path, params
        else:
            self.fail('expected a Redirect exception')

    def expect_redirect_publish(self, req, path='edit'):
        """call the publish method of the application publisher, expecting to
        get a Redirect exception
        """
        return self.expect_redirect(lambda x: self.app_publish(x, path), req)

    def init_authentication(self, authmode, anonuser=None):
        self.set_option('auth-mode', authmode)
        self.set_option('anonymous-user', anonuser)
        if anonuser is None:
            self.config.anonymous_credential = None
        else:
            self.config.anonymous_credential = (anonuser, anonuser)
        req = self.request()
        origsession = req.session
        req.session = req.cnx = None
        del req.execute # get back to class implementation
        sh = self.app.session_handler
        authm = sh.session_manager.authmanager
        authm.anoninfo = self.vreg.config.anonymous_user()
        authm.anoninfo = authm.anoninfo[0], {'password': authm.anoninfo[1]}
        # not properly cleaned between tests
        self.open_sessions = sh.session_manager._sessions = {}
        return req, origsession

    def assertAuthSuccess(self, req, origsession, nbsessions=1):
        sh = self.app.session_handler
        path, params = self.expect_redirect(lambda x: self.app.connect(x), req)
        session = req.session
        self.assertEqual(len(self.open_sessions), nbsessions, self.open_sessions)
        self.assertEqual(session.login, origsession.login)
        self.assertEqual(session.anonymous_session, False)
        self.assertEqual(path, 'view')
        self.assertEqual(params, {'__message': 'welcome %s !' % req.user.login})

    def assertAuthFailure(self, req, nbsessions=0):
        self.app.connect(req)
        self.assertIsInstance(req.session, DBAPISession)
        self.assertEqual(req.session.cnx, None)
        self.assertEqual(req.cnx, None)
        self.assertEqual(len(self.open_sessions), nbsessions)
        clear_cache(req, 'get_authorization')

    # content validation #######################################################

    # validators are used to validate (XML, DTD, whatever) view's content
    # validators availables are :
    #  DTDValidator : validates XML + declared DTD
    #  SaxOnlyValidator : guarantees XML is well formed
    #  None : do not try to validate anything
    # validators used must be imported from from.devtools.htmlparser
    content_type_validators = {
        # maps MIME type : validator name
        #
        # do not set html validators here, we need HTMLValidator for html
        # snippets
        #'text/html': DTDValidator,
        #'application/xhtml+xml': DTDValidator,
        'application/xml': htmlparser.SaxOnlyValidator,
        'text/xml': htmlparser.SaxOnlyValidator,
        'text/plain': None,
        'text/comma-separated-values': None,
        'text/x-vcard': None,
        'text/calendar': None,
        'application/json': None,
        'image/png': None,
        }
    # maps vid : validator name (override content_type_validators)
    vid_validators = dict((vid, htmlparser.VALMAP[valkey])
                          for vid, valkey in VIEW_VALIDATORS.iteritems())


    def view(self, vid, rset=None, req=None, template='main-template',
             **kwargs):
        """This method tests the view `vid` on `rset` using `template`

        If no error occurred while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        req = req or rset and rset.req or self.request()
        req.form['vid'] = vid
        kwargs['rset'] = rset
        viewsreg = self.vreg['views']
        view = viewsreg.select(vid, req, **kwargs)
        # set explicit test description
        if rset is not None:
            self.set_description("testing vid=%s defined in %s with (%s)" % (
                vid, view.__module__, rset.printable_rql()))
        else:
            self.set_description("testing vid=%s defined in %s without rset" % (
                vid, view.__module__))
        if template is None: # raw view testing, no template
            viewfunc = view.render
        else:
            kwargs['view'] = view
            templateview = viewsreg.select(template, req, **kwargs)
            viewfunc = lambda **k: viewsreg.main_template(req, template,
                                                          **kwargs)
        kwargs.pop('rset')
        return self._test_view(viewfunc, view, template, kwargs)


    def _test_view(self, viewfunc, view, template='main-template', kwargs={}):
        """this method does the actual call to the view

        If no error occurred while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        try:
            output = viewfunc(**kwargs)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            # hijack exception: generative tests stop when the exception
            # is not an AssertionError
            klass, exc, tcbk = sys.exc_info()
            try:
                msg = '[%s in %s] %s' % (klass, view.__regid__, exc)
            except:
                msg = '[%s in %s] undisplayable exception' % (klass, view.__regid__)
            raise AssertionError, msg, tcbk
        return self._check_html(output, view, template)

    def get_validator(self, view=None, content_type=None, output=None):
        if view is not None:
            try:
                return self.vid_validators[view.__regid__]()
            except KeyError:
                if content_type is None:
                    content_type = view.content_type
        if content_type is None:
            content_type = 'text/html'
        if content_type in ('text/html', 'application/xhtml+xml'):
            if output and output.startswith('<?xml'):
                default_validator = htmlparser.DTDValidator
            else:
                default_validator = htmlparser.HTMLValidator
        else:
            default_validator = None
        validatorclass = self.content_type_validators.get(content_type,
                                                          default_validator)
        if validatorclass is None:
            return
        return validatorclass()

    @nocoverage
    def _check_html(self, output, view, template='main-template'):
        """raises an exception if the HTML is invalid"""
        output = output.strip()
        validator = self.get_validator(view, output=output)
        if validator is None:
            return
        if isinstance(validator, htmlparser.DTDValidator):
            # XXX remove <canvas> used in progress widget, unknown in html dtd
            output = re.sub('<canvas.*?></canvas>', '', output)
        return self.assertWellFormed(validator, output.strip(), context= view.__regid__)

    def assertWellFormed(self, validator, content, context=None):
        try:
            return validator.parse_string(content)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            # hijack exception: generative tests stop when the exception
            # is not an AssertionError
            klass, exc, tcbk = sys.exc_info()
            if context is None:
                msg = u'[%s]' % (klass,)
            else:
                msg = u'[%s in %s]' % (klass, context)
            msg = msg.encode(sys.getdefaultencoding(), 'replace')

            try:
                str_exc = str(exc)
            except:
                str_exc = 'undisplayable exception'
            msg += str_exc
            if content is not None:
                position = getattr(exc, "position", (0,))[0]
                if position:
                    # define filter
                    if isinstance(content, str):
                        content = unicode(content, sys.getdefaultencoding(), 'replace')
                    content = content.splitlines()
                    width = int(log(len(content), 10)) + 1
                    line_template = " %" + ("%i" % width) + "i: %s"
                    # XXX no need to iterate the whole file except to get
                    # the line number
                    content = u'\n'.join(line_template % (idx + 1, line)
                                         for idx, line in enumerate(content)
                                         if line_context_filter(idx+1, position))
                    msg += u'\nfor content:\n%s' % content
            raise AssertionError, msg, tcbk

    def assertDocTestFile(self, testfile):
        # doctest returns tuple (failure_count, test_count)
        result = self.shell().process_script(testfile)
        if result[0] and result[1]:
            raise self.failureException("doctest file '%s' failed"
                                        % testfile)

    # notifications ############################################################

    def assertSentEmail(self, subject, recipients=None, nb_msgs=None):
        """test recipients in system mailbox for given email subject

        :param subject: email subject to find in mailbox
        :param recipients: list of email recipients
        :param nb_msgs: expected number of entries
        :returns: list of matched emails
        """
        messages = [email for email in MAILBOX
                    if email.message.get('Subject') == subject]
        if recipients is not None:
            sent_to = set()
            for msg in messages:
                sent_to.update(msg.recipients)
            self.assertSetEqual(set(recipients), sent_to)
        if nb_msgs is not None:
            self.assertEqual(len(MAILBOX), nb_msgs)
        return messages

    # deprecated ###############################################################

    @deprecated('[3.8] use self.execute(...).get_entity(0, 0)')
    def entity(self, rql, args=None, eidkey=None, req=None):
        if eidkey is not None:
            warn('[3.8] eidkey is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        return self.execute(rql, args, req=req).get_entity(0, 0)

    @deprecated('[3.6] use self.request().create_entity(...)')
    def add_entity(self, etype, req=None, **kwargs):
        if req is None:
            req = self.request()
        return req.create_entity(etype, **kwargs)


# auto-populating test classes and utilities ###################################

from cubicweb.devtools.fill import insert_entity_queries, make_relations_queries

# XXX cleanup unprotected_entities & all mess

def how_many_dict(schema, cursor, how_many, skip):
    """given a schema, compute how many entities by type we need to be able to
    satisfy relations cardinality.

    The `how_many` argument tells how many entities of which type we want at
    least.

    Return a dictionary with entity types as key, and the number of entities for
    this type as value.
    """
    relmap = {}
    for rschema in schema.relations():
        if rschema.final:
            continue
        for subj, obj in rschema.rdefs:
            card = rschema.rdef(subj, obj).cardinality
            # if the relation is mandatory, we'll need at least as many subj and
            # obj to satisfy it
            if card[0] in '1+' and card[1] in '1?':
                # subj has to be linked to at least one obj,
                # but obj can be linked to only one subj
                # -> we need at least as many subj as obj to satisfy
                #    cardinalities for this relation
                relmap.setdefault((rschema, subj), []).append(str(obj))
            if card[1] in '1+' and card[0] in '1?':
                # reverse subj and obj in the above explanation
                relmap.setdefault((rschema, obj), []).append(str(subj))
    unprotected = unprotected_entities(schema)
    for etype in skip: # XXX (syt) duh? explain or kill
        unprotected.add(etype)
    howmanydict = {}
    # step 1, compute a base number of each entity types: number of already
    # existing entities of this type + `how_many`
    for etype in unprotected_entities(schema, strict=True):
        howmanydict[str(etype)] = cursor.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
        if etype in unprotected:
            howmanydict[str(etype)] += how_many
    # step 2, augment nb entity per types to satisfy cardinality constraints,
    # by recomputing for each relation that constrained an entity type:
    #
    # new num for etype = max(current num, sum(num for possible target etypes))
    #
    # XXX we should first check there is no cycle then propagate changes
    for (rschema, etype), targets in relmap.iteritems():
        relfactor = sum(howmanydict[e] for e in targets)
        howmanydict[str(etype)] = max(relfactor, howmanydict[etype])
    return howmanydict


class AutoPopulateTest(CubicWebTC):
    """base class for test with auto-populating of the database"""
    __abstract__ = True

    tags = CubicWebTC.tags | Tags('autopopulated')

    pdbclass = CubicWebDebugger
    # this is a hook to be able to define a list of rql queries
    # that are application dependent and cannot be guessed automatically
    application_rql = []

    no_auto_populate = ()
    ignored_relations = set()

    def to_test_etypes(self):
        return unprotected_entities(self.schema, strict=True)

    def custom_populate(self, how_many, cursor):
        pass

    def post_populate(self, cursor):
        pass


    @nocoverage
    def auto_populate(self, how_many):
        """this method populates the database with `how_many` entities
        of each possible type. It also inserts random relations between them
        """
        with security_enabled(self.session, read=False, write=False):
            self._auto_populate(how_many)

    def _auto_populate(self, how_many):
        cu = self.cursor()
        self.custom_populate(how_many, cu)
        vreg = self.vreg
        howmanydict = how_many_dict(self.schema, cu, how_many, self.no_auto_populate)
        for etype in unprotected_entities(self.schema):
            if etype in self.no_auto_populate:
                continue
            nb = howmanydict.get(etype, how_many)
            for rql, args in insert_entity_queries(etype, self.schema, vreg, nb):
                cu.execute(rql, args)
        edict = {}
        for etype in unprotected_entities(self.schema, strict=True):
            rset = cu.execute('%s X' % etype)
            edict[str(etype)] = set(row[0] for row in rset.rows)
        existingrels = {}
        ignored_relations = SYSTEM_RELATIONS | self.ignored_relations
        for rschema in self.schema.relations():
            if rschema.final or rschema in ignored_relations:
                continue
            rset = cu.execute('DISTINCT Any X,Y WHERE X %s Y' % rschema)
            existingrels.setdefault(rschema.type, set()).update((x, y) for x, y in rset)
        q = make_relations_queries(self.schema, edict, cu, ignored_relations,
                                   existingrels=existingrels)
        for rql, args in q:
            try:
                cu.execute(rql, args)
            except ValidationError, ex:
                # failed to satisfy some constraint
                print 'error in automatic db population', ex
                self.session.commit_state = None # reset uncommitable flag
        self.post_populate(cu)
        self.commit()

    def iter_individual_rsets(self, etypes=None, limit=None):
        etypes = etypes or self.to_test_etypes()
        for etype in etypes:
            if limit:
                rql = 'Any X LIMIT %s WHERE X is %s' % (limit, etype)
            else:
                rql = 'Any X WHERE X is %s' % etype
            rset = self.execute(rql)
            for row in xrange(len(rset)):
                if limit and row > limit:
                    break
                # XXX iirk
                rset2 = rset.limit(limit=1, offset=row)
                yield rset2

    def iter_automatic_rsets(self, limit=10):
        """generates basic resultsets for each entity type"""
        etypes = self.to_test_etypes()
        if not etypes:
            return
        for etype in etypes:
            yield self.execute('Any X LIMIT %s WHERE X is %s' % (limit, etype))
        etype1 = etypes.pop()
        try:
            etype2 = etypes.pop()
        except KeyError:
            etype2 = etype1
        # test a mixed query (DISTINCT/GROUP to avoid getting duplicate
        # X which make muledit view failing for instance (html validation fails
        # because of some duplicate "id" attributes)
        yield self.execute('DISTINCT Any X, MAX(Y) GROUPBY X WHERE X is %s, Y is %s' % (etype1, etype2))
        # test some application-specific queries if defined
        for rql in self.application_rql:
            yield self.execute(rql)

    def _test_everything_for(self, rset):
        """this method tries to find everything that can be tested
        for `rset` and yields a callable test (as needed in generative tests)
        """
        propdefs = self.vreg['propertydefs']
        # make all components visible
        for k, v in propdefs.items():
            if k.endswith('visible') and not v['default']:
                propdefs[k]['default'] = True
        for view in self.list_views_for(rset):
            backup_rset = rset.copy(rset.rows, rset.description)
            yield InnerTest(self._testname(rset, view.__regid__, 'view'),
                            self.view, view.__regid__, rset,
                            rset.req.reset_headers(), 'main-template')
            # We have to do this because some views modify the
            # resultset's syntax tree
            rset = backup_rset
        for action in self.list_actions_for(rset):
            yield InnerTest(self._testname(rset, action.__regid__, 'action'), self._test_action, action)
        for box in self.list_boxes_for(rset):
            w = [].append
            yield InnerTest(self._testname(rset, box.__regid__, 'box'), box.render, w)

    @staticmethod
    def _testname(rset, objid, objtype):
        return '%s_%s_%s' % ('_'.join(rset.column_types(0)), objid, objtype)


# concrete class for automated application testing  ############################

class AutomaticWebTest(AutoPopulateTest):
    """import this if you wan automatic tests to be ran"""

    tags = AutoPopulateTest.tags | Tags('web', 'generated')

    def setUp(self):
        AutoPopulateTest.setUp(self)
        # access to self.app for proper initialization of the authentication
        # machinery (else some views may fail)
        self.app

    ## one each
    def test_one_each_config(self):
        self.auto_populate(1)
        for rset in self.iter_automatic_rsets(limit=1):
            for testargs in self._test_everything_for(rset):
                yield testargs

    ## ten each
    def test_ten_each_config(self):
        self.auto_populate(10)
        for rset in self.iter_automatic_rsets(limit=10):
            for testargs in self._test_everything_for(rset):
                yield testargs

    ## startup views
    def test_startup_views(self):
        for vid in self.list_startup_views():
            req = self.request()
            yield self.view, vid, None, req


# registry instrumentization ###################################################

def not_selected(vreg, appobject):
    try:
        vreg._selected[appobject.__class__] -= 1
    except (KeyError, AttributeError):
        pass


def vreg_instrumentize(testclass):
    # XXX broken
    from cubicweb.devtools.apptest import TestEnvironment
    env = testclass._env = TestEnvironment('data', configcls=testclass.configcls)
    for reg in env.vreg.values():
        reg._selected = {}
        try:
            orig_select_best = reg.__class__.__orig_select_best
        except:
            orig_select_best = reg.__class__._select_best
        def instr_select_best(self, *args, **kwargs):
            selected = orig_select_best(self, *args, **kwargs)
            try:
                self._selected[selected.__class__] += 1
            except KeyError:
                self._selected[selected.__class__] = 1
            except AttributeError:
                pass # occurs on reg used to restore database
            return selected
        reg.__class__._select_best = instr_select_best
        reg.__class__.__orig_select_best = orig_select_best


def print_untested_objects(testclass, skipregs=('hooks', 'etypes')):
    for regname, reg in testclass._env.vreg.iteritems():
        if regname in skipregs:
            continue
        for appobjects in reg.itervalues():
            for appobject in appobjects:
                if not reg._selected.get(appobject):
                    print 'not tested', regname, appobject
