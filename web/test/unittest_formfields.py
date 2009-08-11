"""unittests for cw.web.formfields

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main, mock_object as mock

from yams.constraints import StaticVocabularyConstraint, SizeConstraint

from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.formwidgets import PasswordInput, TextArea, Select, Radio
from cubicweb.web.formfields import *
from cubicweb.web.views.forms import EntityFieldsForm

from cubes.file.entities import File

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()

class GuessFieldTC(TestCase):

    def test_state_fields(self):
        title_field = guess_field(schema['State'], schema['name'])
        self.assertIsInstance(title_field, StringField)
        self.assertEquals(title_field.required, True)

#         synopsis_field = guess_field(schema['State'], schema['synopsis'])
#         self.assertIsInstance(synopsis_field, StringField)
#         self.assertIsInstance(synopsis_field.widget, TextArea)
#         self.assertEquals(synopsis_field.required, False)
#         self.assertEquals(synopsis_field.help, 'an abstract for this state')

        description_field = guess_field(schema['State'], schema['description'])
        self.assertIsInstance(description_field, RichTextField)
        self.assertEquals(description_field.required, False)
        self.assertEquals(description_field.format_field, None)

        description_format_field = guess_field(schema['State'], schema['description_format'])
        self.assertEquals(description_format_field, None)

        description_format_field = guess_field(schema['State'], schema['description_format'], skip_meta_attr=False)
        self.assertEquals(description_format_field.internationalizable, True)
        self.assertEquals(description_format_field.sort, True)
        self.assertEquals(description_format_field.initial(None), 'text/rest')

#         wikiid_field = guess_field(schema['State'], schema['wikiid'])
#         self.assertIsInstance(wikiid_field, StringField)
#         self.assertEquals(wikiid_field.required, False)


    def test_cwuser_fields(self):
        upassword_field = guess_field(schema['CWUser'], schema['upassword'])
        self.assertIsInstance(upassword_field, StringField)
        self.assertIsInstance(upassword_field.widget, PasswordInput)
        self.assertEquals(upassword_field.required, True)

        last_login_time_field = guess_field(schema['CWUser'], schema['last_login_time'])
        self.assertIsInstance(last_login_time_field, DateTimeField)
        self.assertEquals(last_login_time_field.required, False)

        in_group_field = guess_field(schema['CWUser'], schema['in_group'])
        self.assertIsInstance(in_group_field, RelationField)
        self.assertEquals(in_group_field.required, True)
        self.assertEquals(in_group_field.role, 'subject')
        self.assertEquals(in_group_field.help, 'groups grant permissions to the user')

        owned_by_field = guess_field(schema['CWUser'], schema['owned_by'], 'object')
        self.assertIsInstance(owned_by_field, RelationField)
        self.assertEquals(owned_by_field.required, False)
        self.assertEquals(owned_by_field.role, 'object')


    def test_file_fields(self):
        data_format_field = guess_field(schema['File'], schema['data_format'])
        self.assertEquals(data_format_field, None)
        data_encoding_field = guess_field(schema['File'], schema['data_encoding'])
        self.assertEquals(data_encoding_field, None)

        data_field = guess_field(schema['File'], schema['data'])
        self.assertIsInstance(data_field, FileField)
        self.assertEquals(data_field.required, True)
        self.assertIsInstance(data_field.format_field, StringField)
        self.assertIsInstance(data_field.encoding_field, StringField)

    def test_constraints_priority(self):
        salesterm_field = guess_field(schema['Salesterm'], schema['reason'])
        constraints = schema['reason'].rproperty('Salesterm', 'String', 'constraints')
        self.assertEquals([c.__class__ for c in constraints],
                          [SizeConstraint, StaticVocabularyConstraint])
        self.assertIsInstance(salesterm_field.widget, Select)


    def test_bool_field_base(self):
        field = guess_field(schema['CWAttribute'], schema['indexed'])
        self.assertIsInstance(field, BooleanField)
        self.assertEquals(field.required, False)
        self.assertEquals(field.initial(None), None)
        self.assertIsInstance(field.widget, Radio)
        self.assertEquals(field.vocabulary(mock(req=mock(_=unicode))),
                          [(u'yes', '1'), (u'no', '')])

    def test_bool_field_explicit_choices(self):
        field = guess_field(schema['CWAttribute'], schema['indexed'],
                            choices=[(u'maybe', '1'), (u'no', '')])
        self.assertIsInstance(field.widget, Radio)
        self.assertEquals(field.vocabulary(mock(req=mock(_=unicode))),
                          [(u'maybe', '1'), (u'no', '')])


class MoreFieldsTC(CubicWebTC):
    def test_rtf_format_field(self):
        req = self.request()
        req.use_fckeditor = lambda: False
        e = self.vreg['etypes'].etype_class('State')(req)
        form = EntityFieldsForm(req, entity=e)
        description_field = guess_field(schema['State'], schema['description'])
        description_format_field = description_field.get_format_field(form)
        self.assertEquals(description_format_field.internationalizable, True)
        self.assertEquals(description_format_field.sort, True)
        # unlike below, initial is bound to form.form_field_format
        self.assertEquals(description_format_field.initial(form), 'text/html')
        self.execute('INSERT CWProperty X: X pkey "ui.default-text-format", X value "text/rest", X for_user U WHERE U login "admin"')
        self.commit()
        self.assertEquals(description_format_field.initial(form), 'text/rest')

if __name__ == '__main__':
    unittest_main()
