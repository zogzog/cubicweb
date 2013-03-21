from logilab.common.testlib import TestCase, unittest_main, tag, Tags

from cubicweb.web import StatusResponse
from cubicweb.devtools.fake import FakeRequest


def _test_cache(hin, hout, method='GET'):
    """forge and process a request

    return status code and the request object

    status is None is no cache is involved
    """
    # forge request
    req = FakeRequest(method=method)
    for key, value in hin:
        req._headers_in.addRawHeader(key, str(value))
    for key, value in hout:
        req.headers_out.addRawHeader(key, str(value))
    # process
    status = None
    try:
        req.validate_cache()
    except StatusResponse, ex:
        status = ex.status
    return status, req

class HTTPCache(TestCase):
    """Check that the http cache logiac work as expected
    (as far as we understood the RFC)

    """
    tags = TestCase.tags | Tags('http', 'cache')


    def assertCache(self, expected, status, situation=''):
        """simple assert for nicer message"""
        if expected != status:
            if expected is None:
                expected = "MODIFIED"
            if status is None:
                status = "MODIFIED"
            msg = 'expected %r got %r' % (expected, status)
            if situation:
                msg = "%s - when: %s" % (msg, situation)
            self.fail(msg)

    def test_IN_none_OUT_none(self):
        #: test that no caching is requested when not data is available
        #: on any side
        status, req =_test_cache((),())
        self.assertIsNone(status)

    def test_IN_Some_OUT_none(self):
        #: test that no caching is requested when no data is available
        #: server (origin) side
        hin = [('if-modified-since','Sat, 14 Apr 2012 14:39:32 GM'),
              ]
        status, req = _test_cache(hin, ())
        self.assertIsNone(status)
        hin = [('if-none-match','babar/huitre'),
              ]
        status, req = _test_cache(hin, ())
        self.assertIsNone(status)
        hin = [('if-modified-since','Sat, 14 Apr 2012 14:39:32 GM'),
               ('if-none-match','babar/huitre'),
              ]
        status, req = _test_cache(hin, ())
        self.assertIsNone(status)

    def test_IN_none_OUT_Some(self):
        #: test that no caching is requested when no data is provided
        #: by the client
        hout = [('last-modified','Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache((), hout)
        self.assertIsNone(status)
        hout = [('etag','babar/huitre'),
               ]
        status, req = _test_cache((), hout)
        self.assertIsNone(status)
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
                ('etag','babar/huitre'),
               ]
        status, req = _test_cache((), hout)
        self.assertIsNone(status)

    @tag('last_modified')
    def test_last_modified_newer(self):
        #: test the proper behavior of modification date only
        # newer
        hin  = [('if-modified-since', 'Sat, 13 Apr 2012 14:39:32 GM'),
               ]
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'origin is newer than client')

    @tag('last_modified')
    def test_last_modified_older(self):
        # older
        hin  = [('if-modified-since', 'Sat, 15 Apr 2012 14:39:32 GM'),
               ]
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'origin is older than client')

    @tag('last_modified')
    def test_last_modified_same(self):
        # same
        hin  = [('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'origin is equal to client')

    @tag('etag')
    def test_etag_mismatch(self):
        #: test the proper behavior of etag only
        # etag mismatch
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'celestine'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'etag mismatch')

    @tag('etag')
    def test_etag_match(self):
        # etag match
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'etag match')
        # etag match in multiple
        hin  = [('if-none-match', 'loutre'),
                ('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'etag match in multiple')
        # client use "*" as etag
        hin  = [('if-none-match', '*'),
               ]
        hout = [('etag', 'babar'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'client use "*" as etag')

    @tag('etag', 'last_modified')
    def test_both(self):
        #: test the proper behavior of etag only
        # both wrong
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'loutre'),
                ('last-modified', 'Sat, 15 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'both wrong')

    @tag('etag', 'last_modified')
    def test_both_etag_mismatch(self):
        # both etag mismatch
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'loutre'),
                ('last-modified', 'Sat, 13 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'both  but etag mismatch')

    @tag('etag', 'last_modified')
    def test_both_but_modified(self):
        # both but modified
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'babar'),
                ('last-modified', 'Sat, 15 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'both  but modified')

    @tag('etag', 'last_modified')
    def test_both_ok(self):
        # both ok
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'babar'),
                ('last-modified', 'Sat, 13 Apr 2012 14:39:32 GM'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'both ok')

    @tag('etag', 'HEAD')
    def test_head_verb(self):
        #: check than FOUND 200 is properly raise without content on HEAD request
        #: This logic does not really belong here :-/
        # modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'rhino/really-not-babar'),
               ]
        status, req = _test_cache(hin, hout, method='HEAD')
        self.assertCache(200, status, 'modifier HEAD verb')
        # not modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        status, req = _test_cache(hin, hout, method='HEAD')
        self.assertCache(304, status, 'not modifier HEAD verb')

    @tag('etag', 'POST')
    def test_post_verb(self):
        # modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'rhino/really-not-babar'),
               ]
        status, req = _test_cache(hin, hout, method='POST')
        self.assertCache(None, status, 'modifier HEAD verb')
        # not modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        status, req = _test_cache(hin, hout, method='POST')
        self.assertCache(412, status, 'not modifier HEAD verb')

    @tag('expires')
    def test_expires_added(self):
        #: Check that Expires header is added:
        #: - when the page is modified
        #: - when none was already present
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'rhino/really-not-babar'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'modifier HEAD verb')
        value = req.headers_out.getHeader('expires')
        self.assertIsNotNone(value)

    @tag('expires')
    def test_expires_not_added(self):
        #: Check that Expires header is not added if NOT-MODIFIED
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(304, status, 'not modifier HEAD verb')
        value = req.headers_out.getHeader('expires')
        self.assertIsNone(value)

    @tag('expires')
    def test_expires_no_overwrite(self):
        #: Check that cache does not overwrite existing Expires header
        hin  = [('if-none-match', 'babar'),
               ]
        DATE = 'Sat, 13 Apr 2012 14:39:32 GM'
        hout = [('etag', 'rhino/really-not-babar'),
                ('expires', DATE),
               ]
        status, req = _test_cache(hin, hout)
        self.assertCache(None, status, 'not modifier HEAD verb')
        value = req.headers_out.getRawHeaders('expires')
        self.assertEqual(value, [DATE])


if __name__ == '__main__':
    unittest_main()
