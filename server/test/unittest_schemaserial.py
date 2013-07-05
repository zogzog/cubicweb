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
"""unit tests for schema rql (de)serialization"""

import sys
from cStringIO import StringIO

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.schema import CubicWebSchemaLoader
from cubicweb.devtools import TestServerConfiguration

from logilab.database import get_db_helper
from yams import register_base_type, unregister_base_type

schema = config = None
def setUpModule(*args):
    register_base_type('BabarTestType', ('jungle_speed',))
    helper = get_db_helper('sqlite')
    helper.TYPE_MAPPING['BabarTestType'] = 'TEXT'
    helper.TYPE_CONVERTERS['BabarTestType'] = lambda x: '"%s"' % x

    global schema, config
    loader = CubicWebSchemaLoader()
    apphome = Schema2RQLTC.datadir + '-schemaserial'
    config = TestServerConfiguration('data', apphome=apphome)
    config.bootstrap_cubes()
    schema = loader.load(config)


def tearDownModule(*args):
    global schema, config
    schema = config = None

    unregister_base_type('BabarTestType')
    helper = get_db_helper('sqlite')
    helper.TYPE_MAPPING.pop('BabarTestType', None)
    helper.TYPE_CONVERTERS.pop('BabarTestType', None)

from cubicweb.server.schemaserial import *
from cubicweb.server.schemaserial import _erperms2rql as erperms2rql

cstrtypemap = {'RQLConstraint': 'RQLConstraint_eid',
               'SizeConstraint': 'SizeConstraint_eid',
               'StaticVocabularyConstraint': 'StaticVocabularyConstraint_eid',
               'FormatConstraint': 'FormatConstraint_eid',
               }

