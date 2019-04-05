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
"""cubicweb.web.views.basecontrollers unit tests"""

import time
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qs

import lxml

from logilab.common.testlib import unittest_main

from cubicweb import Binary, NoSelectableObject, ValidationError, transaction as tx
from cubicweb.schema import RRQLExpression
from cubicweb.predicates import is_instance
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.webtest import CubicWebTestTC
from cubicweb.devtools.httptest import CubicWebServerTC
from cubicweb.utils import json_dumps
from cubicweb.uilib import rql_for_eid
from cubicweb.web import Redirect, RemoteCallFailed, http_headers, formfields as ff
from cubicweb.web.views.autoform import get_pending_inserts, get_pending_deletes
from cubicweb.web.views.ajaxcontroller import ajaxfunc, AjaxFunction
from cubicweb.server.session import Connection
from cubicweb.server.hook import Hook, Operation


class ViewControllerTC(CubicWebTestTC):
    def test_view_ctrl_with_valid_cache_headers(self):
        now = time.time()
        resp = self.webapp.get('/manage')
        self.assertEqual(resp.etag, 'manage/guests')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(http_headers.parseDateTime(resp.headers['Last-Modified']), int(now))
        cache_headers = {'if-modified-since': resp.headers['Last-Modified'],
                         'if-none-match': resp.etag}
        resp = self.webapp.get('/manage', headers=cache_headers)
        self.assertEqual(resp.status_code, 304)
        self.assertEqual(len(resp.body), 0)


def req_form(user):
    return {'eid': [str(user.eid)],
            '_cw_entity_fields:%s' % user.eid: '_cw_generic_field',
            '__type:%s' % user.eid: user.__regid__
            }


class EditControllerTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        self.assertIn('users', self.schema.eschema('CWGroup').get_groups('read'))

    def tearDown(self):
        CubicWebTC.tearDown(self)
        self.assertIn('users', self.schema.eschema('CWGroup').get_groups('read'))

    def test_noparam_edit(self):
        """check behaviour of this controller without any form parameter
        """
        with self.admin_access.web_request() as req:
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            self.assertEqual(cm.exception.errors, {None: u'no selected entities'})

    def test_validation_unique(self):
        """test creation of two linked entities
        """
        with self.admin_access.web_request() as req:
            req.form = {'eid': 'X', '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject',
                        'login-subject:X': u'admin',
                        'upassword-subject:X': u'toto',
                        'upassword-subject-confirm:X': u'toto',
                    }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            cm.exception.translate(str)
            expected = {
                '': u'some relations violate a unicity constraint',
                'login': u'login is part of violated unicity constraint',
            }
            self.assertEqual(cm.exception.errors, expected)

    def test_simultaneous_edition_only_one_commit(self):
        """ Allow two simultaneous edit view of the same entity as long as only one commits
        """
        with self.admin_access.web_request() as req:
            e = req.create_entity('BlogEntry', title=u'cubicweb.org', content=u"hop")
            expected_path = e.rest_path()
            req.cnx.commit()
            form = self.vreg['views'].select('edition', req, rset=e.as_rset(), row=0)
            html_form = lxml.html.fromstring(form.render(w=None, action='edit')).forms[0]

        with self.admin_access.web_request() as req2:
            form2 = self.vreg['views'].select('edition', req, rset=e.as_rset(), row=0)

        with self.admin_access.web_request(**dict(html_form.form_values())) as req:
            path, args = self.expect_redirect_handle_request(req, path='edit')
            self.assertEqual(path, expected_path)

    def test_simultaneous_edition_refuse_second_commit(self):
        """ Disallow committing changes to an entity edited in between """
        with self.admin_access.web_request() as req:
            e = req.create_entity('BlogEntry', title=u'cubicweb.org', content=u"hop")
            eid = e.eid
            req.cnx.commit()
            form = self.vreg['views'].select('edition', req, rset=e.as_rset(), row=0)
            html_form = lxml.html.fromstring(form.render(w=None, action='edit')).forms[0]

        with self.admin_access.web_request() as req2:
            e = req2.entity_from_eid(eid)
            e.cw_set(content = u"hip")
            req2.cnx.commit()

        form_field_name = "content-subject:%d" % eid
        form_values = dict(html_form.form_values())
        assert form_field_name in form_values
        form_values[form_field_name] = u'yep'
        with self.admin_access.web_request(**form_values) as req:
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            reported_eid, dict_info = cm.exception.args
            self.assertEqual(reported_eid, eid)
            self.assertIn(None, dict_info)
            self.assertIn("has changed since you started to edit it.", dict_info[None])

    def test_user_editing_itself(self):
        """checking that a manager user can edit itself
        """
        with self.admin_access.web_request() as req:
            user = req.user
            groupeids = [eid for eid, in req.execute('CWGroup G WHERE G name '
                                                     'in ("managers", "users")')]
            groups = [str(eid) for eid in groupeids]
            eid = str(user.eid)
            req.form = {
                'eid': eid, '__type:'+eid: 'CWUser',
                '_cw_entity_fields:'+eid: 'login-subject,firstname-subject,surname-subject,in_group-subject',
                'login-subject:'+eid:     str(user.login),
                'surname-subject:'+eid: u'Th\xe9nault',
                'firstname-subject:'+eid:   u'Sylvain',
                'in_group-subject:'+eid:  groups,
                }
            self.expect_redirect_handle_request(req, 'edit')
            e = req.execute('Any X WHERE X eid %(x)s',
                            {'x': user.eid}).get_entity(0, 0)
            self.assertEqual(e.firstname, u'Sylvain')
            self.assertEqual(e.surname, u'Th\xe9nault')
            self.assertEqual(e.login, user.login)
            self.assertEqual([g.eid for g in e.in_group], groupeids)

    def test_user_can_change_its_password(self):
        with self.admin_access.repo_cnx() as cnx:
            self.create_user(cnx, u'user')
            cnx.commit()
        with self.new_access(u'user').web_request() as req:
            eid = str(req.user.eid)
            req.form = {
                'eid': eid, '__maineid' : eid,
                '__type:'+eid: 'CWUser',
                '_cw_entity_fields:'+eid: 'upassword-subject',
                'upassword-subject:'+eid: 'tournicoton',
                'upassword-subject-confirm:'+eid: 'tournicoton',
                }
            path, params = self.expect_redirect_handle_request(req, 'edit')
            req.cnx.commit() # commit to check we don't get late validation error for instance
            self.assertEqual(path, 'cwuser/user')
            self.assertNotIn('vid', params)

    def test_user_editing_itself_no_relation(self):
        """checking we can edit an entity without specifying some required
        relations (meaning no changes)
        """
        with self.admin_access.web_request() as req:
            user = req.user
            groupeids = [g.eid for g in user.in_group]
            eid = str(user.eid)
            req.form = {
                'eid':       eid,
                '__type:'+eid:    'CWUser',
                '_cw_entity_fields:'+eid: 'login-subject,firstname-subject,surname-subject',
                'login-subject:'+eid:     str(user.login),
                'firstname-subject:'+eid: u'Th\xe9nault',
                'surname-subject:'+eid:   u'Sylvain',
                }
            self.expect_redirect_handle_request(req, 'edit')
            e = req.execute('Any X WHERE X eid %(x)s',
                            {'x': user.eid}).get_entity(0, 0)
            self.assertEqual(e.login, user.login)
            self.assertEqual(e.firstname, u'Th\xe9nault')
            self.assertEqual(e.surname, u'Sylvain')
            self.assertEqual([g.eid for g in e.in_group], groupeids)
            self.assertEqual(e.cw_adapt_to('IWorkflowable').state, 'activated')


    def test_create_multiple_linked(self):
        with self.admin_access.web_request() as req:
            gueid = req.execute('CWGroup G WHERE G name "users"')[0][0]
            req.form = {'eid': ['X', 'Y'], '__maineid' : 'X',
                        '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject,surname-subject,in_group-subject',
                        'login-subject:X': u'adim',
                        'upassword-subject:X': u'toto', 'upassword-subject-confirm:X': u'toto',
                        'surname-subject:X': u'Di Mascio',
                        'in_group-subject:X': str(gueid),

                        '__type:Y': 'EmailAddress',
                        '_cw_entity_fields:Y': 'address-subject,use_email-object',
                        'address-subject:Y': u'dima@logilab.fr',
                        'use_email-object:Y': 'X',
                        }
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            # should be redirected on the created person
            self.assertEqual(path, 'cwuser/adim')
            e = req.execute('Any P WHERE P surname "Di Mascio"').get_entity(0, 0)
            self.assertEqual(e.surname, 'Di Mascio')
            email = e.use_email[0]
            self.assertEqual(email.address, 'dima@logilab.fr')

    def test_create_mandatory_inlined(self):
        with self.admin_access.web_request() as req:
            req.form = {'eid': ['X', 'Y'], '__maineid' : 'X',

                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': '',

                        '__type:Y': 'File',
                        '_cw_entity_fields:Y': 'data-subject,described_by_test-object',
                        'data-subject:Y': (u'coucou.txt', Binary(b'coucou')),
                        'described_by_test-object:Y': 'X',
                        }
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            self.assertTrue(path.startswith('salesterm/'), path)
            eid = path.split('/')[1]
            salesterm = req.entity_from_eid(eid)
            # The NOT NULL constraint of mandatory relation implies that the File
            # must be created before the Salesterm, otherwise Salesterm insertion
            # will fail.
            # NOTE: sqlite does have NOT NULL constraint, unlike Postgres so the
            # insertion does not fail and we have to check dumbly that File is
            # created before.
            self.assertGreater(salesterm.eid, salesterm.described_by_test[0].eid)

    def test_create_mandatory_inlined2(self):
        with self.admin_access.web_request() as req:
            req.form = {'eid': ['X', 'Y'], '__maineid' : 'X',

                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'described_by_test-subject',
                        'described_by_test-subject:X': 'Y',

                        '__type:Y': 'File',
                        '_cw_entity_fields:Y': 'data-subject',
                        'data-subject:Y': (u'coucou.txt', Binary(b'coucou')),
                        }
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            self.assertTrue(path.startswith('salesterm/'), path)
            eid = path.split('/')[1]
            salesterm = req.entity_from_eid(eid)
            # The NOT NULL constraint of mandatory relation implies that the File
            # must be created before the Salesterm, otherwise Salesterm insertion
            # will fail.
            # NOTE: sqlite does have NOT NULL constraint, unlike Postgres so the
            # insertion does not fail and we have to check dumbly that File is
            # created before.
            self.assertGreater(salesterm.eid, salesterm.described_by_test[0].eid)

    def test_edit_mandatory_inlined3_object(self):
        # non regression test for #3120495. Without the fix, leads to
        # "unhashable type: 'list'" error
        with self.admin_access.web_request() as req:
            cwrelation = str(req.execute('CWEType X WHERE X name "CWSource"')[0][0])
            req.form = {'eid': [cwrelation], '__maineid' : cwrelation,

                        '__type:'+cwrelation: 'CWEType',
                        '_cw_entity_fields:'+cwrelation: 'to_entity-object',
                        'to_entity-object:'+cwrelation: [9999, 9998],
                        }
            with req.cnx.deny_all_hooks_but():
                path, _params = self.expect_redirect_handle_request(req, 'edit')
            self.assertTrue(path.startswith('cwetype/CWSource'), path)

    def test_edit_multiple_linked(self):
        with self.admin_access.web_request() as req:
            peid = str(self.create_user(req, u'adim').eid)
            req.form = {'eid': [peid, 'Y'], '__maineid': peid,

                        '__type:'+peid: u'CWUser',
                        '_cw_entity_fields:'+peid: u'surname-subject',
                        'surname-subject:'+peid: u'Di Masci',

                        '__type:Y': u'EmailAddress',
                        '_cw_entity_fields:Y': u'address-subject,use_email-object',
                        'address-subject:Y': u'dima@logilab.fr',
                        'use_email-object:Y': peid,
                        }
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            # should be redirected on the created person
            self.assertEqual(path, 'cwuser/adim')
            e = req.execute('Any P WHERE P surname "Di Masci"').get_entity(0, 0)
            email = e.use_email[0]
            self.assertEqual(email.address, 'dima@logilab.fr')

        # with self.admin_access.web_request() as req:
            emaileid = str(email.eid)
            req.form = {'eid': [peid, emaileid],

                        '__type:'+peid: u'CWUser',
                        '_cw_entity_fields:'+peid: u'surname-subject',
                        'surname-subject:'+peid: u'Di Masci',

                        '__type:'+emaileid: u'EmailAddress',
                        '_cw_entity_fields:'+emaileid: u'address-subject,use_email-object',
                        'address-subject:'+emaileid: u'adim@logilab.fr',
                        'use_email-object:'+emaileid: peid,
                        }
            self.expect_redirect_handle_request(req, 'edit')
            email.cw_clear_all_caches()
            self.assertEqual(email.address, 'adim@logilab.fr')

    def test_password_confirm(self):
        """test creation of two linked entities
        """
        with self.admin_access.web_request() as req:
            user = req.user
            req.form = {'eid': 'X',
                        '__cloned_eid:X': str(user.eid), '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject',
                        'login-subject:X': u'toto',
                        'upassword-subject:X': u'toto',
                        }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            self.assertEqual({'upassword-subject': u'password and confirmation don\'t match'},
                             cm.exception.errors)
            req.form = {'__cloned_eid:X': str(user.eid),
                        'eid': 'X', '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject',
                        'login-subject:X': u'toto',
                        'upassword-subject:X': u'toto',
                        'upassword-subject-confirm:X': u'tutu',
                        }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            self.assertEqual({'upassword-subject': u'password and confirmation don\'t match'},
                             cm.exception.errors)


    def test_interval_bound_constraint_success(self):
        with self.admin_access.repo_cnx() as cnx:
            feid = cnx.execute('INSERT File X: X data_name "toto.txt", X data %(data)s',
                               {'data': Binary(b'yo')})[0][0]
            cnx.commit()

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'-10',
                        'described_by_test-subject:X': str(feid),
                    }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            cm.exception.translate(str)
            self.assertEqual({'amount-subject': 'value -10 must be >= 0'},
                             cm.exception.errors)

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'110',
                        'described_by_test-subject:X': str(feid),
                        }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            cm.exception.translate(str)
            self.assertEqual(cm.exception.errors, {'amount-subject': 'value 110 must be <= 100'})

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'10',
                        'described_by_test-subject:X': str(feid),
                        }
            self.expect_redirect_handle_request(req, 'edit')
            # should be redirected on the created
            #eid = params['rql'].split()[-1]
            e = req.execute('Salesterm X').get_entity(0, 0)
            self.assertEqual(e.amount, 10)

    def test_interval_bound_constraint_validateform(self):
        """Test the FormValidatorController controller on entity with
        constrained attributes"""
        with self.admin_access.repo_cnx() as cnx:
            feid = cnx.execute('INSERT File X: X data_name "toto.txt", X data %(data)s',
                               {'data': Binary(b'yo')})[0][0]
            seid = cnx.create_entity('Salesterm', amount=0, described_by_test=feid).eid
            cnx.commit()

        # ensure a value that violate a constraint is properly detected
        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': [str(seid)],
                        '__type:%s'%seid: 'Salesterm',
                        '_cw_entity_fields:%s'%seid: 'amount-subject',
                        'amount-subject:%s'%seid: u'-10',
                    }
            self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [false, [%s, {"amount-subject": "value -10 must be >= 0"}], null], null);
