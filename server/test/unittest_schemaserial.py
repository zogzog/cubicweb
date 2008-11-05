"""unit tests for schema rql (de)serialization
"""

import sys
from cStringIO import StringIO

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.schema import CubicWebSchemaLoader
from cubicweb.devtools import TestServerConfiguration

loader = CubicWebSchemaLoader()
config = TestServerConfiguration('data')
config.bootstrap_cubes()
loader.lib_directory = config.schemas_lib_dir()
schema = loader.load(config)

from cubicweb.server.schemaserial import *
    
class Schema2RQLTC(TestCase):
        
    def test_eschema2rql1(self):
        self.assertListEquals(list(eschema2rql(schema.eschema('EFRDef'))),
                              [
            ('INSERT EEType X: X description %(description)s,X final %(final)s,X meta %(meta)s,X name %(name)s',
             {'description': u'define a final relation: link a final relation type from a non final entity to a final entity type. used to build the application schema',
              'meta': True, 'name': u'EFRDef', 'final': False})
            ])
        
    def test_eschema2rql2(self):
        self.assertListEquals(list(eschema2rql(schema.eschema('String'))), [
                ('INSERT EEType X: X description %(description)s,X final %(final)s,X meta %(meta)s,X name %(name)s',
                 {'description': u'', 'final': True, 'meta': True, 'name': u'String'})])
    
    def test_eschema2rql_specialization(self):
        self.assertListEquals(list(specialize2rql(schema)),
                              [
                ('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                 {'x': 'Division', 'et': 'Societe'}),
                ('SET X specializes ET WHERE X name %(x)s, ET name %(et)s',
                 {'x': 'SubDivision', 'et': 'Division'})])
        
    def test_rschema2rql1(self):
        self.assertListEquals(list(rschema2rql(schema.rschema('relation_type'))),
                             [
            ('INSERT ERType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X meta %(meta)s,X name %(name)s,X symetric %(symetric)s',
             {'description': u'link a relation definition to its relation type', 'meta': True, 'symetric': False, 'name': u'relation_type', 'final' : False, 'fulltext_container': None, 'inlined': True}),
            ('INSERT ENFRDef X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'relation_type', 'description': u'', 'composite': u'object', 'oe': 'ERType',
              'ordernum': 1, 'cardinality': u'1*', 'se': 'EFRDef'}),
            ('INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is ENFRDef',
             {'rt': 'relation_type', 'oe': 'ERType', 'ctname': u'RQLConstraint', 'se': 'EFRDef', 'value': u'O final TRUE'}),
            ('INSERT ENFRDef X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'relation_type', 'description': u'', 'composite': u'object', 'oe': 'ERType',
              'ordernum': 1, 'cardinality': u'1*', 'se': 'ENFRDef'}),
            ('INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is ENFRDef',
             {'rt': 'relation_type', 'oe': 'ERType', 'ctname': u'RQLConstraint', 'se': 'ENFRDef', 'value': u'O final FALSE'}),
            ])
        
    def test_rschema2rql2(self):
        expected = [
            ('INSERT ERType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X meta %(meta)s,X name %(name)s,X symetric %(symetric)s', {'description': u'core relation giving to a group the permission to add an entity or relation type', 'meta': True, 'symetric': False, 'name': u'add_permission', 'final': False, 'fulltext_container': None, 'inlined': False}),
            ('INSERT ENFRDef X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'rql expression allowing to add entities/relations of this type', 'composite': 'subject', 'oe': 'RQLExpression', 'ordernum': 5, 'cardinality': u'*?', 'se': 'EEType'}),
            ('INSERT ENFRDef X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'rql expression allowing to add entities/relations of this type', 'composite': 'subject', 'oe': 'RQLExpression', 'ordernum': 5, 'cardinality': u'*?', 'se': 'ERType'}),
            
            ('INSERT ENFRDef X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'groups allowed to add entities/relations of this type', 'composite': None, 'oe': 'EGroup', 'ordernum': 3, 'cardinality': u'**', 'se': 'EEType'}),
            ('INSERT ENFRDef X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'add_permission', 'description': u'groups allowed to add entities/relations of this type', 'composite': None, 'oe': 'EGroup', 'ordernum': 3, 'cardinality': u'**', 'se': 'ERType'}),
            ]
        for i, (rql, args) in enumerate(rschema2rql(schema.rschema('add_permission'))):
            yield self.assertEquals, (rql, args), expected[i]
        
    def test_rschema2rql3(self):
        self.assertListEquals(list(rschema2rql(schema.rschema('cardinality'))), 
                             [
            ('INSERT ERType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X meta %(meta)s,X name %(name)s,X symetric %(symetric)s',
             {'description': u'', 'meta': False, 'symetric': False, 'name': u'cardinality', 'final': True, 'fulltext_container': None, 'inlined': False}),

            ('INSERT EFRDef X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'cardinality', 'description': u'subject/object cardinality', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 5, 'defaultval': None, 'indexed': False, 'cardinality': u'?1', 'oe': 'String', 'se': 'EFRDef'}),
            ('INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is EFRDef',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'SizeConstraint', 'se': 'EFRDef', 'value': u'max=2'}),
            ('INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is EFRDef',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'StaticVocabularyConstraint', 'se': 'EFRDef', 'value': u"u'?1', u'11', u'??', u'1?'"}),

            ('INSERT EFRDef X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE name %(se)s,ER name %(rt)s,OE name %(oe)s',
             {'rt': 'cardinality', 'description': u'subject/object cardinality', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 5, 'defaultval': None, 'indexed': False, 'cardinality': u'?1', 'oe': 'String', 'se': 'ENFRDef'}),
            ('INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is EFRDef',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'SizeConstraint', 'se': 'ENFRDef', 'value': u'max=2'}),
            ('INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, ER name %(rt)s, SE name %(se)s, OE name %(oe)s, EDEF is EFRDef',
             {'rt': 'cardinality', 'oe': 'String', 'ctname': u'StaticVocabularyConstraint', 'se': 'ENFRDef', 'value': u"u'?*', u'1*', u'+*', u'**', u'?+', u'1+', u'++', u'*+', u'?1', u'11', u'+1', u'*1', u'??', u'1?', u'+?', u'*?'"}),
            ])
        

    def test_updateeschema2rql1(self):
        self.assertListEquals(list(updateeschema2rql(schema.eschema('EFRDef'))),
                              [('SET X description %(description)s,X final %(final)s,X meta %(meta)s,X name %(name)s WHERE X is EEType, X name %(et)s',
                                {'description': u'define a final relation: link a final relation type from a non final entity to a final entity type. used to build the application schema', 'meta': True, 'et': 'EFRDef', 'final': False, 'name': u'EFRDef'}),
                               ])
        
    def test_updateeschema2rql2(self):
        self.assertListEquals(list(updateeschema2rql(schema.eschema('String'))),
                              [('SET X description %(description)s,X final %(final)s,X meta %(meta)s,X name %(name)s WHERE X is EEType, X name %(et)s',
                                {'description': u'', 'meta': True, 'et': 'String', 'final': True, 'name': u'String'})
                               ])
        
    def test_updaterschema2rql1(self):
        self.assertListEquals(list(updaterschema2rql(schema.rschema('relation_type'))),
                             [
            ('SET X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X meta %(meta)s,X name %(name)s,X symetric %(symetric)s WHERE X is ERType, X name %(rt)s',
             {'rt': 'relation_type', 'symetric': False,
              'description': u'link a relation definition to its relation type',
              'meta': True, 'final': False, 'fulltext_container': None, 'inlined': True, 'name': u'relation_type'})
            ])
        
    def test_updaterschema2rql2(self):
        expected = [
            ('SET X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X meta %(meta)s,X name %(name)s,X symetric %(symetric)s WHERE X is ERType, X name %(rt)s',
             {'rt': 'add_permission', 'symetric': False,
              'description': u'core relation giving to a group the permission to add an entity or relation type',
              'meta': True, 'final': False, 'fulltext_container': None, 'inlined': False, 'name': u'add_permission'})
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
        self.assertListEquals([rql for rql, kwargs in erperms2rql(schema.eschema('EEType'), self.GROUP_MAPPING)],
                              ['SET X read_permission Y WHERE X is EEType, X name "EEType", Y eid 2',
                               'SET X read_permission Y WHERE X is EEType, X name "EEType", Y eid 0',
                               'SET X read_permission Y WHERE X is EEType, X name "EEType", Y eid 1',
                               'SET X add_permission Y WHERE X is EEType, X name "EEType", Y eid 0',
                               'SET X update_permission Y WHERE X is EEType, X name "EEType", Y eid 0',
                               'SET X update_permission Y WHERE X is EEType, X name "EEType", Y eid 3',
                               'SET X delete_permission Y WHERE X is EEType, X name "EEType", Y eid 0',
                               ])
        
    def test_rperms2rql2(self):
        self.assertListEquals([rql for rql, kwargs in erperms2rql(schema.rschema('read_permission'), self.GROUP_MAPPING)],
                              ['SET X read_permission Y WHERE X is ERType, X name "read_permission", Y eid 2',
                               'SET X read_permission Y WHERE X is ERType, X name "read_permission", Y eid 0',
                               'SET X read_permission Y WHERE X is ERType, X name "read_permission", Y eid 1',
                               'SET X add_permission Y WHERE X is ERType, X name "read_permission", Y eid 0',
                               'SET X delete_permission Y WHERE X is ERType, X name "read_permission", Y eid 0',
                               ])
        
    def test_rperms2rql3(self):
        self.assertListEquals([rql for rql, kwargs in erperms2rql(schema.rschema('name'), self.GROUP_MAPPING)],
                              ['SET X read_permission Y WHERE X is ERType, X name "name", Y eid 2',
                               'SET X read_permission Y WHERE X is ERType, X name "name", Y eid 0',
                               'SET X read_permission Y WHERE X is ERType, X name "name", Y eid 1',
                               'SET X add_permission Y WHERE X is ERType, X name "name", Y eid 2',
                               'SET X add_permission Y WHERE X is ERType, X name "name", Y eid 0',
                               'SET X add_permission Y WHERE X is ERType, X name "name", Y eid 1',
                               'SET X delete_permission Y WHERE X is ERType, X name "name", Y eid 2',
                               'SET X delete_permission Y WHERE X is ERType, X name "name", Y eid 0',
                               'SET X delete_permission Y WHERE X is ERType, X name "name", Y eid 1',
                               ])
        
    #def test_perms2rql(self):
    #    self.assertListEquals(perms2rql(schema, self.GROUP_MAPPING),
    #                         ['INSERT EEType X: X name 'Societe', X final FALSE'])
        


if __name__ == '__main__':
    unittest_main()
