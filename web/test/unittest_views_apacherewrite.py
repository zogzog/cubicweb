"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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
