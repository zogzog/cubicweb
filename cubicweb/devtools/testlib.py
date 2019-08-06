# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Base classes and utilities for cubicweb tests"""

import sys
import re
from os.path import dirname, join, abspath
from math import log
from contextlib import contextmanager
from inspect import isgeneratorfunction
from itertools import chain
from unittest import TestCase
from urllib.parse import urlparse, parse_qs, unquote as urlunquote

import yams.schema

from logilab.common.testlib import Tags, nocoverage
from logilab.common.debugger import Debugger
from logilab.common.umessage import message_from_string
from logilab.common.decorators import cached, classproperty, clear_cache, iclassmethod
from logilab.common.deprecation import class_deprecated
from logilab.common.shellutils import getlogin

from cubicweb import (ValidationError, NoSelectableObject, AuthenticationError,
                      BadConnectionId)
from cubicweb import cwconfig, devtools, repoapi, server, web
from cubicweb.utils import json
from cubicweb.sobjects import notification
from cubicweb.web import Redirect, application, eid_param
from cubicweb.server.hook import SendMailOp
from cubicweb.devtools import SYSTEM_ENTITIES, SYSTEM_RELATIONS, VIEW_VALIDATORS
from cubicweb.devtools import fake, htmlparser, DEFAULT_EMPTY_DB_ID
from cubicweb.devtools.fill import insert_entity_queries, make_relations_queries
from cubicweb.web.views.authentication import Session


# provide a data directory for the test class ##################################

class BaseTestCase(TestCase):

    @classproperty
    @cached
    def datadir(cls):  # pylint: disable=E0213
        """helper attribute holding the standard test's data directory
        """
        mod = sys.modules[cls.__module__]
        return join(dirname(abspath(mod.__file__)), 'data')
    # cache it (use a class method to cache on class since TestCase is
    # instantiated for each test run)

    @classmethod
    def datapath(cls, *fname):
        """joins the object's datadir and `fname`"""
        return join(cls.datadir, *fname)


if hasattr(BaseTestCase, 'assertItemsEqual'):
    BaseTestCase.assertCountEqual = BaseTestCase.assertItemsEqual


# low-level utilities ##########################################################

class CubicWebDebugger(Debugger):
    """special debugger class providing a 'view' function which saves some
    html into a temporary file and open a web browser to examinate it.
    """
    def do_view(self, arg):
        import webbrowser
        data = self._getval(arg)
        with open('/tmp/toto.html', 'w') as toto:
            toto.write(data)
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


class JsonValidator(object):
    def parse_string(self, data):
        return json.loads(data.decode('ascii'))


@contextmanager
def real_error_handling(app):
    """By default, CubicWebTC `app` attribute (ie the publisher) is monkey
    patched so that unexpected error are raised rather than going through the
    `error_handler` method.

    By using this context manager you disable this monkey-patching temporarily.
    Hence when publishihng a request no error will be raised, you'll get
    req.status_out set to an HTTP error status code and the generated page will
    usually hold a traceback as HTML.

    >>> with real_error_handling(app):
    >>>     page = app.handle_request(req)
    """
    # remove the monkey patched error handler
    fake_error_handler = app.error_handler
    del app.error_handler
    # return the app
    yield app
    # restore
    app.error_handler = fake_error_handler


# email handling, to test emails sent by an application ########################

MAILBOX = []


class Email(object):
    """you'll get instances of Email into MAILBOX during tests that trigger
    some notification.

    * `msg` is the original message object

    * `recipients` is a list of email address which are the recipients of this
      message
    """
    def __init__(self, fromaddr, recipients, msg):
        self.fromaddr = fromaddr
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

    def sendmail(self, fromaddr, recipients, msg):
        MAILBOX.append(Email(fromaddr, recipients, msg.decode('utf-8')))


cwconfig.SMTP = MockSMTP


# Repoaccess utility ###############################################3###########

