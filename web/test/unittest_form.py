# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""

"""

from xml.etree.ElementTree import fromstring

from logilab.common.testlib import unittest_main, mock_object
from logilab.common.compat import any

from cubicweb import Binary
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.formfields import (IntField, StringField, RichTextField,
                                     PasswordField, DateTimeField,
                                     FileField, EditableFileField)
from cubicweb.web.formwidgets import PasswordInput, Input, DateTimePicker
from cubicweb.web.views.forms import EntityFieldsForm, FieldsForm
from cubicweb.web.views.workflow import ChangeStateForm
from cubicweb.web.views.formrenderers import FormRenderer


class FieldsFormTC(CubicWebTC):

    def test_form_field_format(self):
        form = FieldsForm(self.request(), None)
        self.assertEquals(StringField().format(form), 'text/html')
        self.execute('INSERT CWProperty X: X pkey "ui.default-text-format", X value "text/rest", X for_user U WHERE U login "admin"')
        self.commit()
        self.assertEquals(StringField().format(form), 'text/rest')


class EntityFieldsFormTC(CubicWebTC):

    def setUp(self):
        super(EntityFieldsFormTC, self).setUp()
        self.req = self.request()
        self.entity = self.user(self.req)

    def test_form_field_vocabulary_unrelated(self):
        b = self.req.create_entity('BlogEntry', title=u'di mascii code', content=u'a best-seller')
        t = self.req.create_entity('Tag', name=u'x')
        form1 = self.vreg['forms'].select('edition', self.req, entity=t)
        unrelated = [reid for rview, reid in form1.field_by_name('tags', 'subject', t.e_schema).choices(form1)]
        self.failUnless(b.eid in unrelated, unrelated)
        form2 = self.vreg['forms'].select('edition', self.req, entity=b)
        unrelated = [reid for rview, reid in form2.field_by_name('tags', 'object', t.e_schema).choices(form2)]
        self.failUnless(t.eid in unrelated, unrelated)
        self.execute('SET X tags Y WHERE X is Tag, Y is BlogEntry')
        unrelated = [reid for rview, reid in form1.field_by_name('tags', 'subject', t.e_schema).choices(form1)]
        self.failIf(b.eid in unrelated, unrelated)
        unrelated = [reid for rview, reid in form2.field_by_name('tags', 'object', t.e_schema).choices(form2)]
        self.failIf(t.eid in unrelated, unrelated)


    def test_form_field_vocabulary_new_entity(self):
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        form = self.vreg['forms'].select('edition', self.req, entity=e)
        unrelated = [rview for rview, reid in form.field_by_name('in_group', 'subject').choices(form)]
        # should be default groups but owners, i.e. managers, users, guests
        self.assertEquals(unrelated, [u'guests', u'managers', u'users'])

    def test_consider_req_form_params(self):
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        e.eid = 'A'
        form = EntityFieldsForm(self.request(login=u'toto'), None, entity=e)
        field = StringField(name='login', role='subject', eidparam=True)
        form.append_field(field)
        form.build_context({})
        self.assertEquals(field.widget.values(form, field), (u'toto',))


    def test_linkto_field_duplication(self):
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        e.eid = 'A'
        e._cw = self.req
        geid = self.execute('CWGroup X WHERE X name "users"')[0][0]
        self.req.form['__linkto'] = 'in_group:%s:subject' % geid
        form = self.vreg['forms'].select('edition', self.req, entity=e)
        form.content_type = 'text/html'
        pageinfo = self._check_html(form.render(), form, template=None)
        inputs = pageinfo.find_tag('select', False)
        self.failUnless(any(attrs for t, attrs in inputs if attrs.get('name') == 'in_group-subject:A'))
        inputs = pageinfo.find_tag('input', False)
        self.failIf(any(attrs for t, attrs in inputs if attrs.get('name') == '__linkto'))

    def test_reledit_composite_field(self):
        rset = self.execute('INSERT BlogEntry X: X title "cubicweb.org", X content "hop"')
        form = self.vreg['views'].select('doreledit', self.request(),
                                         rset=rset, row=0, rtype='content')
        data = form.render(row=0, rtype='content')
        self.failUnless('content_format' in data)

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
        form.render(formvalues=dict(state=123, trcomment=u'',
                                    trcomment_format=u'text/plain'))

    def test_change_state_form(self):
        form = ChangeStateForm(self.req, redirect_path='perdu.com',
                               entity=self.entity)
        form.render(formvalues=dict(state=123, trcomment=u'',
                                    trcomment_format=u'text/plain'))

    # fields tests ############################################################

    def _render_entity_field(self, name, form):
        form.build_context({})
        renderer = FormRenderer(self.req)
        return form.field_by_name(name, 'subject').render(form, renderer)

    def _test_richtextfield(self, expected):
        class RTFForm(EntityFieldsForm):
            description = RichTextField(eidparam=True, role='subject')
        state = self.vreg['etypes'].etype_class('State')(self.req)
        state.eid = 'S'
        form = RTFForm(self.req, redirect_path='perdu.com', entity=state)
        # make it think it can use fck editor anyway
        form.field_by_name('description', 'subject').format = lambda x: 'text/html'
        self.assertTextEquals(self._render_entity_field('description', form),
                              expected % {'eid': state.eid})


    def test_richtextfield_1(self):
        self.req.use_fckeditor = lambda: False
        self._test_richtextfield('''<select id="description_format-subject:%(eid)s" name="description_format-subject:%(eid)s" size="1" style="display: block" tabindex="1">
<option value="text/cubicweb-page-template">text/cubicweb-page-template</option>
<option selected="selected" value="text/html">text/html</option>
<option value="text/plain">text/plain</option>
<option value="text/rest">text/rest</option>
</select><textarea cols="80" id="description-subject:%(eid)s" name="description-subject:%(eid)s" onkeyup="autogrow(this)" rows="2" tabindex="2"></textarea>''')


    def test_richtextfield_2(self):
        self.req.use_fckeditor = lambda: True
        self._test_richtextfield('<input name="description_format-subject:%(eid)s" type="hidden" value="text/html" /><textarea cols="80" cubicweb:type="wysiwyg" id="description-subject:%(eid)s" name="description-subject:%(eid)s" onkeyup="autogrow(this)" rows="2" tabindex="1"></textarea>')


    def test_filefield(self):
        class FFForm(EntityFieldsForm):
            data = FileField(
                format_field=StringField(name='data_format', max_length=50,
                                         eidparam=True, role='subject'),
                encoding_field=StringField(name='data_encoding', max_length=20,
                                           eidparam=True, role='subject'),
                eidparam=True, role='subject')
        file = self.req.create_entity('File', data_name=u"pouet.txt", data_encoding=u'UTF-8',
                               data=Binary('new widgets system'))
        form = FFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data-subject:%(eid)s" name="data-subject:%(eid)s" tabindex="1" type="file" value="" />
<a href="javascript: toggleVisibility(&#39;data-subject:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data-subject:%(eid)s-advanced" class="hidden">
<label for="data_format-subject:%(eid)s">data_format</label><input id="data_format-subject:%(eid)s" maxlength="50" name="data_format-subject:%(eid)s" size="45" tabindex="2" type="text" value="text/plain" /><br/>
<label for="data_encoding-subject:%(eid)s">data_encoding</label><input id="data_encoding-subject:%(eid)s" maxlength="20" name="data_encoding-subject:%(eid)s" size="20" tabindex="3" type="text" value="UTF-8" /><br/>
</div>
<br/>
<input name="data-subject__detach:%(eid)s" type="checkbox" />
detach attached file
''' % {'eid': file.eid})


    def test_editablefilefield(self):
        class EFFForm(EntityFieldsForm):
            data = EditableFileField(
                format_field=StringField('data_format', max_length=50,
                                         eidparam=True, role='subject'),
                encoding_field=StringField('data_encoding', max_length=20,
                                           eidparam=True, role='subject'),
                eidparam=True, role='subject')
        file = self.req.create_entity('File', data_name=u"pouet.txt", data_encoding=u'UTF-8',
                               data=Binary('new widgets system'))
        form = EFFForm(self.req, redirect_path='perdu.com', entity=file)
        self.assertTextEquals(self._render_entity_field('data', form),
                              '''<input id="data-subject:%(eid)s" name="data-subject:%(eid)s" tabindex="1" type="file" value="" />
<a href="javascript: toggleVisibility(&#39;data-subject:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data-subject:%(eid)s-advanced" class="hidden">
<label for="data_format-subject:%(eid)s">data_format</label><input id="data_format-subject:%(eid)s" maxlength="50" name="data_format-subject:%(eid)s" size="45" tabindex="2" type="text" value="text/plain" /><br/>
<label for="data_encoding-subject:%(eid)s">data_encoding</label><input id="data_encoding-subject:%(eid)s" maxlength="20" name="data_encoding-subject:%(eid)s" size="20" tabindex="3" type="text" value="UTF-8" /><br/>
</div>
<br/>
<input name="data-subject__detach:%(eid)s" type="checkbox" />
detach attached file
<p><b>You can either submit a new file using the browse button above, or choose to remove already uploaded file by checking the "detach attached file" check-box, or edit file content online with the widget below.</b></p>
<textarea cols="80" name="data-subject:%(eid)s" onkeyup="autogrow(this)" rows="3" tabindex="4">new widgets system</textarea>''' % {'eid': file.eid})


    def test_passwordfield(self):
        class PFForm(EntityFieldsForm):
            upassword = PasswordField(eidparam=True, role='subject')
        form = PFForm(self.req, redirect_path='perdu.com', entity=self.entity)
        self.assertTextEquals(self._render_entity_field('upassword', form),
                              '''<input id="upassword-subject:%(eid)s" name="upassword-subject:%(eid)s" tabindex="1" type="password" value="" />
<br/>
<input name="upassword-subject-confirm:%(eid)s" tabindex="1" type="password" value="" />
&#160;
<span class="emphasis">confirm password</span>''' % {'eid': self.entity.eid})


    # def test_datefield(self):
    #     class DFForm(EntityFieldsForm):
    #         creation_date = DateTimeField(widget=Input)
    #     form = DFForm(self.req, entity=self.entity)
    #     init, cur = (fromstring(self._render_entity_field(attr, form)).get('value')
    #                  for attr in ('edits-creation_date', 'creation_date'))
    #     self.assertEquals(init, cur)

if __name__ == '__main__':
    unittest_main()
