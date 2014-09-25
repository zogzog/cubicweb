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

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.session import HOOKS_ALLOW_ALL, HOOKS_DENY_ALL
from cubicweb.server import hook
from cubicweb.predicates import is_instance

class InternalSessionTC(CubicWebTC):
    def test_dbapi_query(self):
        session = self.repo.internal_session()
        self.assertFalse(session.running_dbapi_query)
        session.close()

    def test_integrity_hooks(self):
        with self.repo.internal_session() as session:
            self.assertEqual(HOOKS_ALLOW_ALL, session.hooks_mode)
            self.assertEqual(set(('integrity', 'security')), session.disabled_hook_categories)
            self.assertEqual(set(), session.enabled_hook_categories)
            session.commit()
            self.assertEqual(HOOKS_ALLOW_ALL, session.hooks_mode)
            self.assertEqual(set(('integrity', 'security')), session.disabled_hook_categories)
            self.assertEqual(set(), session.enabled_hook_categories)

class SessionTC(CubicWebTC):

    def test_hooks_control(self):
        session = self.session
        # this test check the "old" behavior of session with automatic connection management
        # close the default cnx, we do nto want it to interfer with the test
        self.cnx.close()
        # open a dedicated one
        session.set_cnx('Some-random-cnx-unrelated-to-the-default-one')
        # go test go
        self.assertEqual(HOOKS_ALLOW_ALL, session.hooks_mode)
        self.assertEqual(set(), session.disabled_hook_categories)
        self.assertEqual(set(), session.enabled_hook_categories)
        self.assertEqual(1, len(session._cnxs))
        with session.deny_all_hooks_but('metadata'):
            self.assertEqual(HOOKS_DENY_ALL, session.hooks_mode)
            self.assertEqual(set(), session.disabled_hook_categories)
            self.assertEqual(set(('metadata',)), session.enabled_hook_categories)
            session.commit()
            self.assertEqual(HOOKS_DENY_ALL, session.hooks_mode)
            self.assertEqual(set(), session.disabled_hook_categories)
            self.assertEqual(set(('metadata',)), session.enabled_hook_categories)
            session.rollback()
            self.assertEqual(HOOKS_DENY_ALL, session.hooks_mode)
            self.assertEqual(set(), session.disabled_hook_categories)
            self.assertEqual(set(('metadata',)), session.enabled_hook_categories)
            with session.allow_all_hooks_but('integrity'):
                self.assertEqual(HOOKS_ALLOW_ALL, session.hooks_mode)
                self.assertEqual(set(('integrity',)), session.disabled_hook_categories)
                self.assertEqual(set(('metadata',)), session.enabled_hook_categories) # not changed in such case
            self.assertEqual(HOOKS_DENY_ALL, session.hooks_mode)
            self.assertEqual(set(), session.disabled_hook_categories)
            self.assertEqual(set(('metadata',)), session.enabled_hook_categories)
        # leaving context manager with no transaction running should reset the
        # transaction local storage (and associated cnxset)
        self.assertEqual({}, session._cnxs)
        self.assertEqual(None, session.cnxset)
        self.assertEqual(HOOKS_ALLOW_ALL, session.hooks_mode, session.HOOKS_ALLOW_ALL)
        self.assertEqual(set(), session.disabled_hook_categories)
        self.assertEqual(set(), session.enabled_hook_categories)

    def test_explicit_connection(self):
        with self.session.new_cnx() as cnx:
            rset = cnx.execute('Any X LIMIT 1 WHERE X is CWUser')
            self.assertEqual(1, len(rset))
            user = rset.get_entity(0, 0)
            user.cw_delete()
            cnx.rollback()
            new_user = cnx.entity_from_eid(user.eid)
            self.assertIsNotNone(new_user.login)
        self.assertFalse(cnx._open)

    def test_internal_cnx(self):
        with self.repo.internal_cnx() as cnx:
            rset = cnx.execute('Any X LIMIT 1 WHERE X is CWUser')
            self.assertEqual(1, len(rset))
            user = rset.get_entity(0, 0)
            user.cw_delete()
            cnx.rollback()
            new_user = cnx.entity_from_eid(user.eid)
            self.assertIsNotNone(new_user.login)
        self.assertFalse(cnx._open)

    def test_connection_exit(self):
        """exiting a connection should roll back the transaction, including any
        pending operations"""
        self.rollbacked = False
        class RollbackOp(hook.Operation):
            _test = self
            def rollback_event(self):
                self._test.rollbacked = True
        class RollbackHook(hook.Hook):
            __regid__ = 'rollback'
            events = ('after_update_entity',)
            __select__ = hook.Hook.__select__ & is_instance('CWGroup')
            def __call__(self):
                RollbackOp(self._cw)
        with self.temporary_appobjects(RollbackHook):
            with self.admin_access.client_cnx() as cnx:
                cnx.execute('SET G name "foo" WHERE G is CWGroup, G name "managers"')
            self.assertTrue(self.rollbacked)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
