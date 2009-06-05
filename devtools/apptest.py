"""This module provides misc utilities to test applications

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from copy import deepcopy

import simplejson

from logilab.common.testlib import TestCase
from logilab.common.pytest import nocoverage
from logilab.common.umessage import message_from_string

from logilab.common.deprecation import deprecated_function

from cubicweb.devtools import init_test_database, TestServerConfiguration, ApptestConfiguration
from cubicweb.devtools._apptest import TestEnvironment
from cubicweb.devtools.fake import FakeRequest

from cubicweb.dbapi import repo_connect, ConnectionProperties, ProgrammingError


MAILBOX = []
class Email:
    def __init__(self, recipients, msg):
        self.recipients = recipients
        self.msg = msg

    @property
    def message(self):
        return message_from_string(self.msg)

    def __repr__(self):
        return '<Email to %s with subject %s>' % (','.join(self.recipients),
                                                  self.message.get('Subject'))

class MockSMTP:
    def __init__(self, server, port):
        pass
    def close(self):
        pass
    def sendmail(self, helo_addr, recipients, msg):
        MAILBOX.append(Email(recipients, msg))

from cubicweb.server import hookhelper
hookhelper.SMTP = MockSMTP


def get_versions(self, checkversions=False):
    """return the a dictionary containing cubes used by this application
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


@property
def late_binding_env(self):
    """builds TestEnvironment as late as possible"""
    if not hasattr(self, '_env'):
        self.__class__._env = TestEnvironment('data', configcls=self.configcls,
                                              requestcls=self.requestcls)
    return self._env


class autoenv(type):
    """automatically set environment on EnvBasedTC subclasses if necessary
    """
    def __new__(mcs, name, bases, classdict):
        env = classdict.get('env')
        # try to find env in one of the base classes
        if env is None:
            for base in bases:
                env = getattr(base, 'env', None)
                if env is not None:
                    classdict['env'] = env
                    break
        if not classdict.get('__abstract__')  and not classdict.get('env'):
            classdict['env'] = late_binding_env
        return super(autoenv, mcs).__new__(mcs, name, bases, classdict)


class EnvBasedTC(TestCase):
    """abstract class for test using an apptest environment
    """
    __metaclass__ = autoenv
    __abstract__ = True
    env = None
    configcls = ApptestConfiguration
    requestcls = FakeRequest

    # user / session management ###############################################

    def user(self, req=None):
        if req is None:
            req = self.env.create_request()
            return self.env.cnx.user(req)
        else:
            return req.user

    def create_user(self, *args, **kwargs):
        return self.env.create_user(*args, **kwargs)

    def login(self, login, password=None):
        return self.env.login(login, password)

    def restore_connection(self):
        self.env.restore_connection()

    # db api ##################################################################

    @nocoverage
    def cursor(self, req=None):
        return self.env.cnx.cursor(req or self.request())

    @nocoverage
    def execute(self, *args, **kwargs):
        return self.env.execute(*args, **kwargs)

    @nocoverage
    def commit(self):
        self.env.cnx.commit()

    @nocoverage
    def rollback(self):
        try:
            self.env.cnx.rollback()
        except ProgrammingError:
            pass

    # other utilities #########################################################
    def set_debug(self, debugmode):
        from cubicweb.server import set_debug
        set_debug(debugmode)

    @property
    def config(self):
        return self.vreg.config

    def session(self):
        """return current server side session (using default manager account)"""
        return self.env.repo._sessions[self.env.cnx.sessionid]

    def request(self, *args, **kwargs):
        """return a web interface request"""
        return self.env.create_request(*args, **kwargs)

    @nocoverage
    def rset_and_req(self, *args, **kwargs):
        return self.env.get_rset_and_req(*args, **kwargs)

    def entity(self, rql, args=None, eidkey=None, req=None):
        return self.execute(rql, args, eidkey, req=req).get_entity(0, 0)

    def etype_instance(self, etype, req=None):
        req = req or self.request()
        e = self.env.vreg.etype_class(etype)(req, None, None)
        e.eid = None
        return e

    def add_entity(self, etype, **kwargs):
        rql = ['INSERT %s X' % etype]

        # dict for replacement in RQL Request
        rql_args = {}

        if kwargs: #
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
                    rql_args[new_value] = value.eid

                    sub_rql.append("X %s %s" % (key, new_value))
                # final attributes
                else:
                    sub_rql.append('X %s %%(%s)s' % (key, key))
                    rql_args[key] = value
            rql.append(', '.join(sub_rql))


            if entities:
                rql.append('WHERE')
                # WHERE part of the request (to link entity to they eid)
                sub_rql = []
                for key, value in entities.iteritems():
                    sub_rql.append("%s eid %%(%s)s" % (key, key))
                rql.append(', '.join(sub_rql))

        rql = ' '.join(rql)
        rset = self.execute(rql, rql_args)
        return rset.get_entity(0, 0)

    def set_option(self, optname, value):
        self.vreg.config.global_set_option(optname, value)

    def pviews(self, req, rset):
        return sorted((a.id, a.__class__) for a in self.vreg.possible_views(req, rset))

    def pactions(self, req, rset, skipcategories=('addrelated', 'siteactions', 'useractions')):
        return [(a.id, a.__class__) for a in self.vreg.possible_vobjects('actions', req, rset=rset)
                if a.category not in skipcategories]

    def pactions_by_cats(self, req, rset, categories=('addrelated',)):
        return [(a.id, a.__class__) for a in self.vreg.possible_vobjects('actions', req, rset=rset)
                if a.category in categories]

    paddrelactions = deprecated_function(pactions_by_cats)

    def pactionsdict(self, req, rset, skipcategories=('addrelated', 'siteactions', 'useractions')):
        res = {}
        for a in self.vreg.possible_vobjects('actions', req, rset=rset):
            if a.category not in skipcategories:
                res.setdefault(a.category, []).append(a.__class__)
        return res


    def remote_call(self, fname, *args):
        """remote call simulation"""
        dump = simplejson.dumps
        args = [dump(arg) for arg in args]
        req = self.request(fname=fname, pageid='123', arg=args)
        ctrl = self.vreg.select('controllers', 'json', req)
        return ctrl.publish(), req

    # default test setup and teardown #########################################

    def setup_database(self):
        pass

    def setUp(self):
        self.restore_connection()
        session = self.session()
        #self.maxeid = self.execute('Any MAX(X)')
        session.set_pool()
        self.maxeid = session.system_sql('SELECT MAX(eid) FROM entities').fetchone()[0]
        self.app = self.env.app
        self.vreg = self.env.app.vreg
        self.schema = self.vreg.schema
        self.vreg.config.mode = 'test'
        # set default-dest-addrs to a dumb email address to avoid mailbox or
        # mail queue pollution
        self.set_option('default-dest-addrs', ['whatever'])
        self.setup_database()
        self.commit()
        MAILBOX[:] = [] # reset mailbox

    @nocoverage
    def tearDown(self):
        self.rollback()
        # self.env.restore_database()
        self.env.restore_connection()
        self.session().unsafe_execute('DELETE Any X WHERE X eid > %s' % self.maxeid)
        self.commit()


