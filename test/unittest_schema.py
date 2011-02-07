# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for module cubicweb.schema"""

from __future__ import with_statement

import sys
from os.path import join, isabs, basename, dirname

from logilab.common.testlib import TestCase, unittest_main

from rql import RQLSyntaxError

from yams import BadSchemaDefinition
from yams.constraints import SizeConstraint, StaticVocabularyConstraint
from yams.buildobjs import RelationDefinition, EntityType, RelationType
from yams.reader import PyFileReader

from cubicweb.schema import (
    CubicWebSchema, CubicWebEntitySchema, CubicWebSchemaLoader,
    RQLConstraint, RQLUniqueConstraint, RQLVocabularyConstraint,
    RQLExpression, ERQLExpression, RRQLExpression,
    normalize_expression, order_eschemas, guess_rrqlexpr_mainvars)
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
eperson = schema.add_entity_type(EntityType('Personne', __permissions__=PERSONNE_PERMISSIONS))
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
    ('Personne promo String'),
    # real relations
    ('Personne  travaille Societe'),
    ('Personne  evaluee   Note'),
    ('Societe evaluee   Note'),
    ('Personne  concerne  Affaire'),
    ('Personne  concerne  Societe'),
    ('Affaire concerne  Societe'),
    )
done = {}
for rel in RELS:
    _from, _type, _to = rel.split()
    if not _type.lower() in done:
        schema.add_relation_type(RelationType(_type))
        done[_type.lower()] = True
    if _type == 'concerne':
        schema.add_relation_def(RelationDefinition(_from, _type, _to,
                                                   __permissions__=CONCERNE_PERMISSIONS))
    else:
        schema.add_relation_def(RelationDefinition(_from, _type, _to))

class CubicWebSchemaTC(TestCase):

    def test_rql_constraints_inheritance(self):
        # isinstance(cstr, RQLVocabularyConstraint)
        # -> expected to return RQLVocabularyConstraint and RQLConstraint
        #   instances but not RQLUniqueConstraint
        #
        # isinstance(cstr, RQLConstraint)
        # -> expected to return RQLConstraint instances but not
        #    RRQLVocabularyConstraint and QLUniqueConstraint
        self.failIf(issubclass(RQLUniqueConstraint, RQLVocabularyConstraint))
        self.failIf(issubclass(RQLUniqueConstraint, RQLConstraint))
        self.failUnless(issubclass(RQLConstraint, RQLVocabularyConstraint))

    def test_entity_perms(self):
        self.assertEqual(eperson.get_groups('read'), set(('managers', 'users', 'guests')))
        self.assertEqual(eperson.get_groups('update'), set(('managers', 'owners',)))
        self.assertEqual(eperson.get_groups('delete'), set(('managers', 'owners')))
        self.assertEqual(eperson.get_groups('add'), set(('managers',)))
        self.assertEqual([str(e) for e in eperson.get_rqlexprs('add')],
                         ['Any X WHERE X travaille S, S owned_by U, X eid %(x)s, U eid %(u)s'])
        eperson.set_action_permissions('read', ('managers',))
        self.assertEqual(eperson.get_groups('read'), set(('managers',)))

    def test_relation_perms(self):
        rconcerne = schema.rschema('concerne').rdef('Personne', 'Societe')
        self.assertEqual(rconcerne.get_groups('read'), set(('managers', 'users', 'guests')))
        self.assertEqual(rconcerne.get_groups('delete'), set(('managers',)))
        self.assertEqual(rconcerne.get_groups('add'), set(('managers', )))
        rconcerne.set_action_permissions('read', ('managers',))
        self.assertEqual(rconcerne.get_groups('read'), set(('managers',)))
        self.assertEqual([str(e) for e in rconcerne.get_rqlexprs('add')],
                         ['Any S,U WHERE U has_update_permission S, S eid %(s)s, U eid %(u)s'])

    def test_erqlexpression(self):
        self.assertRaises(RQLSyntaxError, ERQLExpression, '1')
        expr = ERQLExpression('X travaille S, S owned_by U')
        self.assertEqual(str(expr), 'Any X WHERE X travaille S, S owned_by U, X eid %(x)s, U eid %(u)s')

    def test_rrqlexpression(self):
        self.assertRaises(Exception, RRQLExpression, '1')
        self.assertRaises(RQLSyntaxError, RRQLExpression, 'O X Y')
        expr = RRQLExpression('U has_update_permission O')
        self.assertEqual(str(expr), 'Any O,U WHERE U has_update_permission O, O eid %(o)s, U eid %(u)s')

