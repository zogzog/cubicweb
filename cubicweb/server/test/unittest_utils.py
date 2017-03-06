# copyright 2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Tests for cubicweb.server.utils module."""

from cubicweb.devtools import testlib
from cubicweb.server import utils


class UtilsTC(testlib.BaseTestCase):

    def test_crypt(self):
        for hash in (
            utils.crypt_password('xxx'),  # default sha512
            b'ab$5UsKFxRKKN.d8iBIFBnQ80',  # custom md5
            b'ab4Vlm81ZUHlg',  # DES
        ):
            self.assertEqual(utils.crypt_password('xxx', hash), hash)
            self.assertEqual(utils.crypt_password(u'xxx', hash), hash)
            self.assertEqual(utils.crypt_password(u'xxx', hash.decode('ascii')),
                             hash.decode('ascii'))
            self.assertEqual(utils.crypt_password('yyy', hash), b'')

        # accept any password for empty hashes (is it a good idea?)
        self.assertEqual(utils.crypt_password('xxx', ''), '')
        self.assertEqual(utils.crypt_password('yyy', ''), '')

    def test_schedule_periodic_task(self):
        scheduler = utils.scheduler()
        this = []

        def fill_this(x):
            this.append(x)
            if len(this) > 2:
                raise SystemExit()
            elif len(this) > 1:
                raise RuntimeError()

        event = utils.schedule_periodic_task(scheduler, 0.01, fill_this, 1)
        self.assertEqual(event.action.__name__, 'fill_this')
        self.assertEqual(len(scheduler.queue), 1)

        with self.assertLogs('cubicweb.scheduler', level='ERROR') as cm:
            scheduler.run()
        self.assertEqual(this, [1] * 3)
        self.assertEqual(len(cm.output), 2)
        self.assertIn('Unhandled exception in periodic task "fill_this"',
                      cm.output[0])
        self.assertIn('"fill_this" not re-scheduled', cm.output[1])


if __name__ == '__main__':
    import unittest
    unittest.main()
