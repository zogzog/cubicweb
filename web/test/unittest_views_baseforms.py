"""cubicweb.web.views.baseforms unit tests"""

from StringIO import StringIO
import re

from mx.DateTime import DateTime

from logilab.common.testlib import unittest_main
from logilab.common.decorators import clear_cache
from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.entities import AnyEntity
from cubicweb.web import widgets

orig_today = widgets.today
orig_now = widgets.now

def setup_module(options):
    def _today():
        return DateTime(0000, 1, 1)
    widgets.today = widgets.now = _today

def teardown_module(options, result):
    widgets.today = orig_today
    widgets.now = orig_now


def cleanup_text(text):
    return re.sub('\d\d:\d\d', 'hh:mm', re.sub('\d+/\d\d/\d\d', 'YYYY/MM/DD', '\n'.join(l.strip() for l in text.splitlines() if l.strip())))



class EditionFormTC(EnvBasedTC):

    def setup_database(self):
        self.create_user('joe')
        
    def _build_creation_form(self, etype):
        req = self.request()
        req.next_tabindex()
        req.next_tabindex()
        req.del_page_data()
        req.form['etype'] = etype
        view = self.vreg.select_view('creation', req, None)
        entity = self.vreg.etype_class(etype)(req, None, None)
        buffer = StringIO()
        view.w = buffer.write
        view.edit_form(entity, {})
        return buffer.getvalue()
    
    def _test_view_for(self, etype, expected):
        self.assertTextEquals(expected, cleanup_text(self._build_creation_form(etype)))
        
    def test_base(self):
        self._test_view_for('EGroup', '''\
<form id="entityForm" class="entityForm" cubicweb:target="eformframe"
method="post" onsubmit="return freezeFormButtons('entityForm')" enctype="application/x-www-form-urlencoded" action="http://testing.fr/cubicweb/validateform">
<div class="formTitle"><span>egroup (creation)</span></div>
<div id="progress">validating...</div>
<div class="iformTitle"><span>main informations</span></div>
<div class="formBody"><fieldset>
<input type="hidden" name="eid" value="A" />
<input type="hidden" name="__type:A" value="EGroup" />
<input type="hidden" name="__maineid" value="A" />
<input id="errorurl" type="hidden" name="__errorurl" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop" />
<input type="hidden" name="__form_id" value="edition" />
<input type="hidden" name="__message" value="element created" />
<table id="entityFormA" class="attributeForm" style="width:100%;">
<tr>
<th class="labelCol"><label class="required" for="name:A">name</label></th>
<td style="width:100%;">
<input type="hidden" name="edits-name:A" value="__cubicweb_internal_field__"/>
<input type="text" name="name:A" value="" accesskey="n" id="name:A" maxlength="64" size="40" tabindex="2"/>
<br/>
</td>
</tr>
</table>
</fieldset>
</div>
<table width="100%">
<tbody>
<tr><td align="center">
<input class="validateButton" type="submit" name="defaultsubmit" value="Button_ok" tabindex="3"/>
</td><td style="align: right; width: 50%;">
<input class="validateButton" type="button" onclick="postForm('__action_apply', 'Button_apply', 'entityForm')" value="Button_apply" tabindex="4"/>
<input class="validateButton" type="button" onclick="postForm('__action_cancel', 'Button_cancel', 'entityForm')" value="Button_cancel" tabindex="5"/>
</td></tr>
</tbody>
</table>
</form>''')

    def test_with_inline_view(self):
        activated = self.execute('Any X WHERE X is State, X name "activated"')[0][0]
        self._test_view_for('EUser', '''<form id="entityForm" class="entityForm" cubicweb:target="eformframe"
method="post" onsubmit="return freezeFormButtons('entityForm')" enctype="application/x-www-form-urlencoded" action="http://testing.fr/cubicweb/validateform">
<div class="formTitle"><span>euser (creation)</span></div>
<div id="progress">validating...</div>
<div class="iformTitle"><span>main informations</span></div>
<div class="formBody"><fieldset>
<input type="hidden" name="eid" value="A" />
<input type="hidden" name="__type:A" value="EUser" />
<input type="hidden" name="__maineid" value="A" />
<input id="errorurl" type="hidden" name="__errorurl" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop" />
<input type="hidden" name="__form_id" value="edition" />
<input type="hidden" name="__message" value="element created" />
<table id="entityFormA" class="attributeForm" style="width:100%%;">
<tr>
<th class="labelCol"><label class="required" for="login:A">login</label></th>
<td style="width:100%%;">
<input type="hidden" name="edits-login:A" value="__cubicweb_internal_field__"/>
<input type="text" name="login:A" value="" accesskey="l" id="login:A" maxlength="64" size="40" tabindex="2"/>
<br/>&nbsp;<span class="helper">unique identifier used to connect to the application</span>
</td>
</tr>
<tr>
<th class="labelCol"><label class="required" for="upassword:A">upassword</label></th>
<td style="width:100%%;">
<input type="hidden" name="edits-upassword:A" value="__cubicweb_internal_field__"/>
<input type="password" name="upassword:A" value="" accesskey="u" id="upassword:A" tabindex="3"/><br/>
<input type="password" name="upassword-confirm:A" id="upassword-confirm:A" tabindex="4"/>&nbsp;<span class="emphasis">(confirm password)</span>
<br/>
</td>
</tr>
<tr>
<th class="labelCol"><label for="firstname:A">firstname</label></th>
<td style="width:100%%;">
<input type="hidden" name="edits-firstname:A" value="__cubicweb_internal_field__"/>
<input type="text" name="firstname:A" value="" accesskey="f" id="firstname:A" maxlength="64" size="40" tabindex="5"/>
<br/>
</td>
</tr>
<tr>
<th class="labelCol"><label for="surname:A">surname</label></th>
<td style="width:100%%;">
<input type="hidden" name="edits-surname:A" value="__cubicweb_internal_field__"/>
<input type="text" name="surname:A" value="" accesskey="s" id="surname:A" maxlength="64" size="40" tabindex="6"/>
<br/>
</td>
</tr>
<tr>
<th class="labelCol"><label class="required" for="in_group:A">in_group</label></th>
<td style="width:100%%;">
<input type="hidden" name="edits-in_group:A" value="__cubicweb_internal_field__"/>
<select name="in_group:A" id="in_group:A" multiple="multiple" size="5" tabindex="7">
<option value="3" >guests</option>
<option value="1" >managers</option>
<option value="2" >users</option>
</select>
<br/>&nbsp;<span class="helper">groups grant permissions to the user</span>
</td>
</tr>
<tr>
<th class="labelCol"><label class="required" for="in_state:A">in_state</label></th>
<td style="width:100%%;">
<input type="hidden" name="edits-in_state:A" value="__cubicweb_internal_field__"/>
<select name="in_state:A" id="in_state:A" tabindex="8">
<option value="%(activated)s" >activated</option>
</select>
<br/>&nbsp;<span class="helper">account state</span>
</td>
</tr>
</table>
<div id="inlineuse_emailslot">
<div class="inlinedform" id="addNewEmailAddressuse_emailsubject:A" cubicweb:limit="true">
<a class="addEntity" id="adduse_email:Alink" href="javascript: addInlineCreationForm('A', 'EUser', 'EmailAddress', 'use_email', 'subject')" >+ add a EmailAddress.</a>
</div>
<div class="trame_grise">&nbsp;</div>
</div>
</fieldset>
</div>
<table width="100%%">
<tbody>
<tr><td align="center">
<input class="validateButton" type="submit" name="defaultsubmit" value="Button_ok" tabindex="9"/>
</td><td style="align: right; width: 50%%;">
<input class="validateButton" type="button" onclick="postForm('__action_apply', 'Button_apply', 'entityForm')" value="Button_apply" tabindex="10"/>
<input class="validateButton" type="button" onclick="postForm('__action_cancel', 'Button_cancel', 'entityForm')" value="Button_cancel" tabindex="11"/>
</td></tr>
</tbody>
</table>
</form>''' % {'activated' : activated})

    def test_redirection_after_creation(self):
        req = self.request()
        req.form['etype'] = 'EUser'
        view = self.vreg.select_view('creation', req, None)
        self.assertEquals(view.redirect_url(), 'http://testing.fr/cubicweb/euser')
        req.form['__redirectrql'] = 'Any X WHERE X eid 3012'
        req.form['__redirectvid'] = 'avid'
        self.assertEquals(view.redirect_url(), 'http://testing.fr/cubicweb/view?rql=Any%20X%20WHERE%20X%20eid%203012&vid=avid')


    def test_need_multipart(self):
        req = self.request()
        class Salesterm(AnyEntity):
            id = 'Salesterm'
            __rtags__ = {'described_by_test' : 'inlineview'}
        vreg = self.vreg
        vreg.register_vobject_class(Salesterm)
        req.form['etype'] = 'Salesterm'
        entity = vreg.etype_class('Salesterm')(req, None, None)
        view = vreg.select_view('creation', req, None)
        self.failUnless(view.need_multipart(entity))
        


    def test_nonregr_check_add_permission_on_relation(self):
        from cubes.blog.entities import BlogEntry
        class BlogEntryPlus(BlogEntry):
            __rtags__ = {'checked_by': 'primary'}
        self.vreg.register_vobject_class(BlogEntryPlus)
        clear_cache(self.vreg, 'etype_class')
        # an admin should be able to edit the checked_by relation
        html = self._build_creation_form('BlogEntry')
        self.failUnless('name="edits-checked_by:A"' in html)
        # a regular user should not be able to see the relation
        self.login('joe')
        html = self._build_creation_form('BlogEntry')
        self.failIf('name="edits-checked_by:A"' in html)
        
from cubicweb.devtools.testlib import WebTest
from cubicweb.devtools.htmlparser import DTDValidator

class CopyWebTest(WebTest):

    def setup_database(self):
        p = self.create_user("Doe")
        # do not try to skip 'primary_email' for this test
        e = self.add_entity('EmailAddress', address=u'doe@doe.com')
        self.execute('SET P use_email E, P primary_email E WHERE P eid %(p)s, E eid %(e)s',
                     {'p' : p.eid, 'e' : e.eid})


    def test_cloned_elements_in_copy_form(self):
        rset = self.execute('EUser P WHERE P login "Doe"')
        output = self.view('copy', rset)
        clones = [attrs for _, attrs in output.input_tags
                  if attrs.get('name', '').startswith('__cloned_eid')]
        # the only cloned entity should be the original person
        self.assertEquals(len(clones), 1)
        attrs = clones[0]
        self.assertEquals(attrs['name'], '__cloned_eid:A')
        self.assertEquals(int(attrs['value']), rset[0][0])


if __name__ == '__main__':
    unittest_main()
