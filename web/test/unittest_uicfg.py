from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import uicfg

abaa = uicfg.actionbox_appearsin_addmenu

class UICFGTC(CubicWebTC):

    def test_default_actionbox_appearsin_addmenu_config(self):
        self.failIf(abaa.etype_get('TrInfo', 'wf_info_for', 'object', 'CWUser'))

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
