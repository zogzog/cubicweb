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
"""unit tests for module cubicweb.server.migractions"""

from datetime import date
from os.path import join

from logilab.common.testlib import TestCase, unittest_main, Tags, tag

from yams.constraints import UniqueConstraint

from cubicweb import ConfigurationError, ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.schema import CubicWebSchemaLoader
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.migractions import *

import cubicweb.devtools

migrschema = None
def tearDownModule(*args):
    global migrschema
    del migrschema
    if hasattr(MigrationCommandsTC, 'origschema'):
        del MigrationCommandsTC.origschema

class MigrationCommandsTC(CubicWebTC):

    configcls = cubicweb.devtools.TestServerConfiguration

    tags = CubicWebTC.tags | Tags(('server', 'migration', 'migractions'))

    @classmethod
    def _init_repo(cls):
        super(MigrationCommandsTC, cls)._init_repo()
        # we have to read schema from the database to get eid for schema entities
        cls.repo.set_schema(cls.repo.deserialize_schema(), resetvreg=False)
        # hack to read the schema from data/migrschema
        config = cls.config
        config.appid = join('data', 'migratedapp')
        config._apphome = cls.datapath('migratedapp')
        global migrschema
        migrschema = config.load_schema()
        config.appid = 'data'
        config._apphome = cls.datadir
        assert 'Folder' in migrschema

    def setUp(self):
        CubicWebTC.setUp(self)
        self.mh = ServerMigrationHelper(self.repo.config, migrschema,
                                        repo=self.repo, cnx=self.cnx,
                                        interactive=False)
        assert self.cnx is self.mh._cnx
        assert self.session is self.mh.session, (self.session.id, self.mh.session.id)

    def tearDown(self):
        CubicWebTC.tearDown(self)
        self.repo.vreg['etypes'].clear_caches()

    def test_add_attribute_int(self):
        self.assertFalse('whatever' in self.schema)
        self.session.create_entity('Note')
        self.session.commit(free_cnxset=False)
        orderdict = dict(self.mh.rqlexec('Any RTN, O WHERE X name "Note", RDEF from_entity X, '
                                         'RDEF relation_type RT, RDEF ordernum O, RT name RTN'))
        self.mh.cmd_add_attribute('Note', 'whatever')
        self.assertTrue('whatever' in self.schema)
        self.assertEqual(self.schema['whatever'].subjects(), ('Note',))
        self.assertEqual(self.schema['whatever'].objects(), ('Int',))
        self.assertEqual(self.schema['Note'].default('whatever'), 2)
        # test default value set on existing entities
        note = self.session.execute('Note X').get_entity(0, 0)
        self.assertEqual(note.whatever, 2)
        # test default value set for next entities
        self.assertEqual(self.session.create_entity('Note').whatever, 2)
        # test attribute order
        orderdict2 = dict(self.mh.rqlexec('Any RTN, O WHERE X name "Note", RDEF from_entity X, '
                                          'RDEF relation_type RT, RDEF ordernum O, RT name RTN'))
        whateverorder = migrschema['whatever'].rdef('Note', 'Int').order
        for k, v in orderdict.iteritems():
            if v >= whateverorder:
                orderdict[k] = v+1
        orderdict['whatever'] = whateverorder
        self.assertDictEqual(orderdict, orderdict2)
        #self.assertEqual([r.type for r in self.schema['Note'].ordered_relations()],
        #                  ['modification_date', 'creation_date', 'owned_by',
        #                   'eid', 'ecrit_par', 'inline1', 'date', 'type',
        #                   'whatever', 'date', 'in_basket'])
        # NB: commit instead of rollback make following test fail with py2.5
        #     this sounds like a pysqlite/2.5 bug (the same eid is affected to
        #     two different entities)
        self.mh.rollback()

    def test_add_attribute_varchar(self):
        self.assertFalse('whatever' in self.schema)
        self.session.create_entity('Note')
        self.session.commit(free_cnxset=False)
        self.assertFalse('shortpara' in self.schema)
        self.mh.cmd_add_attribute('Note', 'shortpara')
        self.assertTrue('shortpara' in self.schema)
        self.assertEqual(self.schema['shortpara'].subjects(), ('Note', ))
        self.assertEqual(self.schema['shortpara'].objects(), ('String', ))
        # test created column is actually a varchar(64)
        notesql = self.mh.sqlexec("SELECT sql FROM sqlite_master WHERE type='table' and name='%sNote'" % SQL_PREFIX)[0][0]
        fields = dict(x.strip().split()[:2] for x in notesql.split('(', 1)[1].rsplit(')', 1)[0].split(','))
        self.assertEqual(fields['%sshortpara' % SQL_PREFIX], 'varchar(64)')
        # test default value set on existing entities
        self.assertEqual(self.session.execute('Note X').get_entity(0, 0).shortpara, 'hop')
        # test default value set for next entities
        self.assertEqual(self.session.create_entity('Note').shortpara, 'hop')
        self.mh.rollback()

    def test_add_datetime_with_default_value_attribute(self):
        self.assertFalse('mydate' in self.schema)
        self.assertFalse('shortpara' in self.schema)
        self.mh.cmd_add_attribute('Note', 'mydate')
        self.assertTrue('mydate' in self.schema)
        self.assertEqual(self.schema['mydate'].subjects(), ('Note', ))
        self.assertEqual(self.schema['mydate'].objects(), ('Date', ))
        testdate = date(2005, 12, 13)
        eid1 = self.mh.rqlexec('INSERT Note N')[0][0]
        eid2 = self.mh.rqlexec('INSERT Note N: N mydate %(mydate)s', {'mydate' : testdate})[0][0]
        d1 = self.mh.rqlexec('Any D WHERE X eid %(x)s, X mydate D', {'x': eid1})[0][0]
        d2 = self.mh.rqlexec('Any D WHERE X eid %(x)s, X mydate D', {'x': eid2})[0][0]
        self.assertEqual(d1, date.today())
        self.assertEqual(d2, testdate)
        self.mh.rollback()

    def test_drop_chosen_constraints_ctxmanager(self):
        with self.mh.cmd_dropped_constraints('Note', 'unique_id', UniqueConstraint):
            self.mh.cmd_add_attribute('Note', 'unique_id')
            # make sure the maxsize constraint is not dropped
            self.assertRaises(ValidationError,
                              self.mh.rqlexec,
                              'INSERT Note N: N unique_id "xyz"')
            self.mh.rollback()
            # make sure the unique constraint is dropped
            self.mh.rqlexec('INSERT Note N: N unique_id "x"')
            self.mh.rqlexec('INSERT Note N: N unique_id "x"')
            self.mh.rqlexec('DELETE Note N')
        self.mh.rollback()

    def test_drop_required_ctxmanager(self):
        with self.mh.cmd_dropped_constraints('Note', 'unique_id', cstrtype=None,
                                             droprequired=True):
            self.mh.cmd_add_attribute('Note', 'unique_id')
            self.mh.rqlexec('INSERT Note N')
        # make sure the required=True was restored
        self.assertRaises(ValidationError, self.mh.rqlexec, 'INSERT Note N')
        self.mh.rollback()

    def test_rename_attribute(self):
        self.assertFalse('civility' in self.schema)
        eid1 = self.mh.rqlexec('INSERT Personne X: X nom "lui", X sexe "M"')[0][0]
        eid2 = self.mh.rqlexec('INSERT Personne X: X nom "l\'autre", X sexe NULL')[0][0]
        self.mh.cmd_rename_attribute('Personne', 'sexe', 'civility')
        self.assertFalse('sexe' in self.schema)
        self.assertTrue('civility' in self.schema)
        # test data has been backported
        c1 = self.mh.rqlexec('Any C WHERE X eid %s, X civility C' % eid1)[0][0]
        self.assertEqual(c1, 'M')
        c2 = self.mh.rqlexec('Any C WHERE X eid %s, X civility C' % eid2)[0][0]
        self.assertEqual(c2, None)


    def test_workflow_actions(self):
        wf = self.mh.cmd_add_workflow(u'foo', ('Personne', 'Email'),
                                      ensure_workflowable=False)
        for etype in ('Personne', 'Email'):
            s1 = self.mh.rqlexec('Any N WHERE WF workflow_of ET, ET name "%s", WF name N' %
                                 etype)[0][0]
            self.assertEqual(s1, "foo")
            s1 = self.mh.rqlexec('Any N WHERE ET default_workflow WF, ET name "%s", WF name N' %
                                 etype)[0][0]
            self.assertEqual(s1, "foo")

    def test_add_entity_type(self):
        self.assertFalse('Folder2' in self.schema)
        self.assertFalse('filed_under2' in self.schema)
        self.mh.cmd_add_entity_type('Folder2')
        self.assertTrue('Folder2' in self.schema)
        self.assertTrue('Old' in self.schema)
        self.assertTrue(self.session.execute('CWEType X WHERE X name "Folder2"'))
        self.assertTrue('filed_under2' in self.schema)
        self.assertTrue(self.session.execute('CWRType X WHERE X name "filed_under2"'))
        self.schema.rebuild_infered_relations()
        self.assertEqual(sorted(str(rs) for rs in self.schema['Folder2'].subject_relations()),
                          ['created_by', 'creation_date', 'cw_source', 'cwuri',
                           'description', 'description_format',
                           'eid',
                           'filed_under2', 'has_text',
                           'identity', 'in_basket', 'is', 'is_instance_of',
                           'modification_date', 'name', 'owned_by'])
        self.assertEqual([str(rs) for rs in self.schema['Folder2'].object_relations()],
                          ['filed_under2', 'identity'])
        # Old will be missing as it has been renamed into 'New' in the migrated
        # schema while New hasn't been added here.
        self.assertEqual(sorted(str(e) for e in self.schema['filed_under2'].subjects()),
                         sorted(str(e) for e in self.schema.entities() if not e.final and e != 'Old'))
        self.assertEqual(self.schema['filed_under2'].objects(), ('Folder2',))
        eschema = self.schema.eschema('Folder2')
        for cstr in eschema.rdef('name').constraints:
            self.assertTrue(hasattr(cstr, 'eid'))

    def test_add_drop_entity_type(self):
        self.mh.cmd_add_entity_type('Folder2')
        wf = self.mh.cmd_add_workflow(u'folder2 wf', 'Folder2',
                                      ensure_workflowable=False)
        todo = wf.add_state(u'todo', initial=True)
        done = wf.add_state(u'done')
        wf.add_transition(u'redoit', done, todo)
        wf.add_transition(u'markasdone', todo, done)
        self.session.commit(free_cnxset=False)
        eschema = self.schema.eschema('Folder2')
        self.mh.cmd_drop_entity_type('Folder2')
        self.assertFalse('Folder2' in self.schema)
        self.assertFalse(self.session.execute('CWEType X WHERE X name "Folder2"'))
        # test automatic workflow deletion
        self.assertFalse(self.session.execute('Workflow X WHERE NOT X workflow_of ET'))
        self.assertFalse(self.session.execute('State X WHERE NOT X state_of WF'))
        self.assertFalse(self.session.execute('Transition X WHERE NOT X transition_of WF'))

    def test_rename_entity_type(self):
        entity = self.mh.create_entity('Old', name=u'old')
        self.repo.type_and_source_from_eid(entity.eid)
        self.mh.cmd_rename_entity_type('Old', 'New')
        self.mh.cmd_rename_attribute('New', 'name', 'new_name')

    def test_add_drop_relation_type(self):
        self.mh.cmd_add_entity_type('Folder2', auto=False)
        self.mh.cmd_add_relation_type('filed_under2')
        self.schema.rebuild_infered_relations()
        self.assertTrue('filed_under2' in self.schema)
        # Old will be missing as it has been renamed into 'New' in the migrated
        # schema while New hasn't been added here.
        self.assertEqual(sorted(str(e) for e in self.schema['filed_under2'].subjects()),
                         sorted(str(e) for e in self.schema.entities()
                                if not e.final and e != 'Old'))
        self.assertEqual(self.schema['filed_under2'].objects(), ('Folder2',))
        self.mh.cmd_drop_relation_type('filed_under2')
        self.assertFalse('filed_under2' in self.schema)

    def test_add_relation_definition_nortype(self):
        self.mh.cmd_add_relation_definition('Personne', 'concerne2', 'Affaire')
        self.assertEqual(self.schema['concerne2'].subjects(),
                          ('Personne',))
        self.assertEqual(self.schema['concerne2'].objects(),
                          ('Affaire', ))
        self.assertEqual(self.schema['concerne2'].rdef('Personne', 'Affaire').cardinality,
                          '1*')
        self.mh.cmd_add_relation_definition('Personne', 'concerne2', 'Note')
        self.assertEqual(sorted(self.schema['concerne2'].objects()), ['Affaire', 'Note'])
        self.mh.create_entity('Personne', nom=u'tot')
        self.mh.create_entity('Affaire')
        self.mh.rqlexec('SET X concerne2 Y WHERE X is Personne, Y is Affaire')
        self.session.commit(free_cnxset=False)
        self.mh.cmd_drop_relation_definition('Personne', 'concerne2', 'Affaire')
        self.assertTrue('concerne2' in self.schema)
        self.mh.cmd_drop_relation_definition('Personne', 'concerne2', 'Note')
        self.assertFalse('concerne2' in self.schema)

    def test_drop_relation_definition_existant_rtype(self):
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].subjects()),
                          ['Affaire', 'Personne'])
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Division', 'Note', 'Societe', 'SubDivision'])
        self.mh.cmd_drop_relation_definition('Personne', 'concerne', 'Affaire')
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].subjects()),
                          ['Affaire'])
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Division', 'Note', 'Societe', 'SubDivision'])
        self.mh.cmd_add_relation_definition('Personne', 'concerne', 'Affaire')
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].subjects()),
                          ['Affaire', 'Personne'])
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Division', 'Note', 'Societe', 'SubDivision'])
        # trick: overwrite self.maxeid to avoid deletion of just reintroduced types
        self.maxeid = self.session.execute('Any MAX(X)')[0][0]

    def test_drop_relation_definition_with_specialization(self):
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].subjects()),
                          ['Affaire', 'Personne'])
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Division', 'Note', 'Societe', 'SubDivision'])
        self.mh.cmd_drop_relation_definition('Affaire', 'concerne', 'Societe')
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].subjects()),
                          ['Affaire', 'Personne'])
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Division', 'Note', 'SubDivision'])
        self.schema.rebuild_infered_relations() # need to be explicitly called once everything is in place
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Note'])
        self.mh.cmd_add_relation_definition('Affaire', 'concerne', 'Societe')
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].subjects()),
                          ['Affaire', 'Personne'])
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Note', 'Societe'])
        self.schema.rebuild_infered_relations() # need to be explicitly called once everything is in place
        self.assertEqual(sorted(str(e) for e in self.schema['concerne'].objects()),
                          ['Affaire', 'Division', 'Note', 'Societe', 'SubDivision'])
        # trick: overwrite self.maxeid to avoid deletion of just reintroduced types
        self.maxeid = self.session.execute('Any MAX(X)')[0][0]

    def test_rename_relation(self):
        self.skipTest('implement me')

    def test_change_relation_props_non_final(self):
        rschema = self.schema['concerne']
        card = rschema.rdef('Affaire', 'Societe').cardinality
        self.assertEqual(card, '**')
        try:
            self.mh.cmd_change_relation_props('Affaire', 'concerne', 'Societe',
                                              cardinality='?*')
            card = rschema.rdef('Affaire', 'Societe').cardinality
            self.assertEqual(card, '?*')
        finally:
            self.mh.cmd_change_relation_props('Affaire', 'concerne', 'Societe',
                                              cardinality='**')

    def test_change_relation_props_final(self):
        rschema = self.schema['adel']
        card = rschema.rdef('Personne', 'String').fulltextindexed
        self.assertEqual(card, False)
        try:
            self.mh.cmd_change_relation_props('Personne', 'adel', 'String',
                                              fulltextindexed=True)
            card = rschema.rdef('Personne', 'String').fulltextindexed
            self.assertEqual(card, True)
        finally:
            self.mh.cmd_change_relation_props('Personne', 'adel', 'String',
                                              fulltextindexed=False)

    @tag('longrun')
    def test_sync_schema_props_perms(self):
        cursor = self.mh.session
        cursor.set_cnxset()
        nbrqlexpr_start = cursor.execute('Any COUNT(X) WHERE X is RQLExpression')[0][0]
        migrschema['titre'].rdefs[('Personne', 'String')].order = 7
        migrschema['adel'].rdefs[('Personne', 'String')].order = 6
        migrschema['ass'].rdefs[('Personne', 'String')].order = 5
        migrschema['Personne'].description = 'blabla bla'
        migrschema['titre'].description = 'usually a title'
        migrschema['titre'].rdefs[('Personne', 'String')].description = 'title for this person'
        delete_concerne_rqlexpr = self._rrqlexpr_rset('delete', 'concerne')
        add_concerne_rqlexpr = self._rrqlexpr_rset('add', 'concerne')

        self.mh.cmd_sync_schema_props_perms(commit=False)

        self.assertEqual(cursor.execute('Any D WHERE X name "Personne", X description D')[0][0],
                          'blabla bla')
        self.assertEqual(cursor.execute('Any D WHERE X name "titre", X description D')[0][0],
                          'usually a title')
        self.assertEqual(cursor.execute('Any D WHERE X relation_type RT, RT name "titre",'
                                         'X from_entity FE, FE name "Personne",'
                                         'X description D')[0][0],
                          'title for this person')
        rinorder = [n for n, in cursor.execute(
            'Any N ORDERBY O,N WHERE X is CWAttribute, X relation_type RT, RT name N,'
            'X from_entity FE, FE name "Personne",'
            'X ordernum O')]
        expected = [u'nom', u'prenom', u'sexe', u'promo', u'ass', u'adel', u'titre',
                    u'web', u'tel', u'fax', u'datenaiss', u'test', u'tzdatenaiss',
                    u'description', u'firstname',
                    u'creation_date', u'cwuri', u'modification_date']
        self.assertEqual(expected, rinorder)

        # test permissions synchronization ####################################
        # new rql expr to add note entity
        eexpr = self._erqlexpr_entity('add', 'Note')
        self.assertEqual(eexpr.expression,
                          'X ecrit_part PE, U in_group G, '
                          'PE require_permission P, P name "add_note", P require_group G')
        self.assertEqual([et.name for et in eexpr.reverse_add_permission], ['Note'])
        self.assertEqual(eexpr.reverse_read_permission, ())
        self.assertEqual(eexpr.reverse_delete_permission, ())
        self.assertEqual(eexpr.reverse_update_permission, ())
        # no more rqlexpr to delete and add para attribute
        self.assertFalse(self._rrqlexpr_rset('add', 'para'))
        self.assertFalse(self._rrqlexpr_rset('delete', 'para'))
        # new rql expr to add ecrit_par relation
        rexpr = self._rrqlexpr_entity('add', 'ecrit_par')
        self.assertEqual(rexpr.expression,
                          'O require_permission P, P name "add_note", '
                          'U in_group G, P require_group G')
        self.assertEqual([rdef.rtype.name for rdef in rexpr.reverse_add_permission], ['ecrit_par'])
        self.assertEqual(rexpr.reverse_read_permission, ())
        self.assertEqual(rexpr.reverse_delete_permission, ())
        # no more rqlexpr to delete and add travaille relation
        self.assertFalse(self._rrqlexpr_rset('add', 'travaille'))
        self.assertFalse(self._rrqlexpr_rset('delete', 'travaille'))
        # no more rqlexpr to delete and update Societe entity
        self.assertFalse(self._erqlexpr_rset('update', 'Societe'))
        self.assertFalse(self._erqlexpr_rset('delete', 'Societe'))
        # no more rqlexpr to read Affaire entity
        self.assertFalse(self._erqlexpr_rset('read', 'Affaire'))
        # rqlexpr to update Affaire entity has been updated
        eexpr = self._erqlexpr_entity('update', 'Affaire')
        self.assertEqual(eexpr.expression, 'X concerne S, S owned_by U')
        # no change for rqlexpr to add and delete Affaire entity
        self.assertEqual(len(self._erqlexpr_rset('delete', 'Affaire')), 1)
        self.assertEqual(len(self._erqlexpr_rset('add', 'Affaire')), 1)
        # no change for rqlexpr to add and delete concerne relation
        self.assertEqual(len(self._rrqlexpr_rset('delete', 'concerne')), len(delete_concerne_rqlexpr))
        self.assertEqual(len(self._rrqlexpr_rset('add', 'concerne')), len(add_concerne_rqlexpr))
        # * migrschema involve:
        #   * 7 rqlexprs deletion (2 in (Affaire read + Societe + travaille) + 1
        #     in para attribute)
        #   * 1 update (Affaire update)
        #   * 2 new (Note add, ecrit_par add)
        #   * 2 implicit new for attributes update_permission (Note.para, Personne.test)
        # remaining orphan rql expr which should be deleted at commit (composite relation)
        self.assertEqual(cursor.execute('Any COUNT(X) WHERE X is RQLExpression, '
                                         'NOT ET1 read_permission X, NOT ET2 add_permission X, '
                                         'NOT ET3 delete_permission X, NOT ET4 update_permission X')[0][0],
                          7+1)
        # finally
        self.assertEqual(cursor.execute('Any COUNT(X) WHERE X is RQLExpression')[0][0],
                          nbrqlexpr_start + 1 + 2 + 2)
        self.mh.commit()
        # unique_together test
        self.assertEqual(len(self.schema.eschema('Personne')._unique_together), 1)
        self.assertCountEqual(self.schema.eschema('Personne')._unique_together[0],
                                           ('nom', 'prenom', 'datenaiss'))
        rset = cursor.execute('Any C WHERE C is CWUniqueTogetherConstraint, C constraint_of ET, ET name "Personne"')
        self.assertEqual(len(rset), 1)
        relations = [r.name for r in rset.get_entity(0, 0).relations]
        self.assertCountEqual(relations, ('nom', 'prenom', 'datenaiss'))

    def _erqlexpr_rset(self, action, ertype):
        rql = 'RQLExpression X WHERE ET is CWEType, ET %s_permission X, ET name %%(name)s' % action
        return self.mh.session.execute(rql, {'name': ertype})
    def _erqlexpr_entity(self, action, ertype):
        rset = self._erqlexpr_rset(action, ertype)
        self.assertEqual(len(rset), 1)
        return rset.get_entity(0, 0)
    def _rrqlexpr_rset(self, action, ertype):
        rql = 'RQLExpression X WHERE RT is CWRType, RDEF %s_permission X, RT name %%(name)s, RDEF relation_type RT' % action
        return self.mh.session.execute(rql, {'name': ertype})
    def _rrqlexpr_entity(self, action, ertype):
        rset = self._rrqlexpr_rset(action, ertype)
        self.assertEqual(len(rset), 1)
        return rset.get_entity(0, 0)

    def test_set_size_constraint(self):
        # existing previous value
        try:
            self.mh.cmd_set_size_constraint('CWEType', 'name', 128)
        finally:
            self.mh.cmd_set_size_constraint('CWEType', 'name', 64)
        # non existing previous value
        try:
            self.mh.cmd_set_size_constraint('CWEType', 'description', 256)
        finally:
            self.mh.cmd_set_size_constraint('CWEType', 'description', None)

    @tag('longrun')
    def test_add_remove_cube_and_deps(self):
        cubes = set(self.config.cubes())
        schema = self.repo.schema
        self.assertEqual(sorted((str(s), str(o)) for s, o in schema['see_also'].rdefs.iterkeys()),
                          sorted([('EmailThread', 'EmailThread'), ('Folder', 'Folder'),
                                  ('Bookmark', 'Bookmark'), ('Bookmark', 'Note'),
                                  ('Note', 'Note'), ('Note', 'Bookmark')]))
        try:
            try:
                self.mh.cmd_remove_cube('email', removedeps=True)
                # file was there because it's an email dependancy, should have been removed
                self.assertFalse('email' in self.config.cubes())
                self.assertFalse(self.config.cube_dir('email') in self.config.cubes_path())
                self.assertFalse('file' in self.config.cubes())
                self.assertFalse(self.config.cube_dir('file') in self.config.cubes_path())
                for ertype in ('Email', 'EmailThread', 'EmailPart', 'File',
                               'sender', 'in_thread', 'reply_to', 'data_format'):
                    self.assertFalse(ertype in schema, ertype)
                self.assertEqual(sorted(schema['see_also'].rdefs.iterkeys()),
                                  sorted([('Folder', 'Folder'),
                                          ('Bookmark', 'Bookmark'),
                                          ('Bookmark', 'Note'),
                                          ('Note', 'Note'),
                                          ('Note', 'Bookmark')]))
                self.assertEqual(sorted(schema['see_also'].subjects()), ['Bookmark', 'Folder', 'Note'])
                self.assertEqual(sorted(schema['see_also'].objects()), ['Bookmark', 'Folder', 'Note'])
                self.assertEqual(self.session.execute('Any X WHERE X pkey "system.version.email"').rowcount, 0)
                self.assertEqual(self.session.execute('Any X WHERE X pkey "system.version.file"').rowcount, 0)
            except :
                import traceback
                traceback.print_exc()
                raise
        finally:
            self.mh.cmd_add_cube('email')
            self.assertTrue('email' in self.config.cubes())
            self.assertTrue(self.config.cube_dir('email') in self.config.cubes_path())
            self.assertTrue('file' in self.config.cubes())
            self.assertTrue(self.config.cube_dir('file') in self.config.cubes_path())
            for ertype in ('Email', 'EmailThread', 'EmailPart', 'File',
                           'sender', 'in_thread', 'reply_to', 'data_format'):
                self.assertTrue(ertype in schema, ertype)
            self.assertEqual(sorted(schema['see_also'].rdefs.iterkeys()),
                              sorted([('EmailThread', 'EmailThread'), ('Folder', 'Folder'),
                                      ('Bookmark', 'Bookmark'),
                                      ('Bookmark', 'Note'),
                                      ('Note', 'Note'),
                                      ('Note', 'Bookmark')]))
            self.assertEqual(sorted(schema['see_also'].subjects()), ['Bookmark', 'EmailThread', 'Folder', 'Note'])
            self.assertEqual(sorted(schema['see_also'].objects()), ['Bookmark', 'EmailThread', 'Folder', 'Note'])
            from cubes.email.__pkginfo__ import version as email_version
            from cubes.file.__pkginfo__ import version as file_version
            self.assertEqual(self.session.execute('Any V WHERE X value V, X pkey "system.version.email"')[0][0],
                              email_version)
            self.assertEqual(self.session.execute('Any V WHERE X value V, X pkey "system.version.file"')[0][0],
                              file_version)
            # trick: overwrite self.maxeid to avoid deletion of just reintroduced
            #        types (and their associated tables!)
            self.maxeid = self.session.execute('Any MAX(X)')[0][0]
            # why this commit is necessary is unclear to me (though without it
            # next test may fail complaining of missing tables
            self.session.commit(free_cnxset=False)


    @tag('longrun')
    def test_add_remove_cube_no_deps(self):
        cubes = set(self.config.cubes())
        schema = self.repo.schema
        try:
            try:
                self.mh.cmd_remove_cube('email')
                cubes.remove('email')
                self.assertFalse('email' in self.config.cubes())
                self.assertTrue('file' in self.config.cubes())
                for ertype in ('Email', 'EmailThread', 'EmailPart',
                               'sender', 'in_thread', 'reply_to'):
                    self.assertFalse(ertype in schema, ertype)
            except :
                import traceback
                traceback.print_exc()
                raise
        finally:
            self.mh.cmd_add_cube('email')
            self.assertTrue('email' in self.config.cubes())
            # trick: overwrite self.maxeid to avoid deletion of just reintroduced
            #        types (and their associated tables!)
            self.maxeid = self.session.execute('Any MAX(X)')[0][0]
            # why this commit is necessary is unclear to me (though without it
            # next test may fail complaining of missing tables
            self.session.commit(free_cnxset=False)

    def test_remove_dep_cube(self):
        with self.assertRaises(ConfigurationError) as cm:
            self.mh.cmd_remove_cube('file')
        self.assertEqual(str(cm.exception), "can't remove cube file, used as a dependency")

    @tag('longrun')
    def test_introduce_base_class(self):
        self.mh.cmd_add_entity_type('Para')
        self.mh.repo.schema.rebuild_infered_relations()
        self.assertEqual(sorted(et.type for et in self.schema['Para'].specialized_by()),
                          ['Note'])
        self.assertEqual(self.schema['Note'].specializes().type, 'Para')
        self.mh.cmd_add_entity_type('Text')
        self.mh.repo.schema.rebuild_infered_relations()
        self.assertEqual(sorted(et.type for et in self.schema['Para'].specialized_by()),
                          ['Note', 'Text'])
        self.assertEqual(self.schema['Text'].specializes().type, 'Para')
        # test columns have been actually added
        text = self.session.execute('INSERT Text X: X para "hip", X summary "hop", X newattr "momo"').get_entity(0, 0)
        note = self.session.execute('INSERT Note X: X para "hip", X shortpara "hop", X newattr "momo", X unique_id "x"').get_entity(0, 0)
        aff = self.session.execute('INSERT Affaire X').get_entity(0, 0)
        self.assertTrue(self.session.execute('SET X newnotinlined Y WHERE X eid %(x)s, Y eid %(y)s',
                                     {'x': text.eid, 'y': aff.eid}))
        self.assertTrue(self.session.execute('SET X newnotinlined Y WHERE X eid %(x)s, Y eid %(y)s',
                                     {'x': note.eid, 'y': aff.eid}))
        self.assertTrue(self.session.execute('SET X newinlined Y WHERE X eid %(x)s, Y eid %(y)s',
                                     {'x': text.eid, 'y': aff.eid}))
        self.assertTrue(self.session.execute('SET X newinlined Y WHERE X eid %(x)s, Y eid %(y)s',
                                     {'x': note.eid, 'y': aff.eid}))
        # XXX remove specializes by ourselves, else tearDown fails when removing
        # Para because of Note inheritance. This could be fixed by putting the
        # MemSchemaCWETypeDel(session, name) operation in the
        # after_delete_entity(CWEType) hook, since in that case the MemSchemaSpecializesDel
        # operation would be removed before, but I'm not sure this is a desired behaviour.
        #
        # also we need more tests about introducing/removing base classes or
        # specialization relationship...
        self.session.data['rebuild-infered'] = True
        try:
            self.session.execute('DELETE X specializes Y WHERE Y name "Para"')
            self.session.commit(free_cnxset=False)
        finally:
            self.session.data['rebuild-infered'] = False
        self.assertEqual(sorted(et.type for et in self.schema['Para'].specialized_by()),
                          [])
        self.assertEqual(self.schema['Note'].specializes(), None)
        self.assertEqual(self.schema['Text'].specializes(), None)


    def test_add_symmetric_relation_type(self):
        same_as_sql = self.mh.sqlexec("SELECT sql FROM sqlite_master WHERE type='table' "
                                      "and name='same_as_relation'")
        self.assertFalse(same_as_sql)
        self.mh.cmd_add_relation_type('same_as')
        same_as_sql = self.mh.sqlexec("SELECT sql FROM sqlite_master WHERE type='table' "
                                      "and name='same_as_relation'")
        self.assertTrue(same_as_sql)

if __name__ == '__main__':
    unittest_main()
