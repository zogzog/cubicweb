# copyright 2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""tests for notification hooks"""

from cubicweb.devtools.testlib import CubicWebTC


class NotificationHooksTC(CubicWebTC):

    def test_entity_update(self):
        """Check transaction_data['changes'] filled by "notifentityupdated" hook.
        """
        with self.admin_access.repo_cnx() as cnx:
            root = cnx.create_entity('Folder', name=u'a')
            cnx.commit()
            root.cw_set(name=u'b')
            self.assertIn('changes', cnx.transaction_data)
            self.assertEqual(cnx.transaction_data['changes'],
                             {root.eid: set([('name', u'a', u'b')])})


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
