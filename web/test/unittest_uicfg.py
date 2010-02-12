from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import uicfg

class UICFGTC(CubicWebTC):

    def test(self):
        self.skip('write some tests')

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
