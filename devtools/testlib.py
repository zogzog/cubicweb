# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
__docformat__ = "restructuredtext en"

import sys
import re
import urlparse
from os.path import dirname, join, abspath
from urllib import unquote
from math import log
from contextlib import contextmanager
from warnings import warn
from types import NoneType
from itertools import chain

import yams.schema

from logilab.common.testlib import TestCase, InnerTest, Tags
from logilab.common.pytest import nocoverage, pause_trace
from logilab.common.debugger import Debugger
from logilab.common.umessage import message_from_string
from logilab.common.decorators import cached, classproperty, clear_cache, iclassmethod
from logilab.common.deprecation import deprecated, class_deprecated
from logilab.common.shellutils import getlogin

from cubicweb import (ValidationError, NoSelectableObject, AuthenticationError,
                      ProgrammingError, BadConnectionId)
from cubicweb import cwconfig, devtools, web, server, repoapi
from cubicweb.utils import json
from cubicweb.sobjects import notification
from cubicweb.web import Redirect, application, eid_param
from cubicweb.server.hook import SendMailOp
from cubicweb.server.session import Session
from cubicweb.devtools import SYSTEM_ENTITIES, SYSTEM_RELATIONS, VIEW_VALIDATORS
from cubicweb.devtools import fake, htmlparser, DEFAULT_EMPTY_DB_ID
from cubicweb.utils import json

# low-level utilities ##########################################################

class CubicWebDebugger(Debugger):
    """special debugger class providing a 'view' function which saves some
    html into a temporary file and open a web browser to examinate it.
    """
    def do_view(self, arg):
        import webbrowser
        data = self._getval(arg)
        with file('/tmp/toto.html', 'w') as toto:
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
        return json.loads(data)

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
        MAILBOX.append(Email(fromaddr, recipients, msg))

cwconfig.SMTP = MockSMTP


