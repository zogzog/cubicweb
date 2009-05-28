from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC

class PyViewsTC(EnvBasedTC):

    def test_pyvaltable(self):
        content = self.vreg.view('pyvaltable', self.request(),
                                 pyvalue=[[1, 'a'], [2, 'b']],
                                 headers=['num', 'char'])
        self.assertEquals(content.strip(), '''<table class="listing">
<tr><th>num</th><th>char</th></tr>
<tr><td>1</td><td>a</td></tr>
<tr><td>2</td><td>b</td></tr>
</table>''')

    def test_pyvallist(self):
        content = self.vreg.view('pyvallist', self.request(),
                                 pyvalue=[1, 'a'])
        self.assertEquals(content.strip(), '''<ul>
<li>1</li>
<li>a</li>
</ul>''')

if __name__ == '__main__':
    unittest_main()
