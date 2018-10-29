# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import base64

from six import text_type
from six.moves import http_client
from six.moves.http_cookies import SimpleCookie

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.decorators import clear_cache

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
        d = {'arg1': "value1",
             'arg2': ('foo', INTERNAL_FIELD_VALUE,),
             'arg3': ['bar']}
        self.assertEqual(list_arg('arg1', d, True), ['value1'])
        self.assertEqual(d, {'arg2': ('foo', INTERNAL_FIELD_VALUE), 'arg3': ['bar']})
        self.assertEqual(list_arg('arg2', d, True), ['foo'])
        self.assertEqual({'arg3': ['bar']}, d)
        self.assertEqual(list_arg('arg3', d), ['bar'])
        self.assertEqual({'arg3': ['bar']}, d)

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

    def test_execute_linkto(self):
        """tests the execute_linkto() function"""
        self.assertEqual(self.ctrl.execute_linkto(), None)
        self.assertEqual(self.ctrl._cursor.executed,
                         [])

        self.ctrl.set_form({'__linkto': 'works_for:12_13_14:object',
                            'eid': 8})
        self.ctrl.execute_linkto()
        self.assertEqual(self.ctrl._cursor.executed,
                         ['SET Y works_for X WHERE X eid 8, Y eid %s' % i
                          for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl.set_form({'__linkto': 'works_for:12_13_14:subject',
                            'eid': 8})
        self.ctrl.execute_linkto()
        self.assertEqual(self.ctrl._cursor.executed,
                         ['SET X works_for Y WHERE X eid 8, Y eid %s' % i
                          for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl._cw.form = {'__linkto': 'works_for:12_13_14:object'}
        self.ctrl.execute_linkto(eid=8)
        self.assertEqual(self.ctrl._cursor.executed,
                         ['SET Y works_for X WHERE X eid 8, Y eid %s' % i
                          for i in (12, 13, 14)])

        self.ctrl.new_cursor()
        self.ctrl.set_form({'__linkto': 'works_for:12_13_14:subject'})
        self.ctrl.execute_linkto(eid=8)
        self.assertEqual(self.ctrl._cursor.executed,
                         ['SET X works_for Y WHERE X eid 8, Y eid %s' % i
                          for i in (12, 13, 14)])


class ApplicationTC(CubicWebTC):

    @classmethod
    def setUpClass(cls):
        super(ApplicationTC, cls).setUpClass()
        cls.config.global_set_option('allow-email-login', True)

    def test_cnx_user_groups_sync(self):
        with self.admin_access.client_cnx() as cnx:
            user = cnx.user
            self.assertEqual(user.groups, set(('managers',)))
            cnx.execute('SET X in_group G WHERE X eid %s, G name "guests"' % user.eid)
            user = cnx.user
            self.assertEqual(user.groups, set(('managers',)))
            cnx.commit()
            user = cnx.user
            self.assertEqual(user.groups, set(('managers', 'guests')))
            # cleanup
            cnx.execute('DELETE X in_group G WHERE X eid %s, G name "guests"' % user.eid)
            cnx.commit()

    def test_publish_validation_error(self):
        with self.admin_access.web_request() as req:
            user = req.user
            eid = text_type(user.eid)
            req.form = {
                'eid': eid,
                '__type:' + eid: 'CWUser',
                '_cw_entity_fields:' + eid: 'login-subject',
                'login-subject:' + eid: '',  # ERROR: no login specified
                # just a sample, missing some necessary information for real life
                '__errorurl': 'view?vid=edition...'
            }
            path, params = self.expect_redirect_handle_request(req, 'edit')
            forminfo = req.session.data['view?vid=edition...']
            eidmap = forminfo['eidmap']
            self.assertEqual(eidmap, {})
            values = forminfo['values']
            self.assertEqual(values['login-subject:' + eid], '')
            self.assertEqual(values['eid'], eid)
            error = forminfo['error']
            self.assertEqual(error.entity, user.eid)
            self.assertEqual(error.errors['login-subject'], 'required field')

    def test_validation_error_dont_loose_subentity_data_ctrl(self):
        """test creation of two linked entities

        error occurs on the web controller
        """
        with self.admin_access.web_request() as req:
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

    def test_handle_request_with_lang_fromurl(self):
        """No language negociation, get language from URL."""
        self.config.global_set_option('language-mode', 'url-prefix')
        req = self.init_authentication('http')
        self.assertEqual(req.url(), 'http://testing.fr/cubicweb/login')
        self.assertEqual(req.lang, 'en')
        self.app.handle_request(req)
        newreq = self.requestcls(req.vreg, url='fr/toto')
        self.assertEqual(newreq.lang, 'en')
        self.assertEqual(newreq.url(), 'http://testing.fr/cubicweb/fr/toto')
        self.app.handle_request(newreq)
        self.assertEqual(newreq.lang, 'fr')
        self.assertEqual(newreq.url(), 'http://testing.fr/cubicweb/fr/toto')
        # unknown language
        newreq = self.requestcls(req.vreg, url='unknown-lang/cwuser')
        result = self.app.handle_request(newreq)
        self.assertEqual(newreq.lang, 'en')
        self.assertEqual(newreq.url(), 'http://testing.fr/cubicweb/unknown-lang/cwuser')
        self.assertIn('this resource does not exist',
                      result.decode('ascii', errors='ignore'))
        # no prefix
        newreq = self.requestcls(req.vreg, url='cwuser')
        result = self.app.handle_request(newreq)
        self.assertEqual(newreq.lang, 'en')
        self.assertEqual(newreq.url(), 'http://testing.fr/cubicweb/cwuser')
        self.assertNotIn('this resource does not exist',
                         result.decode('ascii', errors='ignore'))

    def test_handle_request_with_lang_negotiated(self):
        """Language negociated, normal case."""
        self.config.global_set_option('language-mode', 'http-negotiation')
        orig_translations = self.config.translations.copy()
        self.config.translations = {
            'fr': (text_type, lambda x, y: text_type(y)),
            'en': (text_type, lambda x, y: text_type(y))}
        try:
            headers = {'Accept-Language': 'fr'}
            with self.admin_access.web_request(headers=headers) as req:
                self.app.handle_request(req)
            self.assertEqual(req.lang, 'fr')
        finally:
            self.config.translations = orig_translations

    def test_handle_request_with_lang_negotiated_prefix_in_url(self):
        """Language negociated, unexpected language prefix in URL."""
        self.config.global_set_option('language-mode', 'http-negotiation')
        with self.admin_access.web_request(url='fr/toto') as req:
            result = self.app.handle_request(req)
        self.assertIn('this resource does not exist',  # NotFound.
                      result.decode('ascii', errors='ignore'))

    def test_handle_request_no_lang_negotiation_fixed_language(self):
        """No language negociation, "ui.language" fixed."""
        self.config.global_set_option('language-mode', '')
        vreg = self.app.vreg
        self.assertEqual(vreg.property_value('ui.language'), 'en')
        props = []
        try:
            with self.admin_access.cnx() as cnx:
                props.append(cnx.create_entity('CWProperty', value=u'de',
                                               pkey=u'ui.language').eid)
                cnx.commit()
            self.assertEqual(vreg.property_value('ui.language'), 'de')
            headers = {'Accept-Language': 'fr'}  # should not have any effect.
            with self.admin_access.web_request(headers=headers) as req:
                self.app.handle_request(req)
            # user has no "ui.language" property, getting site's default.
            self.assertEqual(req.lang, 'de')
            # XXX The following should work, but nasty handling of session and
            # request user make it fail...
            # with self.admin_access.cnx() as cnx:
            #     props.append(cnx.create_entity('CWProperty', value=u'es',
            #                                    pkey=u'ui.language',
            #                                    for_user=cnx.user).eid)
            #     cnx.commit()
            # with self.admin_access.web_request(headers=headers) as req:
            #     result = self.app.handle_request(req)
            # self.assertEqual(req.lang, 'es')
        finally:
            with self.admin_access.cnx() as cnx:
                for peid in props:
                    cnx.entity_from_eid(peid).cw_delete()
                cnx.commit()

    def test_validation_error_dont_loose_subentity_data_repo(self):
        """test creation of two linked entities

        error occurs on the repository
        """
        with self.admin_access.web_request() as req:
            # set Y before X to ensure both entities are edited, not only X
            req.form = {
                'eid': ['Y', 'X'], '__maineid': 'X',
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
            expected_errors = {
                '': u'some relations violate a unicity constraint',
                'login': u'login is part of violated unicity constraint',
            }
            self.assertEqual(forminfo['error'].errors, expected_errors)
            self.assertEqual(forminfo['values'], req.form)

    def _edit_parent(self, dir_eid, parent_eid, role='subject',
                     etype='Directory', **kwargs):
        parent_eid = parent_eid or '__cubicweb_internal_field__'
        with self.admin_access.web_request() as req:
            req.form = {
                'eid': text_type(dir_eid),
                '__maineid': text_type(dir_eid),
                '__type:%s' % dir_eid: etype,
                'parent-%s:%s' % (role, dir_eid): parent_eid,
            }
            req.form.update(kwargs)
            req.form['_cw_entity_fields:%s' % dir_eid] = ','.join(
                ['parent-%s' % role]
                + [key.split(':')[0]
                   for key in kwargs.keys()
                   if not key.startswith('_')])
            self.expect_redirect_handle_request(req)

    def _edit_in_version(self, ticket_eid, version_eid, **kwargs):
        version_eid = version_eid or '__cubicweb_internal_field__'
        with self.admin_access.web_request() as req:
            req.form = {
                'eid': text_type(ticket_eid),
                '__maineid': text_type(ticket_eid),
                '__type:%s' % ticket_eid: 'Ticket',
                'in_version-subject:%s' % ticket_eid: version_eid,
            }
            req.form.update(kwargs)
            req.form['_cw_entity_fields:%s' % ticket_eid] = ','.join(
                ['in_version-subject']
                + [key.split(':')[0]
                   for key in kwargs.keys()
                   if not key.startswith('_')])
            self.expect_redirect_handle_request(req)

    def test_create_and_link_directories(self):
        with self.admin_access.web_request() as req:
            req.form = {
                'eid': (u'A', u'B'),
                '__maineid': u'A',
                '__type:A': 'Directory',
                '__type:B': 'Directory',
                'parent-subject:B': u'A',
                'name-subject:A': u'topd',
                'name-subject:B': u'subd',
                '_cw_entity_fields:A': 'name-subject',
                '_cw_entity_fields:B': 'parent-subject,name-subject',
            }
            self.expect_redirect_handle_request(req)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', name=u'topd'))
            self.assertTrue(cnx.find('Directory', name=u'subd'))
            self.assertEqual(1, cnx.execute(
                'Directory SUBD WHERE SUBD parent TOPD,'
                ' SUBD name "subd", TOPD name "topd"').rowcount)

    def test_create_subentity(self):
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            cnx.commit()

        with self.admin_access.web_request() as req:
            req.form = {
                'eid': (text_type(topd.eid), u'B'),
                '__maineid': text_type(topd.eid),
                '__type:%s' % topd.eid: 'Directory',
                '__type:B': 'Directory',
                'parent-object:%s' % topd.eid: u'B',
                'name-subject:B': u'subd',
                '_cw_entity_fields:%s' % topd.eid: 'parent-object',
                '_cw_entity_fields:B': 'name-subject',
            }
            self.expect_redirect_handle_request(req)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', name=u'topd'))
            self.assertTrue(cnx.find('Directory', name=u'subd'))
            self.assertEqual(1, cnx.execute(
                'Directory SUBD WHERE SUBD parent TOPD,'
                ' SUBD name "subd", TOPD name "topd"').rowcount)

    def test_subject_subentity_removal(self):
        """Editcontroller: detaching a composite relation removes the subentity
        (edit from the subject side)
        """
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            sub1 = cnx.create_entity('Directory', name=u'sub1', parent=topd)
            sub2 = cnx.create_entity('Directory', name=u'sub2', parent=topd)
            cnx.commit()

        attrs = {'name-subject:%s' % sub1.eid: ''}
        self._edit_parent(sub1.eid, parent_eid=None, **attrs)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=topd.eid))
            self.assertFalse(cnx.find('Directory', eid=sub1.eid))
            self.assertTrue(cnx.find('Directory', eid=sub2.eid))

    def test_object_subentity_removal(self):
        """Editcontroller: detaching a composite relation removes the subentity
        (edit from the object side)
        """
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            sub1 = cnx.create_entity('Directory', name=u'sub1', parent=topd)
            sub2 = cnx.create_entity('Directory', name=u'sub2', parent=topd)
            cnx.commit()

        self._edit_parent(topd.eid, parent_eid=sub1.eid, role='object')

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=topd.eid))
            self.assertTrue(cnx.find('Directory', eid=sub1.eid))
            self.assertFalse(cnx.find('Directory', eid=sub2.eid))

    def test_reparent_subentity(self):
        "Editcontroller: re-parenting a subentity does not remove it"
        with self.admin_access.repo_cnx() as cnx:
            top1 = cnx.create_entity('Directory', name=u'top1')
            top2 = cnx.create_entity('Directory', name=u'top2')
            subd = cnx.create_entity('Directory', name=u'subd', parent=top1)
            cnx.commit()

        self._edit_parent(subd.eid, parent_eid=top2.eid)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=top1.eid))
            self.assertTrue(cnx.find('Directory', eid=top2.eid))
            self.assertTrue(cnx.find('Directory', eid=subd.eid))
            self.assertEqual(
                cnx.find('Directory', eid=subd.eid).one().parent[0], top2)

    def test_reparent_subentity_inlined(self):
        """Editcontroller: re-parenting a subentity does not remove it
        (inlined case)"""
        with self.admin_access.repo_cnx() as cnx:
            version1 = cnx.create_entity('Version', name=u'version1')
            version2 = cnx.create_entity('Version', name=u'version2')
            ticket = cnx.create_entity('Ticket', title=u'ticket',
                                       in_version=version1)
            cnx.commit()

        self._edit_in_version(ticket.eid, version_eid=version2.eid)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Version', eid=version1.eid))
            self.assertTrue(cnx.find('Version', eid=version2.eid))
            self.assertTrue(cnx.find('Ticket', eid=ticket.eid))
            self.assertEqual(
                cnx.find('Ticket', eid=ticket.eid).one().in_version[0], version2)

    def test_subject_mixed_composite_subentity_removal_1(self):
        """Editcontroller: detaching several subentities respects each rdef's
        compositeness - Remove non composite
        """
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            fs = cnx.create_entity('Filesystem', name=u'/tmp')
            subd = cnx.create_entity('Directory', name=u'subd',
                                     parent=(topd, fs))
            cnx.commit()

        self._edit_parent(subd.eid, parent_eid=topd.eid)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=topd.eid))
            self.assertTrue(cnx.find('Directory', eid=subd.eid))
            self.assertTrue(cnx.find('Filesystem', eid=fs.eid))
            self.assertEqual(cnx.find('Directory', eid=subd.eid).one().parent,
                             (topd,))

    def test_subject_mixed_composite_subentity_removal_2(self):
        """Editcontroller: detaching several subentities respects each rdef's
        compositeness - Remove composite
        """
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            fs = cnx.create_entity('Filesystem', name=u'/tmp')
            subd = cnx.create_entity('Directory', name=u'subd',
                                     parent=(topd, fs))
            cnx.commit()

        self._edit_parent(subd.eid, parent_eid=fs.eid)

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=topd.eid))
            self.assertFalse(cnx.find('Directory', eid=subd.eid))
            self.assertTrue(cnx.find('Filesystem', eid=fs.eid))

    def test_object_mixed_composite_subentity_removal_1(self):
        """Editcontroller: detaching several subentities respects each rdef's
        compositeness - Remove non composite
        """
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            fs = cnx.create_entity('Filesystem', name=u'/tmp')
            subd = cnx.create_entity('Directory', name=u'subd',
                                     parent=(topd, fs))
            cnx.commit()

        self._edit_parent(fs.eid, parent_eid=None, role='object',
                          etype='Filesystem')

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=topd.eid))
            self.assertTrue(cnx.find('Directory', eid=subd.eid))
            self.assertTrue(cnx.find('Filesystem', eid=fs.eid))
            self.assertEqual(cnx.find('Directory', eid=subd.eid).one().parent,
                             (topd,))

    def test_object_mixed_composite_subentity_removal_2(self):
        """Editcontroller: detaching several subentities respects each rdef's
        compositeness - Remove composite
        """
        with self.admin_access.repo_cnx() as cnx:
            topd = cnx.create_entity('Directory', name=u'topd')
            fs = cnx.create_entity('Filesystem', name=u'/tmp')
            subd = cnx.create_entity('Directory', name=u'subd',
                                     parent=(topd, fs))
            cnx.commit()

        self._edit_parent(topd.eid, parent_eid=None, role='object')

        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(cnx.find('Directory', eid=topd.eid))
            self.assertFalse(cnx.find('Directory', eid=subd.eid))
            self.assertTrue(cnx.find('Filesystem', eid=fs.eid))

    def test_delete_mandatory_composite(self):
        with self.admin_access.repo_cnx() as cnx:
            perm = cnx.create_entity('DirectoryPermission')
            mydir = cnx.create_entity('Directory', name=u'dir',
                                      has_permission=perm)
            cnx.commit()

        with self.admin_access.web_request() as req:
            dir_eid = text_type(mydir.eid)
            perm_eid = text_type(perm.eid)
            req.form = {
                'eid': [dir_eid, perm_eid],
                '__maineid': dir_eid,
                '__type:%s' % dir_eid: 'Directory',
                '__type:%s' % perm_eid: 'DirectoryPermission',
                '_cw_entity_fields:%s' % dir_eid: '',
                '_cw_entity_fields:%s' % perm_eid: 'has_permission-object',
                'has_permission-object:%s' % perm_eid: '',
            }
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            self.assertTrue(req.find('Directory', eid=mydir.eid))
            self.assertFalse(req.find('DirectoryPermission', eid=perm.eid))

    def test_ajax_view_raise_arbitrary_error(self):
        class ErrorAjaxView(view.View):
            __regid__ = 'test.ajax.error'

            def call(self):
                raise Exception('whatever')

        with self.temporary_appobjects(ErrorAjaxView):
            with real_error_handling(self.app) as app:
                with self.admin_access.web_request(vid='test.ajax.error', url='') as req:
                    req.ajax_request = True
                    app.handle_request(req)
        self.assertEqual(http_client.INTERNAL_SERVER_ERROR,
                         req.status_out)

    def _test_cleaned(self, kwargs, injected, cleaned):
        with self.admin_access.web_request(**kwargs) as req:
            page = self.app_handle_request(req)
            self.assertNotIn(injected.encode('ascii'), page)
            self.assertIn(cleaned.encode('ascii'), page)

    def test_nonregr_script_kiddies(self):
        """test against current script injection"""
        injected = '<i>toto</i>'
        cleaned = 'toto'
        for kwargs in ({'vid': injected}, {'vtitle': injected}):
            with self.subTest(**kwargs):
                self._test_cleaned(kwargs, injected, cleaned)

    def test_site_wide_eproperties_sync(self):
        # XXX work in all-in-one configuration but not in twisted for instance
        # in which case we need a kindof repo -> http server notification
        # protocol
        vreg = self.app.vreg
        # default value
        self.assertEqual(vreg.property_value('ui.language'), 'en')
        with self.admin_access.client_cnx() as cnx:
            cnx.execute('INSERT CWProperty X: X value "fr", X pkey "ui.language"')
            self.assertEqual(vreg.property_value('ui.language'), 'en')
            cnx.commit()
            self.assertEqual(vreg.property_value('ui.language'), 'fr')
            cnx.execute('SET X value "de" WHERE X pkey "ui.language"')
            self.assertEqual(vreg.property_value('ui.language'), 'fr')
            cnx.commit()
            self.assertEqual(vreg.property_value('ui.language'), 'de')
            cnx.execute('DELETE CWProperty X WHERE X pkey "ui.language"')
            self.assertEqual(vreg.property_value('ui.language'), 'de')
            cnx.commit()
            self.assertEqual(vreg.property_value('ui.language'), 'en')

    # authentication tests ####################################################

    def test_http_auth_no_anon(self):
        req = self.init_authentication('http')
        self.assertAuthFailure(req)
        self.app.handle_request(req)
        self.assertEqual(401, req.status_out)
        clear_cache(req, 'get_authorization')
        authstr = base64.encodestring(('%s:%s' % (self.admlogin, self.admpassword)).encode('ascii'))
        req.set_request_header('Authorization', 'basic %s' % authstr.decode('ascii'))
        self.assertAuthSuccess(req)
        req._url = 'logout'
        self.assertRaises(LogOut, self.app_handle_request, req)
        self.assertEqual(len(self.open_sessions), 0)

    def test_cookie_auth_no_anon(self):
        req = self.init_authentication('cookie')
        self.assertAuthFailure(req)
        try:
            form = self.app.handle_request(req)
        except Redirect:
            self.fail('anonymous user should get login form')
        clear_cache(req, 'get_authorization')
        self.assertIn(b'__login', form)
        self.assertIn(b'__password', form)
        self.assertFalse(req.cnx)  # Mock cnx are False
        req.form['__login'] = self.admlogin
        req.form['__password'] = self.admpassword
        self.assertAuthSuccess(req)
        req._url = 'logout'
        self.assertRaises(LogOut, self.app_handle_request, req)
        self.assertEqual(len(self.open_sessions), 0)

    def test_login_by_email(self):
        with self.admin_access.client_cnx() as cnx:
            login = cnx.user.login
            address = login + u'@localhost'
            cnx.execute('INSERT EmailAddress X: X address %(address)s, U primary_email X '
                        'WHERE U login %(login)s', {'address': address, 'login': login})
            cnx.commit()
        req = self.init_authentication('cookie')
        self.set_option('allow-email-login', True)
        req.form['__login'] = address
        req.form['__password'] = self.admpassword
        self.assertAuthSuccess(req)
        req._url = 'logout'
        self.assertRaises(LogOut, self.app_handle_request, req)
        self.assertEqual(len(self.open_sessions), 0)

    def _reset_cookie(self, req):
        # preparing the suite of the test
        # set session id in cookie
        cookie = SimpleCookie()
        sessioncookie = self.app.session_handler.session_cookie(req)
        cookie[sessioncookie] = req.session.sessionid
        req.set_request_header('Cookie', cookie[sessioncookie].OutputString(),
                               raw=True)
        clear_cache(req, 'get_authorization')

    def _test_auth_anon(self, req):
        asession = self.app.get_session(req)
        # important otherwise _reset_cookie will not use the right session
        cnx = asession.new_cnx()
        with cnx:
            req.set_cnx(cnx)
        self.assertEqual(len(self.open_sessions), 1)
        self.assertEqual(asession.user.login, 'anon')
        self.assertTrue(asession.anonymous_session)
        self._reset_cookie(req)

    def _test_anon_auth_fail(self, req):
        self.assertEqual(1, len(self.open_sessions))
        session = self.app.get_session(req)
        cnx = session.new_cnx()
        with cnx:
            # important otherwise _reset_cookie will not use the right session
            req.set_cnx(cnx)
        self.assertEqual(req.message, 'authentication failure')
        self.assertEqual(req.session.anonymous_session, True)
        self.assertEqual(1, len(self.open_sessions))
        self._reset_cookie(req)

    def test_http_auth_anon_allowed(self):
        req = self.init_authentication('http', 'anon')
        self._test_auth_anon(req)
        authstr = base64.encodestring(b'toto:pouet')
        req.set_request_header('Authorization', 'basic %s' % authstr.decode('ascii'))
        self._test_anon_auth_fail(req)
        authstr = base64.encodestring(('%s:%s' % (self.admlogin, self.admpassword)).encode('ascii'))
        req.set_request_header('Authorization', 'basic %s' % authstr.decode('ascii'))
        self.assertAuthSuccess(req)
        req._url = 'logout'
        self.assertRaises(LogOut, self.app_handle_request, req)
        self.assertEqual(len(self.open_sessions), 0)

    def test_cookie_auth_anon_allowed(self):
        req = self.init_authentication('cookie', 'anon')
        self._test_auth_anon(req)
        req.form['__login'] = 'toto'
        req.form['__password'] = 'pouet'
        self._test_anon_auth_fail(req)
        req.form['__login'] = self.admlogin
        req.form['__password'] = self.admpassword
        self.assertAuthSuccess(req)
        req._url = 'logout'
        self.assertRaises(LogOut, self.app_handle_request, req)
        self.assertEqual(0, len(self.open_sessions))

    def test_anonymized_request(self):
        with self.admin_access.web_request() as req:
            self.assertEqual(self.admlogin, req.session.user.login)
            # admin should see anon + admin
            self.assertEqual(2, len(list(req.find('CWUser'))))
            with anonymized_request(req):
                self.assertEqual('anon', req.session.user.login)
                # anon should only see anon user
                self.assertEqual(1, len(list(req.find('CWUser'))))
            self.assertEqual(self.admlogin, req.session.user.login)
            self.assertEqual(2, len(list(req.find('CWUser'))))

    def test_non_regr_optional_first_var(self):
        with self.admin_access.web_request() as req:
            # expect a rset with None in [0][0]
            req.form['rql'] = 'rql:Any OV1, X WHERE X custom_workflow OV1?'
            self.app_handle_request(req)

    def test_handle_deprecation(self):
        """Test deprecation warning for *_handle methods."""
        with self.admin_access.web_request(url='foo') as req:
            with self.assertWarns(DeprecationWarning) as cm:
                self.app.core_handle(req, 'foo')
            self.assertIn('path argument got removed from "core_handle"',
                          str(cm.warning))
            with self.assertWarns(DeprecationWarning) as cm:
                self.app.main_handle_request('foo', req)
            self.assertIn('entry point arguments are now (req, path)',
                          str(cm.warning))


if __name__ == '__main__':
    unittest_main()
