# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common.testlib import TestCase, unittest_main, mock_object

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.session import _make_description, hooks_control

class Variable:
    def __init__(self, name):
        self.name = name
        self.children = []

    def get_type(self, solution, args=None):
        return solution[self.name]
    def as_string(self):
        return self.name

class Function:
    def __init__(self, name, varname):
        self.name = name
        self.children = [Variable(varname)]
    def get_type(self, solution, args=None):
        return 'Int'

class MakeDescriptionTC(TestCase):
    def test_known_values(self):
        solution = {'A': 'Int', 'B': 'CWUser'}
        self.assertEqual(_make_description((Function('max', 'A'), Variable('B')), {}, solution),
                          ['Int','CWUser'])


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
        with hooks_control(session, session.HOOKS_DENY_ALL, 'metadata'):
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
            with hooks_control(session, session.HOOKS_ALLOW_ALL, 'integrity'):
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

    def test_build_descr1(self):
        rset = self.execute('(Any U,L WHERE U login L) UNION (Any G,N WHERE G name N, G is CWGroup)')
        orig_length = len(rset)
        rset.rows[0][0] = 9999999
        description = self.session.build_description(rset.syntax_tree(), None, rset.rows)
        self.assertEqual(len(description), orig_length - 1)
        self.assertEqual(len(rset.rows), orig_length - 1)
        self.assertFalse(rset.rows[0][0] == 9999999)

    def test_build_descr2(self):
        rset = self.execute('Any X,Y WITH X,Y BEING ((Any G,NULL WHERE G is CWGroup) UNION (Any U,G WHERE U in_group G))')
        for x, y in rset.description:
            if y is not None:
                self.assertEqual(y, 'CWGroup')

    def test_build_descr3(self):
        rset = self.execute('(Any G,NULL WHERE G is CWGroup) UNION (Any U,G WHERE U in_group G)')
        for x, y in rset.description:
            if y is not None:
                self.assertEqual(y, 'CWGroup')


if __name__ == '__main__':
    unittest_main()
