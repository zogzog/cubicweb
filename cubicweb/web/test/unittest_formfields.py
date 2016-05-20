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
"""unittests for cw.web.formfields"""

from logilab.common.testlib import TestCase, unittest_main, mock_object as mock

from yams.constraints import StaticVocabularyConstraint, SizeConstraint

import cubicweb
from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.formwidgets import PasswordInput, Select, Radio
from cubicweb.web.formfields import *
from cubicweb.web.views.forms import EntityFieldsForm, FieldsForm


def setUpModule(*args):
    global schema
    config = TestServerConfiguration('data', __file__)
    config.bootstrap_cubes()
    schema = config.load_schema()


class GuessFieldTC(CubicWebTC):

    def test_state_fields(self):
        with self.admin_access.web_request() as req:
            title_field = guess_field(schema['State'], schema['name'], req=req)
            self.assertIsInstance(title_field, StringField)
            self.assertEqual(title_field.required, True)

        with self.admin_access.web_request() as req:
            description_field = guess_field(schema['State'], schema['description'], req=req)
            self.assertIsInstance(description_field, RichTextField)
            self.assertEqual(description_field.required, False)
            self.assertEqual(description_field.format_field, None)

        # description_format_field = guess_field(schema['State'], schema['description_format'])
        # self.assertEqual(description_format_field, None)

        with self.admin_access.web_request() as req:
            description_format_field = guess_field(schema['State'], schema['description_format'],
                                                   req=req)
            self.assertEqual(description_format_field.internationalizable, True)
            self.assertEqual(description_format_field.sort, True)

    def test_cwuser_fields(self):
        with self.admin_access.web_request() as req:
            upassword_field = guess_field(schema['CWUser'], schema['upassword'], req=req)
            self.assertIsInstance(upassword_field, StringField)
            self.assertIsInstance(upassword_field.widget, PasswordInput)
            self.assertEqual(upassword_field.required, True)

        with self.admin_access.web_request() as req:
            last_login_time_field = guess_field(schema['CWUser'], schema['last_login_time'],
                                                req=req)
            self.assertIsInstance(last_login_time_field, DateTimeField)
            self.assertEqual(last_login_time_field.required, False)

        with self.admin_access.web_request() as req:
            in_group_field = guess_field(schema['CWUser'], schema['in_group'], req=req)
            self.assertIsInstance(in_group_field, RelationField)
            self.assertEqual(in_group_field.required, True)
            self.assertEqual(in_group_field.role, 'subject')
            self.assertEqual(in_group_field.help, 'groups grant permissions to the user')

        with self.admin_access.web_request() as req:
            owned_by_field = guess_field(schema['CWUser'], schema['owned_by'], 'object', req=req)
            self.assertIsInstance(owned_by_field, RelationField)
            self.assertEqual(owned_by_field.required, False)
            self.assertEqual(owned_by_field.role, 'object')

    def test_file_fields(self):
        with self.admin_access.web_request() as req:
            data_field = guess_field(schema['File'], schema['data'], req=req)
            self.assertIsInstance(data_field, FileField)
            self.assertEqual(data_field.required, True)
            self.assertIsInstance(data_field.format_field, StringField)
            self.assertIsInstance(data_field.encoding_field, StringField)
            self.assertIsInstance(data_field.name_field, StringField)

    def test_constraints_priority(self):
        with self.admin_access.web_request() as req:
            salesterm_field = guess_field(schema['Salesterm'], schema['reason'], req=req)
            constraints = schema['reason'].rdef('Salesterm', 'String').constraints
            self.assertEqual([c.__class__ for c in constraints],
                             [SizeConstraint, StaticVocabularyConstraint])
            self.assertIsInstance(salesterm_field, StringField)
            self.assertIsInstance(salesterm_field.widget, Select)

    def test_bool_field_base(self):
        with self.admin_access.web_request() as req:
            field = guess_field(schema['CWAttribute'], schema['indexed'], req=req)
            self.assertIsInstance(field, BooleanField)
            self.assertEqual(field.required, False)
            self.assertIsInstance(field.widget, Radio)
            self.assertEqual(field.vocabulary(mock(_cw=mock(_=cubicweb._))),
                             [(u'yes', '1'), (u'no', '')])

    def test_bool_field_explicit_choices(self):
        with self.admin_access.web_request() as req:
            field = guess_field(schema['CWAttribute'], schema['indexed'],
                                choices=[(u'maybe', '1'), (u'no', '')], req=req)
            self.assertIsInstance(field.widget, Radio)
            self.assertEqual(field.vocabulary(mock(req=mock(_=cubicweb._))),
                             [(u'maybe', '1'), (u'no', '')])


class MoreFieldsTC(CubicWebTC):
    def test_rtf_format_field(self):
        with self.admin_access.web_request() as req:
            req.use_fckeditor = lambda: False
            e = self.vreg['etypes'].etype_class('State')(req)
            form = EntityFieldsForm(req, entity=e)
            description_field = guess_field(schema['State'], schema['description'])
            description_format_field = description_field.get_format_field(form)
            self.assertEqual(description_format_field.internationalizable, True)
            self.assertEqual(description_format_field.sort, True)
            # unlike below, initial is bound to form.form_field_format
            self.assertEqual(description_format_field.value(form), 'text/plain')
            req.cnx.create_entity('CWProperty', pkey=u"ui.default-text-format", value=u"text/rest",
                                  for_user=req.user.eid)
            req.cnx.commit()
            self.assertEqual(description_format_field.value(form), 'text/rest')

    def test_property_key_field(self):
        from cubicweb.web.views.cwproperties import PropertyKeyField
        with self.admin_access.web_request() as req:
            field = PropertyKeyField(name='test')
            e = self.vreg['etypes'].etype_class('CWProperty')(req)
            renderer = self.vreg['formrenderers'].select('base', req)
            form = EntityFieldsForm(req, entity=e)
            form.formvalues = {}
            field.render(form, renderer)


class CompoundFieldTC(CubicWebTC):

    def test_multipart(self):
        """Ensures that compound forms have needs_multipart set if their children require it"""
        class AForm(FieldsForm):
            comp = CompoundField([IntField(), StringField()])

        with self.admin_access.web_request() as req:
            aform = AForm(req, None)
            self.assertFalse(aform.needs_multipart)

        class MForm(FieldsForm):
            comp = CompoundField([IntField(), FileField()])

        with self.admin_access.web_request() as req:
            mform = MForm(req, None)
            self.assertTrue(mform.needs_multipart)


class UtilsTC(TestCase):
    def test_vocab_sort(self):
        self.assertEqual(vocab_sort([('Z', 1), ('A', 2),
                                     ('Group 1', None), ('Y', 3), ('B', 4),
                                     ('Group 2', None), ('X', 5), ('C', 6)]),
                         [('A', 2), ('Z', 1),
                          ('Group 1', None), ('B', 4), ('Y', 3),
                          ('Group 2', None), ('C', 6), ('X', 5)])


if __name__ == '__main__':
    unittest_main()
