from logilab.common.testlib import unittest_main, mock_object
from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.web.form import *
from cubicweb.web.views.baseforms import ChangeStateForm

class CustomChangeStateForm(ChangeStateForm):
    hello = IntField(name='youlou')
    creation_date = DateTimeField(widget=DateTimePicker)
    
class EntityFieldsFormTC(EnvBasedTC):

    def setUp(self):
        super(EntityFieldsFormTC, self).setUp()
        self.req = self.request()
        self.entity = self.user(self.req)
        
    def test(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com')
        self.assertEquals(form.form_render(self.entity, state=123),
                          ''' ''')

    def test_form_inheritance(self):
        form = CustomChangeStateForm(self.req, redirect_path='perdu.com')
        self.assertEquals(form.form_render(self.entity, state=123),
                          ''' ''')
        
        
if __name__ == '__main__':
    unittest_main()
