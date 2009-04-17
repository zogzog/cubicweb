from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.common.rest import rest_publish
        
class RestTC(EnvBasedTC):
    def context(self):
        return self.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)
    
    def test_eid_role(self):
        context = self.context()
        self.assertEquals(rest_publish(context, ':eid:`%s`' % context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/euser/admin">#%s</a></p>\n' % context.eid)
        self.assertEquals(rest_publish(context, ':eid:`%s:some text`' %  context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/euser/admin">some text</a></p>\n')
        
    def test_card_role_create(self):
        self.assertEquals(rest_publish(self.context(), ':card:`index`'),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/view?etype=Card&amp;wikiid=index&amp;vid=creation">index</a></p>\n')

    def test_card_role_link(self):
        self.add_entity('Card', wikiid=u'index', title=u'Site index page', synopsis=u'yo')
        self.assertEquals(rest_publish(self.context(), ':card:`index`'),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/card/index">index</a></p>\n')

    def test_bad_rest_no_crash(self):
        data = rest_publish(self.context(), '''
| card | implication     |
--------------------------
| 1-1  | N1 = N2         |
| 1-?  | N1 <= N2        |
| 1-+  | N1 >= N2        |
| 1-*  | N1>0 => N2>0    |       
--------------------------
| ?-?  | N1 # N2         |
| ?-+  | N1 >= N2        |
| ?-*  | N1 #  N2        |
--------------------------
| +-+  | N1>0 => N2>0 et |
|      | N2>0 => N1>0    |
| +-*  | N1>+ => N2>0    |
--------------------------
| *-*  | N1#N2           |
--------------------------

''')
        
if __name__ == '__main__':
    unittest_main()
