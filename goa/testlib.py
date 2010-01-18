"""
:organization: Logilab
:copyright: 2008-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.testlib import TestCase, TestSkipped
try:
    import google.appengine
except ImportError:
    raise TestSkipped('Can not import google.appengine. Skip this module')

import os, os.path as osp
import time
from shutil import copy

# additional monkey patches necessary in regular cubicweb environment
from cubicweb.server import rqlannotation
from cubicweb.goa.overrides import rqlannotation as goarqlannotation
rqlannotation.SQLGenAnnotator = goarqlannotation.SQLGenAnnotator
rqlannotation.set_qdata = goarqlannotation.set_qdata

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
from google.appengine.ext import db as gdb

from cubicweb.devtools.fake import FakeRequest

from cubicweb.goa import db, do_monkey_patch
from cubicweb.goa.goavreg import GAEVRegistry
from cubicweb.goa.goaconfig import GAEConfiguration
from cubicweb.goa.dbinit import (create_user, create_groups, fix_entities,
                                 init_persistent_schema, insert_versions)

import logging
logger = logging.getLogger()
logger.setLevel(logging.CRITICAL)

do_monkey_patch()

class GAEBasedTC(TestCase):
    APP_ID = u'test_app'
    AUTH_DOMAIN = 'gmail.com'
    LOGGED_IN_USER = u't...@example.com'  # set to '' for no logged in user
    MODEL_CLASSES = None
    LOAD_APP_MODULES = None
    config = None
    _DS_TEMPL_FILE = 'tmpdb-template'

    def load_schema_hook(self, loader):
        loader.import_yams_cube_schema('data')

    @property
    def DS_FILE(self):
        return self.DS_TEMPL_FILE.replace('-template', '')

    @property
    def DS_TEMPL_FILE(self):
        return self._DS_TEMPL_FILE + '_'.join(sorted(cls.__name__ for cls in self.MODEL_CLASSES))

    def _set_ds_file(self, dsfile):
        # Start with a fresh api proxy.
        apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
        # Use a fresh stub datastore.
        stub = datastore_file_stub.DatastoreFileStub(self.APP_ID, dsfile,
                                                     dsfile+'.history')
        apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', stub)

    def setUp(self):
        # Ensure we're in UTC.
        os.environ['TZ'] = 'UTC'
        time.tzset()
        if osp.exists(self.DS_TEMPL_FILE):
            copy(self.DS_TEMPL_FILE, self.DS_FILE)
            need_ds_init = False
            self._set_ds_file(self.DS_FILE)
        else:
            need_ds_init = True
            self._set_ds_file(self.DS_TEMPL_FILE)
#         from google.appengine.api import mail_stub
#         from google3.apphosting.api import urlfetch_stub
#         from google3.apphosting.api import user_service_stub
#         # Use a fresh stub UserService.
#         apiproxy_stub_map.apiproxy.RegisterStub(
#             'user', user_service_stub.UserServiceStub())
        os.environ['AUTH_DOMAIN'] = self.AUTH_DOMAIN
        os.environ['USER_EMAIL'] = self.LOGGED_IN_USER
#         # Use a fresh urlfetch stub.
#         apiproxy_stub_map.apiproxy.RegisterStub(
#             'urlfetch', urlfetch_stub.URLFetchServiceStub())
#         # Use a fresh mail stub.
#         apiproxy_stub_map.apiproxy.RegisterStub(
#             'mail', mail_stub.MailServiceStub())
        if self.MODEL_CLASSES is None:
            raise Exception('GAEBasedTC should set MODEL_CLASSES class attribute')
        gdb._kind_map = {}
        self.config = self.config or GAEConfiguration('toto')
        self.config.init_log(logging.CRITICAL)
        self.schema = self.config.load_schema(self.MODEL_CLASSES,
                                              self.load_schema_hook)
        self.vreg = GAEVregistry(self.config)
        self.vreg.schema = self.schema
        self.vreg.load_module(db)
        from cubicweb.goa.appobjects import sessions
        self.vreg.load_module(sessions)
        from cubicweb.entities import authobjs, schemaobjs
        self.vreg.load_module(authobjs)
        self.vreg.load_module(schemaobjs)
        if self.config['use-google-auth']:
            from cubicweb.goa.appobjects import gauthservice
            self.vreg.load_module(gauthservice)
        if self.LOAD_APP_MODULES is not None:
            for module in self.LOAD_APP_MODULES:
                self.vreg.load_module(module)
        for cls in self.MODEL_CLASSES:
            self.vreg.load_object(cls)
        self.session_manager = self.vreg.select('components', 'sessionmanager')
        if need_ds_init:
            # create default groups and create entities according to the schema
            create_groups()
            if not self.config['use-google-auth']:
                create_user(self.LOGGED_IN_USER, 'toto', ('users', 'managers'))
                self.session = self.login(self.LOGGED_IN_USER, 'toto')
            else:
                req = FakeRequest(vreg=self.vreg)
                self.session = self.session_manager.open_session(req)
            self.user = self.session.user()
            ssession = self.config.repo_session(self.session.sessionid)
            ssession.set_pool()
            init_persistent_schema(ssession, self.schema)
            insert_versions(ssession, self.config)
            ssession.commit()
            fix_entities(self.schema)
            copy(self.DS_TEMPL_FILE, self.DS_FILE)
            self._set_ds_file(self.DS_FILE)
        else:
            if not self.config['use-google-auth']:
                self.session = self.login(self.LOGGED_IN_USER, 'toto')
            else:
                req = FakeRequest(vreg=self.vreg)
                self.session = self.session_manager.open_session(req)
            self.user = self.session.user()

    def tearDown(self):
        self.session.close()

    def request(self):
        req = FakeRequest(vreg=self.vreg)
        req.set_connection(self.session, self.user)
        return req

    def add_entity(self, etype, **kwargs):
        cu = self.session.cursor()
        rql = 'INSERT %s X' % etype
        if kwargs:
            rql += ': %s' % ', '.join('X %s %%(%s)s' % (key, key) for key in kwargs)
        rset = cu.execute(rql, kwargs)
        return rset.get_entity(0, 0)

    def execute(self, *args):
        return self.session.cursor().execute(*args)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def create_user(self, login, groups=('users',), req=None):
        assert not self.config['use-google-auth']
        user = self.add_entity('CWUser', upassword=str(login), login=unicode(login))
        cu = self.session.cursor()
        cu.execute('SET X in_group G WHERE X eid %%(x)s, G name IN(%s)'
                    % ','.join(repr(g) for g in groups),
                    {'x': user.eid}, 'x')
        return user

    def login(self, login, password=None):
        assert not self.config['use-google-auth']
        req = FakeRequest(vreg=self.vreg)
        req.form['__login'] = login
        req.form['__password'] = password or login
        return self.session_manager.open_session(req)