</script>'''%seid, self.ctrl_publish(req, 'validateform').decode('ascii'))

        # ensure a value that comply a constraint is properly processed
        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': [str(seid)],
                        '__type:%s'%seid: 'Salesterm',
                        '_cw_entity_fields:%s'%seid: 'amount-subject',
                        'amount-subject:%s'%seid: u'20',
                    }
            self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [true, "http://testing.fr/cubicweb/view", null], null);
</script>''', self.ctrl_publish(req, 'validateform').decode('ascii'))
            self.assertEqual(20, req.execute('Any V WHERE X amount V, X eid %(eid)s',
                                             {'eid': seid})[0][0])

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'0',
                        'described_by_test-subject:X': str(feid),
                    }

            # ensure a value that is modified in an operation on a modify
            # hook works as it should (see
            # https://www.cubicweb.org/ticket/2509729 )
            class MyOperation(Operation):
                def precommit_event(self):
                    self.entity.cw_set(amount=-10)
            class ValidationErrorInOpAfterHook(Hook):
                __regid__ = 'valerror-op-after-hook'
                __select__ = Hook.__select__ & is_instance('Salesterm')
                events = ('after_add_entity',)
                def __call__(self):
                    MyOperation(self._cw, entity=self.entity)

            with self.temporary_appobjects(ValidationErrorInOpAfterHook):
                self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [false, ["X", {"amount-subject": "value -10 must be >= 0"}], null], null);
