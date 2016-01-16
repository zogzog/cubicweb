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

from logilab.common.testlib import unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.views import actions, uicfg


class ActionsTC(CubicWebTC):
    def test_view_action(self):
        with self.admin_access.web_request(vid='rss', rql='CWUser X') as req:
            rset = req.execute('CWUser X')
            actions = self.vreg['actions'].poss_visible_objects(req, rset=rset)
            vaction = [action for action in actions if action.__regid__ == 'view'][0]
            self.assertEqual(vaction.url(), 'http://testing.fr/cubicweb/view?rql=CWUser%20X')

    def test_has_editable_relations(self):
        """ensure has_editable_relation predicate used by ModifyAction
        return positive score if there is only some inlined forms
        """
        # The schema only allows the anonymous user to modify his/her own
        # EmailAddress if it is set, not to create one. Since the 'anon' CWUser
        # entity is created without any associated EmailAddress entities, there
        # are no attributes nor relations that can be edited: the "modify"
        # action should not appear.
        with self.new_access('anon').web_request() as req:
            predicate = actions.has_editable_relation()
            self.assertEqual(predicate(None, req, rset=req.user.as_rset()),
                             0)
        # being allowed to 'add' the relation is not enough
        use_email = self.schema['use_email'].rdefs['CWUser', 'EmailAddress']
        with self.temporary_permissions((use_email, {'add': ('guests',)})):
            with self.new_access('anon').web_request() as req:
                predicate = actions.has_editable_relation()
                self.assertEqual(predicate(None, req, rset=req.user.as_rset()),
                                 0)
        # if we also allow creating the target etype, then the "modify" action
        # should appear
        with self.temporary_permissions((use_email, {'add': ('guests',)}),
                                        EmailAddress={'add': ('guests',)}):
            with self.new_access('anon').web_request() as req:
                predicate = actions.has_editable_relation()
                self.assertEqual(predicate(None, req, rset=req.user.as_rset()),
                                 1)


if __name__ == '__main__':
    unittest_main()
