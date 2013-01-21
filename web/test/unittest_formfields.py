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
"""unittests for cw.web.formfields"""

from logilab.common.testlib import TestCase, unittest_main, mock_object as mock

from yams.constraints import StaticVocabularyConstraint, SizeConstraint

from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.formwidgets import PasswordInput, TextArea, Select, Radio
from cubicweb.web.formfields import *
from cubicweb.web.views.forms import EntityFieldsForm

from cubes.file.entities import File

def setUpModule(*args):
    global schema
    config = TestServerConfiguration('data', apphome=GuessFieldTC.datadir)
    config.bootstrap_cubes()
    schema = config.load_schema()

class GuessFieldTC(CubicWebTC):

    def setUp(self):
        super(GuessFieldTC, self).setUp()
        self.req = self.request()

    def test_state_fields(self):
        title_field = guess_field(schema['State'], schema['name'], req=self.req)
        self.assertIsInstance(title_field, StringField)
        self.assertEqual(title_field.required, True)

#         synopsis_field = guess_field(schema['State'], schema['synopsis'])
#         self.assertIsInstance(synopsis_field, StringField)
#         self.assertIsInstance(synopsis_field.widget, TextArea)
#         self.assertEqual(synopsis_field.required, False)
#         self.assertEqual(synopsis_field.help, 'an abstract for this state')

        description_field = guess_field(schema['State'], schema['description'], req=self.req)
        self.assertIsInstance(description_field, RichTextField)
        self.assertEqual(description_field.required, False)
        self.assertEqual(description_field.format_field, None)

        # description_format_field = guess_field(schema['State'], schema['description_format'])
        # self.assertEqual(description_format_field, None)

        description_format_field = guess_field(schema['State'], schema['description_format'],
                                               req=self.req)
        self.assertEqual(description_format_field.internationalizable, True)
        self.assertEqual(description_format_field.sort, True)

#         wikiid_field = guess_field(schema['State'], schema['wikiid'])
#         self.assertIsInstance(wikiid_field, StringField)
#         self.assertEqual(wikiid_field.required, False)


    def test_cwuser_fields(self):
        upassword_field = guess_field(schema['CWUser'], schema['upassword'], req=self.req)
        self.assertIsInstance(upassword_field, StringField)
        self.assertIsInstance(upassword_field.widget, PasswordInput)
        self.assertEqual(upassword_field.required, True)

        last_login_time_field = guess_field(schema['CWUser'], schema['last_login_time'], req=self.req)
        self.assertIsInstance(last_login_time_field, DateTimeField)
        self.assertEqual(last_login_time_field.required, False)

        in_group_field = guess_field(schema['CWUser'], schema['in_group'], req=self.req)
        self.assertIsInstance(in_group_field, RelationField)
        self.assertEqual(in_group_field.required, True)
        self.assertEqual(in_group_field.role, 'subject')
        self.assertEqual(in_group_field.help, 'groups grant permissions to the user')

        owned_by_field = guess_field(schema['CWUser'], schema['owned_by'], 'object', req=self.req)
        self.assertIsInstance(owned_by_field, RelationField)
        self.assertEqual(owned_by_field.required, False)
        self.assertEqual(owned_by_field.role, 'object')


    def test_file_fields(self):
        # data_format_field = guess_field(schema['File'], schema['data_format'])
        # self.assertEqual(data_format_field, None)
        # data_encoding_field = guess_field(schema['File'], schema['data_encoding'])
        # self.assertEqual(data_encoding_field, None)
        # data_name_field = guess_field(schema['File'], schema['data_name'])
        # self.assertEqual(data_name_field, None)

        data_field = guess_field(schema['File'], schema['data'], req=self.req)
        self.assertIsInstance(data_field, FileField)
        self.assertEqual(data_field.required, True)
        self.assertIsInstance(data_field.format_field, StringField)
        self.assertIsInstance(data_field.encoding_field, StringField)
        self.assertIsInstance(data_field.name_field, StringField)

    def test_constraints_priority(self):
        salesterm_field = guess_field(schema['Salesterm'], schema['reason'], req=self.req)
        constraints = schema['reason'].rdef('Salesterm', 'String').constraints
        self.assertEqual([c.__class__ for c in constraints],
                          [SizeConstraint, StaticVocabularyConstraint])
        self.assertIsInstance(salesterm_field, StringField)
        self.assertIsInstance(salesterm_field.widget, Select)


    def test_bool_field_base(self):
        field = guess_field(schema['CWAttribute'], schema['indexed'], req=self.req)
        self.assertIsInstance(field, BooleanField)
        self.assertEqual(field.required, False)
        self.assertIsInstance(field.widget, Radio)
        self.assertEqual(field.vocabulary(mock(_cw=mock(_=unicode))),
                          [(u'yes', '1'), (u'no', '')])

    def test_bool_field_explicit_choices(self):
        field = guess_field(schema['CWAttribute'], schema['indexed'],
                            choices=[(u'maybe', '1'), (u'no', '')], req=self.req)
        self.assertIsInstance(field.widget, Radio)
        self.assertEqual(field.vocabulary(mock(req=mock(_=unicode))),
                          [(u'maybe', '1'), (u'no', '')])


class MoreFieldsTC(CubicWebTC):
    def test_rtf_format_field(self):
        req = self.request()
        req.use_fckeditor = lambda: False
        e = self.vreg['etypes'].etype_class('State')(req)
        form = EntityFieldsForm(req, entity=e)
        description_field = guess_field(schema['State'], schema['description'])
        description_format_field = description_field.get_format_field(form)
        self.assertEqual(description_format_field.internationalizable, True)
        self.assertEqual(description_format_field.sort, True)
        # unlike below, initial is bound to form.form_field_format
        self.assertEqual(description_format_field.value(form), 'text/html')
        self.execute('INSERT CWProperty X: X pkey "ui.default-text-format", X value "text/rest", X for_user U WHERE U login "admin"')
        self.commit()
        self.assertEqual(description_format_field.value(form), 'text/rest')


    def test_property_key_field(self):
        from cubicweb.web.views.cwproperties import PropertyKeyField
        req = self.request()
        field = PropertyKeyField(name='test')
        e = self.vreg['etypes'].etype_class('CWProperty')(req)
        renderer = self.vreg['formrenderers'].select('base', req)
        form = EntityFieldsForm(req, entity=e)
        form.formvalues = {}
        field.render(form, renderer)


class UtilsTC(TestCase):
    def test_vocab_sort(self):
        self.assertEqual(vocab_sort([('Z', 1), ('A', 2),
                                      ('Group 1', None), ('Y', 3), ('B', 4),
                                      ('Group 2', None), ('X', 5), ('C', 6)]),
                          [('A', 2), ('Z', 1),
                           ('Group 1', None), ('B', 4), ('Y', 3),
                           ('Group 2', None), ('C', 6), ('X', 5)]
                          )

if __name__ == '__main__':
    unittest_main()
