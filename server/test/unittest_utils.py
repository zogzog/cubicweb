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
"""

"""
from logilab.common.testlib import TestCase, unittest_main

from cubicweb.server import utils

class UtilsTC(TestCase):
    def test_crypt(self):
        for hash in (
            utils.crypt_password('xxx'), # default sha512
            'ab$5UsKFxRKKN.d8iBIFBnQ80', # custom md5
            'ab4Vlm81ZUHlg', # DES
            ):
            self.assertEqual(utils.crypt_password('xxx', hash), hash)
            self.assertEqual(utils.crypt_password(u'xxx', hash), hash)
            self.assertEqual(utils.crypt_password(u'xxx', unicode(hash)), hash)
            self.assertEqual(utils.crypt_password('yyy', hash), '')

        # accept any password for empty hashes (is it a good idea?)
        self.assertEqual(utils.crypt_password('xxx', ''), '')
        self.assertEqual(utils.crypt_password('yyy', ''), '')


if __name__ == '__main__':
    unittest_main()
