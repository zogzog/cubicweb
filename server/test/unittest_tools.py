from logilab.common.testlib import TestCase, unittest_main

class ImportTC(TestCase):
    def test(self):
        # the minimal test: module is importable...
        import cubicweb.server.server
        import cubicweb.server.checkintegrity
        import cubicweb.server.serverctl

if __name__ == '__main__':
    unittest_main()
