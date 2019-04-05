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
"""unittests for cw.devtools.testlib module"""

from io import BytesIO, StringIO
from unittest import TextTestRunner

from logilab.common.testlib import TestSuite, TestCase, unittest_main
from logilab.common.registry import yes

from cubicweb.devtools import htmlparser
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.pytestconf import clean_repo_test_cls

class FakeFormTC(TestCase):
    def test_fake_form(self):
        class entity:
            cw_etype = 'Entity'
            eid = 0
        sio = BytesIO(b'hop\n')
        form = CubicWebTC.fake_form('import',
                                    {'file': ('filename.txt', sio),
                                     'encoding': u'utf-8',
                                    }, [(entity, {'field': 'value'})])
        self.assertEqual(form, {'__form_id': 'import',
                                '__maineid': 0,
                                '__type:0': 'Entity',
                                '_cw_entity_fields:0': '__type,field',
                                '_cw_fields': 'encoding,file',
                                'eid': [0],
                                'encoding': u'utf-8',
                                'field:0': 'value',
                                'file': ('filename.txt', sio)})

class WebTestTC(TestCase):

    def setUp(self):
        output = StringIO()
        self.runner = TextTestRunner(stream=output)

    def test_error_raised(self):
        class MyWebTest(CubicWebTC):

            def test_error_view(self):
                with self.admin_access.web_request() as req:
                    req.create_entity('Bug', title=u"bt")
                    self.view('raising', req.execute('Bug B'), template=None, req=req)

            def test_correct_view(self):
                with self.admin_access.web_request() as req:
                    self.view('primary', req.execute('CWUser U'), template=None, req=req)

        tests = [MyWebTest('test_error_view'), MyWebTest('test_correct_view')]
        result = self.runner.run(TestSuite(tests))
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.failures), 1)
        clean_repo_test_cls(MyWebTest)


class RepoInstancesConsistencyTC(CubicWebTC):
    test_db_id = 'RepoInstancesConsistencyTC'

    def pre_setup_database(self, cnx, config):
        self.assertIs(cnx.repo, config.repository())

    def test_pre_setup(self):
        pass


HTML_PAGE = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head><title>need a title</title></head>
  <body>
    <h1>Hello World !</h1>
  </body>
</html>
"""

HTML_PAGE2 = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
 <head><title>need a title</title></head>
 <body>
   <h1>Test</h1>
   <h1>Hello <a href="http://www.google.com">world</a> !</h1>
   <h2>h2 title</h2>
   <h3>h3 title</h3>
   <h2>antoher h2 title</h2>
   <h4>h4 title</h4>
   <p><a href="http://www.logilab.org">Logilab</a> introduces CW !</p>
 </body>
</html>
"""

HTML_PAGE_ERROR = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
 <head><title>need a title</title></head>
 <body>
   Logilab</a> introduces CW !
 </body>
</html>
"""

HTML_NON_STRICT = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head><title>need a title</title></head>
  <body>
    <h1><a href="something.com">title</h1>
  </body>
</html>
"""


class HTMLPageInfoTC(TestCase):
    """test cases for PageInfo"""

    def setUp(self):
        parser = htmlparser.HTMLValidator()
        # disable cleanup that would remove doctype
        parser.preprocess_data = lambda data: data
        self.page_info = parser.parse_string(HTML_PAGE2)

    def test_source1(self):
        """make sure source is stored correctly"""
        self.assertEqual(self.page_info.source, HTML_PAGE2)

    def test_source2(self):
        """make sure source is stored correctly - raise exception"""
        parser = htmlparser.DTDValidator()
        self.assertRaises(AssertionError, parser.parse_string, HTML_PAGE_ERROR)

    def test_has_title_no_level(self):
        """tests h? tags information"""
        self.assertEqual(self.page_info.has_title('Test'), True)
        self.assertEqual(self.page_info.has_title('Test '), False)
        self.assertEqual(self.page_info.has_title('Tes'), False)
        self.assertEqual(self.page_info.has_title('Hello world !'), True)

    def test_has_title_level(self):
        """tests h? tags information"""
        self.assertEqual(self.page_info.has_title('Test', level = 1), True)
        self.assertEqual(self.page_info.has_title('Test', level = 2), False)
        self.assertEqual(self.page_info.has_title('Test', level = 3), False)
        self.assertEqual(self.page_info.has_title('Test', level = 4), False)
        self.assertRaises(IndexError, self.page_info.has_title, 'Test', level = 5)

    def test_has_title_regexp_no_level(self):
        """tests has_title_regexp() with no particular level specified"""
        self.assertEqual(self.page_info.has_title_regexp('h[23] title'), True)

    def test_has_title_regexp_level(self):
        """tests has_title_regexp() with a particular level specified"""
        self.assertEqual(self.page_info.has_title_regexp('h[23] title', 2), True)
        self.assertEqual(self.page_info.has_title_regexp('h[23] title', 3), True)
        self.assertEqual(self.page_info.has_title_regexp('h[23] title', 4), False)

    def test_appears(self):
        """tests PageInfo.appears()"""
        self.assertEqual(self.page_info.appears('CW'), True)
        self.assertEqual(self.page_info.appears('Logilab'), True)
        self.assertEqual(self.page_info.appears('Logilab introduces'), True)
        self.assertEqual(self.page_info.appears('H2 title'), False)

    def test_has_link(self):
        """tests has_link()"""
        self.assertEqual(self.page_info.has_link('Logilab'), True)
        self.assertEqual(self.page_info.has_link('logilab'), False)
        self.assertEqual(self.page_info.has_link('Logilab', 'http://www.logilab.org'), True)
        self.assertEqual(self.page_info.has_link('Logilab', 'http://www.google.com'), False)

    def test_has_link_regexp(self):
        """test has_link_regexp()"""
        self.assertEqual(self.page_info.has_link_regexp('L[oi]gilab'), True)
        self.assertEqual(self.page_info.has_link_regexp('L[ai]gilab'), False)


