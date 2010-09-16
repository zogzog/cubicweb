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
mainly regression-preventing tests for reledit/doreledit views
"""

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.uicfg import reledit_ctrl

class ReleditMixinTC(object):

    def setup_database(self):
        self.req = self.request()
        self.proj = self.req.create_entity('Project', title=u'cubicweb-world-domination')
        self.tick = self.req.create_entity('Ticket', title=u'write the code')
        self.toto = self.req.create_entity('Personne', nom=u'Toto')

class ClickAndEditFormTC(ReleditMixinTC, CubicWebTC):

    def test_default_config(self):
        reledit = {'title': """<div id="title-subject-917-reledit" onmouseout="jQuery('#title-subject-917').addClass('hidden')" onmouseover="jQuery('#title-subject-917').removeClass('hidden')" class="releditField"><div id="title-subject-917-value" class="editableFieldValue">cubicweb-world-domination</div><div id="title-subject-917" class="editableField hidden"><div id="title-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;title&#39;, &#39;subject&#39;, &#39;title-subject-917&#39;, false, &#39;&#39;, &#39;&amp;lt;title not specified&amp;gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
                   'long_desc': """<div id="long_desc-subject-917-reledit" onmouseout="jQuery('#long_desc-subject-917').addClass('hidden')" onmouseover="jQuery('#long_desc-subject-917').removeClass('hidden')" class="releditField"><div id="long_desc-subject-917-value" class="editableFieldValue">&lt;long_desc not specified&gt;</div><div id="long_desc-subject-917" class="editableField hidden"><div id="long_desc-subject-917-add" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;edition&#39;, 917, &#39;long_desc&#39;, &#39;subject&#39;, &#39;long_desc-subject-917&#39;, false, &#39;incontext&#39;, &#39;&amp;lt;long_desc not specified&amp;gt;&#39;);" title="click to add a value"><img title="click to add a value" src="data/plus.png" alt="click to add a value"/></div></div></div>""",
                   'manager': """<div id="manager-subject-917-reledit" onmouseout="jQuery('#manager-subject-917').addClass('hidden')" onmouseover="jQuery('#manager-subject-917').removeClass('hidden')" class="releditField"><div id="manager-subject-917-value" class="editableFieldValue">&lt;manager not specified&gt;</div><div id="manager-subject-917" class="editableField hidden"><div id="manager-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-917&#39;, false, &#39;incontext&#39;, &#39;&amp;lt;manager not specified&amp;gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
                   'composite_card11_2ttypes': """&lt;composite_card11_2ttypes not specified&gt;""",
                   'concerns': """&lt;concerns_object not specified&gt;"""}

        for rschema, ttypes, role in self.proj.e_schema.relation_definitions(includefinal=True):
            if rschema not in reledit:
                continue
            rtype = rschema.type
            self.assertTextEquals(reledit[rtype], self.proj.view('reledit', rtype=rtype, role=role), rtype)

    def test_default_forms(self):
        doreledit = {'title': """<div id="title-subject-917-reledit" onmouseout="jQuery('#title-subject-917').addClass('hidden')" onmouseover="jQuery('#title-subject-917').removeClass('hidden')" class="releditField"><div id="title-subject-917-value" class="editableFieldValue">cubicweb-world-domination</div><form action="http://testing.fr/cubicweb/validateform?__onsuccess=window.parent.cw.reledit.onSuccess" method="post" enctype="application/x-www-form-urlencoded" id="title-subject-917-form" onsubmit="return freezeFormButtons(&#39;title-subject-917-form&#39;);" class="releditForm" cubicweb:target="eformframe">
<fieldset>
<input name="__form_id" type="hidden" value="base" />
<input name="__errorurl" type="hidden" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop#title-subject-917-form" />
<input name="__domid" type="hidden" value="title-subject-917-form" />
<input name="__type:917" type="hidden" value="Project" />
<input name="eid" type="hidden" value="917" />
<input name="__maineid" type="hidden" value="917" />
<input name="__reledit|default_value" type="hidden" value="&amp;lt;title not specified&amp;gt;" />
<input name="__reledit|vid" type="hidden" value="" />
<input name="__reledit|rtype" type="hidden" value="title" />
<input name="__reledit|divid" type="hidden" value="title-subject-917" />
<input name="__reledit|formid" type="hidden" value="base" />
<input name="__reledit|reload" type="hidden" value="false" />
<input name="__reledit|role" type="hidden" value="subject" />
<input name="__reledit|eid" type="hidden" value="917" />
<input name="_cw_edited_fields:917" type="hidden" value="title-subject,__type" />
<fieldset class="default">
<table class="">
<tr class="title_subject_row">
<td
>
<input id="title-subject:917" maxlength="32" name="title-subject:917" size="32" tabindex="1" type="text" value="cubicweb-world-domination" />
</td></tr>
</table></fieldset>
<table class="buttonbar">
<tr>

