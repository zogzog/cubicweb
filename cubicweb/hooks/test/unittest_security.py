# copyright 2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server import hook
from cubicweb.predicates import is_instance


class SecurityHooksTC(CubicWebTC):
    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            self.add_eid = cnx.create_entity('EmailAddress',
                                             address=u'hop@perdu.com',
                                             reverse_use_email=cnx.user.eid).eid
            cnx.commit()

    def test_inlined_cw_edited_relation(self):
        """modification of cw_edited to add an inlined relation shouldn't trigger a security error.

        Test for https://www.cubicweb.org/ticket/5477315
        """
        sender = self.repo.schema['Email'].rdef('sender')
        with self.temporary_permissions((sender, {'add': ()})):

            class MyHook(hook.Hook):
                __regid__ = 'test.pouet'
                __select__ = hook.Hook.__select__ & is_instance('Email')
                events = ('before_add_entity',)

                def __call__(self):
                    self.entity.cw_edited['sender'] = self._cw.user.primary_email[0].eid

            with self.temporary_appobjects(MyHook):
                with self.admin_access.repo_cnx() as cnx:
                    email = cnx.create_entity('Email', messageid=u'1234')
                    cnx.commit()
                    self.assertEqual(email.sender[0].eid, self.add_eid)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
