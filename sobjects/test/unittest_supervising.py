# -*- coding: iso-8859-1 -*-
import re

from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.sobjects.supervising import SendMailOp, SupervisionMailOp


class SupervisingTC(EnvBasedTC):

    def setup_database(self):
        self.add_entity('Card', title=u"une news !", content=u"cubicweb c'est beau")
        self.add_entity('Card', title=u"une autre news !", content=u"cubicweb c'est beau")
        self.add_entity('Bookmark', title=u"un signet !", path=u"view?vid=index")
        self.add_entity('Comment', content=u"Yo !")
        self.execute('SET C comments B WHERE B title "une autre news !", C content "Yo !"')
        self.vreg.config.global_set_option('supervising-addrs', 'test@logilab.fr')


    def test_supervision(self):
        session = self.session()
        # do some modification
        ueid = self.execute('INSERT CWUser X: X login "toto", X upassword "sosafe", X in_group G, X in_state S '
                            'WHERE G name "users", S name "activated"')[0][0]
        self.execute('SET X last_login_time NOW WHERE X eid %(x)s', {'x': ueid}, 'x')
        self.execute('SET X in_state S WHERE X login "anon", S name "deactivated"')
        self.execute('DELETE Card B WHERE B title "une news !"')
        self.execute('SET X bookmarked_by U WHERE X is Bookmark, U eid %(x)s', {'x': ueid}, 'x')
        self.execute('SET X content "duh?" WHERE X is Comment')
        self.execute('DELETE X comments Y WHERE Y is Card, Y title "une autre news !"')
        # check only one supervision email operation
        sentops = [op for op in session.pending_operations
                   if isinstance(op, SupervisionMailOp)]
        self.assertEquals(len(sentops), 1)
        # check view content
        op = sentops[0]
        view = sentops[0]._get_view()
        self.assertEquals(view.recipients(), ['test@logilab.fr'])
        self.assertEquals(view.subject(), '[data supervision] changes summary')
        data = view.render(changes=session.query_data('pendingchanges')).strip()
        data = re.sub('#\d+', '#EID', data)
        data = re.sub('/\d+', '/EID', data)
        self.assertTextEquals('''user admin has made the following change(s):

* added cwuser #EID (toto)
  http://testing.fr/cubicweb/cwuser/toto

* added relation in_group from cwuser #EID to cwgroup #EID

* deleted card #EID (une news !)

* added relation bookmarked_by from bookmark #EID to cwuser #EID

* updated comment #EID (#EID)
  http://testing.fr/cubicweb/comment/EID

* deleted relation comments from comment #EID to card #EID

* changed state of cwuser #EID (anon)
  from state activated to state deactivated
  http://testing.fr/cubicweb/cwuser/anon''',
                              data)
        # check prepared email
        op._prepare_email()
        self.assertEquals(len(op.to_send), 1)
        self.assert_(op.to_send[0][0])
        self.assertEquals(op.to_send[0][1], ['test@logilab.fr'])

    def test_nonregr1(self):
        session = self.session()
        # do some unlogged modification
        self.execute('SET X last_login_time NOW WHERE X eid %(x)s', {'x': session.user.eid}, 'x')
        self.commit() # no crash


if __name__ == '__main__':
    unittest_main()
