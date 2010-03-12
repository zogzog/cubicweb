from logilab.common.testlib import TestCase, unittest_main
from cubicweb.req import RequestSessionBase

class RebuildURLTC(TestCase):
    def test(self):
        rebuild_url = RequestSessionBase(None).rebuild_url
        self.assertEquals(rebuild_url('http://logilab.fr?__message=pouet', __message='hop'),
                          'http://logilab.fr?__message=hop')
        self.assertEquals(rebuild_url('http://logilab.fr', __message='hop'),
                          'http://logilab.fr?__message=hop')
        self.assertEquals(rebuild_url('http://logilab.fr?vid=index', __message='hop'),
                          'http://logilab.fr?__message=hop&vid=index')


if __name__ == '__main__':
    unittest_main()
