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

from contextlib import contextmanager
from io import StringIO
import os
import os.path as osp
import sys
from subprocess import PIPE, Popen, STDOUT
from unittest import TestCase, main
from unittest.mock import patch

from cubicweb.devtools import devctl
from cubicweb.devtools.testlib import BaseTestCase

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


TESTCUBE_DIR = osp.join(DATADIR, 'libpython', 'cubicweb_i18ntestcube')


class cubePotGeneratorTC(TestCase):
    """test case for i18n pot file generator"""

    def test_i18ncube(self):
        env = os.environ.copy()
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] += os.pathsep
        else:
            env['PYTHONPATH'] = ''
        env['PYTHONPATH'] += osp.join(DATADIR, 'libpython')
        cubedir = osp.join(DATADIR, 'libpython', 'cubicweb_i18ntestcube')
        self._check(cubedir, env)

    def _check(self, cubedir, env):
        cmd = [sys.executable, '-m', 'cubicweb', 'i18ncube', 'i18ntestcube']
        proc = Popen(cmd, env=env, stdout=PIPE, stderr=STDOUT)
        stdout, _ = proc.communicate()
        msg = stdout.decode(sys.getdefaultencoding(), errors='replace')
        self.assertEqual(proc.returncode, 0, msg=msg)
        msgs = load_po(osp.join(cubedir, 'i18n', 'en.po.ref'))
        newmsgs = load_po(osp.join(cubedir, 'i18n', 'en.po'))
        self.assertEqual(msgs, newmsgs)


class CustomMessageExtractor(devctl.I18nCubeMessageExtractor):
    blacklist = devctl.I18nCubeMessageExtractor.blacklist | set(['excludeme'])


@contextmanager
def capture_stdout():
    stream = StringIO()
    sys.stdout = stream
    yield stream
    stream.seek(0)
    sys.stdout = sys.__stdout__


class I18nCollectorTest(BaseTestCase):

    def test_i18ncube_py_collection(self):
        extractor = CustomMessageExtractor(DATADIR, TESTCUBE_DIR)
        collected = extractor.collect_py()
        expected = [osp.join(TESTCUBE_DIR, path)
                    for path in ('__init__.py', '__pkginfo__.py',
                                 'views.py', 'schema.py')]
        self.assertCountEqual(expected, collected)

    def test_i18ncube_js_collection(self):
        extractor = CustomMessageExtractor(DATADIR, TESTCUBE_DIR)
        collected = extractor.collect_js()
        self.assertCountEqual([], collected, [])
        extractor.blacklist = ()  # don't ignore anything
        collected = extractor.collect_js()
        expected = [osp.join(TESTCUBE_DIR, 'node_modules/cubes.somefile.js')]
        self.assertCountEqual(expected, collected)

    class FakeMessageExtractor(devctl.I18nCubeMessageExtractor):
        """Fake message extractor that generates no pot file."""

        def generate_pot_file(self):
            return None

    @patch('pkg_resources.load_entry_point', return_value=FakeMessageExtractor)
    def test_cube_custom_extractor(self, mock_load_entry_point):
        distname = 'cubicweb_i18ntestcube'  # same for new and legacy layout
        cubedir = osp.join(DATADIR, 'libpython', 'cubicweb_i18ntestcube')
        with capture_stdout() as stream:
            devctl.update_cube_catalogs(cubedir)
        self.assertIn(u'no message catalog for cube i18ntestcube',
                      stream.read())
        mock_load_entry_point.assert_called_once_with(
            distname, 'cubicweb.i18ncube', 'i18ntestcube')
        mock_load_entry_point.reset_mock()


if __name__ == '__main__':
    main()