</script>''', self.ctrl_publish(req, 'validateform').decode('ascii'))

            self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [true, "http://testing.fr/cubicweb/view", null], null);
</script>''', self.ctrl_publish(req, 'validateform').decode('ascii'))

    def test_req_pending_insert(self):
        """make sure req's pending insertions are taken into account"""
        with self.admin_access.web_request() as req:
            tmpgroup = req.create_entity('CWGroup', name=u"test")
            user = req.user
            req.cnx.commit()
        with self.admin_access.web_request(**req_form(user)) as req:
            req.session.data['pending_insert'] = set([(user.eid, 'in_group', tmpgroup.eid)])
            self.expect_redirect_handle_request(req, 'edit')
            usergroups = [gname for gname, in
                          req.execute('Any N WHERE G name N, U in_group G, U eid %(u)s',
                                      {'u': user.eid})]
            self.assertCountEqual(usergroups, ['managers', 'test'])
            self.assertEqual(get_pending_inserts(req), [])

    def test_req_pending_delete(self):
        """make sure req's pending deletions are taken into account"""
        with self.admin_access.web_request() as req:
            user = req.user
            groupeid = req.execute('INSERT CWGroup G: G name "test", U in_group G WHERE U eid %(x)s',
                                    {'x': user.eid})[0][0]
            usergroups = [gname for gname, in
                          req.execute('Any N WHERE G name N, U in_group G, U eid %(u)s',
                                      {'u': user.eid})]
            # just make sure everything was set correctly
            self.assertCountEqual(usergroups, ['managers', 'test'])
            req.cnx.commit()
            # now try to delete the relation
        with self.admin_access.web_request(**req_form(user)) as req:
            req.session.data['pending_delete'] = set([(user.eid, 'in_group', groupeid)])
            self.expect_redirect_handle_request(req, 'edit')
            usergroups = [gname for gname, in
                          req.execute('Any N WHERE G name N, U in_group G, U eid %(u)s',
                                      {'u': user.eid})]
            self.assertCountEqual(usergroups, ['managers'])
            self.assertEqual(get_pending_deletes(req), [])

    def test_redirect_apply_button(self):
        with self.admin_access.web_request() as req:
            redirectrql = rql_for_eid(4012) # whatever
            req.form = {
                'eid': 'A', '__maineid' : 'A',
                '__type:A': 'BlogEntry', '_cw_entity_fields:A': 'content-subject,title-subject',
                'content-subject:A': u'"13:03:43"',
                'title-subject:A': u'huuu',
                '__redirectrql': redirectrql,
                '__redirectvid': 'primary',
                '__redirectparams': 'toto=tutu&tata=titi',
                '__form_id': 'edition',
                '__action_apply': '',
                }
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertTrue(path.startswith('blogentry/'))
            eid = path.split('/')[1]
            self.assertEqual(params['vid'], 'edition')
            self.assertNotEqual(int(eid), 4012)
            self.assertEqual(params['__redirectrql'], redirectrql)
            self.assertEqual(params['__redirectvid'], 'primary')
            self.assertEqual(params['__redirectparams'], 'toto=tutu&tata=titi')

    def test_redirect_ok_button(self):
        with self.admin_access.web_request() as req:
            redirectrql = rql_for_eid(4012) # whatever
            req.form = {
                'eid': 'A', '__maineid' : 'A',
                '__type:A': 'BlogEntry', '_cw_entity_fields:A': 'content-subject,title-subject',
                'content-subject:A': u'"13:03:43"',
                'title-subject:A': u'huuu',
                '__redirectrql': redirectrql,
                '__redirectvid': 'primary',
                '__redirectparams': 'toto=tutu&tata=titi',
                '__form_id': 'edition',
                }
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'view')
            self.assertEqual(params['rql'], redirectrql)
            self.assertEqual(params['vid'], 'primary')
            self.assertEqual(params['tata'], 'titi')
            self.assertEqual(params['toto'], 'tutu')

    def test_redirect_delete_button(self):
        with self.admin_access.web_request() as req:
            eid = req.create_entity('BlogEntry', title=u'hop', content=u'hop').eid
            req.form = {'eid': str(eid), '__type:%s'%eid: 'BlogEntry',
                        '__action_delete': ''}
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'blogentry')
            self.assertIn('_cwmsgid', params)
            eid = req.create_entity('EmailAddress', address=u'hop@logilab.fr').eid
            req.execute('SET X use_email E WHERE E eid %(e)s, X eid %(x)s',
                        {'x': req.user.eid, 'e': eid})
            req.cnx.commit()
            req.form = {'eid': str(eid), '__type:%s'%eid: 'EmailAddress',
                        '__action_delete': ''}
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'cwuser/admin')
            self.assertIn('_cwmsgid', params)
            eid1 = req.create_entity('BlogEntry', title=u'hop', content=u'hop').eid
            eid2 = req.create_entity('EmailAddress', address=u'hop@logilab.fr').eid
            req.form = {'eid': [str(eid1), str(eid2)],
                        '__type:%s'%eid1: 'BlogEntry',
                        '__type:%s'%eid2: 'EmailAddress',
                        '__action_delete': ''}
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'view')
            self.assertIn('_cwmsgid', params)

    def test_simple_copy(self):
        with self.admin_access.web_request() as req:
            blog = req.create_entity('Blog', title=u'my-blog')
            blogentry = req.create_entity('BlogEntry', title=u'entry1',
                                          content=u'content1', entry_of=blog)
            req.form = {'__maineid' : 'X', 'eid': 'X',
                        '__cloned_eid:X': blogentry.eid, '__type:X': 'BlogEntry',
                        '_cw_entity_fields:X': 'title-subject,content-subject',
                        'title-subject:X': u'entry1-copy',
                        'content-subject:X': u'content1',
                        }
            self.expect_redirect_handle_request(req, 'edit')
            blogentry2 = req.find('BlogEntry', title=u'entry1-copy').one()
            self.assertEqual(blogentry2.entry_of[0].eid, blog.eid)

    def test_skip_copy_for(self):
        with self.admin_access.web_request() as req:
            blog = req.create_entity('Blog', title=u'my-blog')
            blogentry = req.create_entity('BlogEntry', title=u'entry1',
                                          content=u'content1', entry_of=blog)
            blogentry.__class__.cw_skip_copy_for = [('entry_of', 'subject')]
            try:
                req.form = {'__maineid' : 'X', 'eid': 'X',
                            '__cloned_eid:X': blogentry.eid, '__type:X': 'BlogEntry',
                            '_cw_entity_fields:X': 'title-subject,content-subject',
                            'title-subject:X': u'entry1-copy',
                            'content-subject:X': u'content1',
                            }
                self.expect_redirect_handle_request(req, 'edit')
                blogentry2 = req.find('BlogEntry', title=u'entry1-copy').one()
                # entry_of should not be copied
                self.assertEqual(len(blogentry2.entry_of), 0)
            finally:
                blogentry.__class__.cw_skip_copy_for = []

    def test_avoid_multiple_process_posted(self):
        # test that when some entity is being created and data include non-inlined relations, the
        # values for this relation are stored for later usage, without calling twice field's
        # process_form method, which may be unexpected for custom fields

        orig_process_posted = ff.RelationField.process_posted

        def count_process_posted(self, form):
            res = list(orig_process_posted(self, form))
            nb_process_posted_calls[0] += 1
            return res

        ff.RelationField.process_posted = count_process_posted

        try:
            with self.admin_access.web_request() as req:
                gueid = req.execute('CWGroup G WHERE G name "users"')[0][0]
                req.form = {
                    'eid': 'X',
                    '__type:X': 'CWUser',
                    '_cw_entity_fields:X': 'login-subject,upassword-subject,in_group-subject',
                    'login-subject:X': u'adim',
                    'upassword-subject:X': u'toto', 'upassword-subject-confirm:X': u'toto',
                    'in_group-subject:X': repr(gueid),
                }
                nb_process_posted_calls = [0]
                self.expect_redirect_handle_request(req, 'edit')
                self.assertEqual(nb_process_posted_calls[0], 1)
                user = req.find('CWUser', login=u'adim').one()
                self.assertEqual(set(g.eid for g in user.in_group), set([gueid]))
                req.form = {
                    'eid': ['X', 'Y'],
                    '__type:X': 'CWUser',
                    '_cw_entity_fields:X': 'login-subject,upassword-subject,in_group-subject',
                    'login-subject:X': u'dlax',
                    'upassword-subject:X': u'toto', 'upassword-subject-confirm:X': u'toto',
                    'in_group-subject:X': repr(gueid),

                    '__type:Y': 'EmailAddress',
                    '_cw_entity_fields:Y': 'address-subject,use_email-object',
                    'address-subject:Y': u'dlax@cw.org',
                    'use_email-object:Y': 'X',
                }
                nb_process_posted_calls = [0]
                self.expect_redirect_handle_request(req, 'edit')
                self.assertEqual(nb_process_posted_calls[0], 3)  # 3 = 1 (in_group) + 2 (use_email)
                user = req.find('CWUser', login=u'dlax').one()
                self.assertEqual(set(e.address for e in user.use_email), set(['dlax@cw.org']))

        finally:
            ff.RelationField.process_posted = orig_process_posted

    def test_nonregr_eetype_etype_editing(self):
        """non-regression test checking that a manager user can edit a CWEType entity
        """
        with self.admin_access.web_request() as req:
            groupeids = sorted(eid
                               for eid, in req.execute('CWGroup G '
                                                       'WHERE G name in ("managers", "users")'))
            groups = [str(eid) for eid in groupeids]
            cwetypeeid = req.execute('CWEType X WHERE X name "CWEType"')[0][0]
            basegroups = [str(eid)
                          for eid, in req.execute('CWGroup G '
                                                  'WHERE X read_permission G, X eid %(x)s',
                                                  {'x': cwetypeeid})]
            cwetypeeid = str(cwetypeeid)
            req.form = {
                'eid':      cwetypeeid,
                '__type:'+cwetypeeid:  'CWEType',
                '_cw_entity_fields:'+cwetypeeid: 'name-subject,final-subject,description-subject,read_permission-subject',
                'name-subject:'+cwetypeeid:     u'CWEType',
                'final-subject:'+cwetypeeid:    '',
                'description-subject:'+cwetypeeid:     u'users group',
                'read_permission-subject:'+cwetypeeid:  groups,
            }
            try:
                self.expect_redirect_handle_request(req, 'edit')
                e = req.execute('Any X WHERE X eid %(x)s', {'x': cwetypeeid}).get_entity(0, 0)
                self.assertEqual(e.name, 'CWEType')
                self.assertEqual(sorted(g.eid for g in e.read_permission), groupeids)
            finally:
                # restore
                req.execute('SET X read_permission Y WHERE X name "CWEType", '
                            'Y eid IN (%s), NOT X read_permission Y' % (','.join(basegroups)))
                req.cnx.commit()

    def test_nonregr_strange_text_input(self):
        """non-regression test checking text input containing "13:03:43"

        this seems to be postgres (tsearch?) specific
        """
        with self.admin_access.web_request() as req:
            req.form = {
                'eid': 'A', '__maineid' : 'A',
                '__type:A': 'BlogEntry', '_cw_entity_fields:A': 'title-subject,content-subject',
                'title-subject:A': u'"13:03:40"',
                'content-subject:A': u'"13:03:43"',}
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            self.assertTrue(path.startswith('blogentry/'))
            eid = path.split('/')[1]
            e = req.execute('Any C, T WHERE C eid %(x)s, C content T', {'x': eid}).get_entity(0, 0)
            self.assertEqual(e.title, '"13:03:40"')
            self.assertEqual(e.content, '"13:03:43"')

    def test_nonregr_multiple_empty_email_addr(self):
        with self.admin_access.web_request() as req:
            gueid = req.execute('CWGroup G WHERE G name "users"')[0][0]
            req.form = {'eid': ['X', 'Y'],

                        '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject,in_group-subject',
                        'login-subject:X': u'adim',
                        'upassword-subject:X': u'toto', 'upassword-subject-confirm:X': u'toto',
                        'in_group-subject:X': repr(gueid),

                        '__type:Y': 'EmailAddress',
                        '_cw_entity_fields:Y': 'address-subject,alias-subject,use_email-object',
                        'address-subject:Y': u'',
                        'alias-subject:Y': u'',
                        'use_email-object:Y': 'X',
                        }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            self.assertEqual(cm.exception.errors, {'address-subject': u'required field'})

    def test_nonregr_copy(self):
        with self.admin_access.web_request() as req:
            user = req.user
            req.form = {'__maineid' : 'X', 'eid': 'X',
                        '__cloned_eid:X': user.eid, '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject',
                        'login-subject:X': u'toto',
                        'upassword-subject:X': u'toto', 'upassword-subject-confirm:X': u'toto',
                        }
            path, _params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'cwuser/toto')
            e = req.execute('Any X WHERE X is CWUser, X login "toto"').get_entity(0, 0)
            self.assertEqual(e.login, 'toto')
            self.assertEqual(e.in_group[0].name, 'managers')


    def test_nonregr_rollback_on_validation_error(self):
        with self.admin_access.web_request(url='edit') as req:
            p = self.create_user(req, u"doe")
            # do not try to skip 'primary_email' for this test
            old_skips = p.__class__.cw_skip_copy_for
            p.__class__.cw_skip_copy_for = ()
            try:
                e = req.create_entity('EmailAddress', address=u'doe@doe.com')
                req.execute('SET P use_email E, P primary_email E WHERE P eid %(p)s, E eid %(e)s',
                            {'p' : p.eid, 'e' : e.eid})
                req.form = {'eid': 'X',
                            '__cloned_eid:X': p.eid, '__type:X': 'CWUser',
                            '_cw_entity_fields:X': 'login-subject,surname-subject',
                            'login-subject': u'dodo',
                            'surname-subject:X': u'Boom',
                            '__errorurl' : "whatever but required",
                            }
                # try to emulate what really happens in the web application
                # 1/ validate form => EditController.publish raises a ValidationError
                #    which fires a Redirect
                # 2/ When re-publishing the copy form, the publisher implicitly commits
                try:
                    self.app_handle_request(req)
                except Redirect:
                    req.form['rql'] = 'Any X WHERE X eid %s' % p.eid
                    req.form['vid'] = 'copy'
                    self.app_handle_request(req, 'view')
                rset = req.execute('CWUser P WHERE P surname "Boom"')
                self.assertEqual(len(rset), 0)
            finally:
                p.__class__.cw_skip_copy_for = old_skips

    def test_regr_inlined_forms(self):
        with self.admin_access.web_request() as req:
            self.schema['described_by_test'].inlined = False
            try:
                req.data['eidmap'] = {}
                req.data['pending_others'] = set()
                req.data['pending_inlined'] = {}
                req.form = {'eid': ['X', 'Y'], '__maineid' : 'X',

                            '__type:X': 'Salesterm',
                            '_cw_entity_fields:X': 'described_by_test-subject',
                            'described_by_test-subject:X': 'Y',

                            '__type:Y': 'File',
                            '_cw_entity_fields:Y': 'data-subject',
                            'data-subject:Y': (u'coucou.txt', Binary(b'coucou')),
                            }
                values_by_eid = dict((eid, req.extract_entity_params(eid, minparams=2))
                                     for eid in req.edited_eids())
                editctrl = self.vreg['controllers'].select('edit', req)
                # don't call publish to enforce select order
                editctrl.errors = []
                editctrl._to_create = {}
                editctrl.edit_entity(values_by_eid['X']) # #3064653 raise ValidationError
                editctrl.edit_entity(values_by_eid['Y'])
            finally:
                self.schema['described_by_test'].inlined = False