class RepoAccess(object):
    """An helper to easily create object to access the repo as a specific user

    Each RepoAccess have it own session.

    A repo access can create three type of object:

    .. automethod:: cubicweb.testlib.RepoAccess.cnx
    .. automethod:: cubicweb.testlib.RepoAccess.web_request
    """

    def __init__(self, repo, login, requestcls):
        self._repo = repo
        self._login = login
        self.requestcls = requestcls
        with repo.internal_cnx() as cnx:
            self._user = cnx.find('CWUser', login=login).one()
            self._user.cw_attr_cache['login'] = login

    @contextmanager
    def cnx(self):
        """Context manager returning a server side connection for the user"""
        with repoapi.Connection(self._repo, self._user) as cnx:
            yield cnx

    # aliases for bw compat
    client_cnx = repo_cnx = cnx

    @contextmanager
    def web_request(self, url=None, headers={}, method='GET', **kwargs):
        """Context manager returning a web request pre-linked to a client cnx

        To commit and rollback use::

            req.cnx.commit()
            req.cnx.rolback()
        """
        session = kwargs.pop('session', Session(self._repo, self._user))
        req = self.requestcls(self._repo.vreg, url=url, headers=headers,
                              method=method, form=kwargs)
        with self.cnx() as cnx:
            # web request expect a session attribute on cnx referencing the web session
            cnx.session = session
            req.set_cnx(cnx)
            yield req

    @contextmanager
    def shell(self):
        from cubicweb.server.migractions import ServerMigrationHelper
        with self.cnx() as cnx:
            mih = ServerMigrationHelper(None, repo=self._repo, cnx=cnx,
                                        interactive=False,
                                        # hack so it don't try to load fs schema
                                        schema=1)
            yield mih
            cnx.commit()


# base class for cubicweb tests requiring a full cw environments ###############

