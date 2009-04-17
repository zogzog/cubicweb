"""unit tests for module cubicweb.schema"""

import sys
from os.path import join, isabs, basename, dirname

from logilab.common.testlib import TestCase, unittest_main

from rql import RQLSyntaxError

from yams import BadSchemaDefinition
from yams.constraints import SizeConstraint, StaticVocabularyConstraint
from yams.buildobjs import RelationDefinition, EntityType, RelationType

from cubicweb.schema import CubicWebSchema, CubicWebEntitySchema, \
     RQLConstraint, CubicWebSchemaLoader, ERQLExpression, RRQLExpression, \
     normalize_expression
from cubicweb.devtools import TestServerConfiguration as TestConfiguration

DATADIR = join(dirname(__file__), 'data')

# build a dummy schema ########################################################


PERSONNE_PERMISSIONS =  {
    'read':   ('managers', 'users', 'guests'),
    'update': ('managers', 'owners'),
    'add':    ('managers', ERQLExpression('X travaille S, S owned_by U')),
    'delete': ('managers', 'owners',),
    }

CONCERNE_PERMISSIONS = {
    'read':   ('managers', 'users', 'guests'),
    'add':    ('managers', RRQLExpression('U has_update_permission S')),
    'delete': ('managers', RRQLExpression('O owned_by U')),
    }

schema = CubicWebSchema('Test Schema')
enote = schema.add_entity_type(EntityType('Note'))
eaffaire = schema.add_entity_type(EntityType('Affaire'))
eperson = schema.add_entity_type(EntityType('Personne', permissions=PERSONNE_PERMISSIONS))
esociete = schema.add_entity_type(EntityType('Societe'))

RELS = (
    # attribute relations
    ('Note date String'),
    ('Note type String'),
    ('Affaire sujet String'),
    ('Affaire ref String'),
    ('Personne nom String'),
    ('Personne prenom String'),
    ('Personne sexe String'),
    ('Personne tel Int'),
    ('Personne fax Int'),
    ('Personne datenaiss Date'),
    ('Personne TEST Boolean'),
    ('Personne promo String'),
    # real relations
    ('Personne  travaille Societe'),
    ('Personne  evaluee   Note'),
    ('Societe evaluee   Note'),
    ('Personne  concerne  Affaire'),
    ('Personne  concerne  Societe'),
    ('Affaire Concerne  Societe'),
    )
done = {}
for rel in RELS:
    _from, _type, _to = rel.split()
    if not _type.lower() in done:
        if _type == 'concerne':
            schema.add_relation_type(RelationType(_type, permissions=CONCERNE_PERMISSIONS))
        else:
            schema.add_relation_type(RelationType(_type))
        done[_type.lower()] = True
    schema.add_relation_def(RelationDefinition(_from, _type, _to))

class CubicWebSchemaTC(TestCase):

    def test_normalize(self):
        """test that entities, relations and attributes name are normalized
        """
        self.assertEqual(esociete.type, 'Societe')
        self.assertEqual(schema.has_relation('TEST'), 0)
        self.assertEqual(schema.has_relation('test'), 1)
        self.assertEqual(eperson.subject_relation('test').type, 'test')
        self.assertEqual(schema.has_relation('Concerne'), 0)
        self.assertEqual(schema.has_relation('concerne'), 1)
        self.assertEqual(schema.rschema('concerne').type, 'concerne')

    def test_entity_perms(self):
        eperson.set_default_groups()
        self.assertEqual(eperson.get_groups('read'), set(('managers', 'users', 'guests')))
        self.assertEqual(eperson.get_groups('update'), set(('managers', 'owners',)))
        self.assertEqual(eperson.get_groups('delete'), set(('managers', 'owners')))
        self.assertEqual(eperson.get_groups('add'), set(('managers',)))
        self.assertEqual([str(e) for e in eperson.get_rqlexprs('add')],
                         ['Any X WHERE X travaille S, S owned_by U, X eid %(x)s, U eid %(u)s'])
        eperson.set_groups('read', ('managers',))
        self.assertEqual(eperson.get_groups('read'), set(('managers',)))
        
    def test_relation_perms(self):
        rconcerne = schema.rschema('concerne')
        rconcerne.set_default_groups()
        self.assertEqual(rconcerne.get_groups('read'), set(('managers', 'users', 'guests')))
        self.assertEqual(rconcerne.get_groups('delete'), set(('managers',)))
        self.assertEqual(rconcerne.get_groups('add'), set(('managers', )))
        rconcerne.set_groups('read', ('managers',))
        self.assertEqual(rconcerne.get_groups('read'), set(('managers',)))
        self.assertEqual([str(e) for e in rconcerne.get_rqlexprs('add')],
                         ['Any S WHERE U has_update_permission S, S eid %(s)s, U eid %(u)s'])

    def test_erqlexpression(self):
        self.assertRaises(RQLSyntaxError, ERQLExpression, '1')
        expr = ERQLExpression('X travaille S, S owned_by U')
        self.assertEquals(str(expr), 'Any X WHERE X travaille S, S owned_by U, X eid %(x)s, U eid %(u)s')
        
    def test_rrqlexpression(self):
        self.assertRaises(Exception, RRQLExpression, '1')
        self.assertRaises(RQLSyntaxError, RRQLExpression, 'O X Y')
        expr = RRQLExpression('U has_update_permission O')
        self.assertEquals(str(expr), 'Any O WHERE U has_update_permission O, O eid %(o)s, U eid %(u)s')
        

loader = CubicWebSchemaLoader()
config = TestConfiguration('data')
config.bootstrap_cubes()
loader.lib_directory = config.schemas_lib_dir()
    
