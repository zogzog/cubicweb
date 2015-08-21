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

from logilab.common import tempattr

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sources.native import FTIndexEntityOp

class NativeSourceTC(CubicWebTC):

    def test_index_entity_consider_do_fti(self):
        source = self.repo.system_source
        with tempattr(source, 'do_fti', False):
            with self.admin_access.repo_cnx() as cnx:
                # when do_fti is set to false, call to index_entity (as may be done from hooks)
                # should have no effect
                source.index_entity(cnx, cnx.user)
                self.assertNotIn(cnx.user.eid, FTIndexEntityOp.get_instance(cnx).get_data())


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
