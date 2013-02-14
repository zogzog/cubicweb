# -*- coding: utf-8 -*-
# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""functional tests for core hooks

Note:
  syncschema.py hooks are mostly tested in server/test/unittest_migrations.py
"""

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC

class CWPropertyHooksTC(CubicWebTC):

    def test_unexistant_cwproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "bla.bla", X value "hop", X for_user U')
        cm.exception.translate(unicode)
        self.assertEqual(cm.exception.errors, {'pkey-subject': 'unknown property key bla.bla'})
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "bla.bla", X value "hop"')
        cm.exception.translate(unicode)
        self.assertEqual(cm.exception.errors, {'pkey-subject': 'unknown property key bla.bla'})

    def test_site_wide_cwproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "ui.site-title", X value "hop", X for_user U')
        self.assertEqual(cm.exception.errors, {'for_user-subject': "site-wide property can't be set for user"})

    def test_system_cwproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "system.version.cubicweb", X value "hop", X for_user U')
        self.assertEqual(cm.exception.errors, {'for_user-subject': "site-wide property can't be set for user"})

    def test_bad_type_cwproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "ui.language", X value "hop", X for_user U')
        self.assertEqual(cm.exception.errors, {'value-subject': u'unauthorized value'})
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "ui.language", X value "hop"')
        self.assertEqual(cm.exception.errors, {'value-subject': u'unauthorized value'})

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
