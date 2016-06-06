# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import time
from datetime import datetime
import pytz

from xml.etree.ElementTree import fromstring
from lxml import html

from six import text_type

from logilab.common.testlib import unittest_main

from cubicweb import Binary, ValidationError
from cubicweb.mttransforms import HAS_TAL
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.formfields import (IntField, StringField, RichTextField,
                                     PasswordField, DateTimeField,
                                     FileField, EditableFileField,
                                     TZDatetimeField)
from cubicweb.web.formwidgets import PasswordInput, Input, DateTimePicker
from cubicweb.web.views.forms import EntityFieldsForm, FieldsForm
from cubicweb.web.views.workflow import ChangeStateForm
from cubicweb.web.views.formrenderers import FormRenderer


class FieldsFormTC(CubicWebTC):

    def test_form_field_format(self):
        with self.admin_access.web_request() as req:
            form = FieldsForm(req, None)
            self.assertEqual(StringField().format(form), 'text/plain')
            req.cnx.execute('INSERT CWProperty X: X pkey "ui.default-text-format", X value "text/rest", X for_user U WHERE U login "admin"')
            req.cnx.commit()
            self.assertEqual(StringField().format(form), 'text/rest')


    def test_process_posted(self):
        class AForm(FieldsForm):
            anint = IntField()
            astring = StringField()
        with self.admin_access.web_request(anint='1', astring='2', _cw_fields='anint,astring') as req:
            form = AForm(req)
            self.assertEqual(form.process_posted(), {'anint': 1, 'astring': '2'})
        with self.admin_access.web_request(anint='1a', astring='2b', _cw_fields='anint,astring') as req:
            form = AForm(req)
            self.assertRaises(ValidationError, form.process_posted)