loader = CubicWebSchemaLoader()
config = TestConfiguration('data', apphome=DATADIR)
config.bootstrap_cubes()

class SchemaReaderClassTest(TestCase):

    def test_order_eschemas(self):
        schema = loader.load(config)
        self.assertEqual(order_eschemas([schema['Note'], schema['SubNote']]),
                                         [schema['Note'], schema['SubNote']])
        self.assertEqual(order_eschemas([schema['SubNote'], schema['Note']]),
                                         [schema['Note'], schema['SubNote']])

    def test_knownValues_load_schema(self):
        schema = loader.load(config)
        self.assert_(isinstance(schema, CubicWebSchema))
        self.assertEqual(schema.name, 'data')
        entities = sorted([str(e) for e in schema.entities()])
        expected_entities = ['BaseTransition', 'Bookmark', 'Boolean', 'Bytes', 'Card',
                             'Date', 'Datetime', 'Decimal',
                             'CWCache', 'CWConstraint', 'CWConstraintType', 'CWEType',
                             'CWAttribute', 'CWGroup', 'EmailAddress', 'CWRelation',
                             'CWPermission', 'CWProperty', 'CWRType',
                             'CWSource', 'CWSourceHostConfig', 'CWSourceSchemaConfig',
                             'CWUniqueTogetherConstraint', 'CWUser',
                             'ExternalUri', 'File', 'Float', 'Int', 'Interval', 'Note',
                             'Password', 'Personne',
                             'RQLExpression',
                             'Societe', 'State', 'StateFull', 'String', 'SubNote', 'SubWorkflowExitPoint',
                             'Tag', 'Time', 'Transition', 'TrInfo',
                             'Workflow', 'WorkflowTransition']
        self.assertListEqual(sorted(expected_entities), entities)
        relations = sorted([str(r) for r in schema.relations()])
        expected_relations = ['add_permission', 'address', 'alias', 'allowed_transition',
                              'bookmarked_by', 'by_transition',

                              'cardinality', 'comment', 'comment_format',
                              'composite', 'condition', 'config', 'connait',
                              'constrained_by', 'constraint_of',
                              'content', 'content_format',
                              'created_by', 'creation_date', 'cstrtype', 'custom_workflow',
                              'cwuri', 'cw_for_source', 'cw_host_config_of', 'cw_schema', 'cw_source',

                              'data', 'data_encoding', 'data_format', 'data_name', 'default_workflow', 'defaultval', 'delete_permission',
                              'description', 'description_format', 'destination_state',

                              'ecrit_par', 'eid', 'evaluee', 'expression', 'exprtype',

                              'final', 'firstname', 'for_user',
                              'from_entity', 'from_state', 'fulltext_container', 'fulltextindexed',

                              'has_text',
                              'identity', 'in_group', 'in_state', 'indexed',
                              'initial_state', 'inlined', 'internationalizable', 'is', 'is_instance_of',

                              'label', 'last_login_time', 'login',

                              'mainvars', 'match_host', 'modification_date',

                              'name', 'nom',

                              'options', 'ordernum', 'owned_by',

                              'path', 'pkey', 'prefered_form', 'prenom', 'primary_email',

                              'read_permission', 'relation_type', 'relations', 'require_group',

                              'specializes', 'state_of', 'subworkflow', 'subworkflow_exit', 'subworkflow_state', 'surname', 'symmetric', 'synopsis',

                              'tags', 'timestamp', 'title', 'to_entity', 'to_state', 'transition_of', 'travaille', 'type',

                              'upassword', 'update_permission', 'uri', 'use_email',

                              'value',

                              'wf_info_for', 'wikiid', 'workflow_of', 'tr_count']

        self.assertListEqual(sorted(expected_relations), relations)

        eschema = schema.eschema('CWUser')
        rels = sorted(str(r) for r in eschema.subject_relations())
        self.assertListEqual(rels, ['created_by', 'creation_date', 'custom_workflow',
                                    'cw_source', 'cwuri', 'eid',
                                     'evaluee', 'firstname', 'has_text', 'identity',
                                     'in_group', 'in_state', 'is',
                                     'is_instance_of', 'last_login_time',
                                     'login', 'modification_date', 'owned_by',
                                     'primary_email', 'surname', 'upassword',
                                     'use_email'])
        rels = sorted(r.type for r in eschema.object_relations())
        self.assertListEqual(rels, ['bookmarked_by', 'created_by', 'for_user',
                                     'identity', 'owned_by', 'wf_info_for'])
        rschema = schema.rschema('relation_type')
        properties = rschema.rdef('CWAttribute', 'CWRType')
        self.assertEqual(properties.cardinality, '1*')
        constraints = properties.constraints
        self.failUnlessEqual(len(constraints), 1, constraints)
        constraint = constraints[0]
        self.failUnless(isinstance(constraint, RQLConstraint))
        self.failUnlessEqual(constraint.restriction, 'O final TRUE')

    def test_fulltext_container(self):
        schema = loader.load(config)
        self.failUnless('has_text' in schema['CWUser'].subject_relations())
        self.failIf('has_text' in schema['EmailAddress'].subject_relations())

    def test_permission_settings(self):
        schema = loader.load(config)
        aschema = schema['TrInfo'].rdef('comment')
        self.assertEqual(aschema.get_groups('read'),
                          set(('managers', 'users', 'guests')))
        self.assertEqual(aschema.get_rqlexprs('read'),
                          ())
        self.assertEqual(aschema.get_groups('update'),
                          set(('managers',)))
        self.assertEqual([x.expression for x in aschema.get_rqlexprs('update')],
                          ['U has_update_permission X'])