# XXX
try:
    from cubicweb.web import Redirect
    from urllib import unquote
except ImportError:
    pass # cubicweb-web not installed
else:
    class ControllerTC(EnvBasedTC):
        def setUp(self):
            super(ControllerTC, self).setUp()
            self.req = self.request()
            self.ctrl = self.vreg.select('controllers', 'edit', self.req)

        def publish(self, req):
            assert req is self.ctrl.req
            try:
                result = self.ctrl.publish()
                req.cnx.commit()
            except Redirect:
                req.cnx.commit()
                raise
            return result

        def expect_redirect_publish(self, req=None):
            if req is not None:
                self.ctrl = self.vreg.select('controllers', 'edit', req)
            else:
                req = self.req
            try:
                res = self.publish(req)
            except Redirect, ex:
                try:
                    path, params = ex.location.split('?', 1)
                except:
                    path, params = ex.location, ""
                req._url = path
                cleanup = lambda p: (p[0], unquote(p[1]))
                params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
                return req.relative_path(False), params # path.rsplit('/', 1)[-1], params
            else:
                self.fail('expected a Redirect exception')


def make_late_binding_repo_property(attrname):
    @property
    def late_binding(self):
        """builds cnx as late as possible"""
        if not hasattr(self, attrname):
            # sets explicit test mode here to avoid autoreload
            from cubicweb.cwconfig import CubicWebConfiguration
            CubicWebConfiguration.mode = 'test'
            cls = self.__class__
            config = self.repo_config or TestServerConfiguration('data')
            cls._repo, cls._cnx = init_test_database('sqlite',  config=config)
        return getattr(self, attrname)
    return late_binding


class autorepo(type):
    """automatically set repository on RepositoryBasedTC subclasses if necessary
    """
    def __new__(mcs, name, bases, classdict):
        repo = classdict.get('repo')
        # try to find repo in one of the base classes
        if repo is None:
            for base in bases:
                repo = getattr(base, 'repo', None)
                if repo is not None:
                    classdict['repo'] = repo
                    break
        if name != 'RepositoryBasedTC' and not classdict.get('repo'):
            classdict['repo'] = make_late_binding_repo_property('_repo')
            classdict['cnx'] = make_late_binding_repo_property('_cnx')
        return super(autorepo, mcs).__new__(mcs, name, bases, classdict)


