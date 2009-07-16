"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
#from __future__ import with_statement

from xml.etree.ElementTree import fromstring

from logilab.common.testlib import unittest_main, mock_object

from cubicweb import Binary
from cubicweb.devtools.testlib import WebTest
from cubicweb.web.formfields import (IntField, StringField, RichTextField,
                                     DateTimeField, DateTimePicker,
                                     FileField, EditableFileField)
from cubicweb.web.formwidgets import PasswordInput, Input
from cubicweb.web.views.forms import EntityFieldsForm, FieldsForm
from cubicweb.web.views.workflow import ChangeStateForm
from cubicweb.web.views.formrenderers import FormRenderer


class FieldsFormTC(WebTest):

    def test_form_field_format(self):
        form = FieldsForm(self.request(), None)
        self.assertEquals(form.form_field_format(None), 'text/html')
        self.execute('INSERT CWProperty X: X pkey "ui.default-text-format", X value "text/rest", X for_user U WHERE U login "admin"')
        self.commit()
        self.assertEquals(form.form_field_format(None), 'text/rest')


class EntityFieldsFormTC(WebTest):

    def setUp(self):
        super(EntityFieldsFormTC, self).setUp()
        self.req = self.request()
        self.entity = self.user(self.req)

    def test_form_field_vocabulary_unrelated(self):
        b = self.add_entity('BlogEntry', title=u'di mascii code', content=u'a best-seller')
        t = self.add_entity('Tag', name=u'x')
        form1 = EntityFieldsForm(self.request(), None, entity=t)
        unrelated = [reid for rview, reid in form1.subject_relation_vocabulary('tags')]
        self.failUnless(b.eid in unrelated, unrelated)
        form2 = EntityFieldsForm(self.request(), None, entity=b)
        unrelated = [reid for rview, reid in form2.object_relation_vocabulary('tags')]
        self.failUnless(t.eid in unrelated, unrelated)
        self.execute('SET X tags Y WHERE X is Tag, Y is BlogEntry')
        unrelated = [reid for rview, reid in form1.subject_relation_vocabulary('tags')]
        self.failIf(b.eid in unrelated, unrelated)
        unrelated = [reid for rview, reid in form2.object_relation_vocabulary('tags')]
        self.failIf(t.eid in unrelated, unrelated)

    def test_form_field_vocabulary_new_entity(self):
        e = self.etype_instance('CWUser')
        form = EntityFieldsForm(self.request(), None, entity=e)
        unrelated = [rview for rview, reid in form.subject_relation_vocabulary('in_group')]
        # should be default groups but owners, i.e. managers, users, guests
        self.assertEquals(unrelated, [u'guests', u'managers', u'users'])

    def test_subject_in_state_vocabulary(self):
        # on a new entity
        e = self.etype_instance('CWUser')
        form = EntityFieldsForm(self.request(), None, entity=e)
        states = list(form.subject_in_state_vocabulary('in_state'))
        self.assertEquals(len(states), 1)
        self.assertEquals(states[0][0], u'activated') # list of (combobox view, state eid)
        # on an existant entity
        e = self.user()
        form = EntityFieldsForm(self.request(), None, entity=e)
        states = list(form.subject_in_state_vocabulary('in_state'))
        self.assertEquals(len(states), 1)
        self.assertEquals(states[0][0], u'deactivated') # list of (combobox view, state eid)

    def test_consider_req_form_params(self):
        e = self.etype_instance('CWUser')
        e.eid = 'A'
        form = EntityFieldsForm(self.request(login=u'toto'), None, entity=e)
        field = StringField(name='login', eidparam=True)
        form.append_field(field)
        form.form_build_context({})
        self.assertEquals(form.form_field_display_value(field, {}), 'toto')


    def test_linkto_field_duplication(self):
        e = self.etype_instance('CWUser')
        e.eid = 'A'
        e.req = self.req
        geid = self.execute('CWGroup X WHERE X name "users"')[0][0]
        self.req.form['__linkto'] = 'in_group:%s:subject' % geid
        form = self.vreg.select('forms', 'edition', self.req, entity=e)
        form.content_type = 'text/html'
        pageinfo = self._check_html(form.form_render(), form, template=None)
        inputs = pageinfo.find_tag('select', False)
        self.failUnless(any(attrs for t, attrs in inputs if attrs.get('name') == 'in_group:A'))
        inputs = pageinfo.find_tag('input', False)
        self.failIf(any(attrs for t, attrs in inputs if attrs.get('name') == '__linkto'))

    def test_reledit_composite_field(self):
        rset = self.execute('INSERT BlogEntry X: X title "cubicweb.org", X content "hop"')
        form = self.vreg.select_object('views', 'reledit', self.request(),
                                       rset=rset, row=0, rtype='content')
        data = form.render(row=0, rtype='content')
        self.failUnless('edits-content' in data)
        self.failUnless('edits-content_format' in data)

    # form view tests #########################################################

    def test_massmailing_formview(self):
        self.execute('INSERT EmailAddress X: X address L + "@cubicweb.org", '
                     'U use_email X WHERE U is CWUser, U login L')
        rset = self.execute('CWUser X')
        self.view('massmailing', rset, template=None)


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

    # fields tests ############################################################

    def _render_entity_field(self, name, form):
        form.form_build_context({})
        renderer = FormRenderer(self.req)
        return form.field_by_name(name).render(form, renderer)

    def _test_richtextfield(self, expected):
        class RTFForm(EntityFieldsForm):
            description = RichTextField()
        state = self.execute('State X WHERE X name "activated", X state_of ET, ET name "CWUser"').get_entity(0, 0)
        form = RTFForm(self.req, redirect_path='perdu.com', entity=state)
        # make it think it can use fck editor anyway
        form.form_field_format = lambda x: 'text/html'
        self.assertTextEquals(self._render_entity_field('description', form),
                              expected % {'eid': state.eid})


    def test_richtextfield_1(self):
        self.req.use_fckeditor = lambda: False
        self._test_richtextfield('''<select id="description_format:%(eid)s" name="description_format:%(eid)s" size="1" style="display: block" tabindex="0">
<option value="text/cubicweb-page-template">text/cubicweb-page-template</option>
<option value="text/html">text/html</option>
<option value="text/plain">text/plain</option>
<option selected="selected" value="text/rest">text/rest</option>
</select><textarea cols="80" id="description:%(eid)s" name="description:%(eid)s" onkeyup="autogrow(this)" rows="2" tabindex="1"></textarea>''')


    def test_richtextfield_2(self):
        self.req.use_fckeditor = lambda: True
        self._test_richtextfield('<input name="description_format:%(eid)s" style="display: block" type="hidden" value="text/rest"></input><textarea cols="80" cubicweb:type="wysiwyg" id="description:%(eid)s" name="description:%(eid)s" onkeyup="autogrow(this)" rows="2" tabindex="0"></textarea>')


    def test_filefield(self):
        class FFForm(EntityFieldsForm):
            data = FileField(format_field=StringField(name='data_format', max_length=50),
                             encoding_field=StringField(name='data_encoding', max_length=20))
        file = self.add_entity('File', name=u"pouet.txt", data_encoding=u'UTF-8',
                               data=Binary('new widgets system'))
        form = FFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data:%(eid)s" name="data:%(eid)s" tabindex="0" type="file" value=""></input>