class CWUtilitiesTC(CubicWebTC):

    def test_temporary_permissions_eschema(self):
        eschema = self.schema['CWUser']
        with self.temporary_permissions(CWUser={'read': ()}):
            self.assertEqual(eschema.permissions['read'], ())
            self.assertTrue(eschema.permissions['add'])
        self.assertTrue(eschema.permissions['read'], ())

    def test_temporary_permissions_rdef(self):
        rdef = self.schema['CWUser'].rdef('in_group')
        with self.temporary_permissions((rdef, {'read': ()})):
            self.assertEqual(rdef.permissions['read'], ())
            self.assertTrue(rdef.permissions['add'])
        self.assertTrue(rdef.permissions['read'], ())

    def test_temporary_permissions_rdef_with_exception(self):
        rdef = self.schema['CWUser'].rdef('in_group')
        try:
            with self.temporary_permissions((rdef, {'read': ()})):
                self.assertEqual(rdef.permissions['read'], ())
                self.assertTrue(rdef.permissions['add'])
                raise ValueError('goto')
        except ValueError:
            self.assertTrue(rdef.permissions['read'], ())
        else:
            self.fail('exception was caught unexpectedly')

    def test_temporary_appobjects_registered(self):

        class AnAppobject(object):
            __registries__ = ('hip',)
            __regid__ = 'hop'
            __select__ = yes()
            registered = None

            @classmethod
            def __registered__(cls, reg):
                cls.registered = reg

        with self.temporary_appobjects(AnAppobject):
            self.assertEqual(self.vreg['hip'], AnAppobject.registered)
            self.assertIn(AnAppobject, self.vreg['hip']['hop'])
        self.assertNotIn(AnAppobject, self.vreg['hip']['hop'])

    def test_login(self):
        """Calling login should not break hook control"""
        with self.admin_access.repo_cnx() as cnx:
            self.hook_executed = False
            self.create_user(cnx, 'babar')
            cnx.commit()

        from cubicweb.server import hook
        from cubicweb.predicates import is_instance

        class MyHook(hook.Hook):
            __regid__ = 'whatever'
            __select__ = hook.Hook.__select__ & is_instance('CWProperty')
            category = 'test-hook'
            events = ('after_add_entity',)
            test = self

            def __call__(self):
                self.test.hook_executed = True

        with self.new_access('babar').repo_cnx() as cnx:
            with self.temporary_appobjects(MyHook):
                with cnx.allow_all_hooks_but('test-hook'):
                    prop = cnx.create_entity('CWProperty', pkey=u'ui.language', value=u'en')
                    cnx.commit()
                    self.assertFalse(self.hook_executed)


class RepoAccessTC(CubicWebTC):

    def test_repo_connection(self):
        acc = self.new_access('admin')
        with acc.repo_cnx() as cnx:
            rset = cnx.execute('Any X WHERE X is CWUser')
            self.assertTrue(rset)

    def test_client_connection(self):
        acc = self.new_access('admin')
        with acc.client_cnx() as cnx:
            rset = cnx.execute('Any X WHERE X is CWUser')
            self.assertTrue(rset)

    def test_web_request(self):
        acc = self.new_access('admin')
        with acc.web_request(elephant='babar') as req:
            rset = req.execute('Any X WHERE X is CWUser')
            self.assertTrue(rset)
            self.assertEqual('babar', req.form['elephant'])

    def test_admin_access(self):
        with self.admin_access.client_cnx() as cnx:
            self.assertEqual('admin', cnx.user.login)


if __name__ == '__main__':
    unittest_main()
