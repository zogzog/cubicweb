"""unit tests for schema rql (de)serialization
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import sys
from cStringIO import StringIO

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.schema import CubicWebSchemaLoader
from cubicweb.devtools import TestServerConfiguration

loader = CubicWebSchemaLoader()
config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = loader.load(config)

from cubicweb.server.schemaserial import *
from cubicweb.server.schemaserial import _erperms2rql as erperms2rql

class Schema2RQLTC(TestCase):

    def test_eschema2rql1(self):
        self.assertListEquals(list(eschema2rql(schema.eschema('CWAttribute'))),
                              [
            ('INSERT CWEType X: X description %(description)s,X final %(final)s,X name %(name)s',
             {'description': u'define a final relation: link a final relation type from a non final entity to a final entity type. used to build the instance schema',
              'name': u'CWAttribute', 'final': False})
            ])

    def test_eschema2rql2(self):
        self.assertListEquals(list(eschema2rql(schema.eschema('String'))), [
                ('INSERT CWEType X: X description %(description)s,X final %(final)s,X name %(name)s',
                 {'description': u'', 'final': True, 'name': u'String'})])

    def test_eschema2rql_specialization(self):
        self.assertListEquals(sorted(specialize2rql(schema)),
                              [('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                                {'et': 'BaseTransition', 'x': 'Transition'}),
                               ('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                                {'et': 'BaseTransition', 'x': 'WorkflowTransition'}),
                               ('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                                {'et': 'Division', 'x': 'SubDivision'}),
                               # ('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                               #  {'et': 'File', 'x': 'Image'}),
                               ('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                                {'et': 'Societe', 'x': 'Division'})])

    def test_rschema2rql1(self):
        self.assertListEquals(list(rschema2rql(schema.rschema('relation_type'))),
                             [
            ('INSERT CWRType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s',
             {'description': u'link a relation definition to its relation type', 'symmetric': False, 'name': u'relation_type', 'final' : False, 'fulltext_container': None, 'inlined': True}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'relation_type', 'description': u'', 'composite': u'object', 'oe': 'CWRType',
              'ordernum': 1, 'cardinality': u'1*', 'se': 'CWAttribute'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is CWRelation',
             {'rt': 'relation_type', 'oe': 'CWRType', 'ctname': u'RQLConstraint', 'se': 'CWAttribute', 'value': u';O;O final TRUE\n'}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'relation_type', 'description': u'', 'composite': u'object', 'oe': 'CWRType',
              'ordernum': 1, 'cardinality': u'1*', 'se': 'CWRelation'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is CWRelation',
             {'rt': 'relation_type', 'oe': 'CWRType', 'ctname': u'RQLConstraint', 'se': 'CWRelation', 'value': u';O;O final FALSE\n'}),
            ])

    def test_rschema2rql2(self):
        self.assertListEquals(list(rschema2rql(schema.rschema('add_permission'))),
                              [
            ('INSERT CWRType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s', {'description': u'', 'symmetric': False, 'name': u'add_permission', 'final': False, 'fulltext_container': None, 'inlined': False}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'groups allowed to add entities/relations of this type', 'composite': None, 'oe': 'CWGroup', 'ordernum': 9999, 'cardinality': u'**', 'se': 'CWEType'}),
            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'rql expression allowing to add entities/relations of this type', 'composite': 'subject', 'oe': 'RQLExpression', 'ordernum': 9999, 'cardinality': u'*?', 'se': 'CWEType'}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'groups allowed to add entities/relations of this type', 'composite': None, 'oe': 'CWGroup', 'ordernum': 9999, 'cardinality': u'**', 'se': 'CWRelation'}),
            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'rql expression allowing to add entities/relations of this type', 'composite': 'subject', 'oe': 'RQLExpression', 'ordernum': 9999, 'cardinality': u'*?', 'se': 'CWRelation'}),
            ])

    def test_rschema2rql3(self):
        self.assertListEquals(list(rschema2rql(schema.rschema('cardinality'))),
                             [
            ('INSERT CWRType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s',
             {'description': u'', 'symmetric': False, 'name': u'cardinality', 'final': True, 'fulltext_container': None, 'inlined': False}),

            ('INSERT CWAttribute X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'cardinality', 'description': u'subject/object cardinality', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 5, 'defaultval': None, 'indexed': False, 'cardinality': u'?1', 'oe': 'String', 'se': 'CWAttribute'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is CWAttribute',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'SizeConstraint', 'se': 'CWAttribute', 'value': u'max=2'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is CWAttribute',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'StaticVocabularyConstraint', 'se': 'CWAttribute', 'value': u"u'?1', u'11'"}),

            ('INSERT CWAttribute X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'cardinality', 'description': u'subject/object cardinality', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 5, 'defaultval': None, 'indexed': False, 'cardinality': u'?1', 'oe': 'String', 'se': 'CWRelation'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is CWAttribute',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'SizeConstraint', 'se': 'CWRelation', 'value': u'max=2'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is CWAttribute',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'StaticVocabularyConstraint', 'se': 'CWRelation', 'value': u"u'?*', u'1*', u'+*', u'**', u'?+', u'1+', u'++', u'*+', u'?1', u'11', u'+1', u'*1', u'??', u'1?', u'+?', u'*?'"}),
            ])


    def test_updateeschema2rql1(self):
        self.assertListEquals(list(updateeschema2rql(schema.eschema('CWAttribute'))),
                              [('SET X description %(description)s,X final %(final)s,X name %(name)s WHERE X is CWEType, X name %(et)s',
                                {'description': u'define a final relation: link a final relation type from a non final entity to a final entity type. used to build the instance schema', 'et': 'CWAttribute', 'final': False, 'name': u'CWAttribute'}),
                               ])

    def test_updateeschema2rql2(self):
        self.assertListEquals(list(updateeschema2rql(schema.eschema('String'))),
                              [('SET X description %(description)s,X final %(final)s,X name %(name)s WHERE X is CWEType, X name %(et)s',
                                {'description': u'', 'et': 'String', 'final': True, 'name': u'String'})
                               ])

    def test_updaterschema2rql1(self):
        self.assertListEquals(list(updaterschema2rql(schema.rschema('relation_type'))),
                             [
            ('SET X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s WHERE X is CWRType, X name %(rt)s',
             {'rt': 'relation_type', 'symmetric': False,
              'description': u'link a relation definition to its relation type',
              'final': False, 'fulltext_container': None, 'inlined': True, 'name': u'relation_type'})
            ])

    def test_updaterschema2rql2(self):
        expected = [
            ('SET X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s WHERE X is CWRType, X name %(rt)s',
             {'rt': 'add_permission', 'symmetric': False,
              'description': u'', 'final': False, 'fulltext_container': None,
              'inlined': False, 'name': u'add_permission'})
            ]
        for i, (rql, args) in enumerate(updaterschema2rql(schema.rschema('add_permission'))):
            yield self.assertEquals, (rql, args), expected[i]

class Perms2RQLTC(TestCase):
    GROUP_MAPPING = {
        'managers': 0,
        'users':  1,
        'guests': 2,
        'owners': 3,
        }

    def test_eperms2rql1(self):
        self.assertListEquals([(rql, kwargs) for rql, kwargs in erperms2rql(schema.eschema('CWEType'), self.GROUP_MAPPING)],
                              [('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 1}),
                               ('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 2}),
                               ('SET X add_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('SET X update_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('SET X update_permission Y WHERE Y eid %(g)s, ', {'g': 3}),
                               ('SET X delete_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ])

    def test_rperms2rql2(self):
        self.assertListEquals([(rql, kwargs) for rql, kwargs in erperms2rql(schema.rschema('read_permission').rdef('CWEType', 'CWGroup'), self.GROUP_MAPPING)],
                              [('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 1}),
                               ('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 2}),
                               ('SET X add_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('SET X delete_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ])

    def test_rperms2rql3(self):
        self.assertListEquals([(rql, kwargs) for rql, kwargs in erperms2rql(schema.rschema('name').rdef('CWEType', 'String'), self.GROUP_MAPPING)],
                              [('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 1}),
                               ('SET X read_permission Y WHERE Y eid %(g)s, ', {'g': 2}),
                               ('SET X update_permission Y WHERE Y eid %(g)s, ', {'g': 0}),
                               ('INSERT RQLExpression E: '
                                'E expression %(e)s, E exprtype %(t)s, E mainvars %(v)s, '
                                'X update_permission E '
                                'WHERE ', # completed by the outer function
                                {'e': u'U has_update_permission X', 't': u'ERQLExpression', 'v': u'X'}),
                               ])

    #def test_perms2rql(self):
    #    self.assertListEquals(perms2rql(schema, self.GROUP_MAPPING),
    #                         ['INSERT CWEType X: X name 'Societe', X final FALSE'])



if __name__ == '__main__':
    unittest_main()