class TestCaseConnectionProxy(object):
    """thin wrapper around `cubicweb.repoapi.ClientConnection` context-manager
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
        # already open
        return self.cnx

    def __exit__(self, exctype, exc, tb):
        try:
            return self.cnx.__exit__(exctype, exc, tb)
        finally:
            self.testcase.restore_connection()

# Repoaccess utility ###############################################3###########

class RepoAccess(object):
    """An helper to easily create object to access the repo as a specific user

    Each RepoAccess have it own session.

    A repo access can create three type of object:

    .. automethod:: cubicweb.testlib.RepoAccess.repo_cnx
    .. automethod:: cubicweb.testlib.RepoAccess.client_cnx
    .. automethod:: cubicweb.testlib.RepoAccess.web_request

    The RepoAccess need to be closed to destroy the associated Session.
    TestCase usually take care of this aspect for the user.

    .. automethod:: cubicweb.testlib.RepoAccess.close
    """

    def __init__(self, repo, login, requestcls):
        self._repo = repo
        self._login = login
        self.requestcls = requestcls
        self._session = self._unsafe_connect(login)

    def _unsafe_connect(self, login, **kwargs):
        """ a completely unsafe connect method for the tests """
        # use an internal connection
        with self._repo.internal_cnx() as cnx:
            # try to get a user object
            user = cnx.find('CWUser', login=login).one()
            user.groups
            user.properties
            user.login
            session = Session(user, self._repo)
            self._repo._sessions[session.sessionid] = session
            user._cw = user.cw_rset.req = session
        with session.new_cnx() as cnx:
            self._repo.hm.call_hooks('session_open', cnx)
            # commit connection at this point in case write operation has been
            # done during `session_open` hooks
            cnx.commit()
        return session

    @contextmanager
    def repo_cnx(self):
        """Context manager returning a server side connection for the user"""
        with self._session.new_cnx() as cnx:
            yield cnx

    @contextmanager
    def client_cnx(self):
        """Context manager returning a client side connection for the user"""
        with repoapi.ClientConnection(self._session) as cnx:
            yield cnx

    @contextmanager
    def web_request(self, url=None, headers={}, method='GET', **kwargs):
        """Context manager returning a web request pre-linked to a client cnx

        To commit and rollback use::

            req.cnx.commit()
            req.cnx.rolback()
        """
        req = self.requestcls(self._repo.vreg, url=url, headers=headers,
                              method=method, form=kwargs)
        clt_cnx = repoapi.ClientConnection(self._session)
        req.set_cnx(clt_cnx)
        with clt_cnx:
            yield req

    def close(self):
        """Close the session associated to the RepoAccess"""
        if self._session is not None:
            self._repo.close(self._session.sessionid)
        self._session = None

    @contextmanager
    def shell(self):
        from cubicweb.server.migractions import ServerMigrationHelper
        with repoapi.ClientConnection(self._session) as cnx:
            mih = ServerMigrationHelper(None, repo=self._repo, cnx=cnx,
                                        interactive=False,
                                        # hack so it don't try to load fs schema
                                        schema=1)
            yield mih
            cnx.commit()



# base class for cubicweb tests requiring a full cw environments ###############

class CubicWebTC(TestCase):
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
    """
    appid = 'data'
    configcls = devtools.ApptestConfiguration
    requestcls = fake.FakeRequest
    tags = TestCase.tags | Tags('cubicweb', 'cw_repo')
    test_db_id = DEFAULT_EMPTY_DB_ID
    _cnxs = set() # establised connection
                  # stay on connection for leak detection purpose

    # anonymous is logged by default in cubicweb test cases
    anonymous_allowed = True

    def __init__(self, *args, **kwargs):
        self._admin_session = None
        self._admin_clt_cnx = None
        self._current_session = None
        self._current_clt_cnx = None
        self.repo = None
        self._open_access = set()
        super(CubicWebTC, self).__init__(*args, **kwargs)

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
                self._open_access.pop().close()
            except BadConnectionId:
                continue # already closed

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def set_cnx(self, cnx):
        assert getattr(cnx, '_session', None) is not None
        if cnx is self._admin_clt_cnx:
            self._pop_custom_cnx()
        else:
            self._cnxs.add(cnx) # register the cnx to make sure it is removed
            self._current_session = cnx._session
            self._current_clt_cnx = cnx

    @property
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def cnx(self):
        # XXX we want to deprecate this
        clt_cnx = self._current_clt_cnx
        if clt_cnx is None:
            clt_cnx = self._admin_clt_cnx
        return clt_cnx

    def _close_cnx(self):
        """ensure that all cnx used by a test have been closed"""
        for cnx in list(self._cnxs):
            if cnx._open and not cnx._session.closed:
                cnx.rollback()
                cnx.close()
            self._cnxs.remove(cnx)

    @property
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def session(self):
        """return current server side session"""
        # XXX We want to use a srv_connection instead and deprecate this
        # property
        session = self._current_session
        if session is None:
            session = self._admin_session
            # bypassing all sanity to use the same repo cnx in the session
            #
            # we can't call set_cnx as the Connection is not managed by the
            # session.
            session._Session__threaddata.cnx = self._admin_clt_cnx._cnx
        else:
            session._Session__threaddata.cnx = self.cnx._cnx
        session.set_cnxset()
        return session

    @property
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def websession(self):
        return self.session

    @property
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def adminsession(self):
        """return current server side session (using default manager account)"""
        return self._admin_session

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def login(self, login, **kwargs):
        """return a connection for the given login/password"""
        __ = kwargs.pop('autoclose', True) # not used anymore
        if login == self.admlogin:
            # undo any previous login, if we're not used as a context manager
            self.restore_connection()
            return self.cnx
        else:
            if not kwargs:
                kwargs['password'] = str(login)
            clt_cnx = repoapi.connect(self.repo, login, **kwargs)
        self.set_cnx(clt_cnx)
        clt_cnx.__enter__()
        return TestCaseConnectionProxy(self, clt_cnx)

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def restore_connection(self):
        self._pop_custom_cnx()

    def _pop_custom_cnx(self):
        if self._current_clt_cnx is not None:
            if self._current_clt_cnx._open:
                self._current_clt_cnx.close()
            if not  self._current_session.closed:
                self.repo.close(self._current_session.sessionid)
            self._current_clt_cnx = None
            self._current_session = None

    #XXX this doesn't need to a be classmethod anymore
    def _init_repo(self):
        """init the repository and connection to it.
        """
        # get or restore and working db.
        db_handler = devtools.get_test_db_handler(self.config, self.init_config)
        db_handler.build_db_cache(self.test_db_id, self.pre_setup_database)
        db_handler.restore_database(self.test_db_id)
        self.repo = db_handler.get_repo(startup=True)
        # get an admin session (without actual login)
        login = unicode(db_handler.config.default_admin_config['login'])
        self.admin_access = self.new_access(login)
        self._admin_session = self.admin_access._session
        self._admin_clt_cnx = repoapi.ClientConnection(self._admin_session)
        self._cnxs.add(self._admin_clt_cnx)
        self._admin_clt_cnx.__enter__()

    # db api ##################################################################

    @nocoverage
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def cursor(self, req=None):
        if req is not None:
            return req.cnx
        else:
            return self.cnx

    @nocoverage
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def execute(self, rql, args=None, req=None):
        """executes <rql>, builds a resultset, and returns a couple (rset, req)
        where req is a FakeRequest
        """
        req = req or self.request(rql=rql)
        return req.execute(unicode(rql), args)

    @nocoverage
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def commit(self):
        try:
            return self.cnx.commit()
        finally:
            self.session.set_cnxset() # ensure cnxset still set after commit

    @nocoverage
    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def rollback(self):
        try:
            self.cnx.rollback()
        except ProgrammingError:
            pass # connection closed
        finally:
            self.session.set_cnxset() # ensure cnxset still set after commit

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def request(self, rollbackfirst=False, url=None, headers={}, **kwargs):
        """return a web ui request"""
        if rollbackfirst:
            self.cnx.rollback()
        req = self.requestcls(self.vreg, url=url, headers=headers, form=kwargs)
        req.set_cnx(self.cnx)
        return req

    # server side db api #######################################################

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def sexecute(self, rql, args=None):
        self.session.set_cnxset()
        return self.session.execute(rql, args)


    # config management ########################################################

    @classproperty
    def config(cls):
        """return the configuration object

        Configuration is cached on the test class.
        """
        try:
            assert not cls is CubicWebTC, "Don't use CubicWebTC directly to prevent database caching issue"
            return cls.__dict__['_config']
        except KeyError:
            home = abspath(join(dirname(sys.modules[cls.__module__].__file__), cls.appid))
            config = cls._config = cls.configcls(cls.appid, apphome=home)
            config.mode = 'test'
            return config

    @classmethod # XXX could be turned into a regular method
    def init_config(cls, config):
        """configuration initialization hooks.

        You may only want to override here the configuraton logic.

        Otherwise, consider to use a different :class:`ApptestConfiguration`
        defined in the `configcls` class attribute.

        This method will be called by the database handler once the config has
        been properly bootstrapped.
        """
        admincfg = config.default_admin_config
        cls.admlogin = unicode(admincfg['login'])
        cls.admpassword = admincfg['password']
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
        except Exception: # not in server only configuration
            pass
        config.set_anonymous_allowed(cls.anonymous_allowed)

    @property
    def vreg(self):
        return self.repo.vreg


    # global resources accessors ###############################################

    @property
    def schema(self):
        """return the application schema"""
        return self.vreg.schema

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
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
        self._patch_SendMailOp()
        with pause_trace():
            previous_failure = self.__class__.__dict__.get('_repo_init_failed')
            if previous_failure is not None:
                self.skipTest('repository is not initialised: %r' % previous_failure)
            try:
                self._init_repo()
                self.addCleanup(self._close_cnx)
            except Exception as ex:
                self.__class__._repo_init_failed = ex
                raise
            self.addCleanup(self._close_access)
        self.setup_database()
        self._admin_clt_cnx.commit()
        MAILBOX[:] = [] # reset mailbox

    def tearDown(self):
        # XXX hack until logilab.common.testlib is fixed
        if self._admin_clt_cnx is not None:
            if self._admin_clt_cnx._open:
                self._admin_clt_cnx.close()
            self._admin_clt_cnx = None
        if self._admin_session is not None:
            if not self._admin_session.closed:
                self.repo.close(self._admin_session.sessionid)
            self._admin_session = None
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

    @deprecated('[3.19] explicitly use RepoAccess object in test instead')
    def user(self, req=None):
        """return the application schema"""
        if req is None:
            return self.request().user
        else:
            return req.user

    @iclassmethod # XXX turn into a class method
    def create_user(self, req, login=None, groups=('users',), password=None,
                    email=None, commit=True, **kwargs):
        """create and return a new user entity"""
        if isinstance(req, basestring):
            warn('[3.12] create_user arguments are now (req, login[, groups, password, commit, **kwargs])',
                 DeprecationWarning, stacklevel=2)
            if not isinstance(groups, (tuple, list)):
                password = groups
                groups = login
            elif isinstance(login, tuple):
                groups = login
            login = req
            assert not isinstance(self, type)
            req = self._admin_clt_cnx
        if password is None:
            password = login.encode('utf8')
        user = req.create_entity('CWUser', login=unicode(login),
                                 upassword=password, **kwargs)
        req.execute('SET X in_group G WHERE X eid %%(x)s, G name IN(%s)'
                    % ','.join(repr(str(g)) for g in groups),
                    {'x': user.eid})
        if email is not None:
            req.create_entity('EmailAddress', address=unicode(email),
                              reverse_primary_email=user)
        user.cw_clear_relation_cache('in_group', 'subject')
        if commit:
            try:
                req.commit() # req is a session
            except AttributeError:
                req.cnx.commit()
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
        for erschema, etypeperms in chain(perm_overrides, perm_kwoverrides.iteritems()):
            if isinstance(erschema, basestring):
                erschema = self.schema[erschema]
            for action, actionperms in etypeperms.iteritems():
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
                        raise NoSelectableObject((req,), {'rset':rset}, views)
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

    @deprecated('[3.19] use the .remote_calling method')
    def remote_call(self, fname, *args):
        """remote json call simulation"""
        dump = json.dumps
        args = [dump(arg) for arg in args]
        req = self.request(fname=fname, pageid='123', arg=args)
        ctrl = self.vreg['controllers'].select('ajax', req)
        return ctrl.publish(), req

    @contextmanager
    def remote_calling(self, fname, *args):
        """remote json call simulation"""
        args = [json.dumps(arg) for arg in args]
        with self.admin_access.web_request(fname=fname, pageid='123', arg=args) as req:
            ctrl = self.vreg['controllers'].select('ajax', req)
            yield ctrl.publish(), req

    def app_handle_request(self, req, path='view'):
        return self.app.core_handle(req, path)

    @deprecated("[3.15] app_handle_request is the new and better way"
                " (beware of small semantic changes)")
    def app_publish(self, *args, **kwargs):
        return self.app_handle_request(*args, **kwargs)

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
            form['_cw_fields'] = ','.join(fields)
        return form

    @deprecated('[3.19] use .admin_request_from_url instead')
    def req_from_url(self, url):
        """parses `url` and builds the corresponding CW-web request

        req.form will be setup using the url's query string
        """
        req = self.request(url=url)
        if isinstance(url, unicode):
            url = url.encode(req.encoding) # req.setup_params() expects encoded strings
        querystring = urlparse.urlparse(url)[-2]
        params = urlparse.parse_qs(querystring)
        req.setup_params(params)
        return req

    @contextmanager
    def admin_request_from_url(self, url):
        """parses `url` and builds the corresponding CW-web request

        req.form will be setup using the url's query string
        """
        with self.admin_access.web_request(url=url) as req:
            if isinstance(url, unicode):
                url = url.encode(req.encoding) # req.setup_params() expects encoded strings
            querystring = urlparse.urlparse(url)[-2]
            params = urlparse.parse_qs(querystring)
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
                result = self.app_handle_request(req, req.relative_path(False))
            return result, req

    @staticmethod
    def _parse_location(req, location):
        try:
            path, params = location.split('?', 1)
        except ValueError:
            path = location
            params = {}
        else:
            cleanup = lambda p: (p[0], unquote(p[1]))
            params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
        if path.startswith(req.base_url()): # may be relative
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
        result = self.app_handle_request(req, path)
        self.assertTrue(300 <= req.status_out <400, req.status_out)
        location = req.get_response_header('location')
        return self._parse_location(req, location)

    @deprecated("[3.15] expect_redirect_handle_request is the new and better way"
                " (beware of small semantic changes)")
    def expect_redirect_publish(self, *args, **kwargs):
        return self.expect_redirect_handle_request(*args, **kwargs)


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
        return req, self.session

    def assertAuthSuccess(self, req, origsession, nbsessions=1):
        sh = self.app.session_handler
        session = self.app.get_session(req)
        clt_cnx = repoapi.ClientConnection(session)
        req.set_cnx(clt_cnx)
        self.assertEqual(len(self.open_sessions), nbsessions, self.open_sessions)
        self.assertEqual(session.login, origsession.login)
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
        #'text/html': DTDValidator,
        #'application/xhtml+xml': DTDValidator,
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
                          for vid, valkey in VIEW_VALIDATORS.iteritems())


    def view(self, vid, rset=None, req=None, template='main-template',
             **kwargs):
        """This method tests the view `vid` on `rset` using `template`

        If no error occurred while rendering the view, the HTML is analyzed
        and parsed.

        :returns: an instance of `cubicweb.devtools.htmlparser.PageInfo`
                  encapsulation the generated HTML
        """
        if req is None:
            if rset is None:
                req = self.request()
            else:
                req = rset.req
        req.form['vid'] = vid
        viewsreg = self.vreg['views']
        view = viewsreg.select(vid, req, rset=rset, **kwargs)
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
            viewfunc = lambda **k: viewsreg.main_template(req, template,
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
        if content_type in ('text/html', 'application/xhtml+xml') and output:
            if output.startswith('<!DOCTYPE html>'):
                # only check XML well-formness since HTMLValidator isn't html5
                # compatible and won't like various other extensions
                default_validator = htmlparser.XMLSyntaxValidator
            elif output.startswith('<?xml'):
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
            return output # return raw output if no validator is defined
        if isinstance(validator, htmlparser.DTDValidator):
            # XXX remove <canvas> used in progress widget, unknown in html dtd
            output = re.sub('<canvas.*?></canvas>', '', output)
        return self.assertWellFormed(validator, output.strip(), context= view.__regid__)

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
            msg += str_exc
            if content is not None:
                position = getattr(exc, "position", (0,))[0]
                if position:
                    # define filter
                    if isinstance(content, str):
                        content = unicode(content, sys.getdefaultencoding(), 'replace')
                    content = validator.preprocess_data(content)
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


# auto-populating test classes and utilities ###################################

from cubicweb.devtools.fill import insert_entity_queries, make_relations_queries

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
    for etype in skip: # XXX (syt) duh? explain or kill
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
    for (rschema, etype), targets in relmap.iteritems():
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
        with self.admin_access.repo_cnx() as cnx:
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
            if rschema.final or rschema in ignored_relations:
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
                print 'error in automatic db population', ex
                cnx.commit_state = None # reset uncommitable flag
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
            yield req.execute('DISTINCT Any X, MAX(Y) GROUPBY X WHERE X is %s, Y is %s' % (etype1, etype2))
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
        assert not self.__class__ is AutomaticWebTest, 'Please subclass AutomaticWebTest to prevent database caching issue'
        super(AutomaticWebTest, self).setUp()

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
            with self.admin_access.web_request() as req:
                yield self.view, vid, None, req


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
#     for reg in env.vreg.itervalues():
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
#     for regname, reg in testclass._env.vreg.iteritems():
#         if regname in skipregs:
#             continue
#         for appobjects in reg.itervalues():
#             for appobject in appobjects:
#                 if not reg._selected.get(appobject):
#                     print 'not tested', regname, appobject
