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
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

import os, os.path as osp, glob
import urllib

from cubicweb.devtools.httptest import CubicWebServerTC


class ETwistHTTPTC(CubicWebServerTC):
    def test_put_content(self):
        data = {'hip': 'hop'}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        body = urllib.urlencode(data)
        response = self.web_request('?vid=put', method='PUT', body=body)
        self.assertEqual(body, response.body)
        response = self.web_request('?vid=put', method='POST', body=body,
                                    headers=headers)
        self.assertEqual(body, response.body)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
