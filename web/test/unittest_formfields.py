"""unittests for cw.web.formfields"""

from yams.constraints import StaticVocabularyConstraint, SizeConstraint
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools import TestServerConfiguration
from cubicweb.web.formwidgets import PasswordInput, TextArea, Select
from cubicweb.web.formfields import *
from cubicweb.entities.wfobjs import State
from cubicweb.entities.authobjs import CWUser
from cubes.file.entities import File

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()
state_schema = schema['State']
cwuser_schema = schema['CWUser']
file_schema = schema['File']
salesterm_schema = schema['Salesterm']

class GuessFieldTC(TestCase):

    def test_state_fields(self):
        title_field = guess_field(state_schema, schema['name'])
        self.assertIsInstance(title_field, StringField)
        self.assertEquals(title_field.required, True)

#         synopsis_field = guess_field(state_schema, schema['synopsis'])
#         self.assertIsInstance(synopsis_field, StringField)
#         self.assertIsInstance(synopsis_field.widget, TextArea)
#         self.assertEquals(synopsis_field.required, False)
#         self.assertEquals(synopsis_field.help, 'an abstract for this state')

        description_field = guess_field(state_schema, schema['description'])
        self.assertIsInstance(description_field, RichTextField)
        self.assertEquals(description_field.required, False)
        self.assertEquals(description_field.format_field, None)

        description_format_field = guess_field(state_schema, schema['description_format'])
        self.assertEquals(description_format_field, None)

        description_format_field = guess_field(state_schema, schema['description_format'], skip_meta_attr=False)
        self.assertEquals(description_format_field.internationalizable, True)
        self.assertEquals(description_format_field.sort, True)
        self.assertEquals(description_format_field.initial(None), 'text/rest')

#         wikiid_field = guess_field(state_schema, schema['wikiid'])
#         self.assertIsInstance(wikiid_field, StringField)
#         self.assertEquals(wikiid_field.required, False)


    def test_euser_fields(self):
        upassword_field = guess_field(cwuser_schema, schema['upassword'])
        self.assertIsInstance(upassword_field, StringField)
        self.assertIsInstance(upassword_field.widget, PasswordInput)
        self.assertEquals(upassword_field.required, True)

        last_login_time_field = guess_field(cwuser_schema, schema['last_login_time'])
        self.assertIsInstance(last_login_time_field, DateTimeField)
        self.assertEquals(last_login_time_field.required, False)

        in_group_field = guess_field(cwuser_schema, schema['in_group'])
        self.assertIsInstance(in_group_field, RelationField)
        self.assertEquals(in_group_field.required, True)
        self.assertEquals(in_group_field.role, 'subject')
        self.assertEquals(in_group_field.help, 'groups grant permissions to the user')

        owned_by_field = guess_field(cwuser_schema, schema['owned_by'], 'object')
        self.assertIsInstance(owned_by_field, RelationField)
        self.assertEquals(owned_by_field.required, False)
        self.assertEquals(owned_by_field.role, 'object')


    def test_file_fields(self):
        data_format_field = guess_field(file_schema, schema['data_format'])
        self.assertEquals(data_format_field, None)
        data_encoding_field = guess_field(file_schema, schema['data_encoding'])
        self.assertEquals(data_encoding_field, None)

        data_field = guess_field(file_schema, schema['data'])
        self.assertIsInstance(data_field, FileField)
        self.assertEquals(data_field.required, True)
        self.assertIsInstance(data_field.format_field, StringField)
        self.assertIsInstance(data_field.encoding_field, StringField)

    def test_constraints_priority(self):
        salesterm_field = guess_field(salesterm_schema, schema['reason'])
        constraints = schema['reason'].rproperty('Salesterm', 'String', 'constraints')
        self.assertEquals([c.__class__ for c in constraints],
                          [SizeConstraint, StaticVocabularyConstraint])
        self.assertIsInstance(salesterm_field.widget, Select)

if __name__ == '__main__':
    unittest_main()
