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
import re

from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.sobjects.supervising import SendMailOp, SupervisionMailOp


class SupervisingTC(CubicWebTC):

    def setup_database(self):
        with self.admin_access.client_cnx() as cnx:
            cnx.create_entity('Card', title=u"une news !", content=u"cubicweb c'est beau")
            card = cnx.create_entity('Card', title=u"une autre news !", content=u"cubicweb c'est beau")
            cnx.create_entity('Bookmark', title=u"un signet !", path=u"view?vid=index")
            cnx.create_entity('Comment', content=u"Yo !", comments=card)
            cnx.commit()
        self.vreg.config.global_set_option('supervising-addrs', 'test@logilab.fr')


    def test_supervision(self):
        # do some modification
        with self.admin_access.repo_cnx() as cnx:
            user = cnx.execute('INSERT CWUser X: X login "toto", X upassword "sosafe", X in_group G '
                                'WHERE G name "users"').get_entity(0, 0)
            cnx.execute('SET X last_login_time NOW WHERE X eid %(x)s', {'x': user.eid})
            cnx.execute('DELETE Card B WHERE B title "une news !"')
            cnx.execute('SET X bookmarked_by U WHERE X is Bookmark, U eid %(x)s', {'x': user.eid})
            cnx.execute('SET X content "duh?" WHERE X is Comment')
            cnx.execute('DELETE Comment C WHERE C comments Y, Y is Card, Y title "une autre news !"')
            # check only one supervision email operation
            sentops = [op for op in cnx.pending_operations
                       if isinstance(op, SupervisionMailOp)]
            self.assertEqual(len(sentops), 1)
            # check view content
            op = sentops[0]
            view = sentops[0]._get_view()
            self.assertEqual(view.recipients(), ['test@logilab.fr'])
            self.assertEqual(view.subject(), '[data supervision] changes summary')
            data = view.render(changes=cnx.transaction_data.get('pendingchanges')).strip()
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
            cnx.commit()
            # some other changes #######
            user.cw_adapt_to('IWorkflowable').fire_transition('deactivate')
            sentops = [op for op in cnx.pending_operations
                       if isinstance(op, SupervisionMailOp)]
            self.assertEqual(len(sentops), 1)
            # check view content
            op = sentops[0]
            view = sentops[0]._get_view()
            data = view.render(changes=cnx.transaction_data.get('pendingchanges')).strip()
            data = re.sub('#\d+', '#EID', data)
            data = re.sub('/\d+', '/EID', data)
            self.assertMultiLineEqual('''user admin has made the following change(s):

* changed state of cwuser #EID (toto)
  from state activated to state deactivated
  http://testing.fr/cubicweb/cwuser/toto''',
                              data)

    def test_nonregr1(self):
        with self.admin_access.repo_cnx() as cnx:
            # do some unlogged modification
            cnx.execute('SET X last_login_time NOW WHERE X eid %(x)s', {'x': cnx.user.eid})
            cnx.commit() # no crash


if __name__ == '__main__':
    unittest_main()
