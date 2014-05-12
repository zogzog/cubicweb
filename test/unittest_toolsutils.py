# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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


from logilab.common.testlib import TestCase, unittest_main

from cubicweb.toolsutils import RQLExecuteMatcher


class RQLExecuteMatcherTests(TestCase):
    def matched_query(self, text):
        match = RQLExecuteMatcher.match(text)
        if match is None:
            return None
        return match['rql_query']

    def test_unknown_function_dont_match(self):
        self.assertIsNone(self.matched_query('foo'))
        self.assertIsNone(self.matched_query('rql('))
        self.assertIsNone(self.matched_query('hell("")'))
        self.assertIsNone(self.matched_query('eval("rql(\'bla\''))

    def test_rql_other_parameters_dont_match(self):
        self.assertIsNone(self.matched_query('rql("Any X WHERE X eid %(x)s")'))
        self.assertIsNone(self.matched_query('rql("Any X WHERE X eid %(x)s", {'))
        self.assertIsNone(self.matched_query('session.execute("Any X WHERE X eid %(x)s")'))
        self.assertIsNone(self.matched_query('session.execute("Any X WHERE X eid %(x)s", {'))

    def test_rql_function_match(self):
        for func_expr in ('rql', 'session.execute'):
            query = self.matched_query('%s("Any X WHERE X is ' % func_expr)
            self.assertEqual(query, 'Any X WHERE X is ')

    def test_offseted_rql_function_match(self):
        """check indentation is allowed"""
        for func_expr in ('  rql', '  session.execute'):
            query = self.matched_query('%s("Any X WHERE X is ' % func_expr)
            self.assertEqual(query, 'Any X WHERE X is ')


if __name__ == '__main__':
    unittest_main()
