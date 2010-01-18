"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.ext.rest import rest_publish

class RestTC(CubicWebTC):
    def context(self):
        return self.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)

    def test_eid_role(self):
        context = self.context()
        self.assertEquals(rest_publish(context, ':eid:`%s`' % context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/cwuser/admin">#%s</a></p>\n' % context.eid)
        self.assertEquals(rest_publish(context, ':eid:`%s:some text`' %  context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/cwuser/admin">some text</a></p>\n')

    def test_bad_rest_no_crash(self):
        data = rest_publish(self.context(), '''
| card | implication     |
--------------------------
| 1-1  | N1 = N2         |
| 1-?  | N1 <= N2        |
| 1-+  | N1 >= N2        |
| 1-*  | N1>0 => N2>0    |
--------------------------
| ?-?  | N1 # N2         |
| ?-+  | N1 >= N2        |
| ?-*  | N1 #  N2        |
--------------------------
| +-+  | N1>0 => N2>0 et |
|      | N2>0 => N1>0    |
| +-*  | N1>+ => N2>0    |
--------------------------
| *-*  | N1#N2           |
--------------------------

''')

if __name__ == '__main__':
    unittest_main()
