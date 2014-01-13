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
import copy
from logilab.common.testlib import tag
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import uihelper, formwidgets as fwdgs
from cubicweb.web.views import uicfg

abaa = uicfg.actionbox_appearsin_addmenu

class UICFGTC(CubicWebTC):

    def test_default_actionbox_appearsin_addmenu_config(self):
        self.assertFalse(abaa.etype_get('TrInfo', 'wf_info_for', 'object', 'CWUser'))



class DefinitionOrderTC(CubicWebTC):
    """This test check that when multiple definition could match a key, only
    the more accurate apply"""

    def setUp(self):
        super(DefinitionOrderTC, self).setUp()
        for rtag in (uicfg.autoform_section, uicfg.autoform_field_kwargs):
            rtag._old_tagdefs = copy.deepcopy(rtag._tagdefs)
        new_def = (
                    (('*', 'login', '*'),
                         {'formtype':'main', 'section':'hidden'}),
                    (('*', 'login', '*'),
                         {'formtype':'muledit', 'section':'hidden'}),
                    (('CWUser', 'login', '*'),
                         {'formtype':'main', 'section':'attributes'}),
                    (('CWUser', 'login', '*'),
                         {'formtype':'muledit', 'section':'attributes'}),
                    (('CWUser', 'login', 'String'),
                         {'formtype':'main', 'section':'inlined'}),
                    (('CWUser', 'login', 'String'),
                         {'formtype':'inlined', 'section':'attributes'}),
                    )
        for key, kwargs in new_def:
            uicfg.autoform_section.tag_subject_of(key, **kwargs)

    def tearDown(self):
        super(DefinitionOrderTC, self).tearDown()
        for rtag in (uicfg.autoform_section, uicfg.autoform_field_kwargs):
            rtag._tagdefs = rtag._old_tagdefs

    @tag('uicfg')
    def test_definition_order_hidden(self):
        result = uicfg.autoform_section.get('CWUser', 'login', 'String', 'subject')
        expected = set(['main_inlined', 'muledit_attributes', 'inlined_attributes'])
        self.assertSetEqual(result, expected)

    @tag('uihelper', 'order', 'func')
    def test_uihelper_set_fields_order(self):
        afk_get = uicfg.autoform_field_kwargs.get
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {})
        uihelper.set_fields_order('CWUser', ('login', 'firstname', 'surname'))
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {'order': 1})

    @tag('uicfg', 'order', 'func')
    def test_uicfg_primaryview_set_fields_order(self):
        pvdc = uicfg.primaryview_display_ctrl
        pvdc.set_fields_order('CWUser', ('login', 'firstname', 'surname'))
        self.assertEqual(pvdc.get('CWUser', 'login', 'String', 'subject'), {'order': 0})
        self.assertEqual(pvdc.get('CWUser', 'firstname', 'String', 'subject'), {'order': 1})
        self.assertEqual(pvdc.get('CWUser', 'surname', 'String', 'subject'), {'order': 2})

    @tag('uihelper', 'kwargs', 'func')
    def test_uihelper_set_field_kwargs(self):
        afk_get = uicfg.autoform_field_kwargs.get
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {})
        wdg = fwdgs.TextInput({'size': 30})
        uihelper.set_field_kwargs('CWUser', 'firstname', widget=wdg)
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {'widget': wdg})

    @tag('uihelper', 'hidden', 'func')
    def test_uihelper_hide_fields(self):
        # original conf : in_group is edited in 'attributes' section everywhere
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_attributes', 'muledit_attributes'])
        # hide field in main form
        uihelper.hide_fields('CWUser', ('login', 'in_group'))
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_hidden', 'muledit_attributes'])
        # hide field in muledit form
        uihelper.hide_fields('CWUser', ('login', 'in_group'), formtype='muledit')
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_hidden', 'muledit_hidden'])

    @tag('uihelper', 'hidden', 'formconfig')
    def test_uihelper_formconfig(self):
        afk_get = uicfg.autoform_field_kwargs.get
        class CWUserFormConfig(uihelper.FormConfig):
            etype = 'CWUser'
            hidden = ('in_group',)
            fields_order = ('login', 'firstname')
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_hidden', 'muledit_attributes'])
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {'order': 1})


class UicfgRegistryTC(CubicWebTC):

    def test_default_uicfg_object(self):
        'CW default ui config objects must be registered in uicfg registry'
        onames = ('autoform_field', 'autoform_section', 'autoform_field_kwargs')
        for oname in onames:
            obj = self.vreg['uicfg'].select_or_none(oname)
            self.assertTrue(obj is not None, '%s not found in uicfg registry'
                            % oname)

    def test_custom_uicfg(self):
        ASRT = uicfg.AutoformSectionRelationTags
        custom_afs = ASRT()
        custom_afs.__select__ = ASRT.__select__ & ASRT.__select__
        self.vreg['uicfg'].register(custom_afs)
        obj = self.vreg['uicfg'].select_or_none('autoform_section')
        self.assertTrue(obj is custom_afs)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
