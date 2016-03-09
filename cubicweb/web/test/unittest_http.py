# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

import contextlib

from logilab.common.testlib import TestCase, unittest_main, tag, Tags

from cubicweb.devtools.fake import FakeRequest
from cubicweb.devtools.testlib import CubicWebTC


def _test_cache(hin, hout, method='GET'):
    """forge and process an HTTP request using given headers in/out and method,
    then return it once its .is_client_cache_valid() method has been called.

    req.status_out is None if the page should have been calculated.
    """
    # forge request
    req = FakeRequest(method=method)
    for key, value in hin:
        req._headers_in.addRawHeader(key, str(value))
    for key, value in hout:
        req.headers_out.addRawHeader(key, str(value))
    # process
    req.status_out = None
    req.is_client_cache_valid()
    return req

class HTTPCache(TestCase):
    """Check that the http cache logic works as expected
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
        req =_test_cache((), ())
        self.assertIsNone(req.status_out)

    def test_IN_Some_OUT_none(self):
        #: test that no caching is requested when no data is available
        #: server (origin) side
        hin = [('if-modified-since','Sat, 14 Apr 2012 14:39:32 GM'),
              ]
        req = _test_cache(hin, ())
        self.assertIsNone(req.status_out)
        hin = [('if-none-match','babar/huitre'),
              ]
        req = _test_cache(hin, ())
        self.assertIsNone(req.status_out)
        hin = [('if-modified-since','Sat, 14 Apr 2012 14:39:32 GM'),
               ('if-none-match','babar/huitre'),
              ]
        req = _test_cache(hin, ())
        self.assertIsNone(req.status_out)

    def test_IN_none_OUT_Some(self):
        #: test that no caching is requested when no data is provided
        #: by the client
        hout = [('last-modified','Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache((), hout)
        self.assertIsNone(req.status_out)
        hout = [('etag','babar/huitre'),
               ]
        req = _test_cache((), hout)
        self.assertIsNone(req.status_out)
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
                ('etag','babar/huitre'),
               ]
        req = _test_cache((), hout)
        self.assertIsNone(req.status_out)

    @tag('last_modified')
    def test_last_modified_newer(self):
        #: test the proper behavior of modification date only
        # newer
        hin  = [('if-modified-since', 'Sat, 13 Apr 2012 14:39:32 GM'),
               ]
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(None, req.status_out, 'origin is newer than client')

    @tag('last_modified')
    def test_last_modified_older(self):
        # older
        hin  = [('if-modified-since', 'Sat, 15 Apr 2012 14:39:32 GM'),
               ]
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(304, req.status_out, 'origin is older than client')

    @tag('last_modified')
    def test_last_modified_same(self):
        # same
        hin  = [('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('last-modified', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(304, req.status_out, 'origin is equal to client')

    @tag('etag')
    def test_etag_mismatch(self):
        #: test the proper behavior of etag only
        # etag mismatch
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'celestine'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(None, req.status_out, 'etag mismatch')

    @tag('etag')
    def test_etag_match(self):
        # etag match
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(304, req.status_out, 'etag match')
        self.assertEqual(req.headers_out.getRawHeaders('etag'), ['babar'])
        # etag match in multiple
        hin  = [('if-none-match', 'loutre'),
                ('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(304, req.status_out, 'etag match in multiple')
        self.assertEqual(req.headers_out.getRawHeaders('etag'), ['babar'])
        # client use "*" as etag
        hin  = [('if-none-match', '*'),
               ]
        hout = [('etag', 'babar'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(304, req.status_out, 'client use "*" as etag')
        self.assertEqual(req.headers_out.getRawHeaders('etag'), ['babar'])

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
        req = _test_cache(hin, hout)
        self.assertCache(None, req.status_out, 'both wrong')

    @tag('etag', 'last_modified')
    def test_both_etag_mismatch(self):
        # both etag mismatch
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'loutre'),
                ('last-modified', 'Sat, 13 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(None, req.status_out, 'both  but etag mismatch')

    @tag('etag', 'last_modified')
    def test_both_but_modified(self):
        # both but modified
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'babar'),
                ('last-modified', 'Sat, 15 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(None, req.status_out, 'both  but modified')

    @tag('etag', 'last_modified')
    def test_both_ok(self):
        # both ok
        hin  = [('if-none-match', 'babar'),
                ('if-modified-since', 'Sat, 14 Apr 2012 14:39:32 GM'),
               ]
        hout = [('etag', 'babar'),
                ('last-modified', 'Sat, 13 Apr 2012 14:39:32 GM'),
               ]
        req = _test_cache(hin, hout)
        self.assertCache(304, req.status_out, 'both ok')
        self.assertEqual(req.headers_out.getRawHeaders('etag'), ['babar'])

    @tag('etag', 'HEAD')
    def test_head_verb(self):
        #: check than FOUND 200 is properly raise without content on HEAD request
        #: This logic does not really belong here :-/
        # modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'rhino/really-not-babar'),
               ]
        req = _test_cache(hin, hout, method='HEAD')
        self.assertCache(None, req.status_out, 'modifier HEAD verb')
        # not modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        req = _test_cache(hin, hout, method='HEAD')
        self.assertCache(304, req.status_out, 'not modifier HEAD verb')
        self.assertEqual(req.headers_out.getRawHeaders('etag'), ['babar'])

    @tag('etag', 'POST')
    def test_post_verb(self):
        # modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'rhino/really-not-babar'),
               ]
        req = _test_cache(hin, hout, method='POST')
        self.assertCache(None, req.status_out, 'modifier HEAD verb')
        # not modified
        hin  = [('if-none-match', 'babar'),
               ]
        hout = [('etag', 'babar'),
               ]
        req = _test_cache(hin, hout, method='POST')
        self.assertCache(412, req.status_out, 'not modifier HEAD verb')


alloworig = 'access-control-allow-origin'
allowmethods = 'access-control-allow-methods'
allowheaders = 'access-control-allow-headers'
allowcreds = 'access-control-allow-credentials'
exposeheaders = 'access-control-expose-headers'
maxage = 'access-control-max-age'

requestmethod = 'access-control-request-method'
requestheaders = 'access-control-request-headers'

class _BaseAccessHeadersTC(CubicWebTC):

    @contextlib.contextmanager
    def options(self, **options):
        for k, values in options.items():
            self.config.set_option(k, values)
        try:
            yield
        finally:
            for k in options:
                self.config.set_option(k, '')
    def check_no_cors(self, req):
        self.assertEqual(None, req.get_response_header(alloworig))
        self.assertEqual(None, req.get_response_header(allowmethods))
        self.assertEqual(None, req.get_response_header(allowheaders))
        self.assertEqual(None, req.get_response_header(allowcreds))
        self.assertEqual(None, req.get_response_header(exposeheaders))
        self.assertEqual(None, req.get_response_header(maxage))


class SimpleAccessHeadersTC(_BaseAccessHeadersTC):

    def test_noaccess(self):
        with self.admin_access.web_request() as req:
            data = self.app_handle_request(req)
            self.check_no_cors(req)

    def test_noorigin(self):
        with self.options(**{alloworig: '*'}):
            with self.admin_access.web_request() as req:
                data = self.app_handle_request(req)
                self.check_no_cors(req)

    def test_origin_noaccess(self):
        with self.admin_access.web_request() as req:
            req.set_request_header('Origin', 'http://www.cubicweb.org')
            data = self.app_handle_request(req)
            self.check_no_cors(req)

    def test_origin_noaccess_bad_host(self):
        with self.options(**{alloworig: '*'}):
            with self.admin_access.web_request() as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'badhost.net')
                data = self.app_handle_request(req)
                self.check_no_cors(req)

    def test_explicit_origin_noaccess(self):
        with self.options(**{alloworig: ['http://www.toto.org', 'http://othersite.fr']}):
            with self.admin_access.web_request() as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'testing.fr')
                data = self.app_handle_request(req)
                self.check_no_cors(req)

    def test_origin_access(self):
        with self.options(**{alloworig: '*'}):
            with self.admin_access.web_request() as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'testing.fr')
                data = self.app_handle_request(req)
                self.assertEqual('http://www.cubicweb.org',
                                 req.get_response_header(alloworig))

    def test_explicit_origin_access(self):
        with self.options(**{alloworig: ['http://www.cubicweb.org', 'http://othersite.fr']}):
            with self.admin_access.web_request() as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'testing.fr')
                data = self.app_handle_request(req)
                self.assertEqual('http://www.cubicweb.org',
                                 req.get_response_header(alloworig))

    def test_origin_access_headers(self):
        with self.options(**{alloworig: '*',
                             exposeheaders: ['ExposeHead1', 'ExposeHead2'],
                             allowheaders: ['AllowHead1', 'AllowHead2'],
                             allowmethods: ['GET', 'POST', 'OPTIONS']}):
            with self.admin_access.web_request() as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'testing.fr')
                data = self.app_handle_request(req)
                self.assertEqual('http://www.cubicweb.org',
                                 req.get_response_header(alloworig))
                self.assertEqual("true",
                                 req.get_response_header(allowcreds))
                self.assertEqual(['ExposeHead1', 'ExposeHead2'],
                                 req.get_response_header(exposeheaders))
                self.assertEqual(None, req.get_response_header(allowmethods))
                self.assertEqual(None, req.get_response_header(allowheaders))


class PreflightAccessHeadersTC(_BaseAccessHeadersTC):

    def test_noaccess(self):
        with self.admin_access.web_request(method='OPTIONS') as req:
            data = self.app_handle_request(req)
            self.check_no_cors(req)

    def test_noorigin(self):
        with self.options(**{alloworig: '*'}):
            with self.admin_access.web_request(method='OPTIONS') as req:
                data = self.app_handle_request(req)
                self.check_no_cors(req)

    def test_origin_noaccess(self):
        with self.admin_access.web_request(method='OPTIONS') as req:
            req.set_request_header('Origin', 'http://www.cubicweb.org')
            data = self.app_handle_request(req)
            self.check_no_cors(req)

    def test_origin_noaccess_bad_host(self):
        with self.options(**{alloworig: '*'}):
            with self.admin_access.web_request(method='OPTIONS') as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'badhost.net')
                data = self.app_handle_request(req)
                self.check_no_cors(req)

    def test_origin_access(self):
        with self.options(**{alloworig: '*',
                             exposeheaders: ['ExposeHead1', 'ExposeHead2'],
                             allowheaders: ['AllowHead1', 'AllowHead2'],
                             allowmethods: ['GET', 'POST', 'OPTIONS']}):
            with self.admin_access.web_request(method='OPTIONS') as req:
                req.set_request_header('Origin', 'http://www.cubicweb.org')
                # in these tests, base_url is http://testing.fr/cubicweb/
                req.set_request_header('Host', 'testing.fr')
                req.set_request_header(requestmethod, 'GET')

                data = self.app_handle_request(req)
                self.assertEqual(200, req.status_out)
                self.assertEqual('http://www.cubicweb.org',
                                 req.get_response_header(alloworig))
                self.assertEqual("true",
                                 req.get_response_header(allowcreds))
                self.assertEqual(set(['GET', 'POST', 'OPTIONS']),
                                 req.get_response_header(allowmethods))
                self.assertEqual(set(['AllowHead1', 'AllowHead2']),
                                 req.get_response_header(allowheaders))
                self.assertEqual(None,
                                 req.get_response_header(exposeheaders))


if __name__ == '__main__':
    unittest_main()
