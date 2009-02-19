from logilab.common.testlib import TestCase, unittest_main, mock_object
from cubicweb.web.form import *

class ChangeStateForm(EntityFieldsForm):
    state = TextField(widget=HiddenInput, eidparam=False)
    __method = TextField(widget=HiddenInput, initial='set_state', eidparam=False)
    trcomment = RichTextField()

    def buttons(self):
        return []

class CustomChangeStateForm(ChangeStateForm):
    hello = IntField(name='youlou')

class EntityFieldsFormTC(TestCase):

    def test(self):
        req = mock_object(build_url=lambda *args,**kwargs: 'myurl.com')
        form = ChangeStateForm(req, redirect_path='perdu.com')
        entity = mock_object(eid=1)
        self.assertEquals(form.render(entity, state=123),
                          '''''')

    def test_form_inheritance(self):
        req = mock_object(build_url=lambda *args,**kwargs: 'myurl.com')
        form = CustomChangeStateForm(req, redirect_path='perdu.com')
        entity = mock_object(eid=1)
        self.assertEquals(form.render(entity, state=123),
                          '''''')
        
        
if __name__ == '__main__':
    unittest_main()
