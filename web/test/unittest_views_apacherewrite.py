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
from logilab.common.testlib import TestCase, unittest_main

from cubicweb.web.views.apacherewrite import *

class ApacheURLRewriteTC(TestCase):

    def test(self):
        class MyAppRules(ApacheURLRewrite):
            rules = [
                RewriteCond('logilab\.fr', match='host',
                            rules=[('/(.*)', r'http://www.logilab.fr/\1')],
                            action='redirect'),
                RewriteCond('(www)\.logilab\.fr', match='host', action='stop'),
                RewriteCond('/(data|json)/', match='path', action='stop'),
                RewriteCond('(?P<cat>.*)\.logilab\.fr', match='host',
                            rules=[('/(.*)', r'/m_%(cat)s/\1')]),
                ]
        urlrewriter = MyAppRules()
        req = None # not used in the above rules, so keep a simple TestCase here
        try:
            urlrewriter.rewrite('logilab.fr', '/whatever', req)
            self.fail('redirect exception expected')
        except Redirect, ex:
            self.assertEquals(ex.location, 'http://www.logilab.fr/whatever')
        self.assertEquals(urlrewriter.rewrite('www.logilab.fr', '/whatever', req),
                          '/whatever')
        self.assertEquals(urlrewriter.rewrite('www.logilab.fr', '/json/bla', req),
                          '/json/bla')
        self.assertEquals(urlrewriter.rewrite('abcd.logilab.fr', '/json/bla', req),
                          '/json/bla')
        self.assertEquals(urlrewriter.rewrite('abcd.logilab.fr', '/data/bla', req),
                          '/data/bla')
        self.assertEquals(urlrewriter.rewrite('abcd.logilab.fr', '/whatever', req),
                          '/m_abcd/whatever')
        self.assertEquals(urlrewriter.rewrite('abcd.fr', '/whatever', req),
                          '/whatever')


if __name__ == '__main__':
    unittest_main()
