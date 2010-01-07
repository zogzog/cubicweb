"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import TestCase, unittest_main, mock_object

from cubicweb.server.session import _make_description

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
        self.assertEquals(_make_description((Function('max', 'A'), Variable('B')), {}, solution),
                          ['Int','CWUser'])

if __name__ == '__main__':
    unittest_main()
