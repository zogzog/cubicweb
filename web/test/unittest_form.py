from logilab.common.testlib import unittest_main, mock_object
from cubicweb import Binary
from cubicweb.devtools.testlib import WebTest
from cubicweb.web.form import *
from cubicweb.web.views.baseforms import ChangeStateForm


class EntityFieldsFormTC(WebTest):

    def setUp(self):
        super(EntityFieldsFormTC, self).setUp()
        self.req = self.request()
        self.entity = self.user(self.req)
        self.renderer = FormRenderer()
        
    # form tests ##############################################################
    
    def test_form_inheritance(self):
        class CustomChangeStateForm(ChangeStateForm):
            hello = IntField(name='youlou')
            creation_date = DateTimeField(widget=DateTimePicker)
        form = CustomChangeStateForm(self.req, redirect_path='perdu.com',
                                     entity=self.entity)
        self.assertTextEquals(form.form_render(state=123, trcomment=u''),
                              ''' ''')

    def test_change_state_form(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com',
                               entity=self.entity)
        self.assertTextEquals(form.form_render(state=123, trcomment=u''),
                              ''' ''')
        
    def test_delete_conf_form_multi(self):
        rset = self.execute('EGroup X')
        self.assertTextEquals(self.view('deleteconf', rset, template=None).source,
                              '')

    # fields tests ############################################################

    def _render_entity_field(self, name, form):
        form.form_build_context({})
        form.form_add_entity_hiddens(form.entity.e_schema)
        return form.field_by_name(name).render(form, self.renderer)
    
    def _test_richtextfield(self, expected):
        class RTFForm(EntityFieldsForm):
            content = RichTextField()
        card = self.add_entity('Card', title=u"tls sprint fev 2009",
                               content=u'<h1>new widgets system</h1>',
                               content_format=u'text/html')
        form = RTFForm(self.req, redirect_path='perdu.com', entity=card)
        self.assertTextEquals(self._render_entity_field('content', form), expected)
        
    def test_richtextfield_1(self):
        self.req.use_fckeditor = lambda: False
        self._test_richtextfield('''<select name="content_format" id="content_format" tabindex="0">
<option value="text/rest">text/rest</option>
<option selected="selected" value="text/html">text/html</option>
<option value="text/plain">text/plain</option>
<option value="text/cubicweb-page-template">text/cubicweb-page-template</option>
</select><textarea tabindex="1" id="content" name="content" onkeypress="autogrow(this)"/>''')
    
    def test_richtextfield_2(self):
        self.req.use_fckeditor = lambda: True
        self._test_richtextfield('''<input type="hidden" name="content_format" value="text/html"/><textarea tabindex="0" cubicweb:type="wysiwyg" id="content" name="content" onkeypress="autogrow(this)"/>''')


    def test_filefield(self):
        class FFForm(EntityFieldsForm):
            data = FileField(format_field=StringField(name='data_format'),
                             encoding_field=StringField(name='data_encoding'))
        file = self.add_entity('File', name=u"pouet.txt",
                               data=Binary('new widgets system'))
        form = FFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data" type="file" name="data" value="" tabindex="0"/>
<a href="javascript: toggleVisibility(&#39;data-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data-advanced" class="hidden">
<label for="data_format">data_format</label><input id="data_format" type="text" name="data_format" value="" tabindex="1"/><br/><br/>
<label for="data_encoding">data_encoding</label><input id="data_encoding" type="text" name="data_encoding" value="" tabindex="2"/><br/><br/>
</div>''')

        
    def test_editablefilefield(self):
        class EFFForm(EntityFieldsForm):
            data = EditableFileField(format_field=StringField(name='data_format'),
                                     encoding_field=StringField(name='data_encoding'))
            def form_field_encoding(self, field):
                return 'ascii'
            def form_field_format(self, field):
                return 'text/plain'
        file = self.add_entity('File', name=u"pouet.txt",
                               data=Binary('new widgets system'))
        form = EFFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data" type="file" name="data" value="" tabindex="0"/>
<a href="javascript: toggleVisibility(&#39;data-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data-advanced" class="hidden">
<label for="data_format">data_format</label><input id="data_format" type="text" name="data_format" value="" tabindex="1"/><br/><br/>
<label for="data_encoding">data_encoding</label><input id="data_encoding" type="text" name="data_encoding" value="" tabindex="2"/><br/><br/>
</div>
<p><b>You can either submit a new file using the browse button above, or choose to remove already uploaded file by checking the "detach attached file" check-box, or edit file content online with the widget below.</b></p>
<textarea tabindex="3" name="data" onkeypress="autogrow(this)">new widgets system</textarea>''')

    def test_passwordfield(self):
        class PFForm(EntityFieldsForm):
            upassword = StringField(widget=PasswordInput)
        form = PFForm(self.req, redirect_path='perdu.com', entity=self.entity)
        self.assertTextEquals(self._render_entity_field('upassword', form),
                              '''<input id="upassword" type="password" name="upassword" value="" tabindex="0"/>
<br/>
<input type="password" id="upassword" name="upassword-confirm" tabindex="0"/>
&nbsp;
<span class="emphasis">confirm password</span>''')

        
if __name__ == '__main__':
    unittest_main()