class Schema2RQLTC(TestCase):

    def test_eschema2rql1(self):
        self.assertListEqual([
            ('INSERT CWEType X: X description %(description)s,X final %(final)s,X name %(name)s',
             {'description': u'define a final relation: link a final relation type from a non final entity to a final entity type. used to build the instance schema',
              'name': u'CWAttribute', 'final': False})],
                             list(eschema2rql(schema.eschema('CWAttribute'))))

    def test_eschema2rql2(self):
        self.assertListEqual([
                ('INSERT CWEType X: X description %(description)s,X final %(final)s,X name %(name)s',
                 {'description': u'', 'final': True, 'name': u'String'})],
                             list(eschema2rql(schema.eschema('String'))))

    def test_eschema2rql_specialization(self):
        # x: None since eschema.eid are None
        self.assertListEqual([('SET X specializes ET WHERE X eid %(x)s, ET eid %(et)s',
                               {'et': None, 'x': None}),
                              ('SET X specializes ET WHERE X eid %(x)s, ET eid %(et)s',
                               {'et': None, 'x': None}),
                              ('SET X specializes ET WHERE X eid %(x)s, ET eid %(et)s',
                               {'et': None, 'x': None}),
                              ('SET X specializes ET WHERE X eid %(x)s, ET eid %(et)s',
                               {'et': None, 'x': None})],
                             sorted(specialize2rql(schema)))

    def test_esche2rql_custom_type(self):
        expected = [('INSERT CWEType X: X description %(description)s,X final %(final)s,X name %(name)s',
                     {'description': u'',
                     'name': u'BabarTestType', 'final': True},)]
        got = list(eschema2rql(schema.eschema('BabarTestType')))
        self.assertListEqual(expected, got)

    def test_rschema2rql1(self):
        self.assertListEqual([
            ('INSERT CWRType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s',
             {'description': u'link a relation definition to its relation type', 'symmetric': False, 'name': u'relation_type', 'final' : False, 'fulltext_container': None, 'inlined': True}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'', 'composite': u'object', 'cardinality': u'1*',
              'ordernum': 1}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'ct': u'RQLConstraint_eid', 'value': u';O;O final TRUE\n'}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'', 'composite': u'object', 
              'ordernum': 1, 'cardinality': u'1*'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'ct': u'RQLConstraint_eid', 'value': u';O;O final FALSE\n'}),
        ],
                             list(rschema2rql(schema.rschema('relation_type'), cstrtypemap)))

    def test_rschema2rql2(self):
        self.assertListEqual([
            ('INSERT CWRType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s', {'description': u'', 'symmetric': False, 'name': u'add_permission', 'final': False, 'fulltext_container': None, 'inlined': False}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'groups allowed to add entities/relations of this type', 'composite': None, 'ordernum': 9999, 'cardinality': u'**'}),
            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'rql expression allowing to add entities/relations of this type', 'composite': 'subject', 'ordernum': 9999, 'cardinality': u'*?'}),

            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'groups allowed to add entities/relations of this type', 'composite': None, 'ordernum': 9999, 'cardinality': u'**'}),
            ('INSERT CWRelation X: X cardinality %(cardinality)s,X composite %(composite)s,X description %(description)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'rql expression allowing to add entities/relations of this type', 'composite': 'subject', 'ordernum': 9999, 'cardinality': u'*?'})],
                             list(rschema2rql(schema.rschema('add_permission'), cstrtypemap)))

    def test_rschema2rql3(self):
        self.assertListEqual([
            ('INSERT CWRType X: X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s',
             {'description': u'', 'symmetric': False, 'name': u'cardinality', 'final': True, 'fulltext_container': None, 'inlined': False}),

            ('INSERT CWAttribute X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'subject/object cardinality', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 5, 'defaultval': None, 'indexed': False, 'cardinality': u'?1'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'ct': u'SizeConstraint_eid', 'value': u'max=2'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'ct': u'StaticVocabularyConstraint_eid', 'value': u"u'?1', u'11'"}),

            ('INSERT CWAttribute X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'subject/object cardinality', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 5, 'defaultval': None, 'indexed': False, 'cardinality': u'?1'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'ct': u'SizeConstraint_eid', 'value': u'max=2'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'ct': u'StaticVocabularyConstraint_eid', 'value': u"u'?*', u'1*', u'+*', u'**', u'?+', u'1+', u'++', u'*+', u'?1', u'11', u'+1', u'*1', u'??', u'1?', u'+?', u'*?'"})],
                             list(rschema2rql(schema.rschema('cardinality'), cstrtypemap)))

    def test_rschema2rql_custom_type(self):
        expected = [('INSERT CWRType X: X description %(description)s,X final %(final)s,'
                     'X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,'
                     'X name %(name)s,X symmetric %(symmetric)s',
                     {'description': u'',
                      'final': True,
                      'fulltext_container': None,
                      'inlined': False,
                      'name': u'custom_field_of_jungle',
                      'symmetric': False}),
                     ('INSERT CWAttribute X: X cardinality %(cardinality)s,'
                      'X defaultval %(defaultval)s,X description %(description)s,'
                      'X extra_props %(extra_props)s,X indexed %(indexed)s,'
                      'X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,'
                      'X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
                      {'cardinality': u'?1',
                       'defaultval': None,
                       'description': u'',
                       'extra_props': '{"jungle_speed": 42}',
                       'indexed': False,
                       'oe': None,
                       'ordernum': 19,
                       'rt': None,
                       'se': None})]

        got = list(rschema2rql(schema.rschema('custom_field_of_jungle'), cstrtypemap))
        self.assertEqual(2, len(got))
        # this is a custom type attribute with an extra parameter
        self.assertIn('extra_props', got[1][1])
        # this extr
        extra_props = got[1][1]['extra_props']
        from cubicweb import Binary
        self.assertIsInstance(extra_props, Binary)
        got[1][1]['extra_props'] = got[1][1]['extra_props'].getvalue()
        self.assertListEqual(expected, got)

    def test_rdef2rql(self):
        self.assertListEqual([
            ('INSERT CWAttribute X: X cardinality %(cardinality)s,X defaultval %(defaultval)s,X description %(description)s,X fulltextindexed %(fulltextindexed)s,X indexed %(indexed)s,X internationalizable %(internationalizable)s,X ordernum %(ordernum)s,X relation_type ER,X from_entity SE,X to_entity OE WHERE SE eid %(se)s,ER eid %(rt)s,OE eid %(oe)s',
             {'se': None, 'rt': None, 'oe': None,
              'description': u'', 'internationalizable': True, 'fulltextindexed': False, 'ordernum': 3, 'defaultval': u'text/plain', 'indexed': False, 'cardinality': u'?1'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'value': u'None', 'ct': 'FormatConstraint_eid'}),
            ('INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE CT eid %(ct)s, EDEF eid %(x)s',
             {'x': None, 'value': u'max=50', 'ct': 'SizeConstraint_eid'})],
                             list(rdef2rql(schema['description_format'].rdefs[('CWRType', 'String')], cstrtypemap)))


    def test_updateeschema2rql1(self):
        self.assertListEqual([('SET X description %(description)s,X final %(final)s,X name %(name)s WHERE X eid %(x)s',
                               {'description': u'define a final relation: link a final relation type from a non final entity to a final entity type. used to build the instance schema', 'x': 1, 'final': False, 'name': u'CWAttribute'})],
                             list(updateeschema2rql(schema.eschema('CWAttribute'), 1)))

    def test_updateeschema2rql2(self):
        self.assertListEqual([('SET X description %(description)s,X final %(final)s,X name %(name)s WHERE X eid %(x)s',
                               {'description': u'', 'x': 1, 'final': True, 'name': u'String'})],
                             list(updateeschema2rql(schema.eschema('String'), 1)))

    def test_updaterschema2rql1(self):
        self.assertListEqual([
            ('SET X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s WHERE X eid %(x)s',
             {'x': 1, 'symmetric': False,
              'description': u'link a relation definition to its relation type',
              'final': False, 'fulltext_container': None, 'inlined': True, 'name': u'relation_type'})],
                             list(updaterschema2rql(schema.rschema('relation_type'), 1)))

    def test_updaterschema2rql2(self):
        expected = [
            ('SET X description %(description)s,X final %(final)s,X fulltext_container %(fulltext_container)s,X inlined %(inlined)s,X name %(name)s,X symmetric %(symmetric)s WHERE X eid %(x)s',
             {'x': 1, 'symmetric': False,
              'description': u'', 'final': False, 'fulltext_container': None,
              'inlined': False, 'name': u'add_permission'})
            ]
        for i, (rql, args) in enumerate(updaterschema2rql(schema.rschema('add_permission'), 1)):
            yield self.assertEqual, expected[i], (rql, args)

class Perms2RQLTC(TestCase):
    GROUP_MAPPING = {
        'managers': 0,
        'users':  1,
        'guests': 2,
        'owners': 3,
        }

    def test_eperms2rql1(self):
        self.assertListEqual([('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0}),
                              ('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 1}),
                              ('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 2}),
                              ('SET X add_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0}),
                              ('SET X update_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0}),
                              ('SET X delete_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0})],
                             [(rql, kwargs)
                              for rql, kwargs in erperms2rql(schema.eschema('CWEType'), self.GROUP_MAPPING)])

    def test_rperms2rql2(self):
        self.assertListEqual([('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0}),
                              ('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 1}),
                              ('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 2}),
                              ('SET X add_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0}),
                              ('SET X delete_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0})],
                             [(rql, kwargs)
                              for rql, kwargs in erperms2rql(schema.rschema('read_permission').rdef('CWEType', 'CWGroup'),
                                                             self.GROUP_MAPPING)])

    def test_rperms2rql3(self):
        self.assertListEqual([('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0}),
                              ('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 1}),
                              ('SET X read_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 2}),
                              ('SET X update_permission Y WHERE Y eid %(g)s, X eid %(x)s', {'g': 0})],
                             [(rql, kwargs)
                              for rql, kwargs in erperms2rql(schema.rschema('name').rdef('CWEType', 'String'),
                                                             self.GROUP_MAPPING)])

    #def test_perms2rql(self):
    #    self.assertListEqual(perms2rql(schema, self.GROUP_MAPPING),
    #                         ['INSERT CWEType X: X name 'Societe', X final FALSE'])



if __name__ == '__main__':
    unittest_main()