class ReportBugControllerTC(CubicWebTC):

    def test_usable_by_guest(self):
        with self.new_access(u'anon').web_request() as req:
            self.assertRaises(NoSelectableObject,
                              self.vreg['controllers'].select, 'reportbug', req)
        with self.new_access(u'anon').web_request(description='hop') as req:
            self.vreg['controllers'].select('reportbug', req)


class AjaxControllerTC(CubicWebTC):
    tested_controller = 'ajax'

    def ctrl(self, req=None):
        req = req or self.request(url='http://whatever.fr/')
        return self.vreg['controllers'].select(self.tested_controller, req)

    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            self.pytag = cnx.create_entity('Tag', name=u'python')
            self.cubicwebtag = cnx.create_entity('Tag', name=u'cubicweb')
            self.john = self.create_user(cnx, u'John')
            cnx.commit()

    ## tests ##################################################################
    def test_simple_exec(self):
        with self.admin_access.web_request(rql='CWUser P WHERE P login "John"',
                                           pageid='123', fname='view') as req:
            ctrl = self.ctrl(req)
            rset = self.john.as_rset()
            rset.req = req
            source = ctrl.publish()
            self.assertTrue(source.startswith(b'<div>'))

#     def test_json_exec(self):
#         rql = 'Any T,N WHERE T is Tag, T name N'
#         ctrl = self.ctrl(self.request(mode='json', rql=rql, pageid='123'))
#         self.assertEqual(ctrl.publish(),
#                           json_dumps(self.execute(rql).rows))

    def test_remote_add_existing_tag(self):
        with self.remote_calling('tag_entity', self.john.eid, ['python']) as (_, req):
            self.assertCountEqual(
                [tname for tname, in req.execute('Any N WHERE T is Tag, T name N')],
                ['python', 'cubicweb'])
            self.assertEqual(
                req.execute('Any N WHERE T tags P, P is CWUser, T name N').rows,
                [['python']])

    def test_remote_add_new_tag(self):
        with self.remote_calling('tag_entity', self.john.eid, ['javascript']) as (_, req):
            self.assertCountEqual(
                [tname for tname, in req.execute('Any N WHERE T is Tag, T name N')],
                ['python', 'cubicweb', 'javascript'])
            self.assertEqual(
                req.execute('Any N WHERE T tags P, P is CWUser, T name N').rows,
                [['javascript']])

    def test_maydel_perms(self):
        """Check that AjaxEditRelationCtxComponent calls rdef.check with a
        sufficient context"""
        with self.remote_calling('tag_entity', self.john.eid, ['python']) as (_, req):
            req.cnx.commit()
        with self.temporary_permissions(
                (self.schema['tags'].rdefs['Tag', 'CWUser'],
                 {'delete': (RRQLExpression('S owned_by U'), )}, )):
            with self.admin_access.web_request(rql='CWUser P WHERE P login "John"',
                                               pageid='123', fname='view',
                                               session=req.session) as req:
                ctrl = self.ctrl(req)
                rset = self.john.as_rset()
                rset.req = req
                source = ctrl.publish()
                # maydel jscall
                self.assertIn(b'ajaxBoxRemoveLinkedEntity', source)

    def test_pending_insertion(self):
        with self.remote_calling('add_pending_inserts', [['12', 'tags', '13']]) as (_, req):
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, [])
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, ['12:tags:13'])
        with self.remote_calling('add_pending_inserts', [['12', 'tags', '14']],
                                 session=req.session) as (_, req):
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, [])
            inserts = get_pending_inserts(req)
            self.assertCountEqual(inserts, ['12:tags:13', '12:tags:14'])
            inserts = get_pending_inserts(req, 12)
            self.assertCountEqual(inserts, ['12:tags:13', '12:tags:14'])
            inserts = get_pending_inserts(req, 13)
            self.assertEqual(inserts, ['12:tags:13'])
            inserts = get_pending_inserts(req, 14)
            self.assertEqual(inserts, ['12:tags:14'])
            req.remove_pending_operations()

    def test_pending_deletion(self):
        with self.remote_calling('add_pending_delete', ['12', 'tags', '13']) as (_, req):
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, [])
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, ['12:tags:13'])
        with self.remote_calling('add_pending_delete', ['12', 'tags', '14'],
                                 session=req.session) as (_, req):
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, [])
            deletes = get_pending_deletes(req)
            self.assertCountEqual(deletes, ['12:tags:13', '12:tags:14'])
            deletes = get_pending_deletes(req, 12)
            self.assertCountEqual(deletes, ['12:tags:13', '12:tags:14'])
            deletes = get_pending_deletes(req, 13)
            self.assertEqual(deletes, ['12:tags:13'])
            deletes = get_pending_deletes(req, 14)
            self.assertEqual(deletes, ['12:tags:14'])
            req.remove_pending_operations()

    def test_remove_pending_operations(self):
        with self.remote_calling('add_pending_delete', ['12', 'tags', '13']) as (_, req):
            pass
        with self.remote_calling('add_pending_inserts', [['12', 'tags', '14']],
                                 session=req.session) as (_, req):
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, ['12:tags:14'])
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, ['12:tags:13'])
            req.remove_pending_operations()
            self.assertEqual(get_pending_deletes(req), [])
            self.assertEqual(get_pending_inserts(req), [])

    def test_add_inserts(self):
        with self.remote_calling('add_pending_inserts',
                                 [('12', 'tags', '13'), ('12', 'tags', '14')]) as (_, req):
            inserts = get_pending_inserts(req)
            self.assertCountEqual(inserts, ['12:tags:13', '12:tags:14'])
            req.remove_pending_operations()


    # silly tests
    def test_external_resource(self):
        with self.remote_calling('external_resource', 'RSS_LOGO') as (res, _):
            self.assertEqual(json_dumps(self.config.uiprops['RSS_LOGO']).encode('ascii'),
                             res)

    def test_i18n(self):
        with self.remote_calling('i18n', ['bimboom']) as (res, _):
            self.assertEqual(json_dumps(['bimboom']).encode('ascii'), res)

    def test_format_date(self):
        with self.remote_calling('format_date', '2007-01-01 12:00:00') as (res, _):
            self.assertEqual(json_dumps('2007/01/01').encode('ascii'), res)

    def test_ajaxfunc_noparameter(self):
        @ajaxfunc
        def foo(self, x, y):
            return 'hello'
        self.assertEqual(foo(object, 1, 2), 'hello')
        appobject = foo.__appobject__
        self.assertTrue(issubclass(appobject, AjaxFunction))
        self.assertEqual(appobject.__regid__, 'foo')
        self.assertEqual(appobject.check_pageid, False)
        self.assertEqual(appobject.output_type, None)
        with self.admin_access.web_request() as req:
            f = appobject(req)
            self.assertEqual(f(12, 13), 'hello')

    def test_ajaxfunc_checkpageid(self):
        @ajaxfunc(check_pageid=True)
        def foo(self, x, y):
            return 'hello'
        self.assertEqual(foo(object, 1, 2), 'hello')
        appobject = foo.__appobject__
        self.assertTrue(issubclass(appobject, AjaxFunction))
        self.assertEqual(appobject.__regid__, 'foo')
        self.assertEqual(appobject.check_pageid, True)
        self.assertEqual(appobject.output_type, None)
        # no pageid
        with self.admin_access.web_request() as req:
            f = appobject(req)
            self.assertRaises(RemoteCallFailed, f, 12, 13)

    def test_ajaxfunc_json(self):
        @ajaxfunc(output_type='json')
        def foo(self, x, y):
            return x + y
        self.assertEqual(foo(object, 1, 2), 3)
        appobject = foo.__appobject__
        self.assertTrue(issubclass(appobject, AjaxFunction))
        self.assertEqual(appobject.__regid__, 'foo')
        self.assertEqual(appobject.check_pageid, False)
        self.assertEqual(appobject.output_type, 'json')
        # no pageid
        with self.admin_access.web_request() as req:
            f = appobject(req)
            self.assertEqual(f(12, 13), '25')

    def test_badrequest(self):
        with self.assertRaises(RemoteCallFailed) as cm:
            with self.remote_calling('foo'):
                pass
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(cm.exception.reason, 'no foo method')


