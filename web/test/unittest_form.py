from logilab.common.testlib import unittest_main, mock_object
from cubicweb import Binary
from cubicweb.devtools.testlib import WebTest
from cubicweb.web.form import EntityFieldsForm, FormRenderer
from cubicweb.web.formfields import (IntField, StringField, RichTextField,
                                     DateTimeField, DateTimePicker,
                                     FileField, EditableFileField)
from cubicweb.web.formwidgets import PasswordInput
from cubicweb.web.views.workflow import ChangeStateForm


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
        form.form_render(state=123, trcomment=u'')

    def test_change_state_form(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com',
                               entity=self.entity)
        form.form_render(state=123, trcomment=u'')
        
    def test_delete_conf_form_multi(self):
        rset = self.execute('EGroup X')
        self.view('deleteconf', rset, template=None).source
        
    def test_massmailing_form(self):
        self.execute('INSERT EmailAddress X: X address L + "@cubicweb.org", '
                     'U use_email X WHERE U is EUser, U login L')
        rset = self.execute('EUser X')
        self.view('massmailing', rset, template=None)
        
    def test_automatic_edition_form(self):
        rset = self.execute('EUser X')
        self.view('edition', rset, row=0, template=None).source
        
    def test_automatic_edition_form(self):
        rset = self.execute('EUser X')
        self.view('copy', rset, row=0, template=None).source
        
    def test_automatic_creation_form(self):
        self.view('creation', None, etype='EUser', template=None).source
        
    def test_automatic_muledit_form(self):
        rset = self.execute('EUser X')
        self.view('muledit', rset, template=None).source
        
    def test_automatic_reledit_form(self):
        rset = self.execute('EUser X')
        self.view('reledit', rset, row=0, rtype='login', template=None).source
        
    def test_automatic_inline_edit_form(self):
        geid = self.execute('EGroup X LIMIT 1')[0][0]
        rset = self.execute('EUser X LIMIT 1')
        self.view('inline-edition', rset, row=0, rtype='in_group', peid=geid, template=None).source
                              
    def test_automatic_inline_creation_form(self):
        geid = self.execute('EGroup X LIMIT 1')[0][0]
        self.view('inline-creation', None, etype='EUser', rtype='in_group', peid=geid, template=None).source


    # fields tests ############################################################

    def _render_entity_field(self, name, form):
        form.form_add_entity_hiddens(form.edited_entity.e_schema)
        form.form_build_context({})
        return form.field_by_name(name).render(form, self.renderer)
    
    def _test_richtextfield(self, expected):
        class RTFForm(EntityFieldsForm):
            content = RichTextField()
        card = self.add_entity('Card', title=u"tls sprint fev 2009",
                               content=u'<h1>new widgets system</h1>',
                               content_format=u'text/html')
        form = RTFForm(self.req, redirect_path='perdu.com', entity=card)
        self.assertTextEquals(self._render_entity_field('content', form), expected % {'eid': card.eid})

        
    def test_richtextfield_1(self):
        self.req.use_fckeditor = lambda: False
        self._test_richtextfield('''<select name="content_format:%(eid)s" id="content_format:%(eid)s" tabindex="0">
<option value="text/rest">text/rest</option>
<option selected="selected" value="text/html">text/html</option>
<option value="text/plain">text/plain</option>
<option value="text/cubicweb-page-template">text/cubicweb-page-template</option>
</select><textarea tabindex="1" id="content:%(eid)s" name="content:%(eid)s" onkeypress="autogrow(this)">&lt;h1&gt;new widgets system&lt;/h1&gt;</textarea>''')

    
    def test_richtextfield_2(self):
        self.req.use_fckeditor = lambda: True
        self._test_richtextfield('''<input type="hidden" name="content_format:%(eid)s" value="text/html"/><textarea tabindex="0" cubicweb:type="wysiwyg" id="content:%(eid)s" name="content:%(eid)s" onkeypress="autogrow(this)">&lt;h1&gt;new widgets system&lt;/h1&gt;</textarea>''')


    def test_filefield(self):
        class FFForm(EntityFieldsForm):
            data = FileField(format_field=StringField(name='data_format'),
                             encoding_field=StringField(name='data_encoding'))
        file = self.add_entity('File', name=u"pouet.txt",
                               data=Binary('new widgets system'))
        form = FFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data:%(eid)s" type="file" name="data:%(eid)s" value="" tabindex="0"/>
<a href="javascript: toggleVisibility(&#39;data:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data:%(eid)s-advanced" class="hidden">
<label for="data_format:%(eid)s">data_format</label><input id="data_format:%(eid)s" type="text" name="data_format:%(eid)s" value="text/plain" tabindex="1"/><br/><br/>
<label for="data_encoding:%(eid)s">data_encoding</label><input id="data_encoding:%(eid)s" type="text" name="data_encoding:%(eid)s" value="UTF-8" tabindex="2"/><br/><br/>
</div>
<br/>
<input type="checkbox" name="data:594__detach"/>
detach attached file
''' % {'eid': file.eid})

        
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
                              '''<input id="data:%(eid)s" type="file" name="data:%(eid)s" value="" tabindex="0"/>
<a href="javascript: toggleVisibility(&#39;data:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data:%(eid)s-advanced" class="hidden">
<label for="data_format:%(eid)s">data_format</label><input id="data_format:%(eid)s" type="text" name="data_format:%(eid)s" value="text/plain" tabindex="1"/><br/><br/>
<label for="data_encoding:%(eid)s">data_encoding</label><input id="data_encoding:%(eid)s" type="text" name="data_encoding:%(eid)s" value="UTF-8" tabindex="2"/><br/><br/>
</div>
<br/>
<input type="checkbox" name="data:594__detach"/>
detach attached file
<p><b>You can either submit a new file using the browse button above, or choose to remove already uploaded file by checking the "detach attached file" check-box, or edit file content online with the widget below.</b></p>
<textarea tabindex="3" name="data:%(eid)s" onkeypress="autogrow(this)">new widgets system</textarea>''' % {'eid': file.eid})


    def test_passwordfield(self):
        class PFForm(EntityFieldsForm):
            upassword = StringField(widget=PasswordInput)
        form = PFForm(self.req, redirect_path='perdu.com', entity=self.entity)
        self.assertTextEquals(self._render_entity_field('upassword', form),
                              '''<input id="upassword:%(eid)s" type="password" name="upassword:%(eid)s" value="__cubicweb_internal_field__" tabindex="0"/>
<br/>
<input type="password" name="upassword-confirm:%(eid)s" tabindex="0"/>
&nbsp;
<span class="emphasis">confirm password</span>''' % {'eid': self.entity.eid})

        
if __name__ == '__main__':
    unittest_main()
