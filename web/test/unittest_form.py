from logilab.common.testlib import unittest_main, mock_object
from cubicweb import Binary
from cubicweb.devtools.testlib import WebTest
from cubicweb.web.form import *
from cubicweb.web.views.baseforms import ChangeStateForm


class CustomChangeStateForm(ChangeStateForm):
    hello = IntField(name='youlou')
    creation_date = DateTimeField(widget=DateTimePicker)


class RTFForm(EntityFieldsForm):
    content = RichTextField()

class FFForm(EntityFieldsForm):
    data = FileField(format_field=StringField(name='data_format'),
                     encoding_field=StringField(name='data_encoding'))

class PFForm(EntityFieldsForm):
    upassword = StringField(widget=PasswordInput)

    
class EntityFieldsFormTC(WebTest):

    def setUp(self):
        super(EntityFieldsFormTC, self).setUp()
        self.req = self.request()
        self.entity = self.user(self.req)
        
    def test_form_inheritance(self):
        form = CustomChangeStateForm(self.req, redirect_path='perdu.com',
                                     entity=self.entity)
        self.assertTextEquals(form.form_render(state=123),
                              ''' ''')

    def test_change_state_form(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com',
                               entity=self.entity)
        self.assertTextEquals(form.form_render(state=123, trcomment=u''),
                              ''' ''')

    def test_richtextfield(self):
        card = self.add_entity('Card', title=u"tls sprint fev 2009",
                               content=u'new widgets system')
        form = RTFForm(self.req, redirect_path='perdu.com',
                       entity=card)
        self.assertTextEquals(form.form_render(),
                              '''''')

    def test_filefield(self):
        file = self.add_entity('File', name=u"pouet.txt",
                               data=Binary('new widgets system'))
        form = FFForm(self.req, redirect_path='perdu.com',
                      entity=file)
        self.assertTextEquals(form.form_render(),
                              '''''')

    def test_passwordfield(self):
        form = PFForm(self.req, redirect_path='perdu.com',
                      entity=self.entity)
        self.assertTextEquals(form.form_render(),
                              '''''')
        
    def test_delete_conf_form_multi(self):
        rset = self.execute('EGroup X')
        self.assertTextEquals(self.view('deleteconf', rset, template=None).source,
                              '')

        
if __name__ == '__main__':
    unittest_main()
