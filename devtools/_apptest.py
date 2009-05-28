"""Hidden internals for the devtools.apptest module

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys, traceback

from logilab.common.pytest import pause_tracing, resume_tracing

import yams.schema

from cubicweb.dbapi import repo_connect, ConnectionProperties, ProgrammingError
from cubicweb.cwvreg import CubicWebRegistry

from cubicweb.web.application import CubicWebPublisher
from cubicweb.web import Redirect

from cubicweb.devtools import ApptestConfiguration, init_test_database
from cubicweb.devtools.fake import FakeRequest

SYSTEM_ENTITIES = ('CWGroup', 'CWUser',
                   'CWAttribute', 'CWRelation',
                   'CWConstraint', 'CWConstraintType', 'CWProperty',
                   'CWEType', 'CWRType',
                   'State', 'Transition', 'TrInfo',
                   'RQLExpression',
                   )
SYSTEM_RELATIONS = (
    # virtual relation
    'identity',
    # metadata
    'is', 'is_instance_of', 'owned_by', 'created_by', 'specializes',
    # workflow related
    'state_of', 'transition_of', 'initial_state', 'allowed_transition',
    'destination_state', 'in_state', 'wf_info_for', 'from_state', 'to_state',
    'condition',
    # permission
    'in_group', 'require_group', 'require_permission',
    'read_permission', 'update_permission', 'delete_permission', 'add_permission',
    # eproperty
    'for_user',
    # schema definition
    'relation_type', 'from_entity', 'to_entity',
    'constrained_by', 'cstrtype', 'widget',
    # deducted from other relations
    'primary_email',
                    )

def unprotected_entities(app_schema, strict=False):
    """returned a Set of each non final entity type, excluding CWGroup, and CWUser...
    """
    if strict:
        protected_entities = yams.schema.BASE_TYPES
    else:
        protected_entities = yams.schema.BASE_TYPES.union(set(SYSTEM_ENTITIES))
    entities = set(app_schema.entities())
    return entities - protected_entities


def ignore_relations(*relations):
    global SYSTEM_RELATIONS
    SYSTEM_RELATIONS += relations

class TestEnvironment(object):
    """TestEnvironment defines a context (e.g. a config + a given connection) in
    which the tests are executed
    """

    def __init__(self, appid, reporter=None, verbose=False,
                 configcls=ApptestConfiguration, requestcls=FakeRequest):
        config = configcls(appid)
        self.requestcls = requestcls
        self.cnx = None
        config.db_perms = False
        source = config.sources()['system']
        if verbose:
            print "init test database ..."
        self.vreg = vreg = CubicWebRegistry(config)
        self.admlogin = source['db-user']
        # restore database <=> init database
        self.restore_database()
        if verbose:
            print "init done"
        config.repository = lambda x=None: self.repo
        self.app = CubicWebPublisher(config, vreg=vreg)
        self.verbose = verbose
        schema = self.vreg.schema
        # else we may run into problems since email address are ususally share in app tests
        # XXX should not be necessary anymore
        schema.rschema('primary_email').set_rproperty('CWUser', 'EmailAddress', 'composite', False)
        self.deletable_entities = unprotected_entities(schema)

    def restore_database(self):
        """called by unittests' tearDown to restore the original database
        """
        try:
            pause_tracing()
            if self.cnx:
                self.cnx.close()
            source = self.vreg.config.sources()['system']
            self.repo, self.cnx = init_test_database(driver=source['db-driver'],
                                                     vreg=self.vreg)
            self._orig_cnx = self.cnx
            resume_tracing()
        except:
            resume_tracing()
            traceback.print_exc()
            sys.exit(1)
        # XXX cnx decoration is usually done by the repository authentication manager,
        # necessary in authentication tests
        self.cnx.vreg = self.vreg
        self.cnx.login = source['db-user']
        self.cnx.password = source['db-password']


    def create_user(self, login, groups=('users',), req=None):
        req = req or self.create_request()
        cursor = self._orig_cnx.cursor(req)
        rset = cursor.execute('INSERT CWUser X: X login %(login)s, X upassword %(passwd)s,'
                              'X in_state S WHERE S name "activated"',
                              {'login': unicode(login), 'passwd': login.encode('utf8')})
        user = rset.get_entity(0, 0)
        cursor.execute('SET X in_group G WHERE X eid %%(x)s, G name IN(%s)'
                       % ','.join(repr(g) for g in groups),
                       {'x': user.eid}, 'x')
        user.clear_related_cache('in_group', 'subject')
        self._orig_cnx.commit()
        return user

    def login(self, login, password=None):
        if login == self.admlogin:
            self.restore_connection()
        else:
            self.cnx = repo_connect(self.repo, unicode(login),
                                    password or str(login),
                                    ConnectionProperties('inmemory'))
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

    ############################################################################

    def execute(self, rql, args=None, eidkey=None, req=None):
        """executes <rql>, builds a resultset, and returns a couple (rset, req)
        where req is a FakeRequest
        """
        req = req or self.create_request(rql=rql)
        return self.cnx.cursor(req).execute(unicode(rql), args, eidkey)

    def create_request(self, rql=None, **kwargs):
        """executes <rql>, builds a resultset, and returns a
        couple (rset, req) where req is a FakeRequest
        """
        if rql:
            kwargs['rql'] = rql
        req = self.requestcls(self.vreg, form=kwargs)
        req.set_connection(self.cnx)
        return req

    def get_rset_and_req(self, rql, optional_args=None, args=None, eidkey=None):
        """executes <rql>, builds a resultset, and returns a
        couple (rset, req) where req is a FakeRequest
        """
        return (self.execute(rql, args, eidkey),
                self.create_request(rql=rql, **optional_args or {}))

    def check_view(self, rql, vid, optional_args, template='main'):
        """checks if vreg.view() raises an exception in this environment

        If any exception is raised in this method, it will be considered
        as a TestFailure
        """
        return self.call_view(vid, rql,
                              template=template, optional_args=optional_args)

    def call_view(self, vid, rql, template='main', optional_args=None):
        """shortcut for self.vreg.view()"""
        assert template
        if optional_args is None:
            optional_args = {}
        optional_args['vid'] = vid
        req = self.create_request(rql=rql, **optional_args)
        return self.vreg.main_template(req, template)

    def call_edit(self, req):
        """shortcut for self.app.edit()"""
        controller = self.app.select_controller('edit', req)
        try:
            controller.publish()
        except Redirect:
            result = 'success'
        else:
            raise Exception('edit should raise Redirect on success')
        req.cnx.commit()
        return result

    def iter_possible_views(self, req, rset):
        """returns a list of possible vids for <rql>"""
        for view in self.vreg.possible_views(req, rset):
            if view.category == 'startupview':
                continue
            yield view.id
        if rset.rowcount == 1:
            yield 'edition'

    def iter_startup_views(self, req):
        """returns the list of startup views"""
        for view in self.vreg.possible_views(req, None):
            if view.category != 'startupview':
                continue
            yield view.id

    def iter_possible_actions(self, req, rset):
        """returns a list of possible vids for <rql>"""
        for action in self.vreg.possible_vobjects('actions', req, rset):
            yield action

class ExistingTestEnvironment(TestEnvironment):

    def __init__(self, appid, sourcefile, verbose=False):
        config = ApptestConfiguration(appid, sourcefile=sourcefile)
        if verbose:
            print "init test database ..."
        source = config.sources()['system']
        self.vreg = CubicWebRegistry(config)
        self.cnx = init_test_database(driver=source['db-driver'],
                                      vreg=self.vreg)[1]
        if verbose:
            print "init done"
        self.app = CubicWebPublisher(config, vreg=self.vreg)
        self.verbose = verbose
        # this is done when the publisher is opening a connection
        self.cnx.vreg = self.vreg

    def setup(self, config=None):
        """config is passed by TestSuite but is ignored in this environment"""
        cursor = self.cnx.cursor()
        self.last_eid = cursor.execute('Any X WHERE X creation_date D ORDERBY D DESC LIMIT 1').rows[0][0]

    def cleanup(self):
        """cancel inserted elements during tests"""
        cursor = self.cnx.cursor()
        cursor.execute('DELETE Any X WHERE X eid > %(x)s', {'x' : self.last_eid}, eid_key='x')
        print "cleaning done"
        self.cnx.commit()
