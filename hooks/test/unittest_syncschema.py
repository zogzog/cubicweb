# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb.server.hooks.syncschema unit and functional tests"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb import ValidationError, Binary
from cubicweb.schema import META_RTYPES
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.devtools.repotest import schema_eids_idx, restore_schema_eids_idx


def tearDownModule(*args):
    del SchemaModificationHooksTC.schema_eids

class SchemaModificationHooksTC(CubicWebTC):

    def setUp(self):
        super(SchemaModificationHooksTC, self).setUp()
        self.repo.set_schema(self.repo.deserialize_schema(), resetvreg=False)
        self.__class__.schema_eids = schema_eids_idx(self.repo.schema)

    def index_exists(self, etype, attr, unique=False):
        self.session.set_cnxset()
        dbhelper = self.repo.system_source.dbhelper
        sqlcursor = self.session.cnxset.cu
        return dbhelper.index_exists(sqlcursor, SQL_PREFIX + etype, SQL_PREFIX + attr, unique=unique)

    def _set_perms(self, eid):
        self.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                     {'x': eid})
        self.execute('SET X add_permission G WHERE X eid %(x)s, G is CWGroup, G name "managers"',
                     {'x': eid})
        self.execute('SET X delete_permission G WHERE X eid %(x)s, G is CWGroup, G name "owners"',
                     {'x': eid})

    def _set_attr_perms(self, eid):
        self.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                     {'x': eid})
        self.execute('SET X update_permission G WHERE X eid %(x)s, G is CWGroup, G name "managers"',
                     {'x': eid})

    def test_base(self):
        schema = self.repo.schema
        self.session.set_cnxset()
        dbhelper = self.repo.system_source.dbhelper
        sqlcursor = self.session.cnxset.cu
        self.assertFalse(schema.has_entity('Societe2'))
        self.assertFalse(schema.has_entity('concerne2'))
        # schema should be update on insertion (after commit)
        eeid = self.execute('INSERT CWEType X: X name "Societe2", X description "", X final FALSE')[0][0]
        self._set_perms(eeid)
        self.execute('INSERT CWRType X: X name "concerne2", X description "", X final FALSE, X symmetric FALSE')
        self.assertFalse(schema.has_entity('Societe2'))
        self.assertFalse(schema.has_entity('concerne2'))
        # have to commit before adding definition relations
        self.commit()
        self.assertTrue(schema.has_entity('Societe2'))
        self.assertTrue(schema.has_relation('concerne2'))
        attreid = self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval %(default)s, '
                               '   X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                               'WHERE RT name "name", E name "Societe2", F name "String"',
                               {'default': Binary.zpickle('noname')})[0][0]
        self._set_attr_perms(attreid)
        concerne2_rdef_eid = self.execute(
            'INSERT CWRelation X: X cardinality "**", X relation_type RT, X from_entity E, X to_entity E '
            'WHERE RT name "concerne2", E name "Societe2"')[0][0]
        self._set_perms(concerne2_rdef_eid)
        self.assertNotIn('name', schema['Societe2'].subject_relations())
        self.assertNotIn('concerne2', schema['Societe2'].subject_relations())
        self.assertFalse(self.index_exists('Societe2', 'name'))
        self.commit()
        self.assertIn('name', schema['Societe2'].subject_relations())
        self.assertIn('concerne2', schema['Societe2'].subject_relations())
        self.assertTrue(self.index_exists('Societe2', 'name'))
        # now we should be able to insert and query Societe2
        s2eid = self.execute('INSERT Societe2 X: X name "logilab"')[0][0]
        self.execute('Societe2 X WHERE X name "logilab"')
        self.execute('SET X concerne2 X WHERE X name "logilab"')
        rset = self.execute('Any X WHERE X concerne2 Y')
        self.assertEqual(rset.rows, [[s2eid]])
        # check that when a relation definition is deleted, existing relations are deleted
        rdefeid = self.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                               '   X from_entity E, X to_entity E '
                               'WHERE RT name "concerne2", E name "CWUser"')[0][0]
        self._set_perms(rdefeid)
        self.commit()
        self.execute('DELETE CWRelation X WHERE X eid %(x)s', {'x': concerne2_rdef_eid})
        self.commit()
        self.assertIn('concerne2', schema['CWUser'].subject_relations())
        self.assertNotIn('concerne2', schema['Societe2'].subject_relations())
        self.assertFalse(self.execute('Any X WHERE X concerne2 Y'))
        # schema should be cleaned on delete (after commit)
        self.execute('DELETE CWEType X WHERE X name "Societe2"')
        self.execute('DELETE CWRType X WHERE X name "concerne2"')
        self.assertTrue(self.index_exists('Societe2', 'name'))
        self.assertTrue(schema.has_entity('Societe2'))
        self.assertTrue(schema.has_relation('concerne2'))
        self.commit()
        self.assertFalse(self.index_exists('Societe2', 'name'))
        self.assertFalse(schema.has_entity('Societe2'))
        self.assertFalse(schema.has_entity('concerne2'))
        self.assertNotIn('concerne2', schema['CWUser'].subject_relations())

    def test_metartype_with_nordefs(self):
        META_RTYPES.add('custom_meta')
        self.execute('INSERT CWRType X: X name "custom_meta", X description "", '
                     'X final FALSE, X symmetric FALSE')
        self.commit()
        eeid = self.execute('INSERT CWEType X: X name "NEWEtype", '
                            'X description "", X final FALSE')[0][0]
        self._set_perms(eeid)
        self.commit()
        META_RTYPES.remove('custom_meta')

    def test_metartype_with_somerdefs(self):
        META_RTYPES.add('custom_meta')
        self.execute('INSERT CWRType X: X name "custom_meta", X description "", '
                     'X final FALSE, X symmetric FALSE')
        self.commit()
        rdefeid = self.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                               '   X from_entity E, X to_entity E '
                               'WHERE RT name "custom_meta", E name "CWUser"')[0][0]
        self._set_perms(rdefeid)
        self.commit()
        eeid = self.execute('INSERT CWEType X: X name "NEWEtype", '
                            'X description "", X final FALSE')[0][0]
        self._set_perms(eeid)
        self.commit()
        META_RTYPES.remove('custom_meta')

    def test_is_instance_of_insertions(self):
        seid = self.execute('INSERT Transition T: T name "subdiv"')[0][0]
        is_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is ET, ET name ETN' % seid)]
        self.assertEqual(is_etypes, ['Transition'])
        instanceof_etypes = [etype for etype, in self.execute('Any ETN WHERE X eid %s, X is_instance_of ET, ET name ETN' % seid)]
        self.assertEqual(sorted(instanceof_etypes), ['BaseTransition', 'Transition'])
        snames = [name for name, in self.execute('Any N WHERE S is BaseTransition, S name N')]
        self.assertNotIn('subdiv', snames)
        snames = [name for name, in self.execute('Any N WHERE S is_instance_of BaseTransition, S name N')]
        self.assertIn('subdiv', snames)


    def test_perms_synchronization_1(self):
        schema = self.repo.schema
        self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers', 'users')))
        self.assertTrue(self.execute('Any X, Y WHERE X is CWEType, X name "CWUser", Y is CWGroup, Y name "users"')[0])
        self.execute('DELETE X read_permission Y WHERE X is CWEType, X name "CWUser", Y name "users"')
        self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers', 'users', )))
        self.commit()
        self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers',)))
        self.execute('SET X read_permission Y WHERE X is CWEType, X name "CWUser", Y name "users"')
        self.commit()
        self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers', 'users',)))

    def test_perms_synchronization_2(self):
        schema = self.repo.schema['in_group'].rdefs[('CWUser', 'CWGroup')]
        self.assertEqual(schema.get_groups('read'), set(('managers', 'users', 'guests')))
        self.execute('DELETE X read_permission Y WHERE X relation_type RT, RT name "in_group", Y name "guests"')
        self.assertEqual(schema.get_groups('read'), set(('managers', 'users', 'guests')))
        self.commit()
        self.assertEqual(schema.get_groups('read'), set(('managers', 'users')))
        self.execute('SET X read_permission Y WHERE X relation_type RT, RT name "in_group", Y name "guests"')
        self.assertEqual(schema.get_groups('read'), set(('managers', 'users')))
        self.commit()
        self.assertEqual(schema.get_groups('read'), set(('managers', 'users', 'guests')))

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
        self.session.set_cnxset()
        dbhelper = self.repo.system_source.dbhelper
        sqlcursor = self.session.cnxset.cu
        self.assertTrue(self.schema['state_of'].inlined)
        try:
            self.execute('SET X inlined FALSE WHERE X name "state_of"')
            self.assertTrue(self.schema['state_of'].inlined)
            self.commit()
            self.assertFalse(self.schema['state_of'].inlined)
            self.assertFalse(self.index_exists('State', 'state_of'))
            rset = self.execute('Any X, Y WHERE X state_of Y')
            self.assertEqual(len(rset), 2) # user states
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self.execute('SET X inlined TRUE WHERE X name "state_of"')
            self.assertFalse(self.schema['state_of'].inlined)
            self.commit()
            self.assertTrue(self.schema['state_of'].inlined)
            self.assertTrue(self.index_exists('State', 'state_of'))
            rset = self.execute('Any X, Y WHERE X state_of Y')
            self.assertEqual(len(rset), 2)

    def test_indexed_change(self):
        self.session.set_cnxset()
        dbhelper = self.repo.system_source.dbhelper
        sqlcursor = self.session.cnxset.cu
        try:
            self.execute('SET X indexed FALSE WHERE X relation_type R, R name "name"')
            self.assertTrue(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.assertTrue(self.index_exists('Workflow', 'name'))
            self.commit()
            self.assertFalse(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.assertFalse(self.index_exists('Workflow', 'name'))
        finally:
            self.execute('SET X indexed TRUE WHERE X relation_type R, R name "name"')
            self.assertFalse(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.assertFalse(self.index_exists('Workflow', 'name'))
            self.commit()
            self.assertTrue(self.schema['name'].rdef('Workflow', 'String').indexed)
            self.assertTrue(self.index_exists('Workflow', 'name'))

    def test_unique_change(self):
        self.session.set_cnxset()
        dbhelper = self.repo.system_source.dbhelper
        sqlcursor = self.session.cnxset.cu
        try:
            eid = self.execute('INSERT CWConstraint X: X cstrtype CT, DEF constrained_by X '
                               'WHERE CT name "UniqueConstraint", DEF relation_type RT, DEF from_entity E,'
                               'RT name "name", E name "Workflow"').rows[0][0]
            self.assertFalse(self.schema['Workflow'].has_unique_values('name'))
            self.assertFalse(self.index_exists('Workflow', 'name', unique=True))
            self.commit()
            self.assertTrue(self.schema['Workflow'].has_unique_values('name'))
            self.assertTrue(self.index_exists('Workflow', 'name', unique=True))
        finally:
            self.execute('DELETE CWConstraint C WHERE C eid %(eid)s', {'eid': eid})
            self.commit()
            self.assertFalse(self.schema['Workflow'].has_unique_values('name'))
            self.assertFalse(self.index_exists('Workflow', 'name', unique=True))

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
        req = self.request()
        self.assertRaises(ValidationError, self.create_user, req, "toto")
        self.rollback()
        self.execute('SET DEF cardinality "?1" '
                     'WHERE DEF relation_type RT, DEF from_entity E,'
                     'RT name "surname", E name "CWUser"')
        self.commit()


    def test_add_attribute_to_base_class(self):
        attreid = self.execute('INSERT CWAttribute X: X cardinality "11", X defaultval %(default)s, '
                               'X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                               'WHERE RT name "messageid", E name "BaseTransition", F name "String"',
                               {'default': Binary.zpickle('noname')})[0][0]
        assert self.execute('SET X read_permission Y WHERE X eid %(x)s, Y name "managers"',
                     {'x': attreid})
        self.commit()
        self.schema.rebuild_infered_relations()
        self.assertIn('Transition', self.schema['messageid'].subjects())
        self.assertIn('WorkflowTransition', self.schema['messageid'].subjects())
        self.execute('Any X WHERE X is_instance_of BaseTransition, X messageid "hop"')

    def test_change_fulltextindexed(self):
        req = self.request()
        target = req.create_entity(u'Email', messageid=u'1234',
                                   subject=u'rick.roll@dance.com')
        self.commit()
        rset = req.execute('Any X WHERE X has_text "rick.roll"')
        self.assertIn(target.eid, [item[0] for item in rset])
        assert req.execute('SET A fulltextindexed FALSE '
                            'WHERE E is CWEType, E name "Email", A is CWAttribute,'
                            'A from_entity E, A relation_type R, R name "subject"')
        self.commit()
        rset = req.execute('Any X WHERE X has_text "rick.roll"')
        self.assertFalse(rset)
        assert req.execute('SET A fulltextindexed TRUE '
                           'WHERE A from_entity E, A relation_type R, '
                           'E name "Email", R name "subject"')
        self.commit()
        rset = req.execute('Any X WHERE X has_text "rick.roll"')
        self.assertIn(target.eid, [item[0] for item in rset])

    def test_change_fulltext_container(self):
        req = self.request()
        target = req.create_entity(u'EmailAddress', address=u'rick.roll@dance.com')
        target.cw_set(reverse_use_email=req.user)
        self.commit()
        rset = req.execute('Any X WHERE X has_text "rick.roll"')
        self.assertIn(req.user.eid, [item[0] for item in rset])
        assert self.execute('SET R fulltext_container NULL '
                            'WHERE R name "use_email"')
        self.commit()
        rset = self.execute('Any X WHERE X has_text "rick.roll"')
        self.assertIn(target.eid, [item[0] for item in rset])
        assert self.execute('SET R fulltext_container "subject" '
                            'WHERE R name "use_email"')
        self.commit()
        rset = req.execute('Any X WHERE X has_text "rick.roll"')
        self.assertIn(req.user.eid, [item[0] for item in rset])

    def test_update_constraint(self):
        rdef = self.schema['Transition'].rdef('type')
        cstr = rdef.constraint_by_type('StaticVocabularyConstraint')
        if not getattr(cstr, 'eid', None):
            self.skipTest('start me alone') # bug in schema reloading, constraint's eid not restored
        self.execute('SET X value %(v)s WHERE X eid %(x)s',
                     {'x': cstr.eid, 'v': u"u'normal', u'auto', u'new'"})
        self.execute('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X '
                     'WHERE CT name %(ct)s, EDEF eid %(x)s',
                     {'ct': 'SizeConstraint', 'value': u'max=10', 'x': rdef.eid})
        self.commit()
        cstr = rdef.constraint_by_type('StaticVocabularyConstraint')
        self.assertEqual(cstr.values, (u'normal', u'auto', u'new'))
        self.execute('INSERT Transition T: T name "hop", T type "new"')

if __name__ == '__main__':
    unittest_main()
