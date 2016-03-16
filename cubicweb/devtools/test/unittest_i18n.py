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

import os
import os.path as osp
import sys
from subprocess import PIPE, Popen, STDOUT

from unittest import TestCase, main


DATADIR = osp.join(osp.abspath(osp.dirname(__file__)), 'data')


def load_po(fname):
    """load a po file and  return a set of encountered (msgid, msgctx)"""
    msgs = set()
    msgid = msgctxt = None
    with open(fname) as fobj:
        for line in fobj:
            if line.strip() in ('', '#'):
                continue
            if line.startswith('msgstr'):
                assert not (msgid, msgctxt) in msgs
                msgs.add((msgid, msgctxt))
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

    def test_i18ncube(self):
        env = os.environ.copy()
        env['CW_CUBES_PATH'] = osp.join(DATADIR, 'cubes')
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] += os.pathsep
        else:
            env['PYTHONPATH'] = ''
        env['PYTHONPATH'] += DATADIR
        cmd = [sys.executable, '-m', 'cubicweb', 'i18ncube', 'i18ntestcube']
        proc = Popen(cmd, env=env, stdout=PIPE, stderr=STDOUT)
        stdout, _ = proc.communicate()
        self.assertEqual(proc.returncode, 0, msg=stdout)
        cube = osp.join(DATADIR, 'cubes', 'i18ntestcube')
        msgs = load_po(osp.join(cube, 'i18n', 'en.po.ref'))
        newmsgs = load_po(osp.join(cube, 'i18n', 'en.po'))
        self.assertEqual(msgs, newmsgs)


if __name__ == '__main__':
    main()
