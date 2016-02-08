# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from json import loads
from os.path import join
import tempfile
import hashlib

try:
    import requests
    assert [int(n) for n in requests.__version__.split('.', 2)][:2] >= [1, 2]
except (ImportError, AssertionError):
    requests = None

from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools.httptest import CubicWebWsgiTC
from cubicweb.devtools.fake import FakeRequest

class AjaxReplaceUrlTC(TestCase):

    def test_ajax_replace_url_1(self):
        self._test_arurl("fname=view&rql=Person%20P&vid=list",
                         rql='Person P', vid='list')

    def test_ajax_replace_url_2(self):
        self._test_arurl("age=12&fname=view&name=bar&rql=Person%20P&vid=oneline",
                         rql='Person P', vid='oneline', name='bar', age=12)

    def _test_arurl(self, qs, **kwargs):
        req = FakeRequest()
        arurl = req.ajax_replace_url
        # NOTE: for the simplest use cases, we could use doctest
        url = arurl('foo', **kwargs)
        self.assertTrue(url.startswith('javascript:'))
        self.assertTrue(url.endswith('()'))
        cbname = url.split()[1][:-2]
        self.assertMultiLineEqual(
            'function %s() { $("#foo").loadxhtml("http://testing.fr/cubicweb/ajax?%s",'
            '{pageid: "%s"},"get","replace"); }' %
            (cbname, qs, req.pageid),
            req.html_headers.post_inlined_scripts[0])


class FileUploadTC(CubicWebWsgiTC):

    def setUp(self):
        "Skip whole test class if a suitable requests module is not available"
        if requests is None:
            self.skipTest('Python ``requests`` module is not available')
        super(FileUploadTC, self).setUp()

    @property
    def _post_url(self):
        with self.admin_access.web_request() as req:
            return req.build_url('ajax', fname='fileupload')

    def _fobject(self, fname):
        return open(join(self.datadir, fname), 'rb')

    def _fcontent(self, fname):
        with self._fobject(fname) as f:
            return f.read()

    def _fhash(self, fname):
        content = self._fcontent(fname)
        return hashlib.md5(content).hexdigest()

    def test_single_file_upload(self):
        files = {'file': ('schema.py', self._fobject('schema.py'))}
        webreq = requests.post(self._post_url, files=files)
        # check backward compat : a single uploaded file leads to a single
        # 2-uple in the request form
        expect = {'fname': u'fileupload',
                  'file': ['schema.py', self._fhash('schema.py')]}
        self.assertEqual(webreq.status_code, 200)
        self.assertDictEqual(expect, loads(webreq.text))

    def test_multiple_file_upload(self):
        files = [('files', ('schema.py', self._fobject('schema.py'))),
                 ('files', ('views.py',  self._fobject('views.py')))]
        webreq = requests.post(self._post_url, files=files,)
        expect = {'fname': u'fileupload',
                  'files': [['schema.py', self._fhash('schema.py')],
                            ['views.py', self._fhash('views.py')]],}
        self.assertEqual(webreq.status_code, 200)
        self.assertDictEqual(expect, loads(webreq.text))


class LanguageTC(CubicWebWsgiTC):

    def test_language_neg(self):
        headers = {'Accept-Language': 'fr'}
        webreq = self.web_request(headers=headers)
        self.assertIn(b'lang="fr"', webreq.read())
        vary = [h.lower().strip() for h in webreq.getheader('Vary').split(',')]
        self.assertIn('accept-language', vary)
        headers = {'Accept-Language': 'en'}
        webreq = self.web_request(headers=headers)
        self.assertIn(b'lang="en"', webreq.read())
        vary = [h.lower().strip() for h in webreq.getheader('Vary').split(',')]
        self.assertIn('accept-language', vary)

    def test_response_codes(self):
        with self.admin_access.client_cnx() as cnx:
            admin_eid = cnx.user.eid
        # guest can't see admin
        webreq = self.web_request('/%d' % admin_eid)
        self.assertEqual(webreq.status, 403)

        # but admin can
        self.web_login()
        webreq = self.web_request('/%d' % admin_eid)
        self.assertEqual(webreq.status, 200)

    def test_session_cookie_httponly(self):
        webreq = self.web_request()
        self.assertIn('HttpOnly', webreq.getheader('set-cookie'))


class MiscOptionsTC(CubicWebWsgiTC):
    @classmethod
    def setUpClass(cls):
        super(MiscOptionsTC, cls).setUpClass()
        cls.logfile = tempfile.NamedTemporaryFile()

    def setUp(self):
        super(MiscOptionsTC, self).setUp()
        self.config.global_set_option('query-log-file', self.logfile.name)
        self.config.global_set_option('datadir-url', '//static.testing.fr/')
        # call load_configuration again to let the config reset its datadir_url
        self.config.load_configuration()

    def test_log_queries(self):
        self.web_request()
        self.assertTrue(self.logfile.read())

    def test_datadir_url(self):
        webreq = self.web_request()
        self.assertNotIn(b'/data/', webreq.read())

    @classmethod
    def tearDownClass(cls):
        super(MiscOptionsTC, cls).tearDownClass()
        cls.logfile.close()


if __name__ == '__main__':
    unittest_main()
