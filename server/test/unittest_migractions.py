"""unit tests for module cubicweb.server.migractions
"""

from mx.DateTime import DateTime, today

from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools.apptest import RepositoryBasedTC, get_versions

from cubicweb.schema import CubicWebSchemaLoader
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.repository import Repository
from cubicweb.server.migractions import *

orig_get_versions = Repository.get_versions

def setup_module(*args):
    Repository.get_versions = get_versions

def teardown_module(*args):
    Repository.get_versions = orig_get_versions

    
class MigrationCommandsTC(RepositoryBasedTC):
    copy_schema = True
    
    def setUp(self):
        if not hasattr(self, '_repo'):
            # first initialization
            repo = self.repo # set by the RepositoryBasedTC metaclass
            # force to read schema from the database
            repo.config._cubes = None
            repo.fill_schema()
            # hack to read the schema from data/migrschema
            CubicWebSchemaLoader.main_schema_directory = 'migrschema'
            global migrschema
            migrschema = self.repo.config.load_schema()
            del CubicWebSchemaLoader.main_schema_directory
            assert 'Folder' in migrschema
            self.repo.hm.deactivate_verification_hooks()
        RepositoryBasedTC.setUp(self)
        self.mh = ServerMigrationHelper(self.repo.config, migrschema,
                                        repo=self.repo, cnx=self.cnx,
                                        interactive=False)
        assert self.cnx is self.mh._cnx
        assert self.session is self.mh.session, (self.session.id, self.mh.session.id)
        
    def test_add_attribute_int(self):
        self.failIf('whatever' in self.schema)
        paraordernum = self.mh.rqlexec('Any O WHERE X name "Note", RT name "para", RDEF from_entity X, RDEF relation_type RT, RDEF ordernum O')[0][0]
        self.mh.cmd_add_attribute('Note', 'whatever')
        self.failUnless('whatever' in self.schema)
        self.assertEquals(self.schema['whatever'].subjects(), ('Note',))
        self.assertEquals(self.schema['whatever'].objects(), ('Int',))
        paraordernum2 = self.mh.rqlexec('Any O WHERE X name "Note", RT name "para", RDEF from_entity X, RDEF relation_type RT, RDEF ordernum O')[0][0]
        self.assertEquals(paraordernum2, paraordernum+1)
        #self.assertEquals([r.type for r in self.schema['Note'].ordered_relations()],
        #                  ['modification_date', 'creation_date', 'owned_by',
        #                   'eid', 'ecrit_par', 'inline1', 'date', 'type',
        #                   'whatever', 'para', 'in_basket'])
        # NB: commit instead of rollback make following test fail with py2.5
        #     this sounds like a pysqlite/2.5 bug (the same eid is affected to
        #     two different entities)
        self.mh.rollback()

    def test_add_attribute_varchar(self):
        self.failIf('shortpara' in self.schema)
        self.mh.cmd_add_attribute('Note', 'shortpara')
        self.failUnless('shortpara' in self.schema)
        self.assertEquals(self.schema['shortpara'].subjects(), ('Note', ))
        self.assertEquals(self.schema['shortpara'].objects(), ('String', ))
        # test created column is actually a varchar(64)
        notesql = self.mh.sqlexec("SELECT sql FROM sqlite_master WHERE type='table' and name='%sNote'" % SQL_PREFIX)[0][0]
        fields = dict(x.strip().split()[:2] for x in notesql.split('(', 1)[1].rsplit(')', 1)[0].split(','))
        self.assertEquals(fields['%sshortpara' % SQL_PREFIX], 'varchar(64)')
        self.mh.rollback()
        
    def test_add_datetime_with_default_value_attribute(self):
        self.failIf('mydate' in self.schema)
        self.mh.cmd_add_attribute('Note', 'mydate')
        self.failUnless('mydate' in self.schema)
        self.assertEquals(self.schema['mydate'].subjects(), ('Note', ))
        self.assertEquals(self.schema['mydate'].objects(), ('Date', ))
        testdate = DateTime(2005, 12, 13)
        eid1 = self.mh.rqlexec('INSERT Note N')[0][0]
        eid2 = self.mh.rqlexec('INSERT Note N: N mydate %(mydate)s', {'mydate' : testdate})[0][0]
        d1 = self.mh.rqlexec('Any D WHERE X eid %(x)s, X mydate D', {'x': eid1}, 'x')[0][0]
        d2 = self.mh.rqlexec('Any D WHERE X eid %(x)s, X mydate D', {'x': eid2}, 'x')[0][0]
        self.assertEquals(d1, today())
        self.assertEquals(d2, testdate)
        self.mh.rollback()
            
    def test_rename_attribute(self):
        self.failIf('civility' in self.schema)
        eid1 = self.mh.rqlexec('INSERT Personne X: X nom "lui", X sexe "M"')[0][0]
        eid2 = self.mh.rqlexec('INSERT Personne X: X nom "l\'autre", X sexe NULL')[0][0]
        self.mh.cmd_rename_attribute('Personne', 'sexe', 'civility')
        self.failIf('sexe' in self.schema)
        self.failUnless('civility' in self.schema)
        # test data has been backported
        c1 = self.mh.rqlexec('Any C WHERE X eid %s, X civility C' % eid1)[0][0]
        self.failUnlessEqual(c1, 'M')
        c2 = self.mh.rqlexec('Any C WHERE X eid %s, X civility C' % eid2)[0][0]
        self.failUnlessEqual(c2, None)


    def test_workflow_actions(self):
        foo = self.mh.cmd_add_state(u'foo', ('Personne', 'Email'), initial=True)
        for etype in ('Personne', 'Email'):
            s1 = self.mh.rqlexec('Any N WHERE S state_of ET, ET name "%s", S name N' %
                                 etype)[0][0]
            self.assertEquals(s1, "foo")
            s1 = self.mh.rqlexec('Any N WHERE ET initial_state S, ET name "%s", S name N' %
                                 etype)[0][0]
            self.assertEquals(s1, "foo")
        bar = self.mh.cmd_add_state(u'bar', ('Personne', 'Email'), initial=True)
        baz = self.mh.cmd_add_transition(u'baz', ('Personne', 'Email'),
                                         (foo,), bar, ('managers',))
        for etype in ('Personne', 'Email'):
            t1 = self.mh.rqlexec('Any N WHERE T transition_of ET, ET name "%s", T name N' %
                                 etype)[0][0]
            self.assertEquals(t1, "baz")
        gn = self.mh.rqlexec('Any GN WHERE T require_group G, G name GN, T eid %s' % baz)[0][0]
        self.assertEquals(gn, 'managers')
        
    def test_add_entity_type(self):
        self.failIf('Folder2' in self.schema)
        self.failIf('filed_under2' in self.schema)
        self.mh.cmd_add_entity_type('Folder2')
        self.failUnless('Folder2' in self.schema)
        self.failUnless(self.execute('EEType X WHERE X name "Folder2"'))
        self.failUnless('filed_under2' in self.schema)
        self.failUnless(self.execute('ERType X WHERE X name "filed_under2"'))
        self.assertEquals(sorted(str(rs) for rs in self.schema['Folder2'].subject_relations()),
                          ['created_by', 'creation_date', 'description', 'description_format', 'eid',
                           'filed_under2', 'has_text', 'identity', 'is', 'is_instance_of',
                           'modification_date', 'name', 'owned_by'])
        self.assertEquals([str(rs) for rs in self.schema['Folder2'].object_relations()],
                          ['filed_under2', 'identity'])
        self.assertEquals(sorted(str(e) for e in self.schema['filed_under2'].subjects()),
                          ['Affaire', 'Card', 'Division', 'Email', 'EmailThread', 'File', 
                           'Folder2', 'Image', 'Note', 'Personne', 'Societe', 'SubDivision'])
        self.assertEquals(self.schema['filed_under2'].objects(), ('Folder2',))
        eschema = self.schema.eschema('Folder2')
        for cstr in eschema.constraints('name'):
            self.failUnless(hasattr(cstr, 'eid'))

    def test_drop_entity_type(self):
        self.mh.cmd_add_entity_type('Folder2')
        todoeid = self.mh.cmd_add_state(u'todo', 'Folder2', initial=True)
        doneeid = self.mh.cmd_add_state(u'done', 'Folder2')
        self.mh.cmd_add_transition(u'redoit', 'Folder2', (doneeid,), todoeid)
        self.mh.cmd_add_transition(u'markasdone', 'Folder2', (todoeid,), doneeid)
        self.commit()
        eschema = self.schema.eschema('Folder2')
        self.mh.cmd_drop_entity_type('Folder2')
        self.failIf('Folder2' in self.schema)
        self.failIf(self.execute('EEType X WHERE X name "Folder2"'))
        # test automatic workflow deletion
        self.failIf(self.execute('State X WHERE NOT X state_of ET'))
        self.failIf(self.execute('Transition X WHERE NOT X transition_of ET'))

    def test_add_relation_type(self):
        self.mh.cmd_add_entity_type('Folder2', auto=False)
        self.mh.cmd_add_relation_type('filed_under2')
        self.failUnless('filed_under2' in self.schema)
        self.assertEquals(sorted(str(e) for e in self.schema['filed_under2'].subjects()),
                          ['Affaire', 'Card', 'Division', 'Email', 'EmailThread', 'File', 
                           'Folder2', 'Image', 'Note', 'Personne', 'Societe', 'SubDivision'])
        self.assertEquals(self.schema['filed_under2'].objects(), ('Folder2',))


    def test_drop_relation_type(self):
        self.mh.cmd_add_entity_type('Folder2', auto=False)
        self.mh.cmd_add_relation_type('filed_under2')
        self.failUnless('filed_under2' in self.schema)
        self.mh.cmd_drop_relation_type('filed_under2')
        self.failIf('filed_under2' in self.schema)

    def test_add_relation_definition(self):
        self.mh.cmd_add_relation_definition('Societe', 'in_state', 'State')
        self.assertEquals(sorted(self.schema['in_state'].subjects()),
                          ['Affaire', 'Division', 'EUser', 'Note', 'Societe', 'SubDivision'])
        self.assertEquals(self.schema['in_state'].objects(), ('State',))

    def test_add_relation_definition_nortype(self):
        self.mh.cmd_add_relation_definition('Personne', 'concerne2', 'Affaire')
        self.assertEquals(self.schema['concerne2'].subjects(),
                          ('Personne',))
        self.assertEquals(self.schema['concerne2'].objects(), ('Affaire',))

    def test_drop_relation_definition1(self):
        self.failUnless('concerne' in self.schema)
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].subjects()), ['Affaire', 'Personne'])
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].objects()), ['Affaire', 'Division', 'Note', 'Societe', 'SubDivision'])
        self.mh.cmd_drop_relation_definition('Personne', 'concerne', 'Affaire')
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].subjects()), ['Affaire'])
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].objects()), ['Division', 'Note', 'Societe', 'SubDivision'])
        
    def test_drop_relation_definition_with_specialization(self):
        self.failUnless('concerne' in self.schema)
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].subjects()), ['Affaire', 'Personne'])
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].objects()), ['Affaire', 'Division', 'Note', 'Societe', 'SubDivision'])
        self.mh.cmd_drop_relation_definition('Affaire', 'concerne', 'Societe')
        self.mh.cmd_drop_relation_definition('None', 'concerne', 'Societe')
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].subjects()), ['Affaire', 'Personne'])
        self.assertEquals(sorted(str(e) for e in self.schema['concerne'].objects()), ['Affaire', 'Note'])
        
    def test_drop_relation_definition2(self):
        self.failUnless('evaluee' in self.schema)
        self.mh.cmd_drop_relation_definition('Personne', 'evaluee', 'Note')
        self.failUnless('evaluee' in self.schema)
        self.assertEquals(sorted(self.schema['evaluee'].subjects()),
                          ['Division', 'EUser', 'Societe', 'SubDivision'])
        self.assertEquals(sorted(self.schema['evaluee'].objects()),
                          ['Note'])

    def test_rename_relation(self):
        self.skip('implement me')

    def test_change_relation_props_non_final(self):
        rschema = self.schema['concerne']
        card = rschema.rproperty('Affaire', 'Societe', 'cardinality')
        self.assertEquals(card, '**')
        try:
            self.mh.cmd_change_relation_props('Affaire', 'concerne', 'Societe',
                                              cardinality='?*')
            card = rschema.rproperty('Affaire', 'Societe', 'cardinality')
            self.assertEquals(card, '?*')
        finally:
            self.mh.cmd_change_relation_props('Affaire', 'concerne', 'Societe',
                                              cardinality='**')
            
    def test_change_relation_props_final(self):
        rschema = self.schema['adel']
        card = rschema.rproperty('Personne', 'String', 'fulltextindexed')
        self.assertEquals(card, False)
        try:
            self.mh.cmd_change_relation_props('Personne', 'adel', 'String',
                                              fulltextindexed=True)
            card = rschema.rproperty('Personne', 'String', 'fulltextindexed')
            self.assertEquals(card, True)
        finally:
            self.mh.cmd_change_relation_props('Personne', 'adel', 'String',
                                              fulltextindexed=False)

    def test_synchronize_schema(self):
        cursor = self.mh.rqlcursor
        nbrqlexpr_start = len(cursor.execute('RQLExpression X'))
        migrschema['titre']._rproperties[('Personne', 'String')]['order'] = 7
        migrschema['adel']._rproperties[('Personne', 'String')]['order'] = 6
        migrschema['ass']._rproperties[('Personne', 'String')]['order'] = 5
