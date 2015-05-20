# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
mainly regression-preventing tests for reledit views
"""

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.views.uicfg import reledit_ctrl

class ReleditMixinTC(object):

    def setup_database(self):
        with self.admin_access.client_cnx() as cnx:
            self.proj = cnx.create_entity('Project', title=u'cubicweb-world-domination').eid
            self.tick = cnx.create_entity('Ticket', title=u'write the code').eid
            self.toto = cnx.create_entity('Personne', nom=u'Toto').eid
            cnx.commit()

class ClickAndEditFormTC(ReleditMixinTC, CubicWebTC):

    def test_default_config(self):
        reledit = {'title': '''<div id="title-subject-%(eid)s-reledit" onmouseout="jQuery('#title-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#title-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="title-subject-%(eid)s-value" class="editableFieldValue">cubicweb-world-domination</div><div id="title-subject-%(eid)s" class="editableField invisible"><div id="title-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;title&#39;, &#39;subject&#39;, &#39;title-subject-%(eid)s&#39;, false, &#39;&#39;, &#39;edit_rtype&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>''',
                   'long_desc': '''<div id="long_desc-subject-%(eid)s-reledit" onmouseout="jQuery('#long_desc-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#long_desc-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="long_desc-subject-%(eid)s-value" class="editableFieldValue">&lt;not specified&gt;</div><div id="long_desc-subject-%(eid)s" class="editableField invisible"><div id="long_desc-subject-%(eid)s-add" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;edition&#39;, %(eid)s, &#39;long_desc&#39;, &#39;subject&#39;, &#39;long_desc-subject-%(eid)s&#39;, false, &#39;autolimited&#39;, &#39;add&#39;);" title="click to add a value"><img title="click to add a value" src="http://testing.fr/cubicweb/data/plus.png" alt="click to add a value"/></div></div></div>''',
                   'manager': '''<div id="manager-subject-%(eid)s-reledit" onmouseout="jQuery('#manager-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#manager-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="manager-subject-%(eid)s-value" class="editableFieldValue">&lt;not specified&gt;</div><div id="manager-subject-%(eid)s" class="editableField invisible"><div id="manager-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-%(eid)s&#39;, false, &#39;autolimited&#39;, &#39;edit_rtype&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>''',
                   'composite_card11_2ttypes': """&lt;not specified&gt;""",
                   'concerns': """&lt;not specified&gt;"""}

        with self.admin_access.web_request() as req:
            proj = req.entity_from_eid(self.proj)

            for rschema, ttypes, role in proj.e_schema.relation_definitions(includefinal=True):
                if rschema not in reledit:
                    continue
                rtype = rschema.type
                self.assertMultiLineEqual(reledit[rtype] % {'eid': self.proj},
                                          proj.view('reledit', rtype=rtype, role=role),
                                          rtype)

    def test_default_forms(self):
        self.skipTest('Need to check if this test should still run post reledit/doreledit merge')
        doreledit = {'title': """<div id="title-subject-%(eid)s-reledit" onmouseout="jQuery('#title-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#title-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="title-subject-%(eid)s-value" class="editableFieldValue">cubicweb-world-domination</div><form action="http://testing.fr/cubicweb/validateform?__onsuccess=window.parent.cw.reledit.onSuccess" method="post" enctype="application/x-www-form-urlencoded" id="title-subject-%(eid)s-form" onsubmit="return freezeFormButtons(&#39;title-subject-%(eid)s-form&#39;);" class="releditForm" target="eformframe">
