# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from __future__ import with_statement

from cubicweb.devtools.testlib import CubicWebTC


class InternalSessionTC(CubicWebTC):
    def test_dbapi_query(self):
        session = self.repo.internal_session()
        self.assertFalse(session.running_dbapi_query)
        session.close()


class SessionTC(CubicWebTC):

    def test_hooks_control(self):
        session = self.session
        self.assertEqual(session.hooks_mode, session.HOOKS_ALLOW_ALL)
        self.assertEqual(session.disabled_hook_categories, set())
        self.assertEqual(session.enabled_hook_categories, set())
        self.assertEqual(len(session._tx_data), 1)
        with session.deny_all_hooks_but('metadata'):
            self.assertEqual(session.hooks_mode, session.HOOKS_DENY_ALL)
            self.assertEqual(session.disabled_hook_categories, set())
            self.assertEqual(session.enabled_hook_categories, set(('metadata',)))
            session.commit()
            self.assertEqual(session.hooks_mode, session.HOOKS_DENY_ALL)
            self.assertEqual(session.disabled_hook_categories, set())
            self.assertEqual(session.enabled_hook_categories, set(('metadata',)))
            session.rollback()
            self.assertEqual(session.hooks_mode, session.HOOKS_DENY_ALL)
            self.assertEqual(session.disabled_hook_categories, set())
            self.assertEqual(session.enabled_hook_categories, set(('metadata',)))
            with session.allow_all_hooks_but('integrity'):
                self.assertEqual(session.hooks_mode, session.HOOKS_ALLOW_ALL)
                self.assertEqual(session.disabled_hook_categories, set(('integrity',)))
                self.assertEqual(session.enabled_hook_categories, set(('metadata',))) # not changed in such case
            self.assertEqual(session.hooks_mode, session.HOOKS_DENY_ALL)
            self.assertEqual(session.disabled_hook_categories, set())
            self.assertEqual(session.enabled_hook_categories, set(('metadata',)))
        # leaving context manager with no transaction running should reset the
        # transaction local storage (and associated cnxset)
        self.assertEqual(session._tx_data, {})
        self.assertEqual(session.cnxset, None)
        self.assertEqual(session.hooks_mode, session.HOOKS_ALLOW_ALL)
        self.assertEqual(session.disabled_hook_categories, set())
        self.assertEqual(session.enabled_hook_categories, set())


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
