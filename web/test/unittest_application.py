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
"""unit tests for cubicweb.web.application"""

import base64, Cookie
import sys
import httplib
from urllib import unquote

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.decorators import clear_cache, classproperty

from cubicweb import AuthenticationError, Unauthorized
from cubicweb import view
from cubicweb.devtools.testlib import CubicWebTC, real_error_handling
from cubicweb.devtools.fake import FakeRequest
from cubicweb.web import LogOut, Redirect, INTERNAL_FIELD_VALUE
from cubicweb.web.views.basecontrollers import ViewController
from cubicweb.web.application import anonymized_request

class FakeMapping:
    """emulates a mapping module"""
    def __init__(self):
        self.ENTITIES_MAP = {}
        self.ATTRIBUTES_MAP = {}
        self.RELATIONS_MAP = {}

class MockCursor:
    def __init__(self):
        self.executed = []
    def execute(self, rql, args=None, build_descr=False):
        args = args or {}
        self.executed.append(rql % args)


class FakeController(ViewController):

    def __init__(self, form=None):
        self._cw = FakeRequest()
        self._cw.form = form or {}
        self._cursor = MockCursor()
        self._cw.execute = self._cursor.execute

    def new_cursor(self):
        self._cursor = MockCursor()
        self._cw.execute = self._cursor.execute

    def set_form(self, form):
        self._cw.form = form


class RequestBaseTC(TestCase):
    def setUp(self):
        self._cw = FakeRequest()


    def test_list_arg(self):
        """tests the list_arg() function"""
        list_arg = self._cw.list_form_param
        self.assertEqual(list_arg('arg3', {}), [])
        d = {'arg1' : "value1",
             'arg2' : ('foo', INTERNAL_FIELD_VALUE,),
             'arg3' : ['bar']}
        self.assertEqual(list_arg('arg1', d, True), ['value1'])
        self.assertEqual(d, {'arg2' : ('foo', INTERNAL_FIELD_VALUE), 'arg3' : ['bar'],})
        self.assertEqual(list_arg('arg2', d, True), ['foo'])
        self.assertEqual({'arg3' : ['bar'],}, d)
        self.assertEqual(list_arg('arg3', d), ['bar',])
        self.assertEqual({'arg3' : ['bar'],}, d)


    def test_from_controller(self):
        self._cw.vreg['controllers'] = {'view': 1, 'login': 1}
        self.assertEqual(self._cw.from_controller(), 'view')
        req = FakeRequest(url='project?vid=list')
        req.vreg['controllers'] = {'view': 1, 'login': 1}
        # this assertion is just to make sure that relative_path can be
        # correctly computed as it is used in from_controller()
        self.assertEqual(req.relative_path(False), 'project')
        self.assertEqual(req.from_controller(), 'view')
        # test on a valid non-view controller
        req = FakeRequest(url='login?x=1&y=2')
        req.vreg['controllers'] = {'view': 1, 'login': 1}
        self.assertEqual(req.relative_path(False), 'login')
        self.assertEqual(req.from_controller(), 'login')


