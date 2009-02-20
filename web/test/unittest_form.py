from logilab.common.testlib import unittest_main, mock_object
from cubicweb.devtools.testlib import WebTest
from cubicweb.web.form import *
from cubicweb.web.views.baseforms import ChangeStateForm


class CustomChangeStateForm(ChangeStateForm):
    hello = IntField(name='youlou')
    creation_date = DateTimeField(widget=DateTimePicker)


class RTFStateForm(EntityFieldsForm):
    content = RichTextField()

    
class EntityFieldsFormTC(WebTest):

    def setUp(self):
        super(EntityFieldsFormTC, self).setUp()
        self.req = self.request()
        self.entity = self.user(self.req)
        
    def test_form_inheritance(self):
        form = CustomChangeStateForm(self.req, redirect_path='perdu.com',
                                     entity=self.entity)
        self.assertEquals(form.form_render(state=123),
                          ''' ''')

    def test_change_state_form(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com',
                               entity=self.entity)
        self.assertEquals(form.form_render(state=123),
                          ''' ''')

    def test_delete_conf_form_multi(self):
        rset = self.execute('EGroup X')
        self.assertEquals(self.view('deleteconf', rset).source,
                          '')

    def test_richtextfield(self):
        card = self.add_entity('Card', title=u"tls sprint fev 2009",
                               content=u'new widgets system')
        form = CustomChangeStateForm(self.req, redirect_path='perdu.com',
                                     entity=card)
        self.assertEquals(form.form_render(),
                          '''''')
        
if __name__ == '__main__':
    unittest_main()
