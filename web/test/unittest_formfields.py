"""unittests for cw.web.formfields"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools import TestServerConfiguration
from cubicweb.entities.lib import Card
from cubicweb.entities.authobjs import EUser
from cubicweb.web.formwidgets import PasswordInput
from cubicweb.web.formfields import *

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()
Card.schema = schema
Card.__initialize__()
EUser.schema = schema
EUser.__initialize__()
        
class GuessFieldTC(TestCase):
    
    def test_card_fields(self):
        title_field = guess_field(Card, schema['title'])
        self.assertIsInstance(title_field, StringField)
        self.assertEquals(title_field.required, True)
        
        synopsis_field = guess_field(Card, schema['synopsis'])
        self.assertIsInstance(synopsis_field, TextField)
        self.assertEquals(synopsis_field.required, False)
        
        content_field = guess_field(Card, schema['content'])
        self.assertIsInstance(content_field, RichTextField)
        self.assertEquals(content_field.required, False)
        
        content_format_field = guess_field(Card, schema['content_format'])
        self.assertEquals(content_format_field, None)
        
        wikiid_field = guess_field(Card, schema['wikiid'])
        self.assertIsInstance(wikiid_field, StringField)
        self.assertEquals(wikiid_field.required, False)

        
    def test_euser_fields(self):
        upassword_field = guess_field(EUser, schema['upassword'])
        self.assertIsInstance(upassword_field, StringField)
        self.assertIsInstance(upassword_field.widget, PasswordInput)
        self.assertEquals(upassword_field.required, True)

        last_login_time_field = guess_field(EUser, schema['last_login_time'])
        self.assertIsInstance(last_login_time_field, DateTimeField)
        self.assertEquals(last_login_time_field.required, False)

        in_group_field = guess_field(EUser, schema['in_group'])
        self.assertIsInstance(in_group_field, RelationField)
        self.assertEquals(in_group_field.required, True)
        self.assertEquals(in_group_field.role, 'subject')

        owned_by_field = guess_field(EUser, schema['owned_by'], 'object')
        self.assertIsInstance(owned_by_field, RelationField)
        self.assertEquals(owned_by_field.required, False)
        self.assertEquals(owned_by_field.role, 'object')

    
if __name__ == '__main__':
    unittest_main()