class UtilsTC(TestCase):
    """test suite for misc application utilities"""

    def setUp(self):
        self.ctrl = FakeController()

    #def test_which_mapping(self):
    #    """tests which mapping is used (application or core)"""
    #    init_mapping()
    #    from cubicweb.common import mapping
    #    self.assertEqual(mapping.MAPPING_USED, 'core')
    #    sys.modules['mapping'] = FakeMapping()
    #    init_mapping()
    #    self.assertEqual(mapping.MAPPING_USED, 'application')
    #    del sys.modules['mapping']

    def test_execute_linkto(self):
        """tests the execute_linkto() function"""
        self.assertEqual(self.ctrl.execute_linkto(), None)
        self.assertEqual(self.ctrl._cursor.executed,
                          [])

        self.ctrl.set_form({'__linkto' : 'works_for:12_13_14:object',
                              'eid': 8})
        self.ctrl.execute_linkto()
        self.assertEqual(self.ctrl._cursor.executed,
                          ['SET Y works_for X WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl.set_form({'__linkto' : 'works_for:12_13_14:subject',
                              'eid': 8})
        self.ctrl.execute_linkto()
        self.assertEqual(self.ctrl._cursor.executed,
                          ['SET X works_for Y WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])


        self.ctrl.new_cursor()
        self.ctrl._cw.form = {'__linkto' : 'works_for:12_13_14:object'}
        self.ctrl.execute_linkto(eid=8)
        self.assertEqual(self.ctrl._cursor.executed,
                          ['SET Y works_for X WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl.set_form({'__linkto' : 'works_for:12_13_14:subject'})
        self.ctrl.execute_linkto(eid=8)
        self.assertEqual(self.ctrl._cursor.executed,
                          ['SET X works_for Y WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])


class ApplicationTC(CubicWebTC):

    @classproperty
    def config(cls):
        try:
            return cls.__dict__['_config']
        except KeyError:
            config = super(ApplicationTC, cls).config
            config.global_set_option('allow-email-login', True)
            return config

    def test_cnx_user_groups_sync(self):
        user = self.user()
        self.assertEqual(user.groups, set(('managers',)))
        self.execute('SET X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        user = self.user()
        self.assertEqual(user.groups, set(('managers',)))
        self.commit()
        user = self.user()
        self.assertEqual(user.groups, set(('managers', 'guests')))
        # cleanup
        self.execute('DELETE X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        self.commit()

    def test_nonregr_publish1(self):
        req = self.request(u'CWEType X WHERE X final FALSE, X meta FALSE')
        self.app.handle_request(req, 'view')

    def test_nonregr_publish2(self):
        req = self.request(u'Any count(N) WHERE N todo_by U, N is Note, U eid %s'
                           % self.user().eid)
        self.app.handle_request(req, 'view')

    def test_publish_validation_error(self):
        req = self.request()
        user = self.user()
        eid = unicode(user.eid)
        req.form = {
            'eid':       eid,
            '__type:'+eid:    'CWUser', '_cw_entity_fields:'+eid: 'login-subject',
            'login-subject:'+eid:     '', # ERROR: no login specified
             # just a sample, missing some necessary information for real life
            '__errorurl': 'view?vid=edition...'
            }
        path, params = self.expect_redirect_handle_request(req, 'edit')
        forminfo = req.session.data['view?vid=edition...']
        eidmap = forminfo['eidmap']
        self.assertEqual(eidmap, {})
        values = forminfo['values']
        self.assertEqual(values['login-subject:'+eid], '')
        self.assertEqual(values['eid'], eid)
        error = forminfo['error']
        self.assertEqual(error.entity, user.eid)
        self.assertEqual(error.errors['login-subject'], 'required field')


    def test_validation_error_dont_loose_subentity_data_ctrl(self):
        """test creation of two linked entities

        error occurs on the web controller
        """
        req = self.request()
        # set Y before X to ensure both entities are edited, not only X
        req.form = {'eid': ['Y', 'X'], '__maineid': 'X',
                    '__type:X': 'CWUser', '_cw_entity_fields:X': 'login-subject',
                    # missing required field
                    'login-subject:X': u'',
                    # but email address is set
                    '__type:Y': 'EmailAddress', '_cw_entity_fields:Y': 'address-subject',
                    'address-subject:Y': u'bougloup@logilab.fr',
                    'use_email-object:Y': 'X',
                    # necessary to get validation error handling
                    '__errorurl': 'view?vid=edition...',
                    }
        path, params = self.expect_redirect_handle_request(req, 'edit')
        forminfo = req.session.data['view?vid=edition...']
        self.assertEqual(set(forminfo['eidmap']), set('XY'))
        self.assertEqual(forminfo['eidmap']['X'], None)
        self.assertIsInstance(forminfo['eidmap']['Y'], int)
        self.assertEqual(forminfo['error'].entity, 'X')
        self.assertEqual(forminfo['error'].errors,
                          {'login-subject': 'required field'})
        self.assertEqual(forminfo['values'], req.form)


    def test_validation_error_dont_loose_subentity_data_repo(self):
        """test creation of two linked entities

        error occurs on the repository
        """
        req = self.request()
        # set Y before X to ensure both entities are edited, not only X
        req.form = {'eid': ['Y', 'X'], '__maineid': 'X',
                    '__type:X': 'CWUser', '_cw_entity_fields:X': 'login-subject,upassword-subject',
                    # already existent user
                    'login-subject:X': u'admin',
                    'upassword-subject:X': u'admin', 'upassword-subject-confirm:X': u'admin',
                    '__type:Y': 'EmailAddress', '_cw_entity_fields:Y': 'address-subject',
                    'address-subject:Y': u'bougloup@logilab.fr',
                    'use_email-object:Y': 'X',
                    # necessary to get validation error handling
                    '__errorurl': 'view?vid=edition...',
                    }
        path, params = self.expect_redirect_handle_request(req, 'edit')
        forminfo = req.session.data['view?vid=edition...']
        self.assertEqual(set(forminfo['eidmap']), set('XY'))
        self.assertIsInstance(forminfo['eidmap']['X'], int)
        self.assertIsInstance(forminfo['eidmap']['Y'], int)
        self.assertEqual(forminfo['error'].entity, forminfo['eidmap']['X'])
        self.assertEqual(forminfo['error'].errors,
                          {'login-subject': u'the value "admin" is already used, use another one'})
        self.assertEqual(forminfo['values'], req.form)

    def test_ajax_view_raise_arbitrary_error(self):
        class ErrorAjaxView(view.View):
            __regid__ = 'test.ajax.error'
            def call(self):
                raise Exception('whatever')
        with self.temporary_appobjects(ErrorAjaxView):
            with real_error_handling(self.app) as app:
                req = self.request(vid='test.ajax.error')
                req.ajax_request = True
                page = app.handle_request(req, '')
        self.assertEqual(httplib.INTERNAL_SERVER_ERROR,
                         req.status_out)

    def _test_cleaned(self, kwargs, injected, cleaned):
        req = self.request(**kwargs)
        page = self.app.handle_request(req, 'view')
        self.assertFalse(injected in page, (kwargs, injected))
        self.assertTrue(cleaned in page, (kwargs, cleaned))

    def test_nonregr_script_kiddies(self):
        """test against current script injection"""
        injected = '<i>toto</i>'
        cleaned = 'toto'
        for kwargs in ({'__message': injected},
                       {'vid': injected},
                       {'vtitle': injected},
                       ):
            yield self._test_cleaned, kwargs, injected, cleaned

    def test_site_wide_eproperties_sync(self):
        # XXX work in all-in-one configuration but not in twisted for instance
        # in which case we need a kindof repo -> http server notification
        # protocol
        vreg = self.app.vreg
        # default value
        self.assertEqual(vreg.property_value('ui.language'), 'en')
        self.execute('INSERT CWProperty X: X value "fr", X pkey "ui.language"')
        self.assertEqual(vreg.property_value('ui.language'), 'en')
        self.commit()
        self.assertEqual(vreg.property_value('ui.language'), 'fr')
        self.execute('SET X value "de" WHERE X pkey "ui.language"')
        self.assertEqual(vreg.property_value('ui.language'), 'fr')
        self.commit()
        self.assertEqual(vreg.property_value('ui.language'), 'de')
        self.execute('DELETE CWProperty X WHERE X pkey "ui.language"')
        self.assertEqual(vreg.property_value('ui.language'), 'de')
        self.commit()
        self.assertEqual(vreg.property_value('ui.language'), 'en')

    def test_fb_login_concept(self):
        """see data/views.py"""
        self.set_auth_mode('cookie', 'anon')
        self.login('anon')
        req = self.request()
        origcnx = req.cnx
        req.form['__fblogin'] = u'turlututu'
        page = self.app.handle_request(req, '')
        self.assertFalse(req.cnx is origcnx)
        self.assertEqual(req.user.login, 'turlututu')
        self.assertTrue('turlututu' in page, page)
        req.cnx.close() # avoid warning

    # authentication tests ####################################################

    def test_http_auth_no_anon(self):
        req, origsession = self.init_authentication('http')
        self.assertAuthFailure(req)
        self.assertRaises(AuthenticationError, self.app_handle_request, req, 'login')
        self.assertEqual(req.cnx, None)
        authstr = base64.encodestring('%s:%s' % (self.admlogin, self.admpassword))
        req.set_request_header('Authorization', 'basic %s' % authstr)
        self.assertAuthSuccess(req, origsession)
        self.assertRaises(LogOut, self.app_handle_request, req, 'logout')
        self.assertEqual(len(self.open_sessions), 0)

    def test_cookie_auth_no_anon(self):
        req, origsession = self.init_authentication('cookie')
        self.assertAuthFailure(req)
        try:
            form = self.app_handle_request(req, 'login')
        except Redirect as redir:
            self.fail('anonymous user should get login form')
        self.assertTrue('__login' in form)
        self.assertTrue('__password' in form)
        self.assertEqual(req.cnx, None)
        req.form['__login'] = self.admlogin
        req.form['__password'] = self.admpassword
        self.assertAuthSuccess(req, origsession)
        self.assertRaises(LogOut, self.app_handle_request, req, 'logout')
        self.assertEqual(len(self.open_sessions), 0)

    def test_login_by_email(self):
        login = self.request().user.login
        address = login + u'@localhost'
        self.execute('INSERT EmailAddress X: X address %(address)s, U primary_email X '
                     'WHERE U login %(login)s', {'address': address, 'login': login})
        self.commit()
        # # option allow-email-login not set
        req, origsession = self.init_authentication('cookie')
        # req.form['__login'] = address
        # req.form['__password'] = self.admpassword
        # self.assertAuthFailure(req)
        # option allow-email-login set
        origsession.login = address
        self.set_option('allow-email-login', True)
        req.form['__login'] = address
        req.form['__password'] = self.admpassword
        self.assertAuthSuccess(req, origsession)
        self.assertRaises(LogOut, self.app_handle_request, req, 'logout')
        self.assertEqual(len(self.open_sessions), 0)

    def _reset_cookie(self, req):
        # preparing the suite of the test
        # set session id in cookie
        cookie = Cookie.SimpleCookie()
        sessioncookie = self.app.session_handler.session_cookie(req)
        cookie[sessioncookie] = req.session.sessionid
        req.set_request_header('Cookie', cookie[sessioncookie].OutputString(),
                               raw=True)
        clear_cache(req, 'get_authorization')
        # reset session as if it was a new incoming request
        req.session = req.cnx = None

    def _test_auth_anon(self, req):
        self.app.connect(req)
        asession = req.session
        self.assertEqual(len(self.open_sessions), 1)
        self.assertEqual(asession.login, 'anon')
        self.assertTrue(asession.anonymous_session)
        self._reset_cookie(req)

    def _test_anon_auth_fail(self, req):
        self.assertEqual(len(self.open_sessions), 1)
        self.app.connect(req)
        self.assertEqual(req.message, 'authentication failure')
        self.assertEqual(req.session.anonymous_session, True)
        self.assertEqual(len(self.open_sessions), 1)
        self._reset_cookie(req)

    def test_http_auth_anon_allowed(self):
        req, origsession = self.init_authentication('http', 'anon')
        self._test_auth_anon(req)
        authstr = base64.encodestring('toto:pouet')
        req.set_request_header('Authorization', 'basic %s' % authstr)
        self._test_anon_auth_fail(req)
        authstr = base64.encodestring('%s:%s' % (self.admlogin, self.admpassword))
        req.set_request_header('Authorization', 'basic %s' % authstr)
        self.assertAuthSuccess(req, origsession)
        self.assertRaises(LogOut, self.app_handle_request, req, 'logout')
        self.assertEqual(len(self.open_sessions), 0)

    def test_cookie_auth_anon_allowed(self):
        req, origsession = self.init_authentication('cookie', 'anon')
        self._test_auth_anon(req)
        req.form['__login'] = 'toto'
        req.form['__password'] = 'pouet'
        self._test_anon_auth_fail(req)
        req.form['__login'] = self.admlogin
        req.form['__password'] = self.admpassword
        self.assertAuthSuccess(req, origsession)
        self.assertRaises(LogOut, self.app_handle_request, req, 'logout')
        self.assertEqual(len(self.open_sessions), 0)

    def test_anonymized_request(self):
        req = self.request()
        self.assertEqual(req.session.login, self.admlogin)
        # admin should see anon + admin
        self.assertEqual(len(list(req.find_entities('CWUser'))), 2)
        with anonymized_request(req):
            self.assertEqual(req.session.login, 'anon')
            # anon should only see anon user
            self.assertEqual(len(list(req.find_entities('CWUser'))), 1)
        self.assertEqual(req.session.login, self.admlogin)
        self.assertEqual(len(list(req.find_entities('CWUser'))), 2)

    def test_non_regr_optional_first_var(self):
        req = self.request()
        # expect a rset with None in [0][0]
        req.form['rql'] = 'rql:Any OV1, X WHERE X custom_workflow OV1?'
        self.app_handle_request(req)


if __name__ == '__main__':
    unittest_main()
