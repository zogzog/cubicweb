from logilab.common.testlib import TestCase, unittest_main, mock_object

from cubicweb.web.form import *
from cubicweb.web.views.baseforms import ChangeStateForm

class CustomChangeStateForm(ChangeStateForm):
    hello = IntField(name='youlou')

class EntityFieldsFormTC(TestCase):

    def setUp(self):
        def next_tabindex(self):
            self.count += 1
            return self.count
        self.req = mock_object(build_url=lambda *args,**kwargs: 'myurl.com/pouet',
                               url=lambda *args,**kwargs: 'myurl.com/form',
                               _=lambda s,x: x, form={},
                               next_tabindex=next_tabindex, count=0)
        self.entity = mock_object(eid=1, has_eid=lambda x: False, id='Entity')
        
    def test(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com')
        self.assertEquals(form.form_render(self.entity, state=123),
                          '''''')

    def test_form_inheritance(self):
        form = CustomChangeStateForm(self.req, redirect_path='perdu.com')
        self.assertEquals(form.form_render(self.entity, state=123),
                          '''''')
        
        
if __name__ == '__main__':
    unittest_main()
