from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC

class HooksTC(EnvBasedTC):

    def test_euser_login_stripped(self):
        u = self.create_user('  joe  ')
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEquals(tname, 'joe')
        self.execute('SET X login " jijoe " WHERE X eid %(x)s', {'x': u.eid})
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEquals(tname, 'jijoe')


    def test_auto_delete_bookmarks(self):
        beid = self.execute('INSERT Bookmark X: X title "hop", X path "view", X bookmarked_by U '
                            'WHERE U login "admin"')[0][0]
        self.execute('SET X bookmarked_by U WHERE U login "anon"')
        self.commit()
        self.execute('DELETE X bookmarked_by U WHERE U login "admin"')
        self.commit()
        self.failUnless(self.execute('Any X WHERE X eid %(x)s', {'x': beid}, 'x'))
        self.execute('DELETE X bookmarked_by U WHERE U login "anon"')
        self.commit()
        self.failIf(self.execute('Any X WHERE X eid %(x)s', {'x': beid}, 'x'))

if __name__ == '__main__':
    unittest_main()