class SQLSchemaReaderClassTest(TestCase):

    def test_knownValues_include_schema_files(self):
        schema_files = loader.include_schema_files('Bookmark')
        for file in schema_files:
            self.assert_(isabs(file))
        self.assertListEquals([basename(f) for f in schema_files], ['Bookmark.py'])

    def test_knownValues_load_schema(self):
        schema = loader.load(config)
        self.assert_(isinstance(schema, CubicWebSchema))
        self.assertEquals(schema.name, 'data')
        entities = [str(e) for e in schema.entities()]
        entities.sort()
        expected_entities = ['Bookmark', 'Boolean', 'Bytes', 'Card', 
                             'Date', 'Datetime', 'Decimal',
                             'CWCache', 'CWConstraint', 'CWConstraintType', 'CWEType',
                             'CWAttribute', 'CWGroup', 'EmailAddress', 'CWRelation',
                             'CWPermission', 'CWProperty', 'CWRType', 'CWUser',
                             'File', 'Float', 'Image', 'Int', 'Interval', 'Note',
                             'Password', 'Personne',
                             'RQLExpression', 
                             'Societe', 'State', 'String', 'SubNote', 'Tag', 'Time', 
                             'Transition', 'TrInfo']
        self.assertListEquals(entities, sorted(expected_entities))
        relations = [str(r) for r in schema.relations()]
        relations.sort()
        expected_relations = ['add_permission', 'address', 'alias',
                              'allowed_transition', 'bookmarked_by', 'canonical',

                              'cardinality', 'comment', 'comment_format', 
                              'composite', 'condition', 'connait', 'constrained_by', 'content',
                              'content_format', 'created_by', 'creation_date', 'cstrtype',

                              'data', 'data_encoding', 'data_format', 'defaultval', 'delete_permission',
                              'description', 'description_format', 'destination_state',

                              'ecrit_par', 'eid', 'evaluee', 'expression', 'exprtype',

                              'final', 'firstname', 'for_user',
                              'from_entity', 'from_state', 'fulltext_container', 'fulltextindexed',

                              'has_text', 
                              'identical_to', 'identity', 'in_group', 'in_state', 'indexed',
                              'initial_state', 'inlined', 'internationalizable', 'is', 'is_instance_of',

                              'label', 'last_login_time', 'login',

                              'mainvars', 'meta', 'modification_date',

                              'name', 'nom',

                              'ordernum', 'owned_by',

                              'path', 'pkey', 'prenom', 'primary_email', 

                              'read_permission', 'relation_type', 'require_group',
                              
                              'specializes', 'state_of', 'surname', 'symetric', 'synopsis',

                              'tags', 'timestamp', 'title', 'to_entity', 'to_state', 'transition_of', 'travaille', 'type',

                              'upassword', 'update_permission', 'use_email',

                              'value', 

                              'wf_info_for', 'wikiid']
    
        self.assertListEquals(relations, expected_relations)

        eschema = schema.eschema('CWUser')
        rels = sorted(str(r) for r in eschema.subject_relations())
        self.assertListEquals(rels, ['created_by', 'creation_date', 'eid',
                                     'evaluee', 'firstname', 'has_text', 'identity',
                                     'in_group', 'in_state', 'is',
                                     'is_instance_of', 'last_login_time',
                                     'login', 'modification_date', 'owned_by',
                                     'primary_email', 'surname', 'upassword',
                                     'use_email'])
        rels = sorted(r.type for r in eschema.object_relations())
        self.assertListEquals(rels, ['bookmarked_by', 'created_by', 'for_user',
                                     'identity', 'owned_by', 'wf_info_for'])
        rschema = schema.rschema('relation_type')
        properties = rschema.rproperties('CWAttribute', 'CWRType')
        self.assertEquals(properties['cardinality'], '1*')
        constraints = properties['constraints']
        self.failUnlessEqual(len(constraints), 1, constraints)
        constraint = constraints[0]
        self.failUnless(isinstance(constraint, RQLConstraint))
        self.failUnlessEqual(constraint.restriction, 'O final TRUE')

    def test_fulltext_container(self):
        schema = loader.load(config)
        self.failUnless('has_text' in schema['CWUser'].subject_relations())
        self.failIf('has_text' in schema['EmailAddress'].subject_relations())


class BadSchemaRQLExprTC(TestCase):
    def setUp(self):
        self.loader = CubicWebSchemaLoader()
        self.loader.defined = {}
        self.loader.loaded_files = []
        self.loader._instantiate_handlers()

    def _test(self, schemafile, msg):
        self.loader.handle_file(join(DATADIR, schemafile))
        ex = self.assertRaises(BadSchemaDefinition,
                               self.loader._build_schema, 'toto', False)
        self.assertEquals(str(ex), msg)
        
    def test_rrqlexpr_on_etype(self):
        self._test('rrqlexpr_on_eetype.py', "can't use RRQLExpression on an entity type, use an ERQLExpression (ToTo)")
        
    def test_erqlexpr_on_rtype(self):
        self._test('erqlexpr_on_ertype.py', "can't use ERQLExpression on a relation type, use a RRQLExpression (toto)")
        
    def test_rqlexpr_on_rtype_read(self):
        self._test('rqlexpr_on_ertype_read.py', "can't use rql expression for read permission of a relation type (toto)")
        
    def test_rrqlexpr_on_attr(self):
        self._test('rrqlexpr_on_attr.py', "can't use RRQLExpression on a final relation type (eg attribute relation), use an ERQLExpression (attr)")


class NormalizeExpressionTC(TestCase):

    def test(self):
        self.assertEquals(normalize_expression('X  bla Y,Y blur Z  ,  Z zigoulou   X '),
                                               'X bla Y, Y blur Z, Z zigoulou X')

if __name__ == '__main__':
    unittest_main()
