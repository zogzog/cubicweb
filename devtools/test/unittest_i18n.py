# -*- coding: iso-8859-1 -*-
# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for i18n messages generator"""

import os, os.path as osp
import sys

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.cwconfig import CubicWebNoAppConfiguration

DATADIR = osp.join(osp.abspath(osp.dirname(__file__)), 'data')

def load_po(fname):
    """load a po file and  return a set of encountered (msgid, msgctx)"""
    msgs = set()
    msgid = msgctxt = None
    for line in open(fname):
        if line.strip() in ('', '#'):
            continue
        if line.startswith('msgstr'):
            assert not (msgid, msgctxt) in msgs
            msgs.add( (msgid, msgctxt) )
            msgid = msgctxt = None
        elif line.startswith('msgid'):
            msgid = line.split(' ', 1)[1][1:-1]
        elif line.startswith('msgctx'):
            msgctxt = line.split(' ', 1)[1][1: -1]
        elif msgid is not None:
            msgid += line[1:-1]
        elif msgctxt is not None:
            msgctxt += line[1:-1]
    return msgs


class cubePotGeneratorTC(TestCase):
    """test case for i18n pot file generator"""

    def setUp(self):
        self._CUBES_PATH = CubicWebNoAppConfiguration.CUBES_PATH[:]
        CubicWebNoAppConfiguration.CUBES_PATH.append(osp.join(DATADIR, 'cubes'))
        CubicWebNoAppConfiguration.cls_adjust_sys_path()

    def tearDown(self):
        CubicWebNoAppConfiguration.CUBES_PATH[:] = self._CUBES_PATH

    def test_i18ncube(self):
        # MUST import here to make, since the import statement fire
        # the cube paths setup (and then must occur after the setUp)
        from cubicweb.devtools.devctl import update_cube_catalogs
        cube = osp.join(DATADIR, 'cubes', 'i18ntestcube')
        msgs = load_po(osp.join(cube, 'i18n', 'en.po.ref'))
        update_cube_catalogs(cube)
        newmsgs = load_po(osp.join(cube, 'i18n', 'en.po'))
        self.assertEqual(msgs, newmsgs)

if __name__ == '__main__':
    # XXX dirty hack to make this test runnable using python (works
    # fine with pytest, but not with python directly if this hack is
    # not present)
    # XXX to remove ASA logilab.common is fixed
    sys.path.append('')
    unittest_main()
