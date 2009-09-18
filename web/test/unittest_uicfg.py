from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.web import uicfg

class UICFGTC(EnvBasedTC):

    def test_autoform_section_inlined(self):
        self.assertEquals(uicfg.autoform_is_inlined.etype_get('CWUser', 'use_email', 'subject', 'EmailAddress'),
                          True)
        self.assertEquals(uicfg.autoform_section.etype_get('CWUser', 'use_email', 'subject', 'EmailAddress'),
                          'generated')

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
