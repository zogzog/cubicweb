"""this module contains base classes and utilities for cubicweb tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
import sys
import re
from urllib import unquote
from math import log

import simplejson

import yams.schema

from logilab.common.testlib import TestCase, InnerTest
from logilab.common.pytest import nocoverage, pause_tracing, resume_tracing
from logilab.common.debugger import Debugger
from logilab.common.umessage import message_from_string
from logilab.common.decorators import cached, classproperty, clear_cache
from logilab.common.deprecation import deprecated

from cubicweb import NoSelectableObject, AuthenticationError
from cubicweb import cwconfig, devtools, web, server
from cubicweb.dbapi import repo_connect, ConnectionProperties, ProgrammingError
from cubicweb.sobjects import notification
from cubicweb.web import Redirect, application
from cubicweb.devtools import SYSTEM_ENTITIES, SYSTEM_RELATIONS, VIEW_VALIDATORS
from cubicweb.devtools import fake, htmlparser


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


def get_versions(self, checkversions=False):
    """return the a dictionary containing cubes used by this instance
    as key with their version as value, including cubicweb version. This is a
    public method, not requiring a session id.

    replace Repository.get_versions by this method if you don't want versions
    checking
    """
    vcconf = {'cubicweb': self.config.cubicweb_version()}
    self.config.bootstrap_cubes()
    for pk in self.config.cubes():
        version = self.config.cube_version(pk)
        vcconf[pk] = version
    self.config._cubes = None
    return vcconf


def refresh_repo(repo):
    devtools.reset_test_database(repo.config)
    for pool in repo.pools:
        pool.reconnect()
    repo._type_source_cache = {}
    repo._extid_cache = {}
    repo.querier._rql_cache = {}
    for source in repo.sources:
        source.reset_caches()


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


# base class for cubicweb tests requiring a full cw environments ###############

class CubicWebTC(TestCase):
    """abstract class for test using an apptest environment

    attributes:
    `vreg`, the vregistry
    `schema`, self.vreg.schema
    `config`, cubicweb configuration
    `cnx`, dbapi connection to the repository using an admin user
    `session`, server side session associated to `cnx`
    `app`, the cubicweb publisher (for web testing)
    `repo`, the repository object

    `admlogin`, login of the admin user
    `admpassword`, password of the admin user

    """
    appid = 'data'
    configcls = devtools.ApptestConfiguration

    @classproperty
    def config(cls):
        """return the configuration object. Configuration is cached on the test
        class.
        """
        try:
            return cls.__dict__['_config']
        except KeyError:
            config = cls._config = cls.configcls(cls.appid)
            config.mode = 'test'
            return config

    @classmethod
    def init_config(cls, config):
        """configuration initialization hooks. You may want to override this."""
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
        try:
            send_to =  '%s@logilab.fr' % os.getlogin()
            # AttributeError since getlogin not available under all platforms
        except (OSError, AttributeError):
            send_to =  '%s@logilab.fr' % (os.environ.get('USER')
                                          or os.environ.get('USERNAME')
                                          or os.environ.get('LOGNAME'))
        config.global_set_option('sender-addr', send_to)
        config.global_set_option('default-dest-addrs', send_to)
        config.global_set_option('sender-name', 'cubicweb-test')
        config.global_set_option('sender-addr', 'cubicweb-test@logilab.fr')
        # web resources
        config.global_set_option('base-url', devtools.BASE_URL)
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
            cls.cnx.rollback()
            cls._refresh_repo()

    @classmethod
    def _build_repo(cls):
        cls.repo, cls.cnx = devtools.init_test_database(config=cls.config)
        cls.init_config(cls.config)
        cls.vreg = cls.repo.vreg
        cls._orig_cnx = cls.cnx
        cls.config.repository = lambda x=None: cls.repo
        # necessary for authentication tests
        cls.cnx.login = cls.admlogin
        cls.cnx.authinfo = {'password': cls.admpassword}

    @classmethod
    def _refresh_repo(cls):
        refresh_repo(cls.repo)

    # global resources accessors ###############################################

    @property
    def schema(self):
        """return the application schema"""
        return self.vreg.schema

    @property
    def session(self):
        """return current server side session (using default manager account)"""
        return self.repo._sessions[self.cnx.sessionid]

    @property
    def adminsession(self):
        """return current server side session (using default manager account)"""
        return self.repo._sessions[self._orig_cnx.sessionid]

    def set_option(self, optname, value):
        self.config.global_set_option(optname, value)

    def set_debug(self, debugmode):
        server.set_debug(debugmode)

    # default test setup and teardown #########################################

    def setUp(self):
        pause_tracing()
        self._init_repo()
        resume_tracing()
        self.setup_database()
        self.commit()
        MAILBOX[:] = [] # reset mailbox

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
                    commit=True):
        """create and return a new user entity"""
        if password is None:
            password = login.encode('utf8')
        cursor = self._orig_cnx.cursor(req or self.request())
        rset = cursor.execute('INSERT CWUser X: X login %(login)s, X upassword %(passwd)s',
                              {'login': unicode(login), 'passwd': password})
        user = rset.get_entity(0, 0)
        cursor.execute('SET X in_group G WHERE X eid %%(x)s, G name IN(%s)'
                       % ','.join(repr(g) for g in groups),
                       {'x': user.eid}, 'x')
        user.clear_related_cache('in_group', 'subject')
        if commit:
            self._orig_cnx.commit()
        return user

    def login(self, login, **kwargs):
        """return a connection for the given login/password"""
        if login == self.admlogin:
            self.restore_connection()
        else:
            if not kwargs:
                kwargs['password'] = str(login)
            self.cnx = repo_connect(self.repo, unicode(login),
                                    cnxprops=ConnectionProperties('inmemory'),
                                    **kwargs)
        if login == self.vreg.config.anonymous_user()[0]:
            self.cnx.anonymous_connection = True
        return self.cnx

    def restore_connection(self):
        if not self.cnx is self._orig_cnx:
            try:
                self.cnx.close()
            except ProgrammingError:
                pass # already closed
        self.cnx = self._orig_cnx

    # db api ##################################################################

    @nocoverage
    def cursor(self, req=None):
        return self.cnx.cursor(req or self.request())

    @nocoverage
    def execute(self, rql, args=None, eidkey=None, req=None):
        """executes <rql>, builds a resultset, and returns a couple (rset, req)
        where req is a FakeRequest
        """
        req = req or self.request(rql=rql)
        return self.cnx.cursor(req).execute(unicode(rql), args, eidkey)

    @nocoverage
    def commit(self):
        self.cnx.commit()

    @nocoverage
    def rollback(self):
        try:
            self.cnx.rollback()
        except ProgrammingError:
            pass

    # # server side db api #######################################################

    def sexecute(self, rql, args=None, eid_key=None):
        self.session.set_pool()
        return self.session.execute(rql, args, eid_key)

    # other utilities #########################################################

    def entity(self, rql, args=None, eidkey=None, req=None):
        return self.execute(rql, args, eidkey, req=req).get_entity(0, 0)

    def add_entity(self, etype, req=None, **kwargs):
        rql = ['INSERT %s X' % etype]
        # dict for replacement in RQL Request
        args = {}
        if kwargs:
            rql.append(':')
            # dict to define new entities variables
            entities = {}
            # assignement part of the request
            sub_rql = []
            for key, value in kwargs.iteritems():
                # entities
                if hasattr(value, 'eid'):
                    new_value = "%s__" % key.upper()
                    entities[new_value] = value.eid
                    args[new_value] = value.eid

                    sub_rql.append("X %s %s" % (key, new_value))
                # final attributes
                else:
                    sub_rql.append('X %s %%(%s)s' % (key, key))
                    args[key] = value
            rql.append(', '.join(sub_rql))
            if entities:
                rql.append('WHERE')
                # WHERE part of the request (to link entity to they eid)
                sub_rql = []
                for key, value in entities.iteritems():
                    sub_rql.append("%s eid %%(%s)s" % (key, key))
                rql.append(', '.join(sub_rql))
        return self.execute(' '.join(rql), args, req=req).get_entity(0, 0)

    # vregistry inspection utilities ###########################################

    def pviews(self, req, rset):
        return sorted((a.__regid__, a.__class__)
                      for a in self.vreg['views'].possible_views(req, rset=rset))

    def pactions(self, req, rset,
                 skipcategories=('addrelated', 'siteactions', 'useractions', 'footer')):
        return [(a.__regid__, a.__class__)
                for a in self.vreg['actions'].poss_visible_objects(req, rset=rset)
                if a.category not in skipcategories]

    def pactions_by_cats(self, req, rset, categories=('addrelated',)):
        return [(a.__regid__, a.__class__)
                for a in self.vreg['actions'].poss_visible_objects(req, rset=rset)
                if a.category in categories]

    def pactionsdict(self, req, rset,
                     skipcategories=('addrelated', 'siteactions', 'useractions', 'footer')):
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
            def mk_action(self, label, url, **kwargs):
                return (label, url)
            def box_action(self, action, **kwargs):
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
                     and not issubclass(view, notification.NotificationView)]
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
        for box in self.vreg['boxes'].possible_objects(req, rset=rset):
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
        return application.CubicWebPublisher(self.config, vreg=self.vreg)

    requestcls = fake.FakeRequest
    def request(self, *args, **kwargs):
        """return a web ui request"""
        req = self.requestcls(self.vreg, form=kwargs)
        req.set_connection(self.cnx)
        return req

    def remote_call(self, fname, *args):
        """remote json call simulation"""
        dump = simplejson.dumps
        args = [dump(arg) for arg in args]
        req = self.request(fname=fname, pageid='123', arg=args)
        ctrl = self.vreg['controllers'].select('json', req)
        return ctrl.publish(), req

    def app_publish(self, req, path='view'):
        return self.app.publish(path, req)

    def publish(self, req):
        """call the publish method of the edit controller"""
        ctrl = self.vreg['controllers'].select('edit', req)
        try:
            result = ctrl.publish()
            req.cnx.commit()
        except web.Redirect:
            req.cnx.commit()
            raise
        return result

    def expect_redirect(self, callback, req):
        """call the given callback with req as argument, expecting to get a
        Redirect exception
        """
        try:
            res = callback(req)
        except Redirect, ex:
            try:
                path, params = ex.location.split('?', 1)
            except ValueError:
                path = ex.location
                params = {}
            else:
                cleanup = lambda p: (p[0], unquote(p[1]))
                params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
            path = path[len(req.base_url()):]
            return path, params
        else:
            self.fail('expected a Redirect exception')

    def expect_redirect_publish(self, req, path='view'):
        """call the publish method of the application publisher, expecting to
        get a Redirect exception
        """
        return self.expect_redirect(lambda x: self.publish(x, path), req)

    def init_authentication(self, authmode, anonuser=None):
        self.set_option('auth-mode', authmode)
        self.set_option('anonymous-user', anonuser)
        req = self.request()
        origcnx = req.cnx
        req.cnx = None
        sh = self.app.session_handler
        authm = sh.session_manager.authmanager
        authm.authinforetreivers[-1].anoninfo = self.vreg.config.anonymous_user()
        # not properly cleaned between tests
        self.open_sessions = sh.session_manager._sessions = {}
        return req, origcnx

    def assertAuthSuccess(self, req, origcnx, nbsessions=1):
        sh = self.app.session_handler
        path, params = self.expect_redirect(lambda x: self.app.connect(x), req)
        cnx = req.cnx
        self.assertEquals(len(self.open_sessions), nbsessions, self.open_sessions)
        self.assertEquals(cnx.login, origcnx.login)
        self.assertEquals(cnx.anonymous_connection, False)
        self.assertEquals(path, 'view')
        self.assertEquals(params, {'__message': 'welcome %s !' % cnx.user().login})

    def assertAuthFailure(self, req, nbsessions=0):
        self.assertRaises(AuthenticationError, self.app.connect, req)
        self.assertEquals(req.cnx, None)
        self.assertEquals(len(self.open_sessions), nbsessions)
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

        If no error occured while rendering the view, the HTML is analyzed
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
            self.set_description("testing %s, mod=%s (%s)" % (
                vid, view.__module__, rset.printable_rql()))
        else:
            self.set_description("testing %s, mod=%s (no rset)" % (
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

        If no error occured while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        output = None
        try:
            output = viewfunc(**kwargs)
            return self._check_html(output, view, template)
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
            if output is not None:
                position = getattr(exc, "position", (0,))[0]
                if position:
                    # define filter
                    output = output.splitlines()
                    width = int(log(len(output), 10)) + 1
                    line_template = " %" + ("%i" % width) + "i: %s"
                    # XXX no need to iterate the whole file except to get
                    # the line number
                    output = '\n'.join(line_template % (idx + 1, line)
                                for idx, line in enumerate(output)
                                if line_context_filter(idx+1, position))
                    msg += '\nfor output:\n%s' % output
            raise AssertionError, msg, tcbk


    @nocoverage
    def _check_html(self, output, view, template='main-template'):
        """raises an exception if the HTML is invalid"""
        try:
            validatorclass = self.vid_validators[view.__regid__]
        except KeyError:
            if template is None:
                default_validator = htmlparser.HTMLValidator
            else:
                default_validator = htmlparser.DTDValidator
            validatorclass = self.content_type_validators.get(view.content_type,
                                                              default_validator)
        if validatorclass is None:
            return None
        validator = validatorclass()
        return validator.parse_string(output.strip())

    # deprecated ###############################################################

    @deprecated('[3.4] use self.vreg["etypes"].etype_class(etype)(self.request())')
    def etype_instance(self, etype, req=None):
        req = req or self.request()
        e = self.vreg['etypes'].etype_class(etype)(req)
        e.eid = None
        return e

    @nocoverage
    @deprecated('[3.4] use req = self.request(); rset = req.execute()')
    def rset_and_req(self, rql, optional_args=None, args=None, eidkey=None):
        """executes <rql>, builds a resultset, and returns a
        couple (rset, req) where req is a FakeRequest
        """
        return (self.execute(rql, args, eidkey),
                self.request(rql=rql, **optional_args or {}))


# auto-populating test classes and utilities ###################################

from cubicweb.devtools.fill import insert_entity_queries, make_relations_queries

def how_many_dict(schema, cursor, how_many, skip):
    """compute how many entities by type we need to be able to satisfy relations
    cardinality
    """
    # compute how many entities by type we need to be able to satisfy relation constraint
    relmap = {}
    for rschema in schema.relations():
        if rschema.final:
            continue
        for subj, obj in rschema.iter_rdefs():
            card = rschema.rproperty(subj, obj, 'cardinality')
            if card[0] in '1?' and len(rschema.subjects(obj)) == 1:
                relmap.setdefault((rschema, subj), []).append(str(obj))
            if card[1] in '1?' and len(rschema.objects(subj)) == 1:
                relmap.setdefault((rschema, obj), []).append(str(subj))
    unprotected = unprotected_entities(schema)
    for etype in skip:
        unprotected.add(etype)
    howmanydict = {}
    for etype in unprotected_entities(schema, strict=True):
        howmanydict[str(etype)] = cursor.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
        if etype in unprotected:
            howmanydict[str(etype)] += how_many
    for (rschema, etype), targets in relmap.iteritems():
        # XXX should 1. check no cycle 2. propagate changes
        relfactor = sum(howmanydict[e] for e in targets)
        howmanydict[str(etype)] = max(relfactor, howmanydict[etype])
    return howmanydict


class AutoPopulateTest(CubicWebTC):
    """base class for test with auto-populating of the database"""
    __abstract__ = True

    pdbclass = CubicWebDebugger
    # this is a hook to be able to define a list of rql queries
    # that are application dependent and cannot be guessed automatically
    application_rql = []

    no_auto_populate = ()
    ignored_relations = ()

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
        ignored_relations = SYSTEM_RELATIONS + self.ignored_relations
        for rschema in self.schema.relations():
            if rschema.final or rschema in ignored_relations:
                continue
            rset = cu.execute('DISTINCT Any X,Y WHERE X %s Y' % rschema)
            existingrels.setdefault(rschema.type, set()).update((x, y) for x, y in rset)
        q = make_relations_queries(self.schema, edict, cu, ignored_relations,
                                   existingrels=existingrels)
        for rql, args in q:
            cu.execute(rql, args)
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
            backup_rset = rset._prepare_copy(rset.rows, rset.description)
            yield InnerTest(self._testname(rset, view.__regid__, 'view'),
                            self.view, view.__regid__, rset,
                            rset.req.reset_headers(), 'main-template')
            # We have to do this because some views modify the
            # resultset's syntax tree
            rset = backup_rset
        for action in self.list_actions_for(rset):
            yield InnerTest(self._testname(rset, action.__regid__, 'action'), self._test_action, action)
        for box in self.list_boxes_for(rset):
            yield InnerTest(self._testname(rset, box.__regid__, 'box'), box.render)

    @staticmethod
    def _testname(rset, objid, objtype):
        return '%s_%s_%s' % ('_'.join(rset.column_types(0)), objid, objtype)


# concrete class for automated application testing  ############################

class AutomaticWebTest(AutoPopulateTest):
    """import this if you wan automatic tests to be ran"""
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