class BadSchemaTC(TestCase):
    def setUp(self):
        self.loader = CubicWebSchemaLoader()
        self.loader.defined = {}
        self.loader.loaded_files = []
        self.loader.post_build_callbacks = []
        self.loader._pyreader = PyFileReader(self.loader)

    def _test(self, schemafile, msg):
        self.loader.handle_file(join(DATADIR, schemafile))
        with self.assertRaises(BadSchemaDefinition) as cm:
            self.loader._build_schema('toto', False)
        self.assertEqual(str(cm.exception), msg)

    def test_lowered_etype(self):
        self._test('lowered_etype.py',
                   "'my_etype' is not a valid name for an entity type. It should "
                   "start with an upper cased letter and be followed by at least "
                   "a lower cased letter")

    def test_uppered_rtype(self):
        self._test('uppered_rtype.py',
                   "'ARelation' is not a valid name for a relation type. It should be lower cased")

    def test_rrqlexpr_on_etype(self):
        self._test('rrqlexpr_on_eetype.py',
                   "can't use RRQLExpression on ToTo, use an ERQLExpression")

    def test_erqlexpr_on_rtype(self):
        self._test('erqlexpr_on_ertype.py',
                   "can't use ERQLExpression on relation ToTo toto TuTu, use a RRQLExpression")

    def test_rqlexpr_on_rtype_read(self):
        self._test('rqlexpr_on_ertype_read.py',
                   "can't use rql expression for read permission of relation ToTo toto TuTu")

    def test_rrqlexpr_on_attr(self):
        self._test('rrqlexpr_on_attr.py',
                   "can't use RRQLExpression on attribute ToTo.attr[String], use an ERQLExpression")


class NormalizeExpressionTC(TestCase):

    def test(self):
        self.assertEqual(normalize_expression('X  bla Y,Y blur Z  ,  Z zigoulou   X '),
                                               'X bla Y, Y blur Z, Z zigoulou X')

class RQLExpressionTC(TestCase):
    def test_comparison(self):
        self.assertEqual(ERQLExpression('X is CWUser', 'X', 0),
                          ERQLExpression('X is CWUser', 'X', 0))
        self.assertNotEqual(ERQLExpression('X is CWUser', 'X', 0),
                             ERQLExpression('X is CWGroup', 'X', 0))

class GuessRrqlExprMainVarsTC(TestCase):
    def test_exists(self):
        mainvars = guess_rrqlexpr_mainvars(normalize_expression('NOT EXISTS(O team_competition C, C level < 3)'))
        self.assertEqual(mainvars, 'O')


if __name__ == '__main__':
    unittest_main()
