# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server import session


class HooksControlTC(CubicWebTC):

    def test_hooks_control(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx._hooks_mode, session.HOOKS_ALLOW_ALL)
            self.assertEqual(cnx._hooks_categories, set())

            with cnx.deny_all_hooks_but('metadata'):
                self.assertEqual(cnx._hooks_mode, session.HOOKS_DENY_ALL)
                self.assertEqual(cnx._hooks_categories, set(['metadata']))

                with cnx.deny_all_hooks_but():
                    self.assertEqual(cnx._hooks_categories, set())
                self.assertEqual(cnx._hooks_categories, set(['metadata']))

                with cnx.deny_all_hooks_but('integrity'):
                    self.assertEqual(cnx._hooks_categories, set(['integrity']))
                self.assertEqual(cnx._hooks_categories, set(['metadata']))

                with cnx.allow_all_hooks_but('integrity'):
                    self.assertEqual(cnx._hooks_mode, session.HOOKS_ALLOW_ALL)
                    self.assertEqual(cnx._hooks_categories, set(['integrity']))
                self.assertEqual(cnx._hooks_mode, session.HOOKS_DENY_ALL)
                self.assertEqual(cnx._hooks_categories, set(['metadata']))

            self.assertEqual(cnx._hooks_mode, session.HOOKS_ALLOW_ALL)
            self.assertEqual(cnx._hooks_categories, set())


if __name__ == '__main__':
    import unittest
    unittest.main()