class UndoControllerTC(CubicWebTC):

    def setUp(self):
        # Force undo feature to be turned on
        Connection.undo_actions = property(lambda self: True, lambda self, v:None)
        super(UndoControllerTC, self).setUp()

    def tearDown(self):
        super(UndoControllerTC, self).tearDown()
        del Connection.undo_actions

    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            self.toto = self.create_user(cnx, u'toto',
                                         password=u'toto',
                                         groups=('users',),
                                         commit=False)
            self.txuuid_toto = cnx.commit()
            self.toto_email = cnx.create_entity('EmailAddress',
                                                address=u'toto@logilab.org',
                                                reverse_use_email=self.toto)
            self.txuuid_toto_email = cnx.commit()

    def test_no_such_transaction(self):
        with self.admin_access.web_request() as req:
            txuuid = u"12345acbd"
            req.form['txuuid'] = txuuid
            controller = self.vreg['controllers'].select('undo', req)
            with self.assertRaises(tx.NoSuchTransaction) as cm:
                result = controller.publish(rset=None)
            self.assertEqual(cm.exception.txuuid, txuuid)

    def assertURLPath(self, url, expected_path, expected_params=None):
        """ This assert that the path part of `url` matches  expected path

        TODO : implement assertion on the expected_params too
        """
        with self.admin_access.web_request() as req:
            scheme, netloc, path, query, fragment = urlsplit(url)
            query_dict = parse_qs(query)
            expected_url = urljoin(req.base_url(), expected_path)
            self.assertEqual( urlunsplit((scheme, netloc, path, None, None)), expected_url)

    def test_redirect_redirectpath(self):
        "Check that the potential __redirectpath is honored"
        with self.admin_access.web_request() as req:
            txuuid = self.txuuid_toto_email
            req.form['txuuid'] = txuuid
            rpath = "toto"
            req.form['__redirectpath'] = rpath
            controller = self.vreg['controllers'].select('undo', req)
            with self.assertRaises(Redirect) as cm:
                result = controller.publish(rset=None)
            self.assertURLPath(cm.exception.location, rpath)


