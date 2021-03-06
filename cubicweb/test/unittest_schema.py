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
"""unit tests for module cubicweb.schema"""

from os.path import join, dirname, splitext

from logilab.common.testlib import TestCase, unittest_main

from rql import RQLSyntaxError

from yams import ValidationError, BadSchemaDefinition
from yams.buildobjs import (RelationDefinition, EntityType, RelationType,
                            Int, String, ComputedRelation)
from yams.reader import fill_schema

from cubicweb import devtools
from cubicweb.schema import (
    CubicWebSchema, CubicWebSchemaLoader,
    RQLConstraint, RQLUniqueConstraint, RQLVocabularyConstraint,
    ERQLExpression, RRQLExpression,
    normalize_expression, order_eschemas, guess_rrqlexpr_mainvars,
    build_schema_from_namespace)
from cubicweb.devtools.testlib import CubicWebTC

DATADIR = join(dirname(__file__), 'data')

# build a dummy schema ########################################################


PERSONNE_PERMISSIONS = {
    'read': ('managers', 'users', 'guests'),
    'update': ('managers', 'owners'),
    'add': ('managers', ERQLExpression('X travaille S, S owned_by U')),
    'delete': ('managers', 'owners',),
}

CONCERNE_PERMISSIONS = {
    'read': ('managers', 'users', 'guests'),
    'add': ('managers', RRQLExpression('U has_update_permission S')),
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
        #    RQLVocabularyConstraint and RQLUniqueConstraint
        self.assertFalse(issubclass(RQLUniqueConstraint, RQLVocabularyConstraint))
        self.assertFalse(issubclass(RQLUniqueConstraint, RQLConstraint))

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
        self.assertEqual(
            str(expr),
            'Any X WHERE X travaille S, S owned_by U, X eid %(x)s, U eid %(u)s')
        expr = ERQLExpression('X foo S, S bar U, X baz XE, S quux SE HAVING XE > SE')
        self.assertEqual(
            str(expr),
            'Any X WHERE X foo S, S bar U, X baz XE, S quux SE, X eid %(x)s, '
            'U eid %(u)s HAVING XE > SE')

    def test_rrqlexpression(self):
        self.assertRaises(Exception, RRQLExpression, '1')
        self.assertRaises(RQLSyntaxError, RRQLExpression, 'O X Y')
        expr = RRQLExpression('U has_update_permission O')
        self.assertEqual(
            str(expr),
            'Any O,U WHERE U has_update_permission O, O eid %(o)s, U eid %(u)s')


loader = CubicWebSchemaLoader()
config = devtools.TestServerConfiguration('data', __file__)
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
        self.assertIsInstance(schema, CubicWebSchema)
        self.assertEqual(schema.name, 'data')
        entities = sorted([str(e) for e in schema.entities()])
        expected_entities = [
            'Ami', 'BaseTransition', 'BigInt', 'Bookmark', 'Boolean', 'Bytes', 'Card',
            'Date', 'Datetime', 'Decimal',
            'CWComputedRType', 'CWConstraint',
            'CWConstraintType', 'CWDataImport', 'CWEType',
            'CWAttribute', 'CWGroup', 'EmailAddress',
            'CWRelation', 'CWPermission', 'CWProperty', 'CWRType', 'CWSession',
            'CWSource', 'CWSourceHostConfig',
            'CWUniqueTogetherConstraint', 'CWUser',
            'ExternalUri', 'FakeFile', 'Float', 'Int', 'Interval', 'Note',
            'Password', 'Personne', 'Produit',
            'RQLExpression', 'Reference',
            'Service', 'Societe', 'State', 'StateFull', 'String', 'SubNote', 'SubWorkflowExitPoint',
            'Tag', 'TZDatetime', 'TZTime', 'Time', 'Transition', 'TrInfo',
            'Usine',
            'Workflow', 'WorkflowTransition',
        ]
        self.assertListEqual(sorted(expected_entities), entities)
        relations = sorted([str(r) for r in schema.relations()])
        expected_relations = [
            'actionnaire', 'add_permission', 'address', 'alias', 'allowed_transition', 'associe',
            'bookmarked_by', 'by_transition', 'buddies',

            'cardinality', 'comment', 'comment_format',
            'composite', 'condition', 'config', 'connait',
            'constrained_by', 'constraint_of',
            'content', 'content_format', 'contrat_exclusif',
            'created_by', 'creation_date', 'cstrtype', 'custom_workflow',
            'cwuri', 'cwsessiondata', 'cw_import_of', 'cw_host_config_of', 'cw_source',

            'data', 'data_encoding', 'data_format', 'data_name', 'default_workflow', 'defaultval',
            'delete_permission', 'description', 'description_format', 'destination_state',
            'dirige',

            'ean', 'ecrit_par', 'eid', 'end_timestamp', 'evaluee', 'expression', 'exprtype',
            'extra_props',

            'fabrique_par', 'final', 'firstname', 'for_user', 'formula', 'fournit',
            'from_entity', 'from_state', 'fulltext_container', 'fulltextindexed',

            'has_group_permission', 'has_text',
            'identity', 'in_group', 'in_state', 'in_synchronization', 'indexed',
            'initial_state', 'inlined', 'internationalizable', 'is', 'is_instance_of',

            'label', 'last_login_time', 'latest_retrieval', 'lieu', 'log', 'login',

            'mainvars', 'match_host', 'modification_date',

            'name', 'nom',

            'ordernum', 'owned_by',

            'parser', 'path', 'pkey', 'prefered_form', 'prenom', 'primary_email',

            'read_permission', 'relation_type', 'relations', 'require_group', 'rule',

            'specializes', 'start_timestamp', 'state_of', 'status', 'subworkflow',
            'subworkflow_exit', 'subworkflow_state', 'surname', 'symmetric', 'synopsis',

            'tags', 'title', 'to_entity', 'to_state', 'transition_of', 'travaille',
            'type',

            'upassword', 'update_permission', 'url', 'uri', 'use_email',

            'value',

            'wf_info_for', 'wikiid', 'workflow_of', 'tr_count',
        ]

        self.assertListEqual(sorted(expected_relations), relations)

        eschema = schema.eschema('CWUser')
        rels = sorted(str(r) for r in eschema.subject_relations())
        self.assertListEqual(rels, ['buddies', 'created_by', 'creation_date', 'custom_workflow',
                                    'cw_source', 'cwuri', 'eid',
                                    'evaluee', 'firstname', 'has_group_permission',
                                    'has_text', 'identity',
                                    'in_group', 'in_state', 'is',
                                    'is_instance_of', 'last_login_time',
                                    'login', 'modification_date', 'owned_by',
                                    'primary_email', 'surname', 'upassword',
                                    'use_email'])
        rels = sorted(r.type for r in eschema.object_relations())
        self.assertListEqual(rels, ['bookmarked_by', 'buddies', 'created_by', 'for_user',
                                    'identity', 'owned_by', 'wf_info_for'])
        rschema = schema.rschema('relation_type')
        properties = rschema.rdef('CWAttribute', 'CWRType')
        self.assertEqual(properties.cardinality, '1*')
        constraints = properties.constraints
        self.assertEqual(len(constraints), 1, constraints)
        constraint = constraints[0]
        self.assertTrue(isinstance(constraint, RQLConstraint))
        self.assertEqual(constraint.expression, 'O final TRUE')

    def test_fulltext_container(self):
        schema = loader.load(config)
        self.assertIn('has_text', schema['CWUser'].subject_relations())
        self.assertNotIn('has_text', schema['EmailAddress'].subject_relations())

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

    def test_nonregr_allowed_type_names(self):
        schema = CubicWebSchema('Test Schema')
        schema.add_entity_type(EntityType('NaN'))

    def test_relation_perm_overriding(self):
        loader = CubicWebSchemaLoader()
        config = devtools.TestServerConfiguration('data_schemareader', __file__)
        config.bootstrap_cubes()
        schema = loader.load(config)
        rdef = next(iter(schema['in_group'].rdefs.values()))
        self.assertEqual(rdef.permissions,
                         {'read': ('managers',),
                          'add': ('managers',),
                          'delete': ('managers',)})
        rdef = next(iter(schema['cw_for_source'].rdefs.values()))
        self.assertEqual(rdef.permissions,
                         {'read': ('managers', 'users'),
                          'add': ('managers',),
                          'delete': ('managers',)})

    def test_computed_attribute(self):
        """Check schema finalization for computed attributes."""
        class Person(EntityType):
            salary = Int()

        class works_for(RelationDefinition):
            subject = 'Person'
            object = 'Company'
            cardinality = '?*'

        class Company(EntityType):
            total_salary = Int(formula='Any SUM(SA) GROUPBY X WHERE P works_for X, P salary SA')

        good_schema = build_schema_from_namespace(vars().items())
        rdef = good_schema['Company'].rdef('total_salary')
        # ensure 'X is Company' is added to the rqlst to avoid ambiguities, see #4901163
        self.assertEqual(str(rdef.formula_select),
                         'Any SUM(SA) GROUPBY X WHERE P works_for X, P salary SA, X is Company')
        # check relation definition permissions
        self.assertEqual(rdef.permissions,
                         {'add': (), 'update': (),
                          'read': ('managers', 'users', 'guests')})

        class Company(EntityType):  # noqa
            total_salary = String(formula='Any SUM(SA) GROUPBY X WHERE '
                                          'P works_for X, P salary SA')

        with self.assertRaises(BadSchemaDefinition) as exc:
            build_schema_from_namespace(vars().items())

        self.assertEqual(str(exc.exception),
                         'computed attribute total_salary on Company: '
                         'computed attribute type (Int) mismatch with '
                         'specified type (String)')


class SchemaReaderComputedRelationAndAttributesTest(TestCase):

    def test_infer_computed_relation(self):
        class Person(EntityType):
            name = String()

        class Company(EntityType):
            name = String()

        class Service(EntityType):
            name = String()

        class works_for(RelationDefinition):
            subject = 'Person'
            object = 'Company'

        class produce(RelationDefinition):
            subject = ('Person', 'Company')
            object = 'Service'

        class achete(RelationDefinition):
            subject = 'Person'
            object = 'Service'

        class produces_and_buys(ComputedRelation):
            rule = 'S produce O, S achete O'

        class produces_and_buys2(ComputedRelation):
            rule = 'S works_for SO, SO produce O'

        class reproduce(ComputedRelation):
            rule = 'S produce O'

        schema = build_schema_from_namespace(vars().items())

        # check object/subject type
        self.assertEqual([('Person', 'Service')],
                         list(schema['produces_and_buys'].rdefs.keys()))
        self.assertEqual([('Person', 'Service')],
                         list(schema['produces_and_buys2'].rdefs.keys()))
        self.assertCountEqual([('Company', 'Service'), ('Person', 'Service')],
                              list(schema['reproduce'].rdefs.keys()))
        # check relation definitions are marked infered
        rdef = schema['produces_and_buys'].rdefs[('Person', 'Service')]
        self.assertTrue(rdef.infered)
        # and have no add/delete permissions
        self.assertEqual(rdef.permissions,
                         {'add': (),
                          'delete': (),
                          'read': ('managers', 'users', 'guests')})

        class autoname(ComputedRelation):
            rule = 'S produce X, X name O'

        with self.assertRaises(BadSchemaDefinition) as cm:
            build_schema_from_namespace(vars().items())
        self.assertEqual(str(cm.exception), 'computed relations cannot be final')


class BadSchemaTC(TestCase):
    def setUp(self):
        self.loader = CubicWebSchemaLoader()
        self.loader.defined = {}
        self.loader.loaded_files = []
        self.loader.post_build_callbacks = []

    def _test(self, schemafile, msg):
        self.loader.handle_file(join(DATADIR, schemafile),
                                splitext(schemafile)[0])
        sch = self.loader.schemacls('toto')
        with self.assertRaises(BadSchemaDefinition) as cm:
            fill_schema(sch, self.loader.defined, False)
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

    def test_rqlexpr_on_computedrel(self):
        self._test(
            'rqlexpr_on_computedrel.py',
            "can't use rql expression for read permission of relation Subject computed Object")


class NormalizeExpressionTC(TestCase):

    def test(self):
        self.assertEqual(normalize_expression('X  bla Y,Y blur Z  ,  Z zigoulou   X '),
                         'X bla Y, Y blur Z, Z zigoulou X')
        self.assertEqual(normalize_expression('X bla Y, Y name "x,y"'),
                         'X bla Y, Y name "x,y"')


class RQLExpressionTC(TestCase):
    def test_comparison(self):
        self.assertEqual(ERQLExpression('X is CWUser', 'X', 0),
                         ERQLExpression('X is CWUser', 'X', 0))
        self.assertNotEqual(ERQLExpression('X is CWUser', 'X', 0),
                            ERQLExpression('X is CWGroup', 'X', 0))

    def test_has_update_permission(self):
        expr = ERQLExpression('P use_email X, U has_update_permission P')
        rql, found, keyarg = expr.transform_has_permission()
        self.assertEqual(rql, 'Any X,P WHERE P use_email X, X eid %(x)s')
        self.assertEqual(found, [(u'update', 1)])
        self.assertEqual(keyarg, None)

    def test_expression(self):
        expr = ERQLExpression('U use_email X')
        rql, found, keyarg = expr.transform_has_permission()
        self.assertEqual(rql, 'Any X WHERE EXISTS(U use_email X, X eid %(x)s, U eid %(u)s)')
        self.assertEqual(found, None)
        self.assertEqual(keyarg, None)


class GuessRrqlExprMainVarsTC(TestCase):
    def test_exists(self):
        mainvars = guess_rrqlexpr_mainvars(normalize_expression(
            'NOT EXISTS(O team_competition C, C level < 3, C concerns S)'))
        self.assertEqual(mainvars, set(['S', 'O']))


class RQLConstraintTC(CubicWebTC):
    def test_user_constraint(self):
        cstr = RQLConstraint('U identity O')
        with self.admin_access.repo_cnx() as cnx:
            anoneid = cnx.execute('Any X WHERE X login "anon"')[0][0]
            self.assertRaises(ValidationError,
                              cstr.repo_check, cnx, 1, 'rel', anoneid)
            self.assertEqual(cstr.repo_check(cnx, 1, cnx.user.eid),
                             None)  # no validation error, constraint checked


class WorkflowShemaTC(CubicWebTC):
    def test_trinfo_default_format(self):
        with self.admin_access.web_request() as req:
            tr = req.user.cw_adapt_to('IWorkflowable').fire_transition('deactivate')
            self.assertEqual(tr.comment_format, 'text/plain')


class CompositeSchemaTC(CubicWebTC):
    composites = {
        'BaseTransition': [('condition', 'BaseTransition', 'RQLExpression', 'subject')],
        'CWAttribute': [('add_permission', 'CWAttribute', 'RQLExpression', 'subject'),
                        ('constrained_by', 'CWAttribute', 'CWConstraint', 'subject'),
                        ('read_permission', 'CWAttribute', 'RQLExpression', 'subject'),
                        ('update_permission', 'CWAttribute', 'RQLExpression', 'subject')],
        'CWEType': [('add_permission', 'CWEType', 'RQLExpression', 'subject'),
                    ('constraint_of', 'CWUniqueTogetherConstraint', 'CWEType', 'object'),
                    ('delete_permission', 'CWEType', 'RQLExpression', 'subject'),
                    ('from_entity', 'CWAttribute', 'CWEType', 'object'),
                    ('from_entity', 'CWRelation', 'CWEType', 'object'),
                    ('read_permission', 'CWEType', 'RQLExpression', 'subject'),
                    ('to_entity', 'CWAttribute', 'CWEType', 'object'),
                    ('to_entity', 'CWRelation', 'CWEType', 'object'),
                    ('update_permission', 'CWEType', 'RQLExpression', 'subject')],
        'CWRType': [('relation_type', 'CWAttribute', 'CWRType', 'object'),
                    ('relation_type', 'CWRelation', 'CWRType', 'object')],
        'CWRelation': [('add_permission', 'CWRelation', 'RQLExpression', 'subject'),
                       ('constrained_by', 'CWRelation', 'CWConstraint', 'subject'),
                       ('delete_permission', 'CWRelation', 'RQLExpression', 'subject'),
                       ('read_permission', 'CWRelation', 'RQLExpression', 'subject')],
        'CWComputedRType': [('read_permission', 'CWComputedRType', 'RQLExpression', 'subject')],
        'CWSource': [('cw_host_config_of', 'CWSourceHostConfig', 'CWSource', 'object'),
                     ('cw_import_of', 'CWDataImport', 'CWSource', 'object'),
                     ('cw_source', 'Ami', 'CWSource', 'object'),
                     ('cw_source', 'BaseTransition', 'CWSource', 'object'),
                     ('cw_source', 'Bookmark', 'CWSource', 'object'),
                     ('cw_source', 'CWAttribute', 'CWSource', 'object'),
                     ('cw_source', 'CWComputedRType', 'CWSource', 'object'),
                     ('cw_source', 'CWConstraint', 'CWSource', 'object'),
                     ('cw_source', 'CWConstraintType', 'CWSource', 'object'),
                     ('cw_source', 'CWDataImport', 'CWSource', 'object'),
                     ('cw_source', 'CWEType', 'CWSource', 'object'),
                     ('cw_source', 'CWGroup', 'CWSource', 'object'),
                     ('cw_source', 'CWPermission', 'CWSource', 'object'),
                     ('cw_source', 'CWProperty', 'CWSource', 'object'),
                     ('cw_source', 'CWRType', 'CWSource', 'object'),
                     ('cw_source', 'CWRelation', 'CWSource', 'object'),
                     ('cw_source', 'CWSession', 'CWSource', 'object'),
                     ('cw_source', 'CWSource', 'CWSource', 'object'),
                     ('cw_source', 'CWSourceHostConfig', 'CWSource', 'object'),
                     ('cw_source', 'CWUniqueTogetherConstraint', 'CWSource', 'object'),
                     ('cw_source', 'CWUser', 'CWSource', 'object'),
                     ('cw_source', 'Card', 'CWSource', 'object'),
                     ('cw_source', 'EmailAddress', 'CWSource', 'object'),
                     ('cw_source', 'ExternalUri', 'CWSource', 'object'),
                     ('cw_source', 'FakeFile', 'CWSource', 'object'),
                     ('cw_source', 'Note', 'CWSource', 'object'),
                     ('cw_source', 'Personne', 'CWSource', 'object'),
                     ('cw_source', 'Produit', 'CWSource', 'object'),
                     ('cw_source', 'RQLExpression', 'CWSource', 'object'),
                     ('cw_source', 'Reference', 'CWSource', 'object'),
                     ('cw_source', 'Service', 'CWSource', 'object'),
                     ('cw_source', 'Societe', 'CWSource', 'object'),
                     ('cw_source', 'State', 'CWSource', 'object'),
                     ('cw_source', 'StateFull', 'CWSource', 'object'),
                     ('cw_source', 'SubNote', 'CWSource', 'object'),
                     ('cw_source', 'SubWorkflowExitPoint', 'CWSource', 'object'),
                     ('cw_source', 'Tag', 'CWSource', 'object'),
                     ('cw_source', 'TrInfo', 'CWSource', 'object'),
                     ('cw_source', 'Transition', 'CWSource', 'object'),
                     ('cw_source', 'Usine', 'CWSource', 'object'),
                     ('cw_source', 'Workflow', 'CWSource', 'object'),
                     ('cw_source', 'WorkflowTransition', 'CWSource', 'object')],
        'CWUser': [('for_user', 'CWProperty', 'CWUser', 'object'),
                   ('use_email', 'CWUser', 'EmailAddress', 'subject'),
                   ('wf_info_for', 'TrInfo', 'CWUser', 'object')],
        'StateFull': [('wf_info_for', 'TrInfo', 'StateFull', 'object')],
        'Transition': [('condition', 'Transition', 'RQLExpression', 'subject')],
        'Workflow': [('state_of', 'State', 'Workflow', 'object'),
                     ('transition_of', 'BaseTransition', 'Workflow', 'object'),
                     ('transition_of', 'Transition', 'Workflow', 'object'),
                     ('transition_of', 'WorkflowTransition', 'Workflow', 'object')],
        'WorkflowTransition': [
            ('condition', 'WorkflowTransition', 'RQLExpression', 'subject'),
            ('subworkflow_exit', 'WorkflowTransition', 'SubWorkflowExitPoint', 'subject')
        ]
    }

    def test_composite_entities(self):
        schema = self.vreg.schema
        self.assertEqual(sorted(self.composites),
                         [eschema.type for eschema in sorted(schema.entities())
                          if eschema.is_composite])
        for etype in self.composites:
            with self.subTest(etype=etype):
                self.assertEqual(self.composites[etype],
                                 sorted([(r.rtype.type, r.subject.type, r.object.type, role)
                                         for r, role in schema[etype].composite_rdef_roles]))


if __name__ == '__main__':
    unittest_main()
