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
"""

"""
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.etwist.server import host_prefixed_baseurl


class HostPrefixedBaseURLTC(CubicWebTC):

    def _check(self, baseurl, host, waited):
        self.assertEquals(host_prefixed_baseurl(baseurl, host), waited,
                          'baseurl %s called through host %s should be considered as %s'
                          % (baseurl, host, waited))

    def test1(self):
        self._check('http://www.cubicweb.org/hg/', 'code.cubicweb.org',
                    'http://code.cubicweb.org/hg/')

    def test2(self):
        self._check('http://www.cubicweb.org/hg/', 'cubicweb.org',
                    'http://www.cubicweb.org/hg/')

    def test3(self):
        self._check('http://cubicweb.org/hg/', 'code.cubicweb.org',
                    'http://code.cubicweb.org/hg/')

    def test4(self):
        self._check('http://www.cubicweb.org/hg/', 'localhost',
                    'http://www.cubicweb.org/hg/')

    def test5(self):
        self._check('http://www.cubicweb.org/cubes/', 'hg.code.cubicweb.org',
                    'http://hg.code.cubicweb.org/cubes/')

    def test6(self):
        self._check('http://localhost:8080/hg/', 'code.cubicweb.org',
                    'http://localhost:8080/hg/')

