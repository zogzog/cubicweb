from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

class PyViewsTC(CubicWebTC):

    def test_pyvaltable(self):
        view = self.vreg['views'].select('pyvaltable', self.request(),
                                         pyvalue=[[1, 'a'], [2, 'b']])
        content = view.render(pyvalue=[[1, 'a'], [2, 'b']],
                              headers=['num', 'char'])
        self.assertEquals(content.strip(), '''<table class="listing">
<thead><tr><th>num</th><th>char</th></tr>
</thead><tbody><tr><td>1</td><td>a</td></tr>
<tr><td>2</td><td>b</td></tr>
</tbody></table>''')

    def test_pyvallist(self):
        view = self.vreg['views'].select('pyvallist', self.request(),
                                         pyvalue=[1, 'a'])
        content = view.render(pyvalue=[1, 'a'])
        self.assertEquals(content.strip(), '''<ul>
<li>1</li>
<li>a</li>
</ul>''')

if __name__ == '__main__':
    unittest_main()
