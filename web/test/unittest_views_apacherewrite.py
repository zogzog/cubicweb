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
        try:
            urlrewriter.rewrite('logilab.fr', '/whatever')
            self.fail('redirect exception expected')
        except Redirect, ex:
            self.assertEquals(ex.location, 'http://www.logilab.fr/whatever')
        self.assertEquals(urlrewriter.rewrite('www.logilab.fr', '/whatever'),
                          '/whatever')
        self.assertEquals(urlrewriter.rewrite('www.logilab.fr', '/json/bla'),
                          '/json/bla')
        self.assertEquals(urlrewriter.rewrite('abcd.logilab.fr', '/json/bla'),
                          '/json/bla')
        self.assertEquals(urlrewriter.rewrite('abcd.logilab.fr', '/data/bla'),
                          '/data/bla')
        self.assertEquals(urlrewriter.rewrite('abcd.logilab.fr', '/whatever'),
                          '/m_abcd/whatever')
        self.assertEquals(urlrewriter.rewrite('abcd.fr', '/whatever'),
                          '/whatever')


if __name__ == '__main__':
    unittest_main()