class CubicWebTC(BaseTestCase):
    """abstract class for test using an apptest environment

    attributes:

    * `vreg`, the vregistry
    * `schema`, self.vreg.schema
    * `config`, cubicweb configuration
    * `cnx`, repoapi connection to the repository using an admin user
    * `session`, server side session associated to `cnx`
    * `app`, the cubicweb publisher (for web testing)
    * `repo`, the repository object
    * `admlogin`, login of the admin user
    * `admpassword`, password of the admin user
    * `shell`, create and use shell environment
    * `anonymous_allowed`: flag telling if anonymous browsing should be allowed
    """
    appid = 'data'
    configcls = devtools.ApptestConfiguration
    requestcls = fake.FakeRequest
    tags = Tags('cubicweb', 'cw_repo')
    test_db_id = DEFAULT_EMPTY_DB_ID

    # anonymous is logged by default in cubicweb test cases
    anonymous_allowed = True

    @classmethod
    def setUpClass(cls):
        test_module_file = sys.modules[cls.__module__].__file__
        assert 'config' not in cls.__dict__, (
            '%s has a config class attribute before entering setUpClass. '
            'Let CubicWebTC.setUpClass instantiate it and modify it afterwards.' % cls)
        cls.config = cls.configcls(cls.appid, test_module_file)
        cls.config.mode = 'test'

    def __init__(self, *args, **kwargs):
        self.repo = None
        self._open_access = set()
        super(CubicWebTC, self).__init__(*args, **kwargs)

    def run(self, *args, **kwds):
        testMethod = getattr(self, self._testMethodName)
        if isgeneratorfunction(testMethod):
            raise RuntimeError(
                '%s appears to be a generative test. This is not handled '
                'anymore, use subTest API instead.' % self)
        return super(CubicWebTC, self).run(*args, **kwds)

    # repository connection handling ###########################################

    def new_access(self, login):
        """provide a new RepoAccess object for a given user

        The access is automatically closed at the end of the test."""
        access = RepoAccess(self.repo, login, self.requestcls)
        self._open_access.add(access)
        return access

    def _close_access(self):
        while self._open_access:
            try:
                self._open_access.pop()
            except BadConnectionId:
                continue  # already closed

    def _init_repo(self):
        """init the repository and connection to it.
        """
        # get or restore and working db.
        db_handler = devtools.get_test_db_handler(self.config, self.init_config)
        db_handler.build_db_cache(self.test_db_id, self.pre_setup_database)
        db_handler.restore_database(self.test_db_id)
        self.repo = db_handler.get_repo(startup=True)
        # get an admin session (without actual login)
        login = db_handler.config.default_admin_config['login']
        self.admin_access = self.new_access(login)

    # config management ########################################################

    @classmethod  # XXX could be turned into a regular method
    def init_config(cls, config):
        """configuration initialization hooks.

        You may only want to override here the configuraton logic.

        Otherwise, consider to use a different :class:`ApptestConfiguration`
        defined in the `configcls` class attribute.

        This method will be called by the database handler once the config has
        been properly bootstrapped.
        """
        admincfg = config.default_admin_config
        cls.admlogin = admincfg['login']
        cls.admpassword = admincfg['password']
        # uncomment the line below if you want rql queries to be logged
        # config.global_set_option('query-log-file',
        #                          '/tmp/test_rql_log.' + `os.getpid()`)
        config.global_set_option('log-file', None)
        # set default-dest-addrs to a dumb email address to avoid mailbox or
        # mail queue pollution
        config.global_set_option('default-dest-addrs', ['whatever'])
        send_to = '%s@logilab.fr' % getlogin()
        config.global_set_option('sender-addr', send_to)
        config.global_set_option('default-dest-addrs', send_to)
        config.global_set_option('sender-name', 'cubicweb-test')
        config.global_set_option('sender-addr', 'cubicweb-test@logilab.fr')
        # default_base_url on config class isn't enough for TestServerConfiguration
        config.global_set_option('base-url', config.default_base_url())

    @property
    def vreg(self):
        return self.repo.vreg

    # global resources accessors ###############################################

    @property
    def schema(self):
        """return the application schema"""
        return self.vreg.schema

    def set_option(self, optname, value):
        self.config.global_set_option(optname, value)

    def set_debug(self, debugmode):
        server.set_debug(debugmode)

    def debugged(self, debugmode):
        return server.debugged(debugmode)

    # default test setup and teardown #########################################

    def setUp(self):
        assert hasattr(self, 'config'), (
            'It seems that CubicWebTC.setUpClass has not been called. '
            'Missing super() call in %s?' % self.setUpClass)
        # monkey patch send mail operation so emails are sent synchronously
        self._patch_SendMailOp()
        previous_failure = self.__class__.__dict__.get('_repo_init_failed')
        if previous_failure is not None:
            self.skipTest('repository is not initialised: %r' % previous_failure)
        try:
            self._init_repo()
        except Exception as ex:
            self.__class__._repo_init_failed = ex
            raise
        self.addCleanup(self._close_access)
        self.config.set_anonymous_allowed(self.anonymous_allowed)
        self.setup_database()
        MAILBOX[:] = []  # reset mailbox

    def tearDown(self):
        while self._cleanups:
            cleanup, args, kwargs = self._cleanups.pop(-1)
            cleanup(*args, **kwargs)
        self.repo.turn_repo_off()

    def _patch_SendMailOp(self):
        # monkey patch send mail operation so emails are sent synchronously
        _old_mail_postcommit_event = SendMailOp.postcommit_event
        SendMailOp.postcommit_event = SendMailOp.sendmails

        def reverse_SendMailOp_monkey_patch():
            SendMailOp.postcommit_event = _old_mail_postcommit_event

        self.addCleanup(reverse_SendMailOp_monkey_patch)

    def setup_database(self):
        """add your database setup code by overriding this method"""

    @classmethod
    def pre_setup_database(cls, cnx, config):
        """add your pre database setup code by overriding this method

        Do not forget to set the cls.test_db_id value to enable caching of the
        result.
        """

    # user / session management ###############################################

    @iclassmethod  # XXX turn into a class method
    def create_user(self, req, login=None, groups=('users',), password=None,
                    email=None, commit=True, **kwargs):
        """create and return a new user entity"""
        if password is None:
            password = login
        user = req.create_entity('CWUser', login=login,
                                 upassword=password, **kwargs)
        req.execute('SET X in_group G WHERE X eid %%(x)s, G name IN(%s)'
                    % ','.join(repr(str(g)) for g in groups),
                    {'x': user.eid})
        if email is not None:
            req.create_entity('EmailAddress', address=email,
                              reverse_primary_email=user)
        user.cw_clear_relation_cache('in_group', 'subject')
        if commit:
            getattr(req, 'cnx', req).commit()
        return user

    # other utilities #########################################################

    @contextmanager
    def temporary_appobjects(self, *appobjects):
        self.vreg._loadedmods.setdefault(self.__module__, {})
        for obj in appobjects:
            self.vreg.register(obj)
            registered = getattr(obj, '__registered__', None)
            if registered:
                for registry in obj.__registries__:
                    registered(self.vreg[registry])
        try:
            yield
        finally:
            for obj in appobjects:
                self.vreg.unregister(obj)

    @contextmanager
    def temporary_permissions(self, *perm_overrides, **perm_kwoverrides):
        """Set custom schema permissions within context.

        There are two ways to call this method, which may be used together :

        * using positional argument(s):

          .. sourcecode:: python

                rdef = self.schema['CWUser'].rdef('login')
                with self.temporary_permissions((rdef, {'read': ()})):
                    ...


        * using named argument(s):

          .. sourcecode:: python

                with self.temporary_permissions(CWUser={'read': ()}):
                    ...

        Usually the former will be preferred to override permissions on a
        relation definition, while the latter is well suited for entity types.

        The allowed keys in the permission dictionary depend on the schema type
        (entity type / relation definition). Resulting permissions will be
        similar to `orig_permissions.update(partial_perms)`.
        """
        torestore = []
        for erschema, etypeperms in chain(perm_overrides, perm_kwoverrides.items()):
            if isinstance(erschema, str):
                erschema = self.schema[erschema]
            for action, actionperms in etypeperms.items():
                origperms = erschema.permissions[action]
                erschema.set_action_permissions(action, actionperms)
                torestore.append([erschema, action, origperms])
        try:
            yield
        finally:
            for erschema, action, permissions in torestore:
                if action is None:
                    erschema.permissions = permissions
                else:
                    erschema.set_action_permissions(action, permissions)

    def assertModificationDateGreater(self, entity, olddate):
        entity.cw_attr_cache.pop('modification_date', None)
        self.assertGreater(entity.modification_date, olddate)

    def assertMessageEqual(self, req, params, expected_msg):
        msg = req.session.data[params['_cwmsgid']]
        self.assertEqual(expected_msg, msg)

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
                    if view is None:
                        raise NoSelectableObject((req,), {'rset': rset}, views)
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
        for box in self.vreg['ctxcomponents'].possible_objects(req, rset=rset,
                                                               view=None):
            yield box

    def list_startup_views(self):
        """returns the list of startup views"""
        with self.admin_access.web_request() as req:
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
        publisher = application.CubicWebPublisher(self.repo, self.config)

        def raise_error_handler(*args, **kwargs):
            raise

        publisher.error_handler = raise_error_handler
        return publisher

    @contextmanager
    def remote_calling(self, fname, *args, **kwargs):
        """remote json call simulation"""
        args = [json.dumps(arg) for arg in args]
        with self.admin_access.web_request(fname=fname, pageid='123', arg=args, **kwargs) as req:
            ctrl = self.vreg['controllers'].select('ajax', req)
            yield ctrl.publish(), req

    def app_handle_request(self, req):
        return self.app.core_handle(req)

    def ctrl_publish(self, req, ctrl='edit', rset=None):
        """call the publish method of the edit controller"""
        ctrl = self.vreg['controllers'].select(ctrl, req, appli=self.app)
        try:
            result = ctrl.publish(rset)
            req.cnx.commit()
        except web.Redirect:
            req.cnx.commit()
            raise
        return result

    @staticmethod
    def fake_form(formid, field_dict=None, entity_field_dicts=()):
        """Build _cw.form dictionnary to fake posting of some standard cubicweb form

        * `formid`, the form id, usually form's __regid__

        * `field_dict`, dictionary of name:value for fields that are not tied to an entity

        * `entity_field_dicts`, list of (entity, dictionary) where dictionary contains name:value
          for fields that are not tied to the given entity
        """
        assert field_dict or entity_field_dicts, \
            'field_dict and entity_field_dicts arguments must not be both unspecified'
        if field_dict is None:
            field_dict = {}
        form = {'__form_id': formid}
        fields = []
        for field, value in field_dict.items():
            fields.append(field)
            form[field] = value

        def _add_entity_field(entity, field, value):
            entity_fields.append(field)
            form[eid_param(field, entity.eid)] = value

        for entity, field_dict in entity_field_dicts:
            if '__maineid' not in form:
                form['__maineid'] = entity.eid
            entity_fields = []
            form.setdefault('eid', []).append(entity.eid)
            _add_entity_field(entity, '__type', entity.cw_etype)
            for field, value in field_dict.items():
                _add_entity_field(entity, field, value)
            if entity_fields:
                form[eid_param('_cw_entity_fields', entity.eid)] = ','.join(entity_fields)
        if fields:
            form['_cw_fields'] = ','.join(sorted(fields))
        return form

    @contextmanager
    def admin_request_from_url(self, url):
        """parses `url` and builds the corresponding CW-web request

        req.form will be setup using the url's query string
        """
        with self.admin_access.web_request(url=url) as req:
            if isinstance(url, str):
                url = url.encode(req.encoding)  # req.setup_params() expects encoded strings
            querystring = urlparse(url)[-2]
            params = parse_qs(querystring)
            req.setup_params(params)
            yield req

    def url_publish(self, url, data=None):
        """takes `url`, uses application's app_resolver to find the appropriate
        controller and result set, then publishes the result.

        To simulate post of www-form-encoded data, give a `data` dictionary
        containing desired key/value associations.

        This should pretty much correspond to what occurs in a real CW server
        except the apache-rewriter component is not called.
        """
        with self.admin_request_from_url(url) as req:
            if data is not None:
                req.form.update(data)
            ctrlid, rset = self.app.url_resolver.process(req, req.relative_path(False))
            return self.ctrl_publish(req, ctrlid, rset)

    def http_publish(self, url, data=None):
        """like `url_publish`, except this returns a http response, even in case
        of errors. You may give form parameters using the `data` argument.
        """
        with self.admin_request_from_url(url) as req:
            if data is not None:
                req.form.update(data)
            with real_error_handling(self.app):
                result = self.app_handle_request(req)
            return result, req

    @staticmethod
    def _parse_location(req, location):
        try:
            path, params = location.split('?', 1)
        except ValueError:
            path = location
            params = {}
        else:
            def cleanup(p):
                return (p[0], urlunquote(p[1]))

            params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
        if path.startswith(req.base_url()):  # may be relative
            path = path[len(req.base_url()):]
        return path, params

    def expect_redirect(self, callback, req):
        """call the given callback with req as argument, expecting to get a
        Redirect exception
        """
        try:
            callback(req)
        except Redirect as ex:
            return self._parse_location(req, ex.location)
        else:
            self.fail('expected a Redirect exception')

    def expect_redirect_handle_request(self, req, path='edit'):
        """call the publish method of the application publisher, expecting to
        get a Redirect exception
        """
        if req.relative_path(False) != path:
            req._url = path
        self.app_handle_request(req)
        self.assertTrue(300 <= req.status_out < 400, req.status_out)
        location = req.get_response_header('location')
        return self._parse_location(req, location)

    def set_auth_mode(self, authmode, anonuser=None):
        self.set_option('auth-mode', authmode)
        self.set_option('anonymous-user', anonuser)
        if anonuser is None:
            self.config.anonymous_credential = None
        else:
            self.config.anonymous_credential = (anonuser, anonuser)

    def init_authentication(self, authmode, anonuser=None):
        self.set_auth_mode(authmode, anonuser)
        req = self.requestcls(self.vreg, url='login')
        sh = self.app.session_handler
        authm = sh.session_manager.authmanager
        authm.anoninfo = self.vreg.config.anonymous_user()
        authm.anoninfo = authm.anoninfo[0], {'password': authm.anoninfo[1]}
        # not properly cleaned between tests
        self.open_sessions = sh.session_manager._sessions = {}
        return req

    def assertAuthSuccess(self, req, nbsessions=1):
        session = self.app.get_session(req)
        cnx = session.new_cnx()
        with cnx:
            req.set_cnx(cnx)
        self.assertEqual(len(self.open_sessions), nbsessions, self.open_sessions)
        self.assertEqual(req.user.login, self.admlogin)
        self.assertEqual(session.anonymous_session, False)

    def assertAuthFailure(self, req, nbsessions=0):
        with self.assertRaises(AuthenticationError):
            self.app.get_session(req)
        # +0 since we do not track the opened session
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
        # 'text/html': DTDValidator,
        # 'application/xhtml+xml': DTDValidator,
        'application/xml': htmlparser.XMLValidator,
        'text/xml': htmlparser.XMLValidator,
        'application/json': JsonValidator,
        'text/plain': None,
        'text/comma-separated-values': None,
        'text/x-vcard': None,
        'text/calendar': None,
        'image/png': None,
    }
    # maps vid : validator name (override content_type_validators)
    vid_validators = dict((vid, htmlparser.VALMAP[valkey])
                          for vid, valkey in VIEW_VALIDATORS.items())

    def view(self, vid, rset=None, req=None, template='main-template',
             **kwargs):
        """This method tests the view `vid` on `rset` using `template`

        If no error occurred while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        if req is None:
            assert rset is not None, 'you must supply at least one of rset or req'
            req = rset.req
        req.form['vid'] = vid
        viewsreg = self.vreg['views']
        view = viewsreg.select(vid, req, rset=rset, **kwargs)
        if template is None:  # raw view testing, no template
            viewfunc = view.render
        else:
            kwargs['view'] = view

            def viewfunc(**k):
                return viewsreg.main_template(req, template,
                                              rset=rset, **kwargs)

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
        except Exception:
            # hijack exception: generative tests stop when the exception
            # is not an AssertionError
            klass, exc, tcbk = sys.exc_info()
            try:
                msg = '[%s in %s] %s' % (klass, view.__regid__, exc)
            except Exception:
                msg = '[%s in %s] undisplayable exception' % (klass, view.__regid__)
            raise AssertionError(msg).with_traceback(sys.exc_info()[-1])
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
        if content_type in ('text/html', 'application/xhtml+xml') and output:
            if output.startswith(b'<!DOCTYPE html>'):
                # only check XML well-formness since HTMLValidator isn't html5
                # compatible and won't like various other extensions
                default_validator = htmlparser.XMLSyntaxValidator
            elif output.startswith(b'<?xml'):
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
        if isinstance(output, str):
            # XXX
            output = output.encode('utf-8')
        validator = self.get_validator(view, output=output)
        if validator is None:
            return output  # return raw output if no validator is defined
        if isinstance(validator, htmlparser.DTDValidator):
            # XXX remove <canvas> used in progress widget, unknown in html dtd
            output = re.sub('<canvas.*?></canvas>', '', output)
        return self.assertWellFormed(validator, output.strip(), context=view.__regid__)

    def assertWellFormed(self, validator, content, context=None):
        try:
            return validator.parse_string(content)
        except Exception:
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
            except Exception:
                str_exc = 'undisplayable exception'
            msg += str_exc.encode(sys.getdefaultencoding(), 'replace')
            if content is not None:
                position = getattr(exc, "position", (0,))[0]
                if position:
                    # define filter
                    if isinstance(content, bytes):
                        content = str(content, sys.getdefaultencoding(), 'replace')
                    content = validator.preprocess_data(content)
                    content = content.splitlines()
                    width = int(log(len(content), 10)) + 1
                    line_template = " %" + ("%i" % width) + "i: %s"
                    # XXX no need to iterate the whole file except to get
                    # the line number
                    content = u'\n'.join(line_template % (idx + 1, line)
                                         for idx, line in enumerate(content)
                                         if line_context_filter(idx + 1, position))
                    msg += u'\nfor content:\n%s' % content
            exc = AssertionError(msg)
            exc.__traceback__ = tcbk
            raise exc

    def assertDocTestFile(self, testfile):
        # doctest returns tuple (failure_count, test_count)
        with self.admin_access.shell() as mih:
            result = mih.process_script(testfile)
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


# auto-populating test classes and utilities ###################################

# XXX cleanup unprotected_entities & all mess

def how_many_dict(schema, cnx, how_many, skip):
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
    for etype in skip:  # XXX (syt) duh? explain or kill
        unprotected.add(etype)
    howmanydict = {}
    # step 1, compute a base number of each entity types: number of already
    # existing entities of this type + `how_many`
    for etype in unprotected_entities(schema, strict=True):
        howmanydict[str(etype)] = cnx.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
        if etype in unprotected:
            howmanydict[str(etype)] += how_many
    # step 2, augment nb entity per types to satisfy cardinality constraints,
    # by recomputing for each relation that constrained an entity type:
    #
    # new num for etype = max(current num, sum(num for possible target etypes))
    #
    # XXX we should first check there is no cycle then propagate changes
    for (rschema, etype), targets in relmap.items():
        relfactor = sum(howmanydict[e] for e in targets)
        howmanydict[str(etype)] = max(relfactor, howmanydict[etype])
    return howmanydict


class AutoPopulateTest(CubicWebTC):
    """base class for test with auto-populating of the database"""
    __abstract__ = True

    test_db_id = 'autopopulate'

    tags = CubicWebTC.tags | Tags('autopopulated')

    pdbclass = CubicWebDebugger
    # this is a hook to be able to define a list of rql queries
    # that are application dependent and cannot be guessed automatically
    application_rql = []

    no_auto_populate = ()
    ignored_relations = set()

    def to_test_etypes(self):
        return unprotected_entities(self.schema, strict=True)

    def custom_populate(self, how_many, cnx):
        pass

    def post_populate(self, cnx):
        pass

    @nocoverage
    def auto_populate(self, how_many):
        """this method populates the database with `how_many` entities
        of each possible type. It also inserts random relations between them
        """
        with self.admin_access.cnx() as cnx:
            with cnx.security_enabled(read=False, write=False):
                self._auto_populate(cnx, how_many)
                cnx.commit()

    def _auto_populate(self, cnx, how_many):
        self.custom_populate(how_many, cnx)
        vreg = self.vreg
        howmanydict = how_many_dict(self.schema, cnx, how_many, self.no_auto_populate)
        for etype in unprotected_entities(self.schema):
            if etype in self.no_auto_populate:
                continue
            nb = howmanydict.get(etype, how_many)
            for rql, args in insert_entity_queries(etype, self.schema, vreg, nb):
                cnx.execute(rql, args)
        edict = {}
        for etype in unprotected_entities(self.schema, strict=True):
            rset = cnx.execute('%s X' % etype)
            edict[str(etype)] = set(row[0] for row in rset.rows)
        existingrels = {}
        ignored_relations = SYSTEM_RELATIONS | self.ignored_relations
        for rschema in self.schema.relations():
            if rschema.final or rschema in ignored_relations or rschema.rule:
                continue
            rset = cnx.execute('DISTINCT Any X,Y WHERE X %s Y' % rschema)
            existingrels.setdefault(rschema.type, set()).update((x, y) for x, y in rset)
        q = make_relations_queries(self.schema, edict, cnx, ignored_relations,
                                   existingrels=existingrels)
        for rql, args in q:
            try:
                cnx.execute(rql, args)
            except ValidationError as ex:
                # failed to satisfy some constraint
                print('error in automatic db population', ex)
                cnx.commit_state = None  # reset uncommitable flag
        self.post_populate(cnx)

    def iter_individual_rsets(self, etypes=None, limit=None):
        etypes = etypes or self.to_test_etypes()
        with self.admin_access.web_request() as req:
            for etype in etypes:
                if limit:
                    rql = 'Any X LIMIT %s WHERE X is %s' % (limit, etype)
                else:
                    rql = 'Any X WHERE X is %s' % etype
                rset = req.execute(rql)
                for row in range(len(rset)):
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
        with self.admin_access.web_request() as req:
            for etype in etypes:
                yield req.execute('Any X LIMIT %s WHERE X is %s' % (limit, etype))
            etype1 = etypes.pop()
            try:
                etype2 = etypes.pop()
            except KeyError:
                etype2 = etype1
            # test a mixed query (DISTINCT/GROUP to avoid getting duplicate
            # X which make muledit view failing for instance (html validation fails
            # because of some duplicate "id" attributes)
            yield req.execute('DISTINCT Any X, MAX(Y) GROUPBY X WHERE X is %s, Y is %s' %
                              (etype1, etype2))
            # test some application-specific queries if defined
            for rql in self.application_rql:
                yield req.execute(rql)

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
            with self.subTest(name=self._testname(rset, view.__regid__, 'view')):
                self.view(view.__regid__, rset,
                          rset.req.reset_headers(), 'main-template')
            # We have to do this because some views modify the
            # resultset's syntax tree
            rset = backup_rset
        for action in self.list_actions_for(rset):
            with self.subTest(name=self._testname(rset, action.__regid__, 'action')):
                self._test_action(action)
        for box in self.list_boxes_for(rset):
            w = [].append
            with self.subTest(name=self._testname(rset, box.__regid__, 'box')):
                box.render(w)

    @staticmethod
    def _testname(rset, objid, objtype):
        return '%s_%s_%s' % ('_'.join(rset.column_types(0)), objid, objtype)


# concrete class for automated application testing  ############################

class AutomaticWebTest(AutoPopulateTest):
    """import this if you wan automatic tests to be ran"""

    tags = AutoPopulateTest.tags | Tags('web', 'generated')

    def setUp(self):
        if self.__class__ is AutomaticWebTest:
            # Prevent direct use of AutomaticWebTest to avoid database caching
            # issues.
            return
        super(AutomaticWebTest, self).setUp()

        # access to self.app for proper initialization of the authentication
        # machinery (else some views may fail)
        self.app

    def test_one_each_config(self):
        self.auto_populate(1)
        for rset in self.iter_automatic_rsets(limit=1):
            self._test_everything_for(rset)

    def test_ten_each_config(self):
        self.auto_populate(10)
        for rset in self.iter_automatic_rsets(limit=10):
            self._test_everything_for(rset)

    def test_startup_views(self):
        for vid in self.list_startup_views():
            with self.admin_access.web_request() as req:
                with self.subTest(vid=vid):
                    self.view(vid, None, req)


# registry instrumentization ###################################################

def not_selected(vreg, appobject):
    try:
        vreg._selected[appobject.__class__] -= 1
    except (KeyError, AttributeError):
        pass


# def vreg_instrumentize(testclass):
#     # XXX broken
#     from cubicweb.devtools.apptest import TestEnvironment
#     env = testclass._env = TestEnvironment('data', configcls=testclass.configcls)
#     for reg in env.vreg.values():
#         reg._selected = {}
#         try:
#             orig_select_best = reg.__class__.__orig_select_best
#         except Exception:
#             orig_select_best = reg.__class__._select_best
#         def instr_select_best(self, *args, **kwargs):
#             selected = orig_select_best(self, *args, **kwargs)
#             try:
#                 self._selected[selected.__class__] += 1
#             except KeyError:
#                 self._selected[selected.__class__] = 1
#             except AttributeError:
#                 pass # occurs on reg used to restore database
#             return selected
#         reg.__class__._select_best = instr_select_best
#         reg.__class__.__orig_select_best = orig_select_best


# def print_untested_objects(testclass, skipregs=('hooks', 'etypes')):
#     for regname, reg in testclass._env.vreg.items():
#         if regname in skipregs:
#             continue
#         for appobjects in reg.values():
#             for appobject in appobjects:
#                 if not reg._selected.get(appobject):
#                     print 'not tested', regname, appobject
