"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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