class LoginControllerTC(CubicWebTC):

    def test_login_with_dest(self):
        with self.admin_access.web_request() as req:
            req.form = {'postlogin_path': 'elephants/babar'}
            with self.assertRaises(Redirect) as cm:
                self.ctrl_publish(req, ctrl='login')
            self.assertEqual(req.build_url('elephants/babar'), cm.exception.location)

    def test_login_no_dest(self):
        with self.admin_access.web_request() as req:
            with self.assertRaises(Redirect) as cm:
                self.ctrl_publish(req, ctrl='login')
            self.assertEqual(req.base_url(), cm.exception.location)


class LoginControllerHTTPTC(CubicWebServerTC):

    anonymous_allowed = True
    # this TC depends on the auth mode being 'cookie' and not 'http'
    # (the former being the default, so everything works)

    def test_http_error_codes_auth_fail(self):
        url = 'login?__login=%s&__password=%s' % ('toto', 'pouetA')
        response = self.web_request(url, 'POST')
        self.assertEqual(response.status, 403)

    def test_http_error_codes_auth_succeed(self):
        url = 'login?__login=%s&__password=%s' % (self.admlogin, self.admpassword)
        response = self.web_request(url, 'POST')
        self.assertEqual(response.status, 303)


if __name__ == '__main__':
    unittest_main()
