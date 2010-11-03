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
from logilab.common.testlib import tag
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import uicfg

abaa = uicfg.actionbox_appearsin_addmenu

class UICFGTC(CubicWebTC):

    def test_default_actionbox_appearsin_addmenu_config(self):
        self.failIf(abaa.etype_get('TrInfo', 'wf_info_for', 'object', 'CWUser'))



class DefinitionOrderTC(CubicWebTC):
    """This test check that when multiple definition could match a key, only
    the more accurate apply"""

    def setUp(self):

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
        self._old_def = []

        for key, kwargs in new_def:
            nkey = key[0], key[1], key[2], 'subject'
            self._old_def.append((nkey, uicfg.autoform_section._tagdefs.get(nkey)))
            uicfg.autoform_section.tag_subject_of(key, **kwargs)

        super(DefinitionOrderTC, self).setUp()


    @tag('uicfg')
    def test_definition_order_hidden(self):
        result = uicfg.autoform_section.get('CWUser', 'login', 'String', 'subject')
        expected = set(['main_inlined', 'muledit_attributes', 'inlined_attributes'])
        self.assertSetEqual(result, expected)

    def tearDown(self):
        super(DefinitionOrderTC, self).tearDown()
        for key, tags in self._old_def:
                if tags is None:
                    uicfg.autoform_section.del_rtag(*key)
                else:
                    for tag in tags:
                        formtype, section = tag.split('_')
                        uicfg.autoform_section.tag_subject_of(key[:3], formtype=formtype, section=section)

        uicfg.autoform_section.clear()
        uicfg.autoform_section.init(self.repo.vreg.schema)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