class EntityFieldsFormTC(CubicWebTC):

    def test_form_field_choices(self):
        with self.admin_access.web_request() as req:
            b = req.create_entity('BlogEntry', title=u'di mascii code', content=u'a best-seller')
            t = req.create_entity('Tag', name=u'x')
            form1 = self.vreg['forms'].select('edition', req, entity=t)
            choices = [reid for rview, reid in form1.field_by_name('tags', 'subject', t.e_schema).choices(form1)]
            self.assertIn(text_type(b.eid), choices)
            form2 = self.vreg['forms'].select('edition', req, entity=b)
            choices = [reid for rview, reid in form2.field_by_name('tags', 'object', t.e_schema).choices(form2)]
            self.assertIn(text_type(t.eid), choices)

            b.cw_clear_all_caches()
            t.cw_clear_all_caches()
            req.cnx.execute('SET X tags Y WHERE X is Tag, Y is BlogEntry')

            choices = [reid for rview, reid in form1.field_by_name('tags', 'subject', t.e_schema).choices(form1)]
            self.assertIn(text_type(b.eid), choices)
            choices = [reid for rview, reid in form2.field_by_name('tags', 'object', t.e_schema).choices(form2)]
            self.assertIn(text_type(t.eid), choices)

    def test_form_field_choices_new_entity(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            form = self.vreg['forms'].select('edition', req, entity=e)
            unrelated = [rview for rview, reid in form.field_by_name('in_group', 'subject').choices(form)]
            # should be default groups but owners, i.e. managers, users, guests
            self.assertEqual(unrelated, [u'guests', u'managers', u'users'])

    def test_consider_req_form_params(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            e.eid = 'A'
            with self.admin_access.web_request(login=u'toto') as toto_req:
                form = EntityFieldsForm(toto_req, None, entity=e)
                field = StringField(name='login', role='subject', eidparam=True)
                form.append_field(field)
                form.build_context({})
                self.assertEqual(field.widget.values(form, field), (u'toto',))

    def test_linkto_field_duplication_inout(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            e.eid = 'A'
            e._cw = req
            geid = req.cnx.execute('CWGroup X WHERE X name "users"')[0][0]
            req.form['__linkto'] = 'in_group:%s:subject' % geid
            form = self.vreg['forms'].select('edition', req, entity=e)
            form.content_type = 'text/html'
            data = []
            form.render(w=data.append)
            pageinfo = self._check_html(u'\n'.join(data), form, template=None)
            inputs = pageinfo.find_tag('select', False)
            ok = False
            for selectnode in pageinfo.matching_nodes('select', name='from_in_group-subject:A'):
                for optionnode in selectnode:
                    self.assertEqual(optionnode.get('value'), str(geid))
                    self.assertEqual(ok, False)
                    ok = True
            inputs = pageinfo.find_tag('input', False)
            self.assertFalse(list(pageinfo.matching_nodes('input', name='__linkto')))

    def test_reledit_composite_field(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('INSERT BlogEntry X: X title "cubicweb.org", X content "hop"')
            form = self.vreg['views'].select('reledit', req,
                                             rset=rset, row=0, rtype='content')
            data = form.render(row=0, rtype='content', formid='base', action='edit_rtype')
            self.assertIn('content_format', data)


    def test_form_generation_time(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('BlogEntry', title=u'cubicweb.org', content=u"hop")
            expected_field_name = '__form_generation_time:%d' % e.eid

            ts_before = time.time()
            form = self.vreg['forms'].select('edition', req, entity=e)
            ts_after = time.time()

            data = []
            form.render(action='edit', w=data.append)
            html_form = html.fromstring(''.join(data)).forms[0]
            fields = dict(html_form.form_values())
            self.assertIn(expected_field_name, fields)
            ts = float(fields[expected_field_name])
            self.assertTrue(ts_before < ts  < ts_after)


    # form tests ##############################################################

    def test_form_inheritance(self):
        with self.admin_access.web_request() as req:
            class CustomChangeStateForm(ChangeStateForm):
                hello = IntField(name='youlou')
                creation_date = DateTimeField(widget=DateTimePicker)
            form = CustomChangeStateForm(req, redirect_path='perdu.com',
                                         entity=req.user)
            data = []
            form.render(w=data.append,
                        formvalues=dict(state=123, trcomment=u'',
                                        trcomment_format=u'text/plain'))

    def test_change_state_form(self):
        with self.admin_access.web_request() as req:
            form = ChangeStateForm(req, redirect_path='perdu.com',
                                   entity=req.user)
            data = []
            form.render(w=data.append,
                        formvalues=dict(state=123, trcomment=u'',
                                        trcomment_format=u'text/plain'))

    # fields tests ############################################################

    def _render_entity_field(self, req, name, form):
        form.build_context({})
        renderer = FormRenderer(req)
        return form.field_by_name(name, 'subject').render(form, renderer)

    def _test_richtextfield(self, req, expected):
        class RTFForm(EntityFieldsForm):
            description = RichTextField(eidparam=True, role='subject')
        state = self.vreg['etypes'].etype_class('State')(req)
        state.eid = 'S'
        form = RTFForm(req, redirect_path='perdu.com', entity=state)
        # make it think it can use fck editor anyway
        form.field_by_name('description', 'subject').format = lambda form, field=None: 'text/html'
        self.assertMultiLineEqual(self._render_entity_field(req, 'description', form),
                              expected % {'eid': state.eid})


    def test_richtextfield_1(self):
        with self.admin_access.web_request() as req:
            req.use_fckeditor = lambda: False
            self._test_richtextfield(req, '''<select id="description_format-subject:%(eid)s" name="description_format-subject:%(eid)s" size="1" style="display: block" tabindex="1">
''' + ('<option value="text/cubicweb-page-template">text/cubicweb-page-template</option>\n'
if HAS_TAL else '') +
'''<option selected="selected" value="text/html">text/html</option>
<option value="text/markdown">text/markdown</option>
<option value="text/plain">text/plain</option>
<option value="text/rest">text/rest</option>
</select><textarea cols="80" id="description-subject:%(eid)s" name="description-subject:%(eid)s" onkeyup="autogrow(this)" rows="2" tabindex="2"></textarea>''')


    def test_richtextfield_2(self):
        with self.admin_access.web_request() as req:
            req.use_fckeditor = lambda: True
            self._test_richtextfield(req, '<input name="description_format-subject:%(eid)s" type="hidden" value="text/html" /><textarea cols="80" cubicweb:type="wysiwyg" id="description-subject:%(eid)s" name="description-subject:%(eid)s" onkeyup="autogrow(this)" rows="2" tabindex="1"></textarea>')


    def test_filefield(self):
        class FFForm(EntityFieldsForm):
            data = FileField(
                format_field=StringField(name='data_format', max_length=50,
                                         eidparam=True, role='subject'),
                encoding_field=StringField(name='data_encoding', max_length=20,
                                           eidparam=True, role='subject'),
                eidparam=True, role='subject')
        with self.admin_access.web_request() as req:
            file = req.create_entity('File', data_name=u"pouet.txt", data_encoding=u'UTF-8',
                                     data=Binary(b'new widgets system'))
            form = FFForm(req, redirect_path='perdu.com', entity=file)
            self.assertMultiLineEqual(self._render_entity_field(req, 'data', form),
                              '''<input id="data-subject:%(eid)s" name="data-subject:%(eid)s" tabindex="1" type="file" value="" />
<a href="javascript: toggleVisibility(&#39;data-subject:%(eid)s-advanced&#39;)" title="show advanced fields"><img src="http://testing.fr/cubicweb/data/puce_down.png" alt="show advanced fields"/></a>
<div id="data-subject:%(eid)s-advanced" class="hidden">
<label for="data_format-subject:%(eid)s">data_format</label><input id="data_format-subject:%(eid)s" maxlength="50" name="data_format-subject:%(eid)s" size="45" tabindex="2" type="text" value="text/plain" /><br/>
<label for="data_encoding-subject:%(eid)s">data_encoding</label><input id="data_encoding-subject:%(eid)s" maxlength="20" name="data_encoding-subject:%(eid)s" size="20" tabindex="3" type="text" value="UTF-8" /><br/>
</div>
<br/>
<input name="data-subject__detach:%(eid)s" type="checkbox" />
detach attached file''' % {'eid': file.eid})


    def test_editablefilefield(self):
        class EFFForm(EntityFieldsForm):
            data = EditableFileField(
                format_field=StringField('data_format', max_length=50,
                                         eidparam=True, role='subject'),
                encoding_field=StringField('data_encoding', max_length=20,
                                           eidparam=True, role='subject'),
                eidparam=True, role='subject')
        with self.admin_access.web_request() as req:
            file = req.create_entity('File', data_name=u"pouet.txt", data_encoding=u'UTF-8',
                                     data=Binary(b'new widgets system'))
            form = EFFForm(req, redirect_path='perdu.com', entity=file)
            self.assertMultiLineEqual(self._render_entity_field(req, 'data', form),
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

    def _modified_tzdatenaiss(self, eid, datestr, timestr):
        ctx = {'tzdatenaiss-subjectdate:%d' % eid: datestr,
               'tzdatenaiss-subjecttime:%d' % eid: timestr}
        with self.admin_access.web_request(**ctx) as req:
            form = EntityFieldsForm(req, None, entity=req.entity_from_eid(eid))
            field = TZDatetimeField(name='tzdatenaiss', eidparam=True,
                                    role='subject')
            form.append_field(field)
            form.build_context({})
            return field.has_been_modified(form)

    def test_tzdatetimefield(self):
        """ Comparison of the tz-aware database-stored value and the posted data
        should not crash, and the posted data should be considered UTC """
        tzd = datetime.now(pytz.utc).replace(second=0, microsecond=0)
        datestr, timestr = tzd.strftime('%Y/%m/%d %H:%M').split()
        with self.admin_access.web_request() as req:
            eid = req.create_entity('Personne', nom=u'Flo', tzdatenaiss=tzd).eid
            req.cnx.commit()

        modified = self._modified_tzdatenaiss(eid, datestr, timestr)
        self.assertFalse(modified)

        modified = self._modified_tzdatenaiss(eid, '2016/05/04', '15:07')
        self.assertTrue(modified)

    def test_passwordfield(self):
        class PFForm(EntityFieldsForm):
            upassword = PasswordField(eidparam=True, role='subject')
        with self.admin_access.web_request() as req:
            form = PFForm(req, redirect_path='perdu.com', entity=req.user)
            self.assertMultiLineEqual(self._render_entity_field(req, 'upassword', form),
                                  '''<input id="upassword-subject:%(eid)s" name="upassword-subject:%(eid)s" tabindex="1" type="password" value="" />
<br/>
<input name="upassword-subject-confirm:%(eid)s" tabindex="1" type="password" value="" />
&#160;
<span class="emphasis">confirm password</span>''' % {'eid': req.user.eid})


    # def test_datefield(self):
    #     class DFForm(EntityFieldsForm):
    #         creation_date = DateTimeField(widget=Input)
    #     form = DFForm(self.req, entity=self.entity)
    #     init, cur = (fromstring(self._render_entity_field(attr, form)).get('value')
    #                  for attr in ('edits-creation_date', 'creation_date'))
    #     self.assertEqual(init, cur)

if __name__ == '__main__':
    unittest_main()
