from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools.testlib import CubicWebTC

#################
# <required  ?> #
#################


from datetime import datetime

from cubicweb import (ConnectionError, ValidationError, AuthenticationError,
                      BadConnectionId)
from cubicweb.devtools.testlib import get_versions

from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.repository import Repository

orig_get_versions = Repository.get_versions
#################
# </required ?> #
#################

def setup_module(*args):
    Repository.get_versions = get_versions

def teardown_module(*args):
    Repository.get_versions = orig_get_versions

class SchemaModificationHooksTC(CubicWebTC):

    @classmethod
    def init_config(cls, config):
        super(SchemaModificationHooksTC, cls).init_config(config)
        config._cubes = None
        cls.repo.fill_schema()

    def index_exists(self, etype, attr, unique=False):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        return dbhelper.index_exists(sqlcursor, SQL_PREFIX + etype, SQL_PREFIX + attr, unique=unique)

    def _set_perms(self, eid):
        self.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                     {'x': eid}, 'x')
        self.execute('SET X add_permission G WHERE X eid %(x)s, G is CWGroup, G name "managers"',
                     {'x': eid}, 'x')
        self.execute('SET X delete_permission G WHERE X eid %(x)s, G is CWGroup, G name "owners"',
                     {'x': eid}, 'x')

    def _set_attr_perms(self, eid):
        self.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                     {'x': eid}, 'x')
        self.execute('SET X update_permission G WHERE X eid %(x)s, G is CWGroup, G name "managers"',
                     {'x': eid}, 'x')

    def test_base(self):
        schema = self.repo.schema
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        # schema should be update on insertion (after commit)
        eeid = self.execute('INSERT CWEType X: X name "Societe2", X description "", X final FALSE')[0][0]
        self._set_perms(eeid)
        self.execute('INSERT CWRType X: X name "concerne2", X description "", X final FALSE, X symmetric FALSE')
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        # have to commit before adding definition relations
        self.commit()
        self.failUnless(schema.has_entity('Societe2'))
        self.failUnless(schema.has_relation('concerne2'))
        attreid = self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval "noname", '
                               '   X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                               'WHERE RT name "name", E name "Societe2", F name "String"')[0][0]
        self._set_attr_perms(attreid)
        concerne2_rdef_eid = self.execute(
            'INSERT CWRelation X: X cardinality "**", X relation_type RT, X from_entity E, X to_entity E '
            'WHERE RT name "concerne2", E name "Societe2"')[0][0]
        self._set_perms(concerne2_rdef_eid)
        self.failIf('name' in schema['Societe2'].subject_relations())
        self.failIf('concerne2' in schema['Societe2'].subject_relations())
        self.failIf(self.index_exists('Societe2', 'name'))
        self.commit()
        self.failUnless('name' in schema['Societe2'].subject_relations())
        self.failUnless('concerne2' in schema['Societe2'].subject_relations())
        self.failUnless(self.index_exists('Societe2', 'name'))
        # now we should be able to insert and query Societe2
        s2eid = self.execute('INSERT Societe2 X: X name "logilab"')[0][0]
        self.execute('Societe2 X WHERE X name "logilab"')
        self.execute('SET X concerne2 X WHERE X name "logilab"')
        rset = self.execute('Any X WHERE X concerne2 Y')
        self.assertEquals(rset.rows, [[s2eid]])
        # check that when a relation definition is deleted, existing relations are deleted
        rdefeid = self.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                               '   X from_entity E, X to_entity E '
                               'WHERE RT name "concerne2", E name "CWUser"')[0][0]
        self._set_perms(rdefeid)
        self.commit()
        self.execute('DELETE CWRelation X WHERE X eid %(x)s', {'x': concerne2_rdef_eid}, 'x')
        self.commit()
        self.failUnless('concerne2' in schema['CWUser'].subject_relations())
        self.failIf('concerne2' in schema['Societe2'].subject_relations())
        self.failIf(self.execute('Any X WHERE X concerne2 Y'))
        # schema should be cleaned on delete (after commit)
        self.execute('DELETE CWEType X WHERE X name "Societe2"')
        self.execute('DELETE CWRType X WHERE X name "concerne2"')
        self.failUnless(self.index_exists('Societe2', 'name'))
        self.failUnless(schema.has_entity('Societe2'))
        self.failUnless(schema.has_relation('concerne2'))
        self.commit()
        self.failIf(self.index_exists('Societe2', 'name'))
        self.failIf(schema.has_entity('Societe2'))
        self.failIf(schema.has_entity('concerne2'))
        self.failIf('concerne2' in schema['CWUser'].subject_relations())

    def test_is_instance_of_insertions(self):
        seid = self.execute('INSERT Transition T: T name "subdiv"')[0][0]
        is_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is ET, ET name ETN' % seid)]
        self.assertEquals(is_etypes, ['Transition'])
        instanceof_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is_instance_of ET, ET name ETN' % seid)]
        self.assertEquals(sorted(instanceof_etypes), ['BaseTransition', 'Transition'])
        snames = [name for name, in self.execute('Any N WHERE S is BaseTransition, S name N')]
        self.failIf('subdiv' in snames)
        snames = [name for name, in self.execute('Any N WHERE S is_instance_of BaseTransition, S name N')]
        self.failUnless('subdiv' in snames)


    def test_perms_synchronization_1(self):
        schema = self.repo.schema
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', 'users')))
        self.failUnless(self.execute('Any X, Y WHERE X is CWEType, X name "CWUser", Y is CWGroup, Y name "users"')[0])
        self.execute('DELETE X read_permission Y WHERE X is CWEType, X name "CWUser", Y name "users"')
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', 'users', )))
        self.commit()
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', )))
        self.execute('SET X read_permission Y WHERE X is CWEType, X name "CWUser", Y name "users"')
        self.commit()
        self.assertEquals(schema['CWUser'].get_groups('read'), set(('managers', 'users',)))

    def test_perms_synchronization_2(self):
        schema = self.repo.schema['in_group'].rdefs[('CWUser', 'CWGroup')]
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users', 'guests')))
        self.execute('DELETE X read_permission Y WHERE X relation_type RT, RT name "in_group", Y name "guests"')
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users', 'guests')))
        self.commit()
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users')))
        self.execute('SET X read_permission Y WHERE X relation_type RT, RT name "in_group", Y name "guests"')
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users')))
        self.commit()
        self.assertEquals(schema.get_groups('read'), set(('managers', 'users', 'guests')))

    def test_nonregr_user_edit_itself(self):
        ueid = self.session.user.eid
        groupeids = [eid for eid, in self.execute('CWGroup G WHERE G name in ("managers", "users")')]
        self.execute('DELETE X in_group Y WHERE X eid %s' % ueid)
        self.execute('SET X surname "toto" WHERE X eid %s' % ueid)
        self.execute('SET X in_group Y WHERE X eid %s, Y name "managers"' % ueid)
        self.commit()
        eeid = self.execute('Any X WHERE X is CWEType, X name "CWEType"')[0][0]
        self.execute('DELETE X read_permission Y WHERE X eid %s' % eeid)
        self.execute('SET X final FALSE WHERE X eid %s' % eeid)
        self.execute('SET X read_permission Y WHERE X eid %s, Y eid in (%s, %s)'
                     % (eeid, groupeids[0], groupeids[1]))
        self.commit()
        self.execute('Any X WHERE X is CWEType, X name "CWEType"')

    # schema modification hooks tests #########################################

    def test_uninline_relation(self):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        self.failUnless(self.schema['state_of'].inlined)
        try:
            self.execute('SET X inlined FALSE WHERE X name "state_of"')
            self.failUnless(self.schema['state_of'].inlined)
            self.commit()
            self.failIf(self.schema['state_of'].inlined)
            self.failIf(self.index_exists('State', 'state_of'))
            rset = self.execute('Any X, Y WHERE X state_of Y')
            self.assertEquals(len(rset), 2) # user states
        finally:
            self.execute('SET X inlined TRUE WHERE X name "state_of"')
            self.failIf(self.schema['state_of'].inlined)
            self.commit()
            self.failUnless(self.schema['state_of'].inlined)
            self.failUnless(self.index_exists('State', 'state_of'))
            rset = self.execute('Any X, Y WHERE X state_of Y')
            self.assertEquals(len(rset), 2)

    def test_indexed_change(self):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        try:
            self.execute('SET X indexed FALSE WHERE X relation_type R, R name "name"')
            self.failUnless(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.failUnless(self.index_exists('Workflow', 'name'))
            self.commit()
            self.failIf(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.failIf(self.index_exists('Workflow', 'name'))
        finally:
            self.execute('SET X indexed TRUE WHERE X relation_type R, R name "name"')
            self.failIf(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.failIf(self.index_exists('Workflow', 'name'))
            self.commit()
            self.failUnless(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.failUnless(self.index_exists('Workflow', 'name'))

    def test_unique_change(self):
        self.session.set_pool()
        dbhelper = self.session.pool.source('system').dbhelper
        sqlcursor = self.session.pool['system']
        try:
            self.execute('INSERT CWConstraint X: X cstrtype CT, DEF constrained_by X '
                         'WHERE CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                         'RT name "name", E name "Workflow"')
            self.failIf(self.schema['Workflow'].has_unique_values('name'))
            self.failIf(self.index_exists('Workflow', 'name', unique=True))
            self.commit()
            self.failUnless(self.schema['Workflow'].has_unique_values('name'))
            self.failUnless(self.index_exists('Workflow', 'name', unique=True))
        finally:
            self.execute('DELETE DEF constrained_by X WHERE X cstrtype CT, '
                         'CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                         'RT name "name", E name "Workflow"')
            self.failUnless(self.schema['Workflow'].has_unique_values('name'))
            self.failUnless(self.index_exists('Workflow', 'name', unique=True))
            self.commit()
            self.failIf(self.schema['Workflow'].has_unique_values('name'))
            self.failIf(self.index_exists('Workflow', 'name', unique=True))

    def test_required_change_1(self):
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "title", E name "Bookmark"')
        self.commit()
        # should now be able to add bookmark without title
        self.execute('INSERT Bookmark X: X path "/view"')
        self.commit()

    def test_required_change_2(self):
        self.execute('SET DEF cardinality "11" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "surname", E name "CWUser"')
        self.commit()
        # should not be able anymore to add cwuser without surname
        self.assertRaises(ValidationError, self.create_user, "toto")
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "surname", E name "CWUser"')
        self.commit()


    def test_add_attribute_to_base_class(self):
        attreid = self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval "noname", X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                               'WHERE RT name "messageid", E name "BaseTransition", F name "String"')[0][0]
        assert self.execute('SET X read_permission Y WHERE X eid %(x)s, Y name "managers"',
                     {'x': attreid}, 'x')
        self.commit()
        self.schema.rebuild_infered_relations()
        self.failUnless('Transition' in self.schema['messageid'].subjects())
        self.failUnless('WorkflowTransition' in self.schema['messageid'].subjects())
        self.execute('Any X WHERE X is_instance_of BaseTransition, X messageid "hop"')

    def test_change_fulltextindexed(self):
        target = self.request().create_entity(u'EmailAddress', address=u'rick.roll@dance.com')
        self.commit()
        rset = self.execute('Any X Where X has_text "rick.roll"')
        self.assertIn(target.eid, [item[0] for item in rset])

        assert self.execute('''SET A fulltextindexed False
                        WHERE E is CWEType,
                              E name "EmailAddress",
                              A is CWAttribute,
                              A from_entity E,
                              A relation_type R,
                              R name "address"
                    ''')
        self.commit()
        rset = self.execute('Any X Where X has_text "rick.roll"')
        self.assertNotIn(target.eid, [item[0] for item in rset])

