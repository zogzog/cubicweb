# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
import warnings

from yams.buildobjs import RelationDefinition, EntityType

from cubicweb.devtools.testlib import CubicWebTC, BaseTestCase
from cubicweb.schema import build_schema_from_namespace
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
             {'formtype': 'main', 'section': 'hidden'}),
            (('*', 'login', '*'),
             {'formtype': 'muledit', 'section': 'hidden'}),
            (('CWUser', 'login', '*'),
             {'formtype': 'main', 'section': 'attributes'}),
            (('CWUser', 'login', '*'),
             {'formtype': 'muledit', 'section': 'attributes'}),
            (('CWUser', 'login', 'String'),
             {'formtype': 'main', 'section': 'inlined'}),
            (('CWUser', 'login', 'String'),
             {'formtype': 'inlined', 'section': 'attributes'}),
        )
        for key, kwargs in new_def:
            uicfg.autoform_section.tag_subject_of(key, **kwargs)

    def tearDown(self):
        super(DefinitionOrderTC, self).tearDown()
        for rtag in (uicfg.autoform_section, uicfg.autoform_field_kwargs):
            rtag._tagdefs = rtag._old_tagdefs

    def test_definition_order_hidden(self):
        result = uicfg.autoform_section.get('CWUser', 'login', 'String', 'subject')
        expected = set(['main_inlined', 'muledit_attributes', 'inlined_attributes'])
        self.assertSetEqual(result, expected)

    def test_uihelper_set_fields_order(self):
        afk_get = uicfg.autoform_field_kwargs.get
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {})
        with warnings.catch_warnings(record=True) as w:
            uihelper.set_fields_order('CWUser', ('login', 'firstname', 'surname'))
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, DeprecationWarning))
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {'order': 1})

    def test_uicfg_primaryview_set_fields_order(self):
        pvdc = uicfg.primaryview_display_ctrl
        pvdc.set_fields_order('CWUser', ('login', 'firstname', 'surname'))
        self.assertEqual(pvdc.get('CWUser', 'login', 'String', 'subject'), {'order': 0})
        self.assertEqual(pvdc.get('CWUser', 'firstname', 'String', 'subject'), {'order': 1})
        self.assertEqual(pvdc.get('CWUser', 'surname', 'String', 'subject'), {'order': 2})

    def test_uihelper_set_field_kwargs(self):
        afk_get = uicfg.autoform_field_kwargs.get
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {})
        wdg = fwdgs.TextInput({'size': 30})
        with warnings.catch_warnings(record=True) as w:
            uihelper.set_field_kwargs('CWUser', 'firstname', widget=wdg)
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, DeprecationWarning))
        self.assertEqual(afk_get('CWUser', 'firstname', 'String', 'subject'), {'widget': wdg})

    def test_uihelper_hide_fields(self):
        # original conf : in_group is edited in 'attributes' section everywhere
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_attributes', 'muledit_attributes'])
        # hide field in main form
        with warnings.catch_warnings(record=True) as w:
            uihelper.hide_fields('CWUser', ('login', 'in_group'))
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, DeprecationWarning))
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_hidden', 'muledit_attributes'])
        # hide field in muledit form
        with warnings.catch_warnings(record=True) as w:
            uihelper.hide_fields('CWUser', ('login', 'in_group'), formtype='muledit')
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category, DeprecationWarning))
        section_conf = uicfg.autoform_section.get('CWUser', 'in_group', '*', 'subject')
        self.assertCountEqual(section_conf, ['main_hidden', 'muledit_hidden'])

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


def _schema():

    class Personne(EntityType):
        pass

    class Societe(EntityType):
        pass

    class Tag(EntityType):
        pass

    class travaille(RelationDefinition):
        subject = 'Personne'
        object = 'Societe'

    class tags(RelationDefinition):
        subject = 'Tag'
        object = ('Personne', 'Societe', 'Tag')

    return build_schema_from_namespace(locals().items())


class AutoformSectionTC(BaseTestCase):

    def test_derivation(self):
        schema = _schema()
        afs = uicfg.AutoformSectionRelationTags()
        afs.tag_subject_of(('Personne', 'travaille', '*'), 'main', 'relations')
        afs.tag_object_of(('*', 'travaille', 'Societe'), 'main', 'relations')
        afs.tag_subject_of(('Tag', 'tags', '*'), 'main', 'relations')

        afs2 = afs.derive(__name__, afs.__select__)
        afs2.tag_subject_of(('Personne', 'travaille', '*'), 'main', 'attributes')
        afs2.tag_object_of(('*', 'travaille', 'Societe'), 'main', 'attributes')
        afs2.tag_subject_of(('Tag', 'tags', 'Societe'), 'main', 'attributes')

        afs.init(schema)
        afs2.init(schema)

        self.assertEqual(afs2.etype_get('Tag', 'tags', 'subject', 'Personne'),
                         set(('main_relations', 'muledit_hidden', 'inlined_relations')))
        self.assertEqual(afs2.etype_get('Tag', 'tags', 'subject', 'Societe'),
                         set(('main_attributes', 'muledit_hidden', 'inlined_attributes')))
        self.assertEqual(afs2.etype_get('Personne', 'travaille', 'subject', 'Societe'),
                         set(('main_attributes', 'muledit_hidden', 'inlined_attributes')))
        self.assertEqual(afs2.etype_get('Societe', 'travaille', 'object', 'Personne'),
                         set(('main_attributes', 'muledit_hidden', 'inlined_attributes')))


if __name__ == '__main__':
    import unittest
    unittest.main()
