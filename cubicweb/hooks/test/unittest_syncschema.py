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
"""cubicweb.server.hooks.syncschema unit and functional tests"""

from yams.constraints import BoundaryConstraint

from cubicweb import ValidationError, Binary
from cubicweb.schema import META_RTYPES
from cubicweb.devtools import startpgcluster, stoppgcluster, PostgresApptestConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.devtools.repotest import schema_eids_idx


def setUpModule():
    startpgcluster(__file__)


def tearDownModule(*args):
    stoppgcluster(__file__)
    del SchemaModificationHooksTC.schema_eids


class SchemaModificationHooksTC(CubicWebTC):
    configcls = PostgresApptestConfiguration

    def setUp(self):
        super(SchemaModificationHooksTC, self).setUp()
        self.repo.set_schema(self.repo.deserialize_schema(), resetvreg=False)
        self.__class__.schema_eids = schema_eids_idx(self.repo.schema)

    def index_exists(self, cnx, etype, attr, unique=False):
        dbhelper = self.repo.system_source.dbhelper
        sqlcursor = cnx.cnxset.cu
        return dbhelper.index_exists(sqlcursor,
                                     SQL_PREFIX + etype,
                                     SQL_PREFIX + attr,
                                     unique=unique)

    def _set_perms(self, cnx, eid):
        cnx.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                    {'x': eid})
        cnx.execute('SET X add_permission G WHERE X eid %(x)s, G is CWGroup, '
                    'G name "managers"', {'x': eid})
        cnx.execute('SET X delete_permission G WHERE X eid %(x)s, G is CWGroup, '
                    'G name "owners"', {'x': eid})

    def _set_attr_perms(self, cnx, eid):
        cnx.execute('SET X read_permission G WHERE X eid %(x)s, G is CWGroup',
                    {'x': eid})
        cnx.execute('SET X update_permission G WHERE X eid %(x)s, G is CWGroup, G name "managers"',
                    {'x': eid})

    def test_base(self):
        with self.admin_access.repo_cnx() as cnx:
            schema = self.repo.schema
            self.assertFalse(schema.has_entity('Societe2'))
            self.assertFalse(schema.has_entity('concerne2'))
            # schema should be update on insertion (after commit)
            eeid = cnx.execute('INSERT CWEType X: X name "Societe2", '
                               'X description "", X final FALSE')[0][0]
            self._set_perms(cnx, eeid)
            cnx.execute('INSERT CWRType X: X name "concerne2", X description "", '
                        'X final FALSE, X symmetric FALSE')
            self.assertFalse(schema.has_entity('Societe2'))
            self.assertFalse(schema.has_entity('concerne2'))
            # have to commit before adding definition relations
            cnx.commit()
            self.assertTrue(schema.has_entity('Societe2'))
            self.assertTrue(schema.has_relation('concerne2'))
            attreid = cnx.execute('INSERT CWAttribute X: X cardinality "11", '
                                  'X defaultval %(default)s, X indexed TRUE, '
                                  'X relation_type RT, X from_entity E, X to_entity F '
                                  'WHERE RT name "name", E name "Societe2", '
                                  'F name "String"',
                                   {'default': Binary.zpickle('noname')})[0][0]
            self._set_attr_perms(cnx, attreid)
            concerne2_rdef_eid = cnx.execute(
                'INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                'X from_entity E, X to_entity E '
                'WHERE RT name "concerne2", E name "Societe2"')[0][0]
            self._set_perms(cnx, concerne2_rdef_eid)
            self.assertNotIn('name', schema['Societe2'].subject_relations())
            self.assertNotIn('concerne2', schema['Societe2'].subject_relations())
            self.assertFalse(self.index_exists(cnx, 'Societe2', 'name'))
            cnx.commit()
            self.assertIn('name', schema['Societe2'].subject_relations())
            self.assertIn('concerne2', schema['Societe2'].subject_relations())
            self.assertTrue(self.index_exists(cnx, 'Societe2', 'name'))
            # now we should be able to insert and query Societe2
            s2eid = cnx.execute('INSERT Societe2 X: X name "logilab"')[0][0]
            cnx.execute('Societe2 X WHERE X name "logilab"')
            cnx.execute('SET X concerne2 X WHERE X name "logilab"')
            rset = cnx.execute('Any X WHERE X concerne2 Y')
            self.assertEqual(rset.rows, [[s2eid]])
            # check that when a relation definition is deleted, existing relations are deleted
            rdefeid = cnx.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                                  '   X from_entity E, X to_entity E '
                                  'WHERE RT name "concerne2", E name "CWUser"')[0][0]
            self._set_perms(cnx, rdefeid)
            cnx.commit()
            cnx.execute('DELETE CWRelation X WHERE X eid %(x)s', {'x': concerne2_rdef_eid})
            cnx.commit()
            self.assertIn('concerne2', schema['CWUser'].subject_relations())
            self.assertNotIn('concerne2', schema['Societe2'].subject_relations())
            self.assertFalse(cnx.execute('Any X WHERE X concerne2 Y'))
            # schema should be cleaned on delete (after commit)
            cnx.execute('DELETE CWEType X WHERE X name "Societe2"')
            cnx.execute('DELETE CWRType X WHERE X name "concerne2"')
            self.assertTrue(self.index_exists(cnx, 'Societe2', 'name'))
            self.assertTrue(schema.has_entity('Societe2'))
            self.assertTrue(schema.has_relation('concerne2'))
            cnx.commit()
            self.assertFalse(self.index_exists(cnx, 'Societe2', 'name'))
            self.assertFalse(schema.has_entity('Societe2'))
            self.assertFalse(schema.has_entity('concerne2'))
            self.assertNotIn('concerne2', schema['CWUser'].subject_relations())

    def test_metartype_with_nordefs(self):
        with self.admin_access.repo_cnx() as cnx:
            META_RTYPES.add('custom_meta')
            cnx.execute('INSERT CWRType X: X name "custom_meta", X description "", '
                        'X final FALSE, X symmetric FALSE')
            cnx.commit()
            eeid = cnx.execute('INSERT CWEType X: X name "NEWEtype", '
                               'X description "", X final FALSE')[0][0]
            self._set_perms(cnx, eeid)
            cnx.commit()
            META_RTYPES.remove('custom_meta')

    def test_metartype_with_somerdefs(self):
        with self.admin_access.repo_cnx() as cnx:
            META_RTYPES.add('custom_meta')
            cnx.execute('INSERT CWRType X: X name "custom_meta", X description "", '
                        'X final FALSE, X symmetric FALSE')
            cnx.commit()
            rdefeid = cnx.execute('INSERT CWRelation X: X cardinality "**", X relation_type RT, '
                                  '   X from_entity E, X to_entity E '
                                  'WHERE RT name "custom_meta", E name "CWUser"')[0][0]
            self._set_perms(cnx, rdefeid)
            cnx.commit()
            eeid = cnx.execute('INSERT CWEType X: X name "NEWEtype", '
                               'X description "", X final FALSE')[0][0]
            self._set_perms(cnx, eeid)
            cnx.commit()
            META_RTYPES.remove('custom_meta')

    def test_is_instance_of_insertions(self):
        with self.admin_access.repo_cnx() as cnx:
            seid = cnx.execute('INSERT Transition T: T name "subdiv"')[0][0]
            is_etypes = [etype for etype, in cnx.execute('Any ETN WHERE X eid %s, '
                                                         'X is ET, ET name ETN' % seid)]
            self.assertEqual(is_etypes, ['Transition'])
            instanceof_etypes = [etype
                                 for etype, in cnx.execute('Any ETN WHERE X eid %s, '
                                                           'X is_instance_of ET, ET name ETN'
                                                           % seid)]
            self.assertEqual(sorted(instanceof_etypes), ['BaseTransition', 'Transition'])
            snames = [name for name, in cnx.execute('Any N WHERE S is BaseTransition, S name N')]
            self.assertNotIn('subdiv', snames)
            snames = [name for name, in cnx.execute('Any N WHERE S is_instance_of BaseTransition, '
                                                    'S name N')]
            self.assertIn('subdiv', snames)

    def test_perms_synchronization_1(self):
        with self.admin_access.repo_cnx() as cnx:
            schema = self.repo.schema
            self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers', 'users')))
            self.assertTrue(cnx.execute('Any X, Y WHERE X is CWEType, X name "CWUser", '
                                        'Y is CWGroup, Y name "users"')[0])
            cnx.execute('DELETE X read_permission Y '
                        'WHERE X is CWEType, X name "CWUser", Y name "users"')
            self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers', 'users', )))
            cnx.commit()
            self.assertEqual(schema['CWUser'].get_groups('read'), set(('managers',)))
            cnx.execute('SET X read_permission Y WHERE X is CWEType, '
                        'X name "CWUser", Y name "users"')
            cnx.commit()
            self.assertEqual(schema['CWUser'].get_groups('read'),
                             set(('managers', 'users',)))

    def test_perms_synchronization_2(self):
        with self.admin_access.repo_cnx() as cnx:
            schema = self.repo.schema['in_group'].rdefs[('CWUser', 'CWGroup')]
            self.assertEqual(schema.get_groups('read'),
                             set(('managers', 'users', 'guests')))
            cnx.execute('DELETE X read_permission Y WHERE X relation_type RT, '
                        'RT name "in_group", Y name "guests"')
            self.assertEqual(schema.get_groups('read'),
                             set(('managers', 'users', 'guests')))
            cnx.commit()
            self.assertEqual(schema.get_groups('read'),
                             set(('managers', 'users')))
            cnx.execute('SET X read_permission Y WHERE X relation_type RT, '
                        'RT name "in_group", Y name "guests"')
            self.assertEqual(schema.get_groups('read'),
                             set(('managers', 'users')))
            cnx.commit()
            self.assertEqual(schema.get_groups('read'),
                             set(('managers', 'users', 'guests')))

    def test_nonregr_user_edit_itself(self):
        with self.admin_access.repo_cnx() as cnx:
            ueid = cnx.user.eid
            groupeids = [eid for eid, in cnx.execute('CWGroup G WHERE G name '
                                                     'in ("managers", "users")')]
            cnx.execute('DELETE X in_group Y WHERE X eid %s' % ueid)
            cnx.execute('SET X surname "toto" WHERE X eid %s' % ueid)
            cnx.execute('SET X in_group Y WHERE X eid %s, Y name "managers"' % ueid)
            cnx.commit()
            eeid = cnx.execute('Any X WHERE X is CWEType, X name "CWEType"')[0][0]
            cnx.execute('DELETE X read_permission Y WHERE X eid %s' % eeid)
            cnx.execute('SET X final FALSE WHERE X eid %s' % eeid)
            cnx.execute('SET X read_permission Y WHERE X eid %s, Y eid in (%s, %s)'
                        % (eeid, groupeids[0], groupeids[1]))
            cnx.commit()
            cnx.execute('Any X WHERE X is CWEType, X name "CWEType"')

    # schema modification hooks tests #########################################

    def test_uninline_relation(self):
        with self.admin_access.repo_cnx() as cnx:
            try:
                self.assertTrue(self.schema['state_of'].inlined)
                cnx.execute('SET X inlined FALSE WHERE X name "state_of"')
                self.assertTrue(self.schema['state_of'].inlined)
                cnx.commit()
                self.assertFalse(self.schema['state_of'].inlined)
                self.assertFalse(self.index_exists(cnx, 'State', 'state_of'))
                rset = cnx.execute('Any X, Y WHERE X state_of Y')
                self.assertEqual(len(rset), 2)  # user states
            finally:
                cnx.execute('SET X inlined TRUE WHERE X name "state_of"')
                self.assertFalse(self.schema['state_of'].inlined)
                cnx.commit()
                self.assertTrue(self.schema['state_of'].inlined)
                self.assertTrue(self.index_exists(cnx, 'State', 'state_of'))
                rset = cnx.execute('Any X, Y WHERE X state_of Y')
                self.assertEqual(len(rset), 2)

    def test_indexed_change(self):
        with self.admin_access.repo_cnx() as cnx:
            try:
                cnx.execute('SET X indexed FALSE WHERE X relation_type R, R name "name"')
                self.assertTrue(self.schema['name'].rdef('Workflow', 'String').indexed)
                self.assertTrue(self.index_exists(cnx, 'Workflow', 'name'))
                cnx.commit()
                self.assertFalse(self.schema['name'].rdef('Workflow', 'String').indexed)
                self.assertFalse(self.index_exists(cnx, 'Workflow', 'name'))
            finally:
                cnx.execute('SET X indexed TRUE WHERE X relation_type R, R name "name"')
                self.assertFalse(self.schema['name'].rdef('Workflow', 'String').indexed)
                self.assertFalse(self.index_exists(cnx, 'Workflow', 'name'))
                cnx.commit()
                self.assertTrue(self.schema['name'].rdef('Workflow', 'String').indexed)
                self.assertTrue(self.index_exists(cnx, 'Workflow', 'name'))

    def test_unique_change(self):
        with self.admin_access.repo_cnx() as cnx:
            try:
                eid = cnx.execute('INSERT CWConstraint X: X cstrtype CT, X value "{}", '
                                  '                       DEF constrained_by X '
                                  'WHERE CT name "UniqueConstraint", DEF relation_type RT, '
                                  'DEF from_entity E, RT name "name", '
                                  'E name "Workflow"').rows[0][0]
                self.assertFalse(self.schema['Workflow'].has_unique_values('name'))
                self.assertFalse(self.index_exists(cnx, 'Workflow', 'name', unique=True))
                cnx.commit()
                self.assertTrue(self.schema['Workflow'].has_unique_values('name'))
                self.assertTrue(self.index_exists(cnx, 'Workflow', 'name', unique=True))
            finally:
                cnx.execute('DELETE CWConstraint C WHERE C eid %(eid)s', {'eid': eid})
                cnx.commit()
                self.assertFalse(self.schema['Workflow'].has_unique_values('name'))
                self.assertFalse(self.index_exists(cnx, 'Workflow', 'name', unique=True))

    def test_required_change_1(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('SET DEF cardinality "?1" '
                        'WHERE DEF relation_type RT, DEF from_entity E,'
                        'RT name "title", E name "Bookmark"')
            cnx.commit()
            # should now be able to add bookmark without title
            cnx.execute('INSERT Bookmark X: X path "/view"')
            cnx.commit()

    def test_required_change_2(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('SET DEF cardinality "11" '
                        'WHERE DEF relation_type RT, DEF from_entity E,'
                        'RT name "surname", E name "CWUser"')
            cnx.execute('SET U surname "Doe" WHERE U surname NULL')
            cnx.commit()
            # should not be able anymore to add cwuser without surname
            self.assertRaises(ValidationError, self.create_user, cnx, "toto")
            cnx.rollback()
            cnx.execute('SET DEF cardinality "?1" '
                        'WHERE DEF relation_type RT, DEF from_entity E,'
                        'RT name "surname", E name "CWUser"')
            cnx.commit()

    def test_add_attribute_to_base_class(self):
        with self.admin_access.repo_cnx() as cnx:
            attreid = cnx.execute(
                'INSERT CWAttribute X: X cardinality "11", X defaultval %(default)s, '
                'X indexed TRUE, X relation_type RT, X from_entity E, X to_entity F '
                'WHERE RT name "messageid", E name "BaseTransition", F name "String"',
                {'default': Binary.zpickle('noname')})[0][0]
            assert cnx.execute('SET X read_permission Y WHERE X eid %(x)s, Y name "managers"',
                               {'x': attreid})
            cnx.commit()
            self.schema.rebuild_infered_relations()
            self.assertIn('Transition', self.schema['messageid'].subjects())
            self.assertIn('WorkflowTransition', self.schema['messageid'].subjects())
            cnx.execute('Any X WHERE X is_instance_of BaseTransition, X messageid "hop"')

    def test_change_fulltextindexed(self):
        with self.admin_access.repo_cnx() as cnx:
            target = cnx.create_entity(u'Email', messageid=u'1234',
                                       subject=u'rick.roll@dance.com')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text "rick.roll"')
            self.assertIn(target.eid, [item[0] for item in rset])
            assert cnx.execute('SET A fulltextindexed FALSE '
                               'WHERE E is CWEType, E name "Email", A is CWAttribute,'
                               'A from_entity E, A relation_type R, R name "subject"')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text "rick.roll"')
            self.assertFalse(rset)
            assert cnx.execute('SET A fulltextindexed TRUE '
                               'WHERE A from_entity E, A relation_type R, '
                               'E name "Email", R name "subject"')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text "rick.roll"')
            self.assertIn(target.eid, [item[0] for item in rset])

    def test_change_fulltext_container(self):
        with self.admin_access.repo_cnx() as cnx:
            target = cnx.create_entity(u'EmailAddress', address=u'rick.roll@dance.com')
            target.cw_set(reverse_use_email=cnx.user)
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text "rick.roll"')
            self.assertIn(cnx.user.eid, [item[0] for item in rset])
            assert cnx.execute('SET R fulltext_container NULL '
                               'WHERE R name "use_email"')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text "rick.roll"')
            self.assertIn(target.eid, [item[0] for item in rset])
            assert cnx.execute('SET R fulltext_container "subject" '
                               'WHERE R name "use_email"')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X has_text "rick.roll"')
            self.assertIn(cnx.user.eid, [item[0] for item in rset])

    def test_update_constraint(self):
        with self.admin_access.repo_cnx() as cnx:
            rdef = self.schema['Transition'].rdef('type')
            cstr = rdef.constraint_by_type('StaticVocabularyConstraint')
            cnx.execute('SET X value %(v)s WHERE X eid %(x)s',
                        {'x': cstr.eid, 'v': u"u'normal', u'auto', u'new'"})
            cnx.execute('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, '
                        'EDEF constrained_by X WHERE CT name %(ct)s, EDEF eid %(x)s',
                        {'ct': 'SizeConstraint', 'value': u'max=10', 'x': rdef.eid})
            cnx.commit()
            cstr = rdef.constraint_by_type('StaticVocabularyConstraint')
            self.assertEqual(cstr.values, (u'normal', u'auto', u'new'))
            cnx.execute('INSERT Transition T: T name "hop", T type "new"')

    def test_add_constraint(self):
        with self.admin_access.repo_cnx() as cnx:
            rdef = self.schema['EmailPart'].rdef('ordernum')
            cstr = BoundaryConstraint('>=', 0)
            cnx.execute('INSERT CWConstraint X: X value %(v)s, X cstrtype CT, '
                        'EDEF constrained_by X WHERE CT name %(ct)s, EDEF eid %(x)s',
                        {'ct': cstr.__class__.__name__, 'v': cstr.serialize(), 'x': rdef.eid})
            cnx.commit()
            cstr2 = rdef.constraint_by_type('BoundaryConstraint')
            self.assertEqual(cstr, cstr2)
            cstr3 = BoundaryConstraint('<=', 1000)
            cnx.execute('INSERT CWConstraint X: X value %(v)s, X cstrtype CT, '
                        'EDEF constrained_by X WHERE CT name %(ct)s, EDEF eid %(x)s',
                        {'ct': cstr3.__class__.__name__, 'v': cstr3.serialize(), 'x': rdef.eid})
            cnx.commit()
            # Do not use assertCountEqual as it does "strange" equality
            # comparison on Python 2.
            self.assertEqual(set(rdef.constraints), set([cstr, cstr3]))

    def test_eschema_composite_properties(self):
        with self.admin_access.repo_cnx() as cnx:
            part_eschema = self.schema['EmailPart']
            email_eschema = self.schema['Email']
            parts_rdef = email_eschema.rdef('parts')
            self.assertEqual(part_eschema.composite_rdef_roles, [])
            self.assertEqual(part_eschema.is_composite, False)
            self.assertEqual(email_eschema.composite_rdef_roles,
                             [(parts_rdef, 'subject')])
            self.assertEqual(email_eschema.is_composite, True)
            cnx.execute('DELETE CWRType X WHERE X name "parts"')
            cnx.commit()
            self.assertEqual(part_eschema.composite_rdef_roles, [])
            self.assertEqual(part_eschema.is_composite, False)
            self.assertEqual(email_eschema.composite_rdef_roles, [])
            self.assertEqual(email_eschema.is_composite, False)


if __name__ == '__main__':
    import unittest
    unittest.main()