<fieldset>
<input name="__form_id" type="hidden" value="base" />
<input name="__errorurl" type="hidden" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop#title-subject-%(eid)s-form" />
<input name="__domid" type="hidden" value="title-subject-%(eid)s-form" />
<input name="__type:%(eid)s" type="hidden" value="Project" />
<input name="eid" type="hidden" value="%(eid)s" />
<input name="__maineid" type="hidden" value="%(eid)s" />
<input name="__reledit|vid" type="hidden" value="" />
<input name="__reledit|rtype" type="hidden" value="title" />
<input name="__reledit|divid" type="hidden" value="title-subject-%(eid)s" />
<input name="__reledit|formid" type="hidden" value="base" />
<input name="__reledit|reload" type="hidden" value="false" />
<input name="__reledit|role" type="hidden" value="subject" />
<input name="__reledit|eid" type="hidden" value="%(eid)s" />
<input name="_cw_entity_fields:%(eid)s" type="hidden" value="title-subject,__type" />
<fieldset class="default">
<table class="">
<tr class="title_subject_row">
<td>
<input id="title-subject:%(eid)s" maxlength="32" name="title-subject:%(eid)s" size="32" tabindex="1" type="text" value="cubicweb-world-domination" />
</td></tr>
</table></fieldset>
<table class="buttonbar">
<tr>
<td><button class="validateButton" tabindex="2" type="submit" value="button_ok"><img alt="OK_ICON" src="http://testing.fr/cubicweb/data/ok.png" />button_ok</button></td>
<td><button class="validateButton" onclick="cw.reledit.cleanupAfterCancel(&#39;title-subject-%(eid)s&#39;)" tabindex="3" type="button" value="button_cancel"><img alt="CANCEL_ICON" src="http://testing.fr/cubicweb/data/cancel.png" />button_cancel</button></td>
</tr></table>
</fieldset>
<iframe width="0px" height="0px" src="javascript: void(0);" name="eformframe" id="eformframe"></iframe>
</form><div id="title-subject-%(eid)s" class="editableField invisible"><div id="title-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;title&#39;, &#39;subject&#39;, &#39;title-subject-%(eid)s&#39;, false, &#39;&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",

                     'long_desc': """<div id="long_desc-subject-%(eid)s-reledit" onmouseout="jQuery('#long_desc-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#long_desc-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="long_desc-subject-%(eid)s-value" class="editableFieldValue">&lt;not specified&gt;</div><form action="http://testing.fr/cubicweb/validateform?__onsuccess=window.parent.cw.reledit.onSuccess" method="post" enctype="application/x-www-form-urlencoded" id="long_desc-subject-%(eid)s-form" onsubmit="return freezeFormButtons(&#39;long_desc-subject-%(eid)s-form&#39;);" class="releditForm" target="eformframe">
<fieldset>
<input name="__form_id" type="invisible" value="edition" />
<input name="__errorurl" type="invisible" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop#long_desc-subject-%(eid)s-form" />
<input name="__domid" type="hidden" value="long_desc-subject-%(eid)s-form" />
<input name="__type:A" type="hidden" value="Blog" />
<input name="eid" type="hidden" value="A" />
<input name="__maineid" type="hidden" value="A" />
<input name="__linkto" type="hidden" value="long_desc:%(eid)s:object" />
<input name="__message" type="hidden" value="entity linked" />
<input name="__reledit|vid" type="hidden" value="autolimited" />
<input name="__reledit|rtype" type="hidden" value="long_desc" />
<input name="__reledit|divid" type="hidden" value="long_desc-subject-%(eid)s" />
<input name="__reledit|formid" type="hidden" value="edition" />
<input name="__reledit|reload" type="hidden" value="false" />
<input name="__reledit|role" type="hidden" value="subject" />
<input name="__reledit|eid" type="hidden" value="%(eid)s" />
<input name="_cw_entity_fields:A" type="hidden" value="title-subject,rss_url-subject,__type,description-subject" />
<fieldset class="default">
<table class="attributeForm">
<tr class="title_subject_row">
<th class="labelCol"><label class="required" for="title-subject:A">title</label></th>
<td>
<input id="title-subject:A" maxlength="50" name="title-subject:A" size="45" tabindex="4" type="text" value="" />
</td></tr>
<tr class="description_subject_row">
<th class="labelCol"><label for="description-subject:A">description</label></th>
<td>
<input name="description_format-subject:A" type="hidden" value="text/html" /><textarea cols="80" cubicweb:type="wysiwyg" id="description-subject:A" name="description-subject:A" onkeyup="autogrow(this)" rows="2" tabindex="5"></textarea>
</td></tr>
<tr class="rss_url_subject_row">
<th class="labelCol"><label for="rss_url-subject:A">rss_url</label></th>
<td>
<input id="rss_url-subject:A" maxlength="128" name="rss_url-subject:A" size="45" tabindex="6" type="text" value="" />
</td></tr>
</table></fieldset>
<table class="buttonbar">
<tr>
<td><button class="validateButton" tabindex="7" type="submit" value="button_ok"><img alt="OK_ICON" src="http://testing.fr/cubicweb/data/ok.png" />button_ok</button></td>
<td><button class="validateButton" onclick="cw.reledit.cleanupAfterCancel(&#39;long_desc-subject-%(eid)s&#39;)" tabindex="8" type="button" value="button_cancel"><img alt="CANCEL_ICON" src="http://testing.fr/cubicweb/data/cancel.png" />button_cancel</button></td>
</tr></table>
</fieldset>
<iframe width="0px" height="0px" src="javascript: void(0);" name="eformframe" id="eformframe"></iframe>
</form><div id="long_desc-subject-%(eid)s" class="editableField invisible"><div id="long_desc-subject-%(eid)s-add" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;edition&#39;, %(eid)s, &#39;long_desc&#39;, &#39;subject&#39;, &#39;long_desc-subject-%(eid)s&#39;, false, &#39;autolimited&#39;);" title="click to add a value"><img title="click to add a value" src="http://testing.fr/cubicweb/data/plus.png" alt="click to add a value"/></div></div></div>""",

                     'manager': """<div id="manager-subject-%(eid)s-reledit" onmouseout="jQuery('#manager-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#manager-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="manager-subject-%(eid)s-value" class="editableFieldValue">&lt;not specified&gt;</div><form action="http://testing.fr/cubicweb/validateform?__onsuccess=window.parent.cw.reledit.onSuccess" method="post" enctype="application/x-www-form-urlencoded" id="manager-subject-%(eid)s-form" onsubmit="return freezeFormButtons(&#39;manager-subject-%(eid)s-form&#39;);" class="releditForm" target="eformframe">
<fieldset>
<input name="__form_id" type="hidden" value="base" />
<input name="__errorurl" type="hidden" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop#manager-subject-%(eid)s-form" />
<input name="__domid" type="hidden" value="manager-subject-%(eid)s-form" />
<input name="__type:%(eid)s" type="hidden" value="Project" />
<input name="eid" type="hidden" value="%(eid)s" />
<input name="__maineid" type="hidden" value="%(eid)s" />
<input name="__linkto" type="hidden" value="long_desc:%(eid)s:object" />
<input name="__message" type="hidden" value="entity linked" />
<input name="__reledit|vid" type="hidden" value="autolimited" />
<input name="__reledit|rtype" type="hidden" value="manager" />
<input name="__reledit|divid" type="hidden" value="manager-subject-%(eid)s" />
<input name="__reledit|formid" type="hidden" value="base" />
<input name="__reledit|reload" type="hidden" value="false" />
<input name="__reledit|role" type="hidden" value="subject" />
<input name="__reledit|eid" type="hidden" value="%(eid)s" />
<input name="_cw_entity_fields:%(eid)s" type="hidden" value="manager-subject,__type" />
<fieldset class="default">
<table class="">
<tr class="manager_subject_row">
<td>
<select id="manager-subject:%(eid)s" name="manager-subject:%(eid)s" size="1" tabindex="9">
<option value="__cubicweb_internal_field__"></option>
<option value="%(toto)s">Toto</option>
</select>
</td></tr>
</table></fieldset>
<table class="buttonbar">
<tr>
<td><button class="validateButton" tabindex="10" type="submit" value="button_ok"><img alt="OK_ICON" src="http://testing.fr/cubicweb/data/ok.png" />button_ok</button></td>
<td><button class="validateButton" onclick="cw.reledit.cleanupAfterCancel(&#39;manager-subject-%(eid)s&#39;)" tabindex="11" type="button" value="button_cancel"><img alt="CANCEL_ICON" src="http://testing.fr/cubicweb/data/cancel.png" />button_cancel</button></td>
</tr></table>
</fieldset>
<iframe width="0px" height="0px" src="javascript: void(0);" name="eformframe" id="eformframe"></iframe>
</form><div id="manager-subject-%(eid)s" class="editableField invisible"><div id="manager-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-%(eid)s&#39;, false, &#39;autolimited&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
                     'composite_card11_2ttypes': """&lt;not specified&gt;""",
                     'concerns': """&lt;not specified&gt;"""
            }
        for rschema, ttypes, role in self.proj.e_schema.relation_definitions(includefinal=True):
            if rschema not in doreledit:
                continue
            rtype = rschema.type
            self.assertMultiLineEqual(doreledit[rtype] % {'eid': self.proj.eid, 'toto': self.toto.eid},
                                  self.proj.view('doreledit', rtype=rtype, role=role,
                                                 formid='edition' if rtype == 'long_desc' else 'base'),
                                  rtype)

class ClickAndEditFormUICFGTC(ReleditMixinTC, CubicWebTC):

    def setup_database(self):
        super(ClickAndEditFormUICFGTC, self).setup_database()
        with self.admin_access.client_cnx() as cnx:
            cnx.execute('SET T concerns P WHERE T eid %(t)s, P eid %(p)s', {'t': self.tick, 'p': self.proj})
            cnx.execute('SET P manager T WHERE P eid %(p)s, T eid %(t)s', {'p': self.proj, 't': self.toto})
            cnx.commit()

    def test_with_uicfg(self):
        old_rctl = reledit_ctrl._tagdefs.copy()
        reledit_ctrl.tag_attribute(('Project', 'title'),
                                   {'novalue_label': '<title is required>', 'reload': True})
        reledit_ctrl.tag_subject_of(('Project', 'long_desc', '*'),
                                    {'reload': True, 'edit_target': 'rtype',
                                     'novalue_label': u'<long_desc is required>'})
        reledit_ctrl.tag_subject_of(('Project', 'manager', '*'),
                                   {'edit_target': 'related'})
        reledit_ctrl.tag_subject_of(('Project', 'composite_card11_2ttypes', '*'),
                                   {'edit_target': 'related'})
        reledit_ctrl.tag_object_of(('Ticket', 'concerns', 'Project'),
                                   {'edit_target': 'rtype'})
        reledit = {
            'title': """<div id="title-subject-%(eid)s-reledit" onmouseout="jQuery('#title-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#title-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="title-subject-%(eid)s-value" class="editableFieldValue">cubicweb-world-domination</div><div id="title-subject-%(eid)s" class="editableField invisible"><div id="title-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;title&#39;, &#39;subject&#39;, &#39;title-subject-%(eid)s&#39;, true, &#39;&#39;, &#39;edit_rtype&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
            'long_desc': """<div id="long_desc-subject-%(eid)s-reledit" onmouseout="jQuery('#long_desc-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#long_desc-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="long_desc-subject-%(eid)s-value" class="editableFieldValue">&lt;long_desc is required&gt;</div><div id="long_desc-subject-%(eid)s" class="editableField invisible"><div id="long_desc-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;long_desc&#39;, &#39;subject&#39;, &#39;long_desc-subject-%(eid)s&#39;, true, &#39;autolimited&#39;, &#39;edit_rtype&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
            'manager': """<div id="manager-subject-%(eid)s-reledit" onmouseout="jQuery('#manager-subject-%(eid)s').addClass('invisible')" onmouseover="jQuery('#manager-subject-%(eid)s').removeClass('invisible')" class="releditField"><div id="manager-subject-%(eid)s-value" class="editableFieldValue"><a href="http://testing.fr/cubicweb/personne/%(toto)s" title="">Toto</a></div><div id="manager-subject-%(eid)s" class="editableField invisible"><div id="manager-subject-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;edition&#39;, %(eid)s, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-%(eid)s&#39;, false, &#39;autolimited&#39;, &#39;edit_related&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div><div id="manager-subject-%(eid)s-delete" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;deleteconf&#39;, %(eid)s, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-%(eid)s&#39;, false, &#39;autolimited&#39;, &#39;delete&#39;);" title="click to delete this value"><img title="click to delete this value" src="http://testing.fr/cubicweb/data/cancel.png" alt="click to delete this value"/></div></div></div>""",
            'composite_card11_2ttypes': """&lt;not specified&gt;""",
            'concerns': """<div id="concerns-object-%(eid)s-reledit" onmouseout="jQuery('#concerns-object-%(eid)s').addClass('invisible')" onmouseover="jQuery('#concerns-object-%(eid)s').removeClass('invisible')" class="releditField"><div id="concerns-object-%(eid)s-value" class="editableFieldValue"><a href="http://testing.fr/cubicweb/ticket/%(tick)s" title="">write the code</a></div><div id="concerns-object-%(eid)s" class="editableField invisible"><div id="concerns-object-%(eid)s-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, %(eid)s, &#39;concerns&#39;, &#39;object&#39;, &#39;concerns-object-%(eid)s&#39;, false, &#39;autolimited&#39;, &#39;edit_rtype&#39;);" title="click to edit this field"><img title="click to edit this field" src="http://testing.fr/cubicweb/data/pen_icon.png" alt="click to edit this field"/></div></div></div>"""
            }
        with self.admin_access.web_request() as req:
            proj = req.entity_from_eid(self.proj)
            for rschema, ttypes, role in proj.e_schema.relation_definitions(includefinal=True):
                if rschema not in reledit:
                    continue
                rtype = rschema.type
                self.assertMultiLineEqual(reledit[rtype] % {'eid': self.proj, 'toto': self.toto, 'tick': self.tick},
                                      proj.view('reledit', rtype=rtype, role=role),
                                      rtype)
        reledit_ctrl.clear()
        reledit_ctrl._tagdefs.update(old_rctl)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
