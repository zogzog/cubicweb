"""cubicweb.common.widget unit tests

"""

from mx.DateTime import now
NOW = now()
from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.common.mttransforms import HAS_TAL
from cubicweb.web.widgets import widget, AutoCompletionWidget


class WidgetsTC(EnvBasedTC):
        
    def get_widget(self, etype, rname, rtype):
        rschema = self.schema[rname]
        return widget(self.vreg, etype, rschema, rtype, role='subject')
    

    def test_hidden_widget(self):
        w = self.get_widget('State', 'eid', 'Int')
        self.assertEquals(w.name, 'eid')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {})
        entity = self.etype_instance('State')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), True)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="eid" value="X" />')

    def test_textarea_widget(self):
        self.add_entity('EProperty', pkey=u'ui.fckeditor', value=u'')
        self.commit()
        w = self.get_widget('State', 'description', 'String')
        self.assertEquals(w.name, 'description')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {'accesskey': 'd'})
        entity = self.etype_instance('State')
        entity.eid = 'X'
        entity
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        if HAS_TAL:
            tal_format = u'\n<option value="text/cubicweb-page-template" >text/cubicweb-page-template</option>'
        else:
            tal_format = u''
        self.assertTextEquals(w.edit_render(entity),
                           u'''<input type="hidden" name="edits-description:X" value="__cubicweb_internal_field__"/>
<input type="hidden" name="edits-description_format:X" value="__cubicweb_internal_field__"/>

<select name="description_format:X" id="description_format:X" tabindex="0">
<option value="text/rest" >text/rest</option>
<option value="text/html" selected="selected">text/html</option>
<option value="text/plain" >text/plain</option>%s
</select><br/><textarea onkeypress="autogrow(this)" name="description:X" accesskey="d" cols="80" id="description:X" rows="20" tabindex="1"></textarea>''' % tal_format)

    def test_textarea_widget_previous_value(self):
        self.add_entity('EProperty', pkey=u'ui.fckeditor', value=u'')
        self.commit()
        w = self.get_widget('State', 'description', 'String')
        req = self.request()
        req.data['formvalues'] = {'description:X': 'a description'}
        entity = self.etype_instance('State', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        if HAS_TAL:
            tal_format = u'\n<option value="text/cubicweb-page-template" >text/cubicweb-page-template</option>'
        else:
            tal_format = u''
        self.assertTextEquals(w.edit_render(entity),
                           u'''<input type="hidden" name="edits-description:X" value="__cubicweb_internal_field__"/>
<input type="hidden" name="edits-description_format:X" value="__cubicweb_internal_field__"/>

<select name="description_format:X" id="description_format:X" tabindex="0">
<option value="text/rest" >text/rest</option>
<option value="text/html" selected="selected">text/html</option>
<option value="text/plain" >text/plain</option>%s
</select><br/><textarea onkeypress="autogrow(this)" name="description:X" accesskey="d" cols="80" id="description:X" rows="20" tabindex="1">a description</textarea>''' % tal_format)

    def test_fckeditor_widget(self):
        w = self.get_widget('State', 'description', 'String')
        req = self.request()
        entity = self.etype_instance('State', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertTextEquals(w.edit_render(entity),
                           u'''<input type="hidden" name="edits-description:X" value="__cubicweb_internal_field__"/>
<input type="hidden" name="edits-description_format:X" value=""/>
<input type="hidden" name="description_format:X" value="text/html"/>
<textarea cubicweb:type="wysiwyg" onkeypress="autogrow(this)" name="description:X" accesskey="d" cols="80" id="description:X" rows="20" tabindex="0"></textarea>''')

    def test_string_widget(self):
        w = self.get_widget('Personne', 'nom', 'String')
        self.assertEquals(w.name, 'nom')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {'accesskey': 'n', 'maxlength': 64, 'size': 40})
        entity = self.etype_instance('Personne')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), True)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-nom:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="nom:X" value="" accesskey="n" id="nom:X" maxlength="64" size="40" tabindex="0"/>')

    def test_string_widget_previous_value(self):
        w = self.get_widget('Personne', 'nom', 'String')
        self.assertEquals(w.name, 'nom')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {'accesskey': 'n', 'maxlength': 64, 'size': 40})
        req = self.request()
        req.data['formvalues'] = {'nom:X': 'a name'}
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), True)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-nom:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="nom:X" value="a name" accesskey="n" id="nom:X" maxlength="64" size="40" tabindex="0"/>')

    def test_static_combo_widget(self):
        w = self.get_widget('Personne', 'promo', 'String')
        self.assertEquals(w.name, 'promo')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {})
        entity = self.etype_instance('Personne')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertTextEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-promo:X" value="__cubicweb_internal_field__"/>\n\n'
                          '<select name="promo:X" id="promo:X" tabindex="0">\n'
                          '<option value="bon" >bon</option>\n'
                          '<option value="pasbon" >pasbon</option>\n'
                          '</select>')

    def test_static_combo_widget_previous_value(self):
        w = self.get_widget('Personne', 'promo', 'String')
        self.assertEquals(w.name, 'promo')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {})
        req = self.request()
        req.data['formvalues'] = {'promo:X': 'pasbon'}
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertTextEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-promo:X" value="__cubicweb_internal_field__"/>\n\n'
                          '<select name="promo:X" id="promo:X" tabindex="0">\n'
                          '<option value="bon" >bon</option>\n'
                          '<option value="pasbon" selected="selected">pasbon</option>\n'
                          '</select>')

    def test_integer_widget(self):
        w = self.get_widget('Personne', 'tel', 'Int')
        self.assertEquals(w.name, 'tel')
        self.assertEquals(w.render_example(self.request()), '23')
        self.assertDictEquals(w.attrs, {'accesskey': 't', 'maxlength': 15, 'size': 5})
        entity = self.etype_instance('Personne')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-tel:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="tel:X" value="" accesskey="t" id="tel:X" maxlength="15" size="5" tabindex="0"/>')

    def test_integer_widget_previous_value(self):
        w = self.get_widget('Personne', 'tel', 'Int')
        self.assertEquals(w.name, 'tel')
        self.assertEquals(w.render_example(self.request()), '23')
        self.assertDictEquals(w.attrs, {'accesskey': 't', 'maxlength': 15, 'size': 5})
        req = self.request()
        req.data['formvalues'] = {'tel:X': '0123456789'}
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-tel:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="tel:X" value="0123456789" accesskey="t" id="tel:X" maxlength="15" size="5" tabindex="0"/>')

    def test_datetime_widget(self):
        w = self.get_widget('Personne', 'datenaiss', 'Datetime')
        self.assertEquals(w.name, 'datenaiss')
        now_ = now()
        example = '%s, or without time: %s' % (        
            now_.strftime(self.vreg.property_value('ui.datetime-format')),
            now_.strftime(self.vreg.property_value('ui.date-format')))
        self.assertEquals(w.render_example(self.request()), example)
        self.assertDictEquals(w.attrs, {'accesskey': 'd', 'maxlength': 16, 'size': 16})
        entity = self.etype_instance('Personne')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-datenaiss:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="datenaiss:X" value="" accesskey="d" id="datenaiss:X" maxlength="16" size="16" tabindex="0"/>'
                          '<a onclick="toggleCalendar(\'datenaiss:Xhelper\', \'datenaiss:X\', %s, %s);" class="calhelper">\n<img src="http://testing.fr/cubicweb/data/calendar.gif" title="calendar" alt="" /></a><div class="calpopup hidden" id="datenaiss:Xhelper"></div>' % (NOW.year, NOW.month))

    def test_datetime_widget_previous_value(self):
        w = self.get_widget('Personne', 'datenaiss', 'Datetime')
        self.assertEquals(w.name, 'datenaiss')
        self.assertDictEquals(w.attrs, {'accesskey': 'd', 'maxlength': 16, 'size': 16})
        req = self.request()
        req.data['formvalues'] = {'datenaiss:X': '2000/01/01'}
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-datenaiss:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="datenaiss:X" value="2000/01/01" accesskey="d" id="datenaiss:X" maxlength="16" size="16" tabindex="0"/>'
                          '<a onclick="toggleCalendar(\'datenaiss:Xhelper\', \'datenaiss:X\', %s, %s);" class="calhelper">\n<img src="http://testing.fr/cubicweb/data/calendar.gif" title="calendar" alt="" /></a><div class="calpopup hidden" id="datenaiss:Xhelper"></div>' % (NOW.year, NOW.month))



    def test_float_widget(self):
        w = self.get_widget('Personne', 'salary', 'Float')
        self.assertEquals(w.name, 'salary')
        format = now().strftime(self.vreg.property_value('ui.float-format'))
        self.assertEquals(w.render_example(self.request()), format % 1.23)
        self.assertDictEquals(w.attrs, {'accesskey': 's', 'maxlength': 15, 'size': 5})
        entity = self.etype_instance('Personne')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                          u'<input type="hidden" name="edits-salary:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="salary:X" value="" accesskey="s" id="salary:X" maxlength="15" size="5" tabindex="0"/>')
                          
                          
    def test_float_widget_previous_value(self):
        w = self.get_widget('Personne', 'salary', 'Float')
        self.assertEquals(w.name, 'salary')
        format = now().strftime(self.vreg.property_value('ui.float-format'))
        self.assertEquals(w.render_example(self.request()), format % 1.23)
        self.assertDictEquals(w.attrs, {'accesskey': 's', 'maxlength': 15, 'size': 5})
        req = self.request()
        req.data['formvalues'] = {'salary:X': 7.89}
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                          u'<input type="hidden" name="edits-salary:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="salary:X" value="7.89" accesskey="s" id="salary:X" maxlength="15" size="5" tabindex="0"/>')


    def test_bool_widget(self):
        w = self.get_widget('Personne', 'test', 'Boolean')
        self.assertEquals(w.name, 'test')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {'accesskey': 't'})
        entity = self.etype_instance('Personne')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'''<input type="hidden" name="edits-test:X" value="__cubicweb_internal_field__"/>

<input type="radio" name="test:X" value="1" accesskey="t" id="test:X" tabindex="0"/>yes<br/>
<input type="radio" name="test:X" value="" accesskey="t" tabindex="0" checked="checked"/>no<br/>''')

    def test_bool_widget_previous_value(self):
        w = self.get_widget('Personne', 'test', 'Boolean')
        self.assertEquals(w.name, 'test')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {'accesskey': 't'})
        req = self.request()
        req.data['formvalues'] = {'test:X': 'checked'}
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'''<input type="hidden" name="edits-test:X" value="__cubicweb_internal_field__"/>

<input type="radio" name="test:X" value="1" accesskey="t" id="test:X" tabindex="0" checked="checked"/>yes<br/>
<input type="radio" name="test:X" value="" accesskey="t" tabindex="0"/>no<br/>''')


    def test_password_widget(self):
        w = self.get_widget('EUser', 'upassword', 'Password')
        self.assertEquals(w.name, 'upassword')
        self.assertEquals(w.render_example(self.request()), '')
        self.assertDictEquals(w.attrs, {'accesskey': 'u'})
        entity = self.etype_instance('EUser')
        entity.eid = 'X'
        self.assertEquals(w.required(entity), True)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                           u'<input type="hidden" name="edits-upassword:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="password" name="upassword:X" value="" accesskey="u" id="upassword:X" tabindex="0"/><br/>\n'
                          '<input type="password" name="upassword-confirm:X" id="upassword-confirm:X" tabindex="1"/>&nbsp;<span class="emphasis">(confirm password)</span>')

    def test_autocompletion_widget(self):
        entity = self.etype_instance('Personne')
        entity.widgets['nom'] = 'AutoCompletionWidget'
        entity.autocomplete_initfuncs = {'nom' : 'getnames'}
        try:
            w = self.get_widget(entity, 'nom', 'String')
            self.failUnless(isinstance(w, AutoCompletionWidget))
            self.assertEquals(w.name, 'nom')
            self.assertEquals(w.render_example(self.request()), '')
            self.assertDictEquals(w.attrs, {'accesskey': 'n', 'maxlength': 64, 'size': 40})
            entity.eid = 'X'
            self.assertEquals(w.required(entity), True)
            self.assertEquals(w.render(entity), '')

            self.assertTextEquals(w.edit_render(entity),
                                  u'<input type="hidden" name="edits-nom:X" value="__cubicweb_internal_field__"/>\n'
                                  u'<input type="text" name="nom:X" value="" cubicweb:dataurl="http://testing.fr/cubicweb/json?pageid=None&amp;mode=remote&amp;fname=getnames" class="widget required" id="nom:X" tabindex="0" cubicweb:loadtype="auto" cubicweb:wdgtype="SuggestField"  cubicweb:accesskey="n" cubicweb:maxlength="64" cubicweb:size="40" />')
                                  
        finally:
            del entity.widgets['nom']


    def test_autocompletion_widget_previous_value(self):
        req = self.request()
        req.data['formvalues'] = {'nom:X': 'a name'}
        entity = self.etype_instance('Personne', req)
        entity.widgets['nom'] = 'AutoCompletionWidget'
        entity.autocomplete_initfuncs = {'nom' : 'getnames'}
        try:
            w = self.get_widget(entity, 'nom', 'String')
            self.failUnless(isinstance(w, AutoCompletionWidget))
            self.assertEquals(w.name, 'nom')
            self.assertEquals(w.render_example(self.request()), '')
            self.assertDictEquals(w.attrs, {'accesskey': 'n', 'maxlength': 64, 'size': 40})
            entity.eid = 'X'
            self.assertEquals(w.required(entity), True)
            self.assertEquals(w.render(entity), '')
            self.assertTextEquals(w.edit_render(entity),
                                  u'<input type="hidden" name="edits-nom:X" value="__cubicweb_internal_field__"/>\n'
                                  u'<input type="text" name="nom:X" value="a name" cubicweb:dataurl="http://testing.fr/cubicweb/json?pageid=None&amp;mode=remote&amp;fname=getnames" class="widget required" id="nom:X" tabindex="0" cubicweb:loadtype="auto" cubicweb:wdgtype="SuggestField"  cubicweb:accesskey="n" cubicweb:maxlength="64" cubicweb:size="40" />')
            
        finally:
            del entity.widgets['nom']


    def test_nonregr_float_widget_with_none(self):
        w = self.get_widget('Personne', 'salary', 'Float')
        self.assertEquals(w.name, 'salary')
        format = now().strftime(self.vreg.property_value('ui.float-format'))
        self.assertEquals(w.render_example(self.request()), format % 1.23)
        self.assertDictEquals(w.attrs, {'accesskey': 's', 'maxlength': 15, 'size': 5})
        req = self.request()
        entity = self.etype_instance('Personne', req)
        entity.eid = 'X'
        entity.salary = None
        self.assertEquals(w.required(entity), False)
        self.assertEquals(w.render(entity), '')
        self.assertEquals(w.edit_render(entity),
                          u'<input type="hidden" name="edits-salary:X" value="__cubicweb_internal_field__"/>\n'
                          '<input type="text" name="salary:X" value="" accesskey="s" id="salary:X" maxlength="15" size="5" tabindex="0"/>')


    def test_custom_widget_for_non_final_relation(self):
        entity = self.etype_instance('Personne', self.request())
        entity.widgets['travaille'] = 'AutoCompletionWidget'
        entity.autocomplete_initfuncs = {'nom' : 'getnames'}
        w = self.get_widget(entity, 'travaille', 'Societe')
        self.failUnless(isinstance(w, AutoCompletionWidget))
        
        
if __name__ == '__main__':
    unittest_main()