class RepositoryBasedTC(TestCase):
    """abstract class for test using direct repository connections
    """
    __metaclass__ = autorepo
    repo_config = None # set a particular config instance if necessary

    # user / session management ###############################################

    def create_user(self, user, groups=('users',), password=None, commit=True):
        if password is None:
            password = user
        eid = self.execute('INSERT CWUser X: X login %(x)s, X upassword %(p)s,'
                            'X in_state S WHERE S name "activated"',
                            {'x': unicode(user), 'p': password})[0][0]
        groups = ','.join(repr(group) for group in groups)
        self.execute('SET X in_group Y WHERE X eid %%(x)s, Y name IN (%s)' % groups,
                      {'x': eid})
        if commit:
            self.commit()
        self.session.reset_pool()
        return eid

    def login(self, login, password=None):
        cnx = repo_connect(self.repo, unicode(login), password or login,
                           ConnectionProperties('inmemory'))
        self.cnxs.append(cnx)
        return cnx

    def current_session(self):
        return self.repo._sessions[self.cnxs[-1].sessionid]

    def restore_connection(self):
        assert len(self.cnxs) == 1, self.cnxs
        cnx = self.cnxs.pop()
        try:
            cnx.close()
        except Exception, ex:
            print "exception occured while closing connection", ex

    # db api ##################################################################

    def execute(self, rql, args=None, eid_key=None):
        assert self.session.id == self.cnxid
        rset = self.__execute(self.cnxid, rql, args, eid_key)
        rset.vreg = self.vreg
        rset.req = self.session
        # call to set_pool is necessary to avoid pb when using
        # application entities for convenience
        self.session.set_pool()
        return rset

    def commit(self):
        self.__commit(self.cnxid)
        self.session.set_pool()

    def rollback(self):
        self.__rollback(self.cnxid)
        self.session.set_pool()

    def close(self):
        self.__close(self.cnxid)

    # other utilities #########################################################

    def set_debug(self, debugmode):
        from cubicweb.server import set_debug
        set_debug(debugmode)

    def set_option(self, optname, value):
        self.vreg.config.global_set_option(optname, value)

    def add_entity(self, etype, **kwargs):
        restrictions = ', '.join('X %s %%(%s)s' % (key, key) for key in kwargs)
        rql = 'INSERT %s X' % etype
        if kwargs:
            rql += ': %s' % ', '.join('X %s %%(%s)s' % (key, key) for key in kwargs)
        rset = self.execute(rql, kwargs)
        return rset.get_entity(0, 0)

    def default_user_password(self):
        config = self.repo.config #TestConfiguration('data')
        user = unicode(config.sources()['system']['db-user'])
        passwd = config.sources()['system']['db-password']
        return user, passwd

    def close_connections(self):
        for cnx in self.cnxs:
            try:
                cnx.rollback()
                cnx.close()
            except:
                continue
        self.cnxs = []

    pactions = EnvBasedTC.pactions.im_func
    pactionsdict = EnvBasedTC.pactionsdict.im_func

    # default test setup and teardown #########################################
    copy_schema = False

    def _prepare(self):
        MAILBOX[:] = [] # reset mailbox
        if hasattr(self, 'cnxid'):
            return
        repo = self.repo
        self.__execute = repo.execute
        self.__commit = repo.commit
        self.__rollback = repo.rollback
        self.__close = repo.close
        self.cnxid = self.cnx.sessionid
        self.session = repo._sessions[self.cnxid]
        # XXX copy schema since hooks may alter it and it may be not fully
        #     cleaned (missing some schema synchronization support)
        try:
            origschema = repo.__schema
        except AttributeError:
            origschema = repo.schema
            repo.__schema = origschema
        if self.copy_schema:
            repo.schema = deepcopy(origschema)
            repo.set_schema(repo.schema) # reset hooks
            repo.vreg.update_schema(repo.schema)
        self.cnxs = []
        # reset caches, they may introduce bugs among tests
        repo._type_source_cache = {}
        repo._extid_cache = {}
        repo.querier._rql_cache = {}
        for source in repo.sources:
            source.reset_caches()
        for s in repo.sources:
            if hasattr(s, '_cache'):
                s._cache = {}

    @property
    def config(self):
        return self.repo.config

    @property
    def vreg(self):
        return self.repo.vreg

    @property
    def schema(self):
        return self.repo.schema

    def setUp(self):
        self._prepare()
        self.session.set_pool()
        self.maxeid = self.session.system_sql('SELECT MAX(eid) FROM entities').fetchone()[0]

    def tearDown(self):
        self.close_connections()
        self.rollback()
        self.session.unsafe_execute('DELETE Any X WHERE X eid > %(x)s', {'x': self.maxeid})
        self.commit()

