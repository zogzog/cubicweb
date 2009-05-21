# -*- coding: iso-8859-1 -*-
from socket import gethostname

from logilab.common.testlib import unittest_main, TestCase
from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.sobjects.notification import construct_message_id, parse_message_id

class MessageIdTC(TestCase):
    def test_base(self):
        msgid1 = construct_message_id('testapp', 21)
        msgid2 = construct_message_id('testapp', 21)
        self.failIfEqual(msgid1, msgid2)
        self.failIf('&' in msgid1)
        self.failIf('=' in msgid1)
        self.failIf('/' in msgid1)
        self.failIf('+' in msgid1)
        values = parse_message_id(msgid1, 'testapp')
        self.failUnless(values)
        # parse_message_id should work with or without surrounding <>
        self.failUnlessEqual(values, parse_message_id(msgid1[1:-1], 'testapp'))
        self.failUnlessEqual(values['eid'], '21')
        self.failUnless('timestamp' in values)
        self.failUnlessEqual(parse_message_id(msgid1[1:-1], 'anotherapp'), None)

    def test_notimestamp(self):
        msgid1 = construct_message_id('testapp', 21, False)
        msgid2 = construct_message_id('testapp', 21, False)
        values = parse_message_id(msgid1, 'testapp')
        self.failUnlessEqual(values, {'eid': '21'})

    def test_parse_message_doesnt_raise(self):
        self.failUnlessEqual(parse_message_id('oijioj@bla.bla', 'tesapp'), None)
        self.failUnlessEqual(parse_message_id('oijioj@bla', 'tesapp'), None)
        self.failUnlessEqual(parse_message_id('oijioj', 'tesapp'), None)


    def test_nonregr_empty_message_id(self):
        for eid in (1, 12, 123, 1234):
            msgid1 = construct_message_id('testapp', eid, 12)
            self.assertNotEquals(msgid1, '<@testapp.%s>' % gethostname())


class RecipientsFinderTC(EnvBasedTC):
    def test(self):
        urset = self.execute('CWUser X WHERE X login "admin"')
        self.execute('INSERT EmailAddress X: X address "admin@logilab.fr", U primary_email X '
                     'WHERE U eid %(x)s', {'x': urset[0][0]})
        self.execute('INSERT CWProperty X: X pkey "ui.language", X value "fr", X for_user U '
                     'WHERE U eid %(x)s', {'x': urset[0][0]})
        self.commit() # commit so that admin get its properties updated
        finder = self.vreg.select_component('recipients_finder', self.request(), urset)
        self.set_option('default-recipients-mode', 'none')
        self.assertEquals(finder.recipients(), [])
        self.set_option('default-recipients-mode', 'users')
        self.assertEquals(finder.recipients(), [(u'admin@logilab.fr', 'fr')])
        self.set_option('default-recipients-mode', 'default-dest-addrs')
        self.set_option('default-dest-addrs', 'abcd@logilab.fr, efgh@logilab.fr')
        self.assertEquals(finder.recipients(), [('abcd@logilab.fr', 'en'), ('efgh@logilab.fr', 'en')])


class StatusChangeViewsTC(EnvBasedTC):

    def test_status_change_view(self):
        req = self.session()
        u = self.create_user('toto', req=req)
        assert u.req
        self.execute('SET X in_state S WHERE X eid %s, S name "deactivated"' % u.eid)
        v = self.vreg.select_view('notif_status_change', req, u.rset, row=0)
        content = v.render(row=0, comment='yeah',
                           previous_state='activated',
                           current_state='deactivated')
        # remove date
        self.assertEquals(content,
                          '''
admin changed status from <activated> to <deactivated> for entity
'toto'

yeah

url: http://testing.fr/cubicweb/cwuser/toto
''')
        self.assertEquals(v.subject(), 'status changed cwuser #%s (admin)' % u.eid)

if __name__ == '__main__':
    unittest_main()
