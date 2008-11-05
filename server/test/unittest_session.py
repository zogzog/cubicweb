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
        solution = {'A': 'Int', 'B': 'EUser'}
        self.assertEquals(_make_description((Function('max', 'A'), Variable('B')), {}, solution),
                          ['Int','EUser'])

if __name__ == '__main__':
    unittest_main()
