# -*- coding: iso-8859-1 -*-
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
import re

from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.sobjects.supervising import SendMailOp, SupervisionMailOp


class SupervisingTC(CubicWebTC):

    def setup_database(self):
        req = self.request()
        req.create_entity('Card', title=u"une news !", content=u"cubicweb c'est beau")
        req.create_entity('Card', title=u"une autre news !", content=u"cubicweb c'est beau")
        req.create_entity('Bookmark', title=u"un signet !", path=u"view?vid=index")
        req.create_entity('Comment', content=u"Yo !")
        self.execute('SET C comments B WHERE B title "une autre news !", C content "Yo !"')
        self.vreg.config.global_set_option('supervising-addrs', 'test@logilab.fr')


    def test_supervision(self):
        # do some modification
        user = self.execute('INSERT CWUser X: X login "toto", X upassword "sosafe", X in_group G '
                            'WHERE G name "users"').get_entity(0, 0)
        self.execute('SET X last_login_time NOW WHERE X eid %(x)s', {'x': user.eid})
        self.execute('DELETE Card B WHERE B title "une news !"')
        self.execute('SET X bookmarked_by U WHERE X is Bookmark, U eid %(x)s', {'x': user.eid})
        self.execute('SET X content "duh?" WHERE X is Comment')
        self.execute('DELETE Comment C WHERE C comments Y, Y is Card, Y title "une autre news !"')
        # check only one supervision email operation
        session = self.session
        sentops = [op for op in session.pending_operations
                   if isinstance(op, SupervisionMailOp)]
        self.assertEqual(len(sentops), 1)
        # check view content
        op = sentops[0]
        view = sentops[0]._get_view()
        self.assertEqual(view.recipients(), ['test@logilab.fr'])
        self.assertEqual(view.subject(), '[data supervision] changes summary')
        data = view.render(changes=session.transaction_data.get('pendingchanges')).strip()
        data = re.sub('#\d+', '#EID', data)
        data = re.sub('/\d+', '/EID', data)
        self.assertMultiLineEqual('''user admin has made the following change(s):

* added cwuser #EID (toto)
  http://testing.fr/cubicweb/cwuser/toto

* added relation in_group from cwuser #EID to cwgroup #EID

* deleted card #EID (une news !)

* added relation bookmarked_by from bookmark #EID to cwuser #EID

* updated comment #EID (duh?)
  http://testing.fr/cubicweb/comment/EID

* deleted comment #EID (duh?)''',
                              data)
        # check prepared email
        op._prepare_email()
        self.assertEqual(len(op.to_send), 1)
        self.assert_(op.to_send[0][0])
        self.assertEqual(op.to_send[0][1], ['test@logilab.fr'])
        self.commit()
        # some other changes #######
        user.cw_adapt_to('IWorkflowable').fire_transition('deactivate')
        sentops = [op for op in session.pending_operations
                   if isinstance(op, SupervisionMailOp)]
        self.assertEqual(len(sentops), 1)
        # check view content
        op = sentops[0]
        view = sentops[0]._get_view()
        data = view.render(changes=session.transaction_data.get('pendingchanges')).strip()
        data = re.sub('#\d+', '#EID', data)
        data = re.sub('/\d+', '/EID', data)
        self.assertMultiLineEqual('''user admin has made the following change(s):

* changed state of cwuser #EID (toto)
  from state activated to state deactivated
  http://testing.fr/cubicweb/cwuser/toto''',
                              data)

    def test_nonregr1(self):
        session = self.session
        # do some unlogged modification
        self.execute('SET X last_login_time NOW WHERE X eid %(x)s', {'x': session.user.eid})
        self.commit() # no crash


if __name__ == '__main__':
    unittest_main()
