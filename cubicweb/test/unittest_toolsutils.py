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


import os
import tempfile
import unittest

from cubicweb.toolsutils import (RQLExecuteMatcher, option_value_from_env,
                                 read_config)


class RQLExecuteMatcherTests(unittest.TestCase):
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


SOURCES_CONTENT = b"""
[admin]

# cubicweb manager account's login (this user will be created)
login=admin

# cubicweb manager account's password
password=admin

[system]

# database driver (postgres, sqlite, sqlserver2005)
db-driver=postgres

# database host
db-host=

# database port
db-port=
"""


class ToolsUtilsTC(unittest.TestCase):

    def test_option_value_from_env(self):
        os.environ['CW_DB_HOST'] = 'here'
        try:
            self.assertEqual(option_value_from_env('db-host'), 'here')
            self.assertEqual(option_value_from_env('db-host', 'nothere'), 'here')
            self.assertEqual(option_value_from_env('db-hots', 'nothere'), 'nothere')
        finally:
            del os.environ['CW_DB_HOST']

    def test_read_config(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(SOURCES_CONTENT)
            f.seek(0)
            config = read_config(f.name)
        expected = {
            'admin': {
                'password': 'admin',
                'login': 'admin',
            },
            'system': {
                'db-port': None,
                'db-driver': 'postgres',
                'db-host': None,
            },
        }
        self.assertEqual(config, expected)

    def test_read_config_env(self):
        os.environ['CW_DB_HOST'] = 'here'
        try:
            with tempfile.NamedTemporaryFile() as f:
                f.write(SOURCES_CONTENT)
                f.seek(0)
                config = read_config(f.name)
        finally:
            del os.environ['CW_DB_HOST']
        self.assertEqual(config['system']['db-host'], 'here')


if __name__ == '__main__':
    unittest.main()