<a href="javascript: toggleVisibility(&#39;data:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data:%(eid)s-advanced" class="hidden">
<label for="data_format:%(eid)s">data_format</label><input id="data_format:%(eid)s" maxlength="50" name="data_format:%(eid)s" size="45" tabindex="1" type="text" value="text/plain"></input><br/>
<label for="data_encoding:%(eid)s">data_encoding</label><input id="data_encoding:%(eid)s" maxlength="20" name="data_encoding:%(eid)s" size="20" tabindex="2" type="text" value="UTF-8"></input><br/>
</div>
<br/>
<input name="data:%(eid)s__detach" type="checkbox"></input>
detach attached file
''' % {'eid': file.eid})


    def test_editablefilefield(self):
        class EFFForm(EntityFieldsForm):
            data = EditableFileField(format_field=StringField(name='data_format', max_length=50),
                                     encoding_field=StringField(name='data_encoding', max_length=20))
            def form_field_encoding(self, field):
                return 'ascii'
            def form_field_format(self, field):
                return 'text/plain'
        file = self.add_entity('File', name=u"pouet.txt", data_encoding=u'UTF-8',
                               data=Binary('new widgets system'))
        form = EFFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data:%(eid)s" name="data:%(eid)s" tabindex="0" type="file" value=""></input>
<a href="javascript: toggleVisibility(&#39;data:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data:%(eid)s-advanced" class="hidden">
<label for="data_format:%(eid)s">data_format</label><input id="data_format:%(eid)s" maxlength="50" name="data_format:%(eid)s" size="45" tabindex="1" type="text" value="text/plain"></input><br/>
<label for="data_encoding:%(eid)s">data_encoding</label><input id="data_encoding:%(eid)s" maxlength="20" name="data_encoding:%(eid)s" size="20" tabindex="2" type="text" value="UTF-8"></input><br/>
</div>
<br/>
<input name="data:%(eid)s__detach" type="checkbox"></input>
detach attached file
<p><b>You can either submit a new file using the browse button above, or choose to remove already uploaded file by checking the "detach attached file" check-box, or edit file content online with the widget below.</b></p>
<textarea cols="80" name="data:%(eid)s" onkeyup="autogrow(this)" rows="3" tabindex="3">new widgets system</textarea>''' % {'eid': file.eid})


    def test_passwordfield(self):
        class PFForm(EntityFieldsForm):
            upassword = StringField(widget=PasswordInput)
        form = PFForm(self.req, redirect_path='perdu.com', entity=self.entity)
        self.assertTextEquals(self._render_entity_field('upassword', form),
                              '''<input id="upassword:%(eid)s" name="upassword:%(eid)s" tabindex="0" type="password" value="__cubicweb_internal_field__"></input>
<br/>
<input name="upassword-confirm:%(eid)s" tabindex="0" type="password" value="__cubicweb_internal_field__"></input>
&nbsp;
<span class="emphasis">confirm password</span>''' % {'eid': self.entity.eid})


    def test_datefield(self):
        class DFForm(EntityFieldsForm):
            creation_date = DateTimeField(widget=Input)
        form = DFForm(self.req, entity=self.entity)
        init, cur = (fromstring(self._render_entity_field(attr, form)).get('value')
                     for attr in ('edits-creation_date', 'creation_date'))
        self.assertEquals(init, cur)

if __name__ == '__main__':
    unittest_main()