#         expected = ['eid', 'has_text', 'creation_date', 'modification_date',
#                     'nom', 'prenom', 'civility', 'promo', 'ass', 'adel', 'titre',
#                     'web', 'tel', 'fax', 'datenaiss', 'test']
#         self.assertEquals([rs.type for rs in migrschema['Personne'].ordered_relations() if rs.is_final()],
#                           expected)
        migrschema['Personne'].description = 'blabla bla'
        migrschema['titre'].description = 'usually a title' 
        migrschema['titre']._rproperties[('Personne', 'String')]['description'] = 'title for this person'
#         rinorderbefore = cursor.execute('Any O,N WHERE X is EFRDef, X relation_type RT, RT name N,'
#                                         'X from_entity FE, FE name "Personne",'
#                                         'X ordernum O ORDERBY O')
#         expected = [u'creation_date', u'modification_date', u'nom', u'prenom',
#                     u'sexe', u'promo', u'titre', u'adel', u'ass', u'web', u'tel',
#                     u'fax', u'datenaiss', u'test', u'description']
#        self.assertListEquals(rinorderbefore, map(list, zip([0, 0]+range(1, len(expected)), expected)))
        
        self.mh.cmd_synchronize_schema(commit=False)
        
        self.assertEquals(cursor.execute('Any D WHERE X name "Personne", X description D')[0][0],
                          'blabla bla')
        self.assertEquals(cursor.execute('Any D WHERE X name "titre", X description D')[0][0],
                          'usually a title')
        self.assertEquals(cursor.execute('Any D WHERE X relation_type RT, RT name "titre",'
                                         'X from_entity FE, FE name "Personne",'
                                         'X description D')[0][0],
                          'title for this person')
        # skip "sexe" and "description" since they aren't in the migration
        # schema and so behaviour is undefined
        # "civility" is also skipped since it may have been added by
        # test_rename_attribut :o/
        rinorder = [n for n, in cursor.execute('Any N ORDERBY O WHERE X is EFRDef, X relation_type RT, RT name N,'
                                               'X from_entity FE, FE name "Personne",'
                                               'X ordernum O') if n not in ('sexe', 'description', 'civility')]
        expected = [u'nom', u'prenom', u'promo', u'ass', u'adel', u'titre',
                    u'web', u'tel', u'fax', u'datenaiss', u'test', u'firstname',
                    u'creation_date', u'modification_date']
        self.assertEquals(rinorder, expected)

        # test permissions synchronization ####################################
        # new rql expr to add note entity
        eexpr = self._erqlexpr_entity('add', 'Note')
        self.assertEquals(eexpr.expression,
                          'X ecrit_part PE, U in_group G, '
                          'PE require_permission P, P name "add_note", P require_group G')
        self.assertEquals([et.name for et in eexpr.reverse_add_permission], ['Note'])
        self.assertEquals(eexpr.reverse_read_permission, [])
        self.assertEquals(eexpr.reverse_delete_permission, [])
        self.assertEquals(eexpr.reverse_update_permission, [])
        # no more rqlexpr to delete and add para attribute
        self.failIf(self._rrqlexpr_rset('add', 'para'))
        self.failIf(self._rrqlexpr_rset('delete', 'para'))
        # new rql expr to add ecrit_par relation        
        rexpr = self._rrqlexpr_entity('add', 'ecrit_par')
        self.assertEquals(rexpr.expression,
                          'O require_permission P, P name "add_note", '
                          'U in_group G, P require_group G')
        self.assertEquals([rt.name for rt in rexpr.reverse_add_permission], ['ecrit_par'])
        self.assertEquals(rexpr.reverse_read_permission, [])
        self.assertEquals(rexpr.reverse_delete_permission, [])
        # no more rqlexpr to delete and add travaille relation
        self.failIf(self._rrqlexpr_rset('add', 'travaille'))
        self.failIf(self._rrqlexpr_rset('delete', 'travaille'))
        # no more rqlexpr to delete and update Societe entity
        self.failIf(self._erqlexpr_rset('update', 'Societe'))
        self.failIf(self._erqlexpr_rset('delete', 'Societe'))
        # no more rqlexpr to read Affaire entity
        self.failIf(self._erqlexpr_rset('read', 'Affaire'))
        # rqlexpr to update Affaire entity has been updated
        eexpr = self._erqlexpr_entity('update', 'Affaire')
        self.assertEquals(eexpr.expression, 'X concerne S, S owned_by U')
        # no change for rqlexpr to add and delete Affaire entity
        self.assertEquals(len(self._erqlexpr_rset('delete', 'Affaire')), 1)
        self.assertEquals(len(self._erqlexpr_rset('add', 'Affaire')), 1)
        # no change for rqlexpr to add and delete concerne relation
        self.assertEquals(len(self._rrqlexpr_rset('delete', 'concerne')), 1)
        self.assertEquals(len(self._rrqlexpr_rset('add', 'concerne')), 1)
        # * migrschema involve:
        #   * 8 deletion (2 in Affaire read + Societe + travaille + para rqlexprs)
        #   * 1 update (Affaire update)
        #   * 2 new (Note add, ecrit_par add)
        # remaining orphan rql expr which should be deleted at commit (composite relation)
        self.assertEquals(len(cursor.execute('RQLExpression X WHERE NOT ET1 read_permission X, NOT ET2 add_permission X, '
                                             'NOT ET3 delete_permission X, NOT ET4 update_permission X')), 8+1)
        # finally
        self.assertEquals(len(cursor.execute('RQLExpression X')), nbrqlexpr_start + 1 + 2) 
                          
        self.mh.rollback()

    def _erqlexpr_rset(self, action, ertype):
        rql = 'RQLExpression X WHERE ET is EEType, ET %s_permission X, ET name %%(name)s' % action
        return self.mh.rqlcursor.execute(rql, {'name': ertype})
    def _erqlexpr_entity(self, action, ertype):
        rset = self._erqlexpr_rset(action, ertype)
        self.assertEquals(len(rset), 1)
        return rset.get_entity(0, 0)
    def _rrqlexpr_rset(self, action, ertype):
        rql = 'RQLExpression X WHERE ET is ERType, ET %s_permission X, ET name %%(name)s' % action
        return self.mh.rqlcursor.execute(rql, {'name': ertype})
    def _rrqlexpr_entity(self, action, ertype):
        rset = self._rrqlexpr_rset(action, ertype)
        self.assertEquals(len(rset), 1)
        return rset.get_entity(0, 0)
    
    def test_set_size_constraint(self):
        # existing previous value
        try:
            self.mh.cmd_set_size_constraint('EEType', 'name', 128)
        finally:
            self.mh.cmd_set_size_constraint('EEType', 'name', 64)
        # non existing previous value
        try:
            self.mh.cmd_set_size_constraint('EEType', 'description', 256)
        finally:
            self.mh.cmd_set_size_constraint('EEType', 'description', None)

    def test_add_remove_cube(self):
        cubes = set(self.config.cubes())
        schema = self.repo.schema
        self.assertEquals(sorted(schema['see_also']._rproperties.keys()),
                          sorted([('EmailThread', 'EmailThread'), ('Folder', 'Folder'),
                                  ('Bookmark', 'Bookmark'), ('Bookmark', 'Note'),
                                  ('Note', 'Note'), ('Note', 'Bookmark')]))
        try:
            try:
                self.mh.cmd_remove_cube('email')
                # file was there because it's an email dependancy, should have been removed
                cubes.remove('email')
                cubes.remove('file')
                self.assertEquals(set(self.config.cubes()), cubes)
                for ertype in ('Email', 'EmailThread', 'EmailPart', 'File', 'Image', 
                               'sender', 'in_thread', 'reply_to', 'data_format'):
                    self.failIf(ertype in schema, ertype)
                self.assertEquals(sorted(schema['see_also']._rproperties.keys()),
                                  sorted([('Folder', 'Folder'),
                                          ('Bookmark', 'Bookmark'),
                                          ('Bookmark', 'Note'),
                                          ('Note', 'Note'),
                                          ('Note', 'Bookmark')]))
                self.assertEquals(sorted(schema['see_also'].subjects()), ['Bookmark', 'Folder', 'Note'])
                self.assertEquals(sorted(schema['see_also'].objects()), ['Bookmark', 'Folder', 'Note'])
                self.assertEquals(self.execute('Any X WHERE X pkey "system.version.email"').rowcount, 0)
                self.assertEquals(self.execute('Any X WHERE X pkey "system.version.file"').rowcount, 0)
                self.failIf('email' in self.config.cubes())
                self.failIf('file' in self.config.cubes())
            except :
                import traceback
                traceback.print_exc()
                raise
        finally:
            self.mh.cmd_add_cube('email')
            cubes.add('email')
            cubes.add('file')
            self.assertEquals(set(self.config.cubes()), cubes)
            for ertype in ('Email', 'EmailThread', 'EmailPart', 'File', 'Image', 
                           'sender', 'in_thread', 'reply_to', 'data_format'):
                self.failUnless(ertype in schema, ertype)
            self.assertEquals(sorted(schema['see_also']._rproperties.keys()),
                              sorted([('EmailThread', 'EmailThread'), ('Folder', 'Folder'),
                                      ('Bookmark', 'Bookmark'),
                                      ('Bookmark', 'Note'),
                                      ('Note', 'Note'),
                                      ('Note', 'Bookmark')]))
            self.assertEquals(sorted(schema['see_also'].subjects()), ['Bookmark', 'EmailThread', 'Folder', 'Note'])
            self.assertEquals(sorted(schema['see_also'].objects()), ['Bookmark', 'EmailThread', 'Folder', 'Note'])
            from cubes.email.__pkginfo__ import version as email_version
            from cubes.file.__pkginfo__ import version as file_version
            self.assertEquals(self.execute('Any V WHERE X value V, X pkey "system.version.email"')[0][0],
                              email_version)
            self.assertEquals(self.execute('Any V WHERE X value V, X pkey "system.version.file"')[0][0],
                              file_version)
            self.failUnless('email' in self.config.cubes())
            self.failUnless('file' in self.config.cubes())
            # trick: overwrite self.maxeid to avoid deletion of just reintroduced
            #        types (and their associated tables!)
            self.maxeid = self.execute('Any MAX(X)')[0][0]
            # why this commit is necessary is unclear to me (though without it
            # next test may fail complaining of missing tables
            self.commit() 

    def test_set_state(self):
        user = self.session.user
        self.set_debug(True)
        self.mh.set_state(user.eid, 'deactivated')
        user.clear_related_cache('in_state', 'subject')
        try:
            self.assertEquals(user.state, 'deactivated')
        finally:
            self.set_debug(False)
        
if __name__ == '__main__':
    unittest_main()
