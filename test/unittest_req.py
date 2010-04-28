# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# logilab-common is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.req import RequestSessionBase

class RebuildURLTC(TestCase):
    def test(self):
        rebuild_url = RequestSessionBase(None).rebuild_url
        self.assertEquals(rebuild_url('http://logilab.fr?__message=pouet', __message='hop'),
                          'http://logilab.fr?__message=hop')
        self.assertEquals(rebuild_url('http://logilab.fr', __message='hop'),
                          'http://logilab.fr?__message=hop')
        self.assertEquals(rebuild_url('http://logilab.fr?vid=index', __message='hop'),
                          'http://logilab.fr?__message=hop&vid=index')


if __name__ == '__main__':
    unittest_main()
