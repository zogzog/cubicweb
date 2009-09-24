# -*- coding: iso-8859-1 -*-
"""unit tests for cubicweb.web.application

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import base64, Cookie
import sys
from urllib import unquote

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.decorators import clear_cache

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.fake import FakeRequest
from cubicweb.web import Redirect, AuthenticationError, ExplicitLogin, INTERNAL_FIELD_VALUE
from cubicweb.web.views.basecontrollers import ViewController

class FakeMapping:
    """emulates a mapping module"""
    def __init__(self):
        self.ENTITIES_MAP = {}
        self.ATTRIBUTES_MAP = {}
        self.RELATIONS_MAP = {}

class MockCursor:
    def __init__(self):
        self.executed = []
    def execute(self, rql, args=None, cachekey=None):
        args = args or {}
        self.executed.append(rql % args)


class FakeController(ViewController):

    def __init__(self, form=None):
        self._cw = FakeRequest()
        self._cw.form = form or {}
        self._cursor = self._cw.cursor = MockCursor()

    def new_cursor(self):
        self._cursor = self._cw.cursor = MockCursor()

    def set_form(self, form):
        self._cw.form = form


class RequestBaseTC(TestCase):
    def setUp(self):
        self._cw = FakeRequest()


    def test_list_arg(self):
        """tests the list_arg() function"""
        list_arg = self._cw.list_form_param
        self.assertEquals(list_arg('arg3', {}), [])
        d = {'arg1' : "value1",
             'arg2' : ('foo', INTERNAL_FIELD_VALUE,),
             'arg3' : ['bar']}
        self.assertEquals(list_arg('arg1', d, True), ['value1'])
        self.assertEquals(d, {'arg2' : ('foo', INTERNAL_FIELD_VALUE), 'arg3' : ['bar'],})
        self.assertEquals(list_arg('arg2', d, True), ['foo'])
        self.assertEquals({'arg3' : ['bar'],}, d)
        self.assertEquals(list_arg('arg3', d), ['bar',])
        self.assertEquals({'arg3' : ['bar'],}, d)


    def test_from_controller(self):
        self._cw.vreg['controllers'] = {'view': 1, 'login': 1}
        self.assertEquals(self._cw.from_controller(), 'view')
        req = FakeRequest(url='project?vid=list')
        req.vreg['controllers'] = {'view': 1, 'login': 1}
        # this assertion is just to make sure that relative_path can be
        # correctly computed as it is used in from_controller()
        self.assertEquals(req.relative_path(False), 'project')
        self.assertEquals(req.from_controller(), 'view')
        # test on a valid non-view controller
        req = FakeRequest(url='login?x=1&y=2')
        req.vreg['controllers'] = {'view': 1, 'login': 1}
        self.assertEquals(req.relative_path(False), 'login')
        self.assertEquals(req.from_controller(), 'login')


class UtilsTC(TestCase):
    """test suite for misc application utilities"""

    def setUp(self):
        self.ctrl = FakeController()

    #def test_which_mapping(self):
    #    """tests which mapping is used (application or core)"""
    #    init_mapping()
    #    from cubicweb.common import mapping
    #    self.assertEquals(mapping.MAPPING_USED, 'core')
    #    sys.modules['mapping'] = FakeMapping()
    #    init_mapping()
    #    self.assertEquals(mapping.MAPPING_USED, 'application')
    #    del sys.modules['mapping']

    def test_execute_linkto(self):
        """tests the execute_linkto() function"""
        self.assertEquals(self.ctrl.execute_linkto(), None)
        self.assertEquals(self.ctrl._cursor.executed,
                          [])

        self.ctrl.set_form({'__linkto' : 'works_for:12_13_14:object',
                              'eid': 8})
        self.ctrl.execute_linkto()
        self.assertEquals(self.ctrl._cursor.executed,
                          ['SET Y works_for X WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl.set_form({'__linkto' : 'works_for:12_13_14:subject',
                              'eid': 8})
        self.ctrl.execute_linkto()
        self.assertEquals(self.ctrl._cursor.executed,
                          ['SET X works_for Y WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])


        self.ctrl.new_cursor()
        self.ctrl._cw.form = {'__linkto' : 'works_for:12_13_14:object'}
        self.ctrl.execute_linkto(eid=8)
        self.assertEquals(self.ctrl._cursor.executed,
                          ['SET Y works_for X WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl.set_form({'__linkto' : 'works_for:12_13_14:subject'})
        self.ctrl.execute_linkto(eid=8)
        self.assertEquals(self.ctrl._cursor.executed,
                          ['SET X works_for Y WHERE X eid 8, Y eid %s' % i
                           for i in (12, 13, 14)])


class ApplicationTC(CubicWebTC):

    def publish(self, req, path='view'):
        return self.app.publish(path, req)

    def expect_redirect(self, callback, req):
        try:
            res = callback(req)
            print res
        except Redirect, ex:
            try:
                path, params = ex.location.split('?', 1)
            except ValueError:
                path = ex.location
                params = {}
            else:
                cleanup = lambda p: (p[0], unquote(p[1]))
                params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
            path = path[len(req.base_url()):]
            return path, params
        else:
            self.fail('expected a Redirect exception')

    def expect_redirect_publish(self, req, path='view'):
        return self.expect_redirect(lambda x: self.publish(x, path), req)

    def test_cnx_user_groups_sync(self):
        user = self.user()
        self.assertEquals(user.groups, set(('managers',)))
        self.execute('SET X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        user = self.user()
        self.assertEquals(user.groups, set(('managers',)))
        self.commit()
        user = self.user()
        self.assertEquals(user.groups, set(('managers', 'guests')))
        # cleanup
        self.execute('DELETE X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        self.commit()

    def test_nonregr_publish1(self):
        req = self.request(u'CWEType X WHERE X final FALSE, X meta FALSE')
        self.app.publish('view', req)

    def test_nonregr_publish2(self):
        req = self.request(u'Any count(N) WHERE N todo_by U, N is Note, U eid %s'
                           % self.user().eid)
        self.app.publish('view', req)

    def test_publish_validation_error(self):
        req = self.request()
        user = self.user()
        req.form = {
            'eid':       `user.eid`,
            '__type:'+`user.eid`:    'CWUser',
            'login:'+`user.eid`:     '', # ERROR: no login specified
            'edits-login:'+`user.eid`: unicode(user.login),
             # just a sample, missing some necessary information for real life
            '__errorurl': 'view?vid=edition...'
            }
        path, params = self.expect_redirect_publish(req, 'edit')
        forminfo = req.get_session_data('view?vid=edition...')
        eidmap = forminfo['eidmap']
        self.assertEquals(eidmap, {})
        values = forminfo['values']
        self.assertEquals(values['login:'+`user.eid`], '')
        self.assertEquals(values['edits-login:'+`user.eid`], user.login)
        self.assertEquals(values['eid'], `user.eid`)
        errors = forminfo['errors']
        self.assertEquals(errors.entity, user.eid)
        self.assertEquals(errors.errors['login'], 'required attribute')


    def test_validation_error_dont_loose_subentity_data(self):
        """test creation of two linked entities
        """
        req = self.request()
        form = {'eid': ['X', 'Y'],
                '__type:X': 'CWUser',
                # missing required field
                'login:X': u'', 'edits-login:X': '',
                'surname:X': u'Mr Ouaoua', 'edits-surname:X': '',
                '__type:Y': 'EmailAddress',
                # but email address is set
                'address:Y': u'bougloup@logilab.fr', 'edits-address:Y': '',
                'alias:Y': u'', 'edits-alias:Y': '',
                'use_email:X': 'Y', 'edits-use_email:X': INTERNAL_FIELD_VALUE,
                # necessary to get validation error handling
                '__errorurl': 'view?vid=edition...',
                }
        req.form = form
        # monkey patch edited_eid to ensure both entities are edited, not only X
        req.edited_eids = lambda : ('Y', 'X')
        path, params = self.expect_redirect_publish(req, 'edit')
        forminfo = req.get_session_data('view?vid=edition...')
        self.assertUnorderedIterableEquals(forminfo['eidmap'].keys(), ['X', 'Y'])
        self.assertEquals(forminfo['errors'].entity, forminfo['eidmap']['X'])
        self.assertEquals(forminfo['errors'].errors, {'login': 'required attribute',
                                                      'upassword': 'required attribute'})
        self.assertEquals(forminfo['values'], form)

    def _test_cleaned(self, kwargs, injected, cleaned):
        req = self.request(**kwargs)
        page = self.app.publish('view', req)
        self.failIf(injected in page, (kwargs, injected))
        self.failUnless(cleaned in page, (kwargs, cleaned))

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
        self.assertEquals(vreg.property_value('ui.language'), 'en')
        self.execute('INSERT CWProperty X: X value "fr", X pkey "ui.language"')
        self.assertEquals(vreg.property_value('ui.language'), 'en')
        self.commit()
        self.assertEquals(vreg.property_value('ui.language'), 'fr')
        self.execute('SET X value "de" WHERE X pkey "ui.language"')
        self.assertEquals(vreg.property_value('ui.language'), 'fr')
        self.commit()
        self.assertEquals(vreg.property_value('ui.language'), 'de')
        self.execute('DELETE CWProperty X WHERE X pkey "ui.language"')
        self.assertEquals(vreg.property_value('ui.language'), 'de')
        self.commit()
        self.assertEquals(vreg.property_value('ui.language'), 'en')

    def test_fb_login_concept(self):
        """see data/views.py"""
        self.set_option('auth-mode', 'cookie')
        self.set_option('anonymous-user', 'anon')
        self.login('anon')
        req = self.request()
        origcnx = req.cnx
        req.form['__fblogin'] = u'turlututu'
        page = self.publish(req)
        self.failIf(req.cnx is origcnx)
        self.assertEquals(req.user.login, 'turlututu')
        self.failUnless('turlututu' in page, page)

    # authentication tests ####################################################

    def _init_auth(self, authmode, anonuser=None):
        self.set_option('auth-mode', authmode)
        self.set_option('anonymous-user', anonuser)
        req = self.request()
        origcnx = req.cnx
        req.cnx = None
        sh = self.app.session_handler
        # not properly cleaned between tests
        self.open_sessions = sh.session_manager._sessions = {}
        return req, origcnx

    def _test_auth_succeed(self, req, origcnx):
        sh = self.app.session_handler
        path, params = self.expect_redirect(lambda x: self.app.connect(x), req)
        cnx = req.cnx
        self.assertEquals(len(self.open_sessions), 1, self.open_sessions)
        self.assertEquals(cnx.login, origcnx.login)
        self.assertEquals(cnx.password, origcnx.password)
        self.assertEquals(cnx.anonymous_connection, False)
        self.assertEquals(path, 'view')
        self.assertEquals(params, {'__message': 'welcome %s !' % cnx.user().login})

    def _test_auth_fail(self, req):
        self.assertRaises(AuthenticationError, self.app.connect, req)
        self.assertEquals(req.cnx, None)
        self.assertEquals(len(self.open_sessions), 0)
        clear_cache(req, 'get_authorization')

    def test_http_auth_no_anon(self):
        req, origcnx = self._init_auth('http')
        self._test_auth_fail(req)
        self.assertRaises(ExplicitLogin, self.publish, req, 'login')
        self.assertEquals(req.cnx, None)
        authstr = base64.encodestring('%s:%s' % (origcnx.login, origcnx.password))
        req._headers['Authorization'] = 'basic %s' % authstr
        self._test_auth_succeed(req, origcnx)
        self.assertRaises(AuthenticationError, self.publish, req, 'logout')
        self.assertEquals(len(self.open_sessions), 0)

    def test_cookie_auth_no_anon(self):
        req, origcnx = self._init_auth('cookie')
        self._test_auth_fail(req)
        form = self.publish(req, 'login')
        self.failUnless('__login' in form)
        self.failUnless('__password' in form)
        self.assertEquals(req.cnx, None)
        req.form['__login'] = origcnx.login
        req.form['__password'] = origcnx.password
        self._test_auth_succeed(req, origcnx)
        self.assertRaises(AuthenticationError, self.publish, req, 'logout')
        self.assertEquals(len(self.open_sessions), 0)

    def test_login_by_email(self):
        login = self.request().user.login
        address = login + u'@localhost'
        self.execute('INSERT EmailAddress X: X address %(address)s, U primary_email X '
                     'WHERE U login %(login)s', {'address': address, 'login': login})
        self.commit()
        # option allow-email-login not set
        req, origcnx = self._init_auth('cookie')
        req.form['__login'] = address
        req.form['__password'] = origcnx.password
        self._test_auth_fail(req)
        # option allow-email-login set
        origcnx.login = address
        self.set_option('allow-email-login', True)
        req.form['__login'] = address
        req.form['__password'] = origcnx.password
        self._test_auth_succeed(req, origcnx)
        self.assertRaises(AuthenticationError, self.publish, req, 'logout')
        self.assertEquals(len(self.open_sessions), 0)

    def _test_auth_anon(self, req):
        self.app.connect(req)
        acnx = req.cnx
        self.assertEquals(len(self.open_sessions), 1)
        self.assertEquals(acnx.login, 'anon')
        self.assertEquals(acnx.password, 'anon')
        self.failUnless(acnx.anonymous_connection)
        self._reset_cookie(req)

    def _reset_cookie(self, req):
        # preparing the suite of the test
        # set session id in cookie
        cookie = Cookie.SimpleCookie()
        cookie['__session'] = req.cnx.sessionid
        req._headers['Cookie'] = cookie['__session'].OutputString()
        clear_cache(req, 'get_authorization')
        # reset cnx as if it was a new incoming request
        req.cnx = None

    def _test_anon_auth_fail(self, req):
        self.assertEquals(len(self.open_sessions), 1)
        self.app.connect(req)
        self.assertEquals(req.message, 'authentication failure')
        self.assertEquals(req.cnx.anonymous_connection, True)
        self.assertEquals(len(self.open_sessions), 1)
        self._reset_cookie(req)

    def test_http_auth_anon_allowed(self):
        req, origcnx = self._init_auth('http', 'anon')
        self._test_auth_anon(req)
        authstr = base64.encodestring('toto:pouet')
        req._headers['Authorization'] = 'basic %s' % authstr
        self._test_anon_auth_fail(req)
        authstr = base64.encodestring('%s:%s' % (origcnx.login, origcnx.password))
        req._headers['Authorization'] = 'basic %s' % authstr
        self._test_auth_succeed(req, origcnx)
        self.assertRaises(AuthenticationError, self.publish, req, 'logout')
        self.assertEquals(len(self.open_sessions), 0)

    def test_cookie_auth_anon_allowed(self):
        req, origcnx = self._init_auth('cookie', 'anon')
        self._test_auth_anon(req)
        req.form['__login'] = 'toto'
        req.form['__password'] = 'pouet'
        self._test_anon_auth_fail(req)
        req.form['__login'] = origcnx.login
        req.form['__password'] = origcnx.password
        self._test_auth_succeed(req, origcnx)
        self.assertRaises(AuthenticationError, self.publish, req, 'logout')
        self.assertEquals(len(self.open_sessions), 0)


if __name__ == '__main__':
    unittest_main()