<td><button class="validateButton" tabindex="2" type="submit" value="button_ok"><img alt="OK_ICON" src="http://crater:8080/data/ok.png" />button_ok</button></td>

<td><button class="validateButton" onclick="cw.reledit.cleanupAfterCancel(&#39;title-subject-917&#39;)" tabindex="3" type="button" value="button_cancel"><img alt="CANCEL_ICON" src="http://crater:8080/data/cancel.png" />button_cancel</button></td>

</tr></table>
</fieldset>
</form><div id="title-subject-917" class="editableField hidden"><div id="title-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;title&#39;, &#39;subject&#39;, &#39;title-subject-917&#39;, false, &#39;&#39;, &#39;&amp;lt;title not specified&amp;gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",

                     'long_desc': """<div id="long_desc-subject-917-reledit" onmouseout="jQuery('#long_desc-subject-917').addClass('hidden')" onmouseover="jQuery('#long_desc-subject-917').removeClass('hidden')" class="releditField"><div id="long_desc-subject-917-value" class="editableFieldValue">&lt;long_desc not specified&gt;</div><form action="http://testing.fr/cubicweb/validateform?__onsuccess=window.parent.cw.reledit.onSuccess" method="post" enctype="application/x-www-form-urlencoded" id="long_desc-subject-917-form" onsubmit="return freezeFormButtons(&#39;long_desc-subject-917-form&#39;);" class="releditForm" cubicweb:target="eformframe">
<fieldset>
<input name="__form_id" type="hidden" value="edition" />
<input name="__errorurl" type="hidden" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop#long_desc-subject-917-form" />
<input name="__domid" type="hidden" value="long_desc-subject-917-form" />
<input name="__type:A" type="hidden" value="Blog" />
<input name="eid" type="hidden" value="A" />
<input name="__maineid" type="hidden" value="A" />
<input name="__linkto" type="hidden" value="long_desc:917:object" />
<input name="__message" type="hidden" value="entity linked" />
<input name="__reledit|default_value" type="hidden" value="&amp;lt;long_desc not specified&amp;gt;" />
<input name="__reledit|vid" type="hidden" value="incontext" />
<input name="__reledit|rtype" type="hidden" value="long_desc" />
<input name="__reledit|divid" type="hidden" value="long_desc-subject-917" />
<input name="__reledit|formid" type="hidden" value="edition" />
<input name="__reledit|reload" type="hidden" value="false" />
<input name="__reledit|role" type="hidden" value="subject" />
<input name="__reledit|eid" type="hidden" value="917" />
<input name="_cw_edited_fields:A" type="hidden" value="title-subject,rss_url-subject,__type,description-subject" />
<fieldset class="default">
<table class="attributeForm">
<tr class="title_subject_row">
<th class="labelCol"><label class="required" for="title-subject:A">title</label></th>
<td
>
<input id="title-subject:A" maxlength="50" name="title-subject:A" size="45" tabindex="4" type="text" value="" />
</td></tr>
<tr class="description_subject_row">
<th class="labelCol"><label for="description-subject:A">description</label></th>
<td
>
<input name="description_format-subject:A" type="hidden" value="text/html" /><textarea cols="80" cubicweb:type="wysiwyg" id="description-subject:A" name="description-subject:A" onkeyup="autogrow(this)" rows="2" tabindex="5"></textarea>
</td></tr>
<tr class="rss_url_subject_row">
<th class="labelCol"><label for="rss_url-subject:A">rss_url</label></th>
<td
>
<input id="rss_url-subject:A" maxlength="128" name="rss_url-subject:A" size="45" tabindex="6" type="text" value="" />
</td></tr>
</table></fieldset>
<table class="buttonbar">
<tr>

<td><button class="validateButton" tabindex="7" type="submit" value="button_ok"><img alt="OK_ICON" src="http://crater:8080/data/ok.png" />button_ok</button></td>

<td><button class="validateButton" onclick="cw.reledit.cleanupAfterCancel(&#39;long_desc-subject-917&#39;)" tabindex="8" type="button" value="button_cancel"><img alt="CANCEL_ICON" src="http://crater:8080/data/cancel.png" />button_cancel</button></td>

</tr></table>
</fieldset>
</form><div id="long_desc-subject-917" class="editableField hidden"><div id="long_desc-subject-917-add" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;edition&#39;, 917, &#39;long_desc&#39;, &#39;subject&#39;, &#39;long_desc-subject-917&#39;, false, &#39;incontext&#39;, &#39;&amp;lt;long_desc not specified&amp;gt;&#39;);" title="click to add a value"><img title="click to add a value" src="data/plus.png" alt="click to add a value"/></div></div></div>""",

                     'manager': """<div id="manager-subject-917-reledit" onmouseout="jQuery('#manager-subject-917').addClass('hidden')" onmouseover="jQuery('#manager-subject-917').removeClass('hidden')" class="releditField"><div id="manager-subject-917-value" class="editableFieldValue">&lt;manager not specified&gt;</div><form action="http://testing.fr/cubicweb/validateform?__onsuccess=window.parent.cw.reledit.onSuccess" method="post" enctype="application/x-www-form-urlencoded" id="manager-subject-917-form" onsubmit="return freezeFormButtons(&#39;manager-subject-917-form&#39;);" class="releditForm" cubicweb:target="eformframe">
<fieldset>
<input name="__form_id" type="hidden" value="base" />
<input name="__errorurl" type="hidden" value="http://testing.fr/cubicweb/view?rql=Blop&amp;vid=blop#manager-subject-917-form" />
<input name="__domid" type="hidden" value="manager-subject-917-form" />
<input name="__type:917" type="hidden" value="Project" />
<input name="eid" type="hidden" value="917" />
<input name="__maineid" type="hidden" value="917" />
<input name="__linkto" type="hidden" value="long_desc:917:object" />
<input name="__message" type="hidden" value="entity linked" />
<input name="__reledit|default_value" type="hidden" value="&amp;lt;manager not specified&amp;gt;" />
<input name="__reledit|vid" type="hidden" value="incontext" />
<input name="__reledit|rtype" type="hidden" value="manager" />
<input name="__reledit|divid" type="hidden" value="manager-subject-917" />
<input name="__reledit|formid" type="hidden" value="base" />
<input name="__reledit|reload" type="hidden" value="false" />
<input name="__reledit|role" type="hidden" value="subject" />
<input name="__reledit|eid" type="hidden" value="917" />
<input name="_cw_edited_fields:917" type="hidden" value="manager-subject,__type" />
<fieldset class="default">
<table class="">
<tr class="manager_subject_row">
<td
>
<select id="manager-subject:917" name="manager-subject:917" size="1" tabindex="9">
<option value="__cubicweb_internal_field__"></option>
<option value="919">Toto</option>
</select>
</td></tr>
</table></fieldset>
<table class="buttonbar">
<tr>

<td><button class="validateButton" tabindex="10" type="submit" value="button_ok"><img alt="OK_ICON" src="http://crater:8080/data/ok.png" />button_ok</button></td>

<td><button class="validateButton" onclick="cw.reledit.cleanupAfterCancel(&#39;manager-subject-917&#39;)" tabindex="11" type="button" value="button_cancel"><img alt="CANCEL_ICON" src="http://crater:8080/data/cancel.png" />button_cancel</button></td>

</tr></table>
</fieldset>
</form><div id="manager-subject-917" class="editableField hidden"><div id="manager-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-917&#39;, false, &#39;incontext&#39;, &#39;&amp;lt;manager not specified&amp;gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
                     'composite_card11_2ttypes': """&lt;composite_card11_2ttypes not specified&gt;""",
                     'concerns': """&lt;concerns_object not specified&gt;"""
            }
        for rschema, ttypes, role in self.proj.e_schema.relation_definitions(includefinal=True):
            if rschema not in doreledit:
                continue
            rtype = rschema.type
            self.assertTextEquals(doreledit[rtype],
                                  self.proj.view('doreledit', rtype=rtype, role=role,
                                                 formid='edition' if rtype == 'long_desc' else 'base'),
                                  rtype)

class ClickAndEditFormUICFGTC(ReleditMixinTC, CubicWebTC):

    def setup_database(self):
        super(ClickAndEditFormUICFGTC, self).setup_database()
        self.tick.set_relations(concerns=self.proj)
        self.proj.set_relations(manager=self.toto)

    def test_with_uicfg(self):
        old_rctl = reledit_ctrl._tagdefs.copy()
        reledit_ctrl.tag_attribute(('Project', 'title'),
                                   {'default_value': '<title is required>', 'reload': True})
        reledit_ctrl.tag_subject_of(('Project', 'long_desc', '*'),
                                    {'reload': True, 'edit_target': 'rtype',
                                     'default_value': u'<long_desc is required>'})
        reledit_ctrl.tag_subject_of(('Project', 'manager', '*'),
                                   {'edit_target': 'related'})
        reledit_ctrl.tag_subject_of(('Project', 'composite_card11_2ttypes', '*'),
                                   {'edit_target': 'related'})
        reledit_ctrl.tag_object_of(('Ticket', 'concerns', 'Project'),
                                   {'edit_target': 'rtype'})
        reledit = {
            'title': """<div id="title-subject-917-reledit" onmouseout="jQuery('#title-subject-917').addClass('hidden')" onmouseover="jQuery('#title-subject-917').removeClass('hidden')" class="releditField"><div id="title-subject-917-value" class="editableFieldValue">cubicweb-world-domination</div><div id="title-subject-917" class="editableField hidden"><div id="title-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;title&#39;, &#39;subject&#39;, &#39;title-subject-917&#39;, true, &#39;&#39;, &#39;&lt;title is required&gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
            'long_desc': """<div id="long_desc-subject-917-reledit" onmouseout="jQuery('#long_desc-subject-917').addClass('hidden')" onmouseover="jQuery('#long_desc-subject-917').removeClass('hidden')" class="releditField"><div id="long_desc-subject-917-value" class="editableFieldValue"><long_desc is required></div><div id="long_desc-subject-917" class="editableField hidden"><div id="long_desc-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;long_desc&#39;, &#39;subject&#39;, &#39;long_desc-subject-917&#39;, true, &#39;incontext&#39;, &#39;&lt;long_desc is required&gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>""",
            'manager': """<div id="manager-subject-917-reledit" onmouseout="jQuery('#manager-subject-917').addClass('hidden')" onmouseover="jQuery('#manager-subject-917').removeClass('hidden')" class="releditField"><div id="manager-subject-917-value" class="editableFieldValue"><a href="http://testing.fr/cubicweb/personne/919" title="">Toto</a></div><div id="manager-subject-917" class="editableField hidden"><div id="manager-subject-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;edition&#39;, 917, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-917&#39;, false, &#39;incontext&#39;, &#39;&amp;lt;manager not specified&amp;gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div><div id="manager-subject-917-delete" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;deleteconf&#39;, 917, &#39;manager&#39;, &#39;subject&#39;, &#39;manager-subject-917&#39;, false, &#39;incontext&#39;, &#39;&amp;lt;manager not specified&amp;gt;&#39;);" title="click to delete this value"><img title="click to delete this value" src="data/cancel.png" alt="click to delete this value"/></div></div></div>""",
            'composite_card11_2ttypes': """&lt;composite_card11_2ttypes not specified&gt;""",
            'concerns': """<div id="concerns-object-917-reledit" onmouseout="jQuery('#concerns-object-917').addClass('hidden')" onmouseover="jQuery('#concerns-object-917').removeClass('hidden')" class="releditField"><div id="concerns-object-917-value" class="editableFieldValue"><a href="http://testing.fr/cubicweb/ticket/918" title="">write the code</a></div><div id="concerns-object-917" class="editableField hidden"><div id="concerns-object-917-update" class="editableField" onclick="cw.reledit.loadInlineEditionForm(&#39;base&#39;, 917, &#39;concerns&#39;, &#39;object&#39;, &#39;concerns-object-917&#39;, false, &#39;csv&#39;, &#39;&amp;lt;concerns_object not specified&amp;gt;&#39;);" title="click to edit this field"><img title="click to edit this field" src="data/pen_icon.png" alt="click to edit this field"/></div></div></div>"""
            }
        for rschema, ttypes, role in self.proj.e_schema.relation_definitions(includefinal=True):
            if rschema not in reledit:
                continue
            rtype = rschema.type
            self.assertTextEquals(reledit[rtype],
                                  self.proj.view('reledit', rtype=rtype, role=role),
                                  rtype)
        reledit_ctrl.clear()
        reledit_ctrl._tagdefs.update(old_rctl)
