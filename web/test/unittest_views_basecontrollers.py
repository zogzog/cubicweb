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
"""cubicweb.web.views.basecontrollers unit tests"""

from urlparse import urlsplit, urlunsplit, urljoin
# parse_qs is deprecated in cgi and has been moved to urlparse in Python 2.6
try:
    from urlparse import parse_qs as url_parse_query
except ImportError:
    from cgi import parse_qs as url_parse_query
from logilab.common.testlib import unittest_main
from logilab.common.decorators import monkeypatch

from cubicweb import Binary, NoSelectableObject, ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.utils import json_dumps
from cubicweb.uilib import rql_for_eid
from cubicweb.web import Redirect, RemoteCallFailed
import cubicweb.server.session
from cubicweb.server.session import Connection as OldConnection
from cubicweb.web.views.autoform import get_pending_inserts, get_pending_deletes
from cubicweb.web.views.basecontrollers import JSonController, xhtmlize, jsonize
from cubicweb.web.views.ajaxcontroller import ajaxfunc, AjaxFunction
import cubicweb.transaction as tx
from cubicweb.server.hook import Hook, Operation
from cubicweb.predicates import is_instance

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
                cm.exception.translate(unicode)
                self.assertEqual({'login-subject': 'the value "admin" is already used, use another one'},
                                 cm.exception.errors)

    def test_user_editing_itself(self):
        """checking that a manager user can edit itself
        """
        with self.admin_access.web_request() as req:
            user = req.user
            groupeids = [eid for eid, in req.execute('CWGroup G WHERE G name '
                                                     'in ("managers", "users")')]
            groups = [unicode(eid) for eid in groupeids]
            eid = unicode(user.eid)
            req.form = {
                'eid': eid, '__type:'+eid: 'CWUser',
                '_cw_entity_fields:'+eid: 'login-subject,firstname-subject,surname-subject,in_group-subject',
                'login-subject:'+eid:     unicode(user.login),
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
            self.create_user(cnx, 'user')
            cnx.commit()
        with self.new_access('user').web_request() as req:
            eid = unicode(req.user.eid)
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
            eid = unicode(user.eid)
            req.form = {
                'eid':       eid,
                '__type:'+eid:    'CWUser',
                '_cw_entity_fields:'+eid: 'login-subject,firstname-subject,surname-subject',
                'login-subject:'+eid:     unicode(user.login),
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
                        'in_group-subject:X': unicode(gueid),

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
                        'data-subject:Y': (u'coucou.txt', Binary('coucou')),
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
                        'data-subject:Y': (u'coucou.txt', Binary('coucou')),
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
            cwrelation = unicode(req.execute('CWEType X WHERE X name "CWSource"')[0][0])
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
            peid = unicode(self.create_user(req, 'adim').eid)
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
            emaileid = unicode(email.eid)
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
                        '__cloned_eid:X': unicode(user.eid), '__type:X': 'CWUser',
                        '_cw_entity_fields:X': 'login-subject,upassword-subject',
                        'login-subject:X': u'toto',
                        'upassword-subject:X': u'toto',
                        }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            self.assertEqual({'upassword-subject': u'password and confirmation don\'t match'},
                             cm.exception.errors)
            req.form = {'__cloned_eid:X': unicode(user.eid),
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
                               {'data': Binary('yo')})[0][0]
            cnx.commit()

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'-10',
                        'described_by_test-subject:X': unicode(feid),
                    }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            cm.exception.translate(unicode)
            self.assertEqual({'amount-subject': 'value -10 must be >= 0'},
                             cm.exception.errors)

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'110',
                        'described_by_test-subject:X': unicode(feid),
                        }
            with self.assertRaises(ValidationError) as cm:
                self.ctrl_publish(req)
            cm.exception.translate(unicode)
            self.assertEqual(cm.exception.errors, {'amount-subject': 'value 110 must be <= 100'})

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'10',
                        'described_by_test-subject:X': unicode(feid),
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
                               {'data': Binary('yo')})[0][0]
            seid = cnx.create_entity('Salesterm', amount=0, described_by_test=feid).eid
            cnx.commit()

        # ensure a value that violate a constraint is properly detected
        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': [unicode(seid)],
                        '__type:%s'%seid: 'Salesterm',
                        '_cw_entity_fields:%s'%seid: 'amount-subject',
                        'amount-subject:%s'%seid: u'-10',
                    }
            self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [false, [%s, {"amount-subject": "value -10 must be >= 0"}], null], null);
</script>'''%seid, self.ctrl_publish(req, 'validateform'))

        # ensure a value that comply a constraint is properly processed
        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': [unicode(seid)],
                        '__type:%s'%seid: 'Salesterm',
                        '_cw_entity_fields:%s'%seid: 'amount-subject',
                        'amount-subject:%s'%seid: u'20',
                    }
            self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [true, "http://testing.fr/cubicweb/view", null], null);
</script>''', self.ctrl_publish(req, 'validateform'))
            self.assertEqual(20, req.execute('Any V WHERE X amount V, X eid %(eid)s',
                                             {'eid': seid})[0][0])

        with self.admin_access.web_request(rollbackfirst=True) as req:
            req.form = {'eid': ['X'],
                        '__type:X': 'Salesterm',
                        '_cw_entity_fields:X': 'amount-subject,described_by_test-subject',
                        'amount-subject:X': u'0',
                        'described_by_test-subject:X': unicode(feid),
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
</script>''', self.ctrl_publish(req, 'validateform'))

            self.assertMultiLineEqual('''<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, null, [true, "http://testing.fr/cubicweb/view", null], null);
</script>''', self.ctrl_publish(req, 'validateform'))

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
            req.form = {'eid': unicode(eid), '__type:%s'%eid: 'BlogEntry',
                        '__action_delete': ''}
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'blogentry')
            self.assertIn('_cwmsgid', params)
            eid = req.create_entity('EmailAddress', address=u'hop@logilab.fr').eid
            req.execute('SET X use_email E WHERE E eid %(e)s, X eid %(x)s',
                        {'x': self.session.user.eid, 'e': eid})
            req.cnx.commit()
            req.form = {'eid': unicode(eid), '__type:%s'%eid: 'EmailAddress',
                        '__action_delete': ''}
            path, params = self.expect_redirect_handle_request(req, 'edit')
            self.assertEqual(path, 'cwuser/admin')
            self.assertIn('_cwmsgid', params)
            eid1 = req.create_entity('BlogEntry', title=u'hop', content=u'hop').eid
            eid2 = req.create_entity('EmailAddress', address=u'hop@logilab.fr').eid
            req.form = {'eid': [unicode(eid1), unicode(eid2)],
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

    def test_nonregr_eetype_etype_editing(self):
        """non-regression test checking that a manager user can edit a CWEType entity
        """
        with self.admin_access.web_request() as req:
            groupeids = sorted(eid
                               for eid, in req.execute('CWGroup G '
                                                       'WHERE G name in ("managers", "users")'))
            groups = [unicode(eid) for eid in groupeids]
            cwetypeeid = req.execute('CWEType X WHERE X name "CWEType"')[0][0]
            basegroups = [unicode(eid)
                          for eid, in req.execute('CWGroup G '
                                                  'WHERE X read_permission G, X eid %(x)s',
                                                  {'x': cwetypeeid})]
            cwetypeeid = unicode(cwetypeeid)
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
                        'in_group-subject:X': `gueid`,

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
        with self.admin_access.web_request() as req:
            p = self.create_user(req, "doe")
            # do not try to skip 'primary_email' for this test
            old_skips = p.__class__.skip_copy_for
            p.__class__.skip_copy_for = ()
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
                    self.app_handle_request(req, 'edit')
                except Redirect:
                    req.form['rql'] = 'Any X WHERE X eid %s' % p.eid
                    req.form['vid'] = 'copy'
                    self.app_handle_request(req, 'view')
                rset = req.execute('CWUser P WHERE P surname "Boom"')
                self.assertEqual(len(rset), 0)
            finally:
                p.__class__.skip_copy_for = old_skips

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
                            'data-subject:Y': (u'coucou.txt', Binary('coucou')),
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
        with self.new_access('anon').web_request() as req:
            self.assertRaises(NoSelectableObject,
                              self.vreg['controllers'].select, 'reportbug', req)
        with self.new_access('anon').web_request(description='hop') as req:
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
            self.assertTrue(source.startswith('<div>'))

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

    def test_pending_insertion(self):
        with self.remote_calling('add_pending_inserts', [['12', 'tags', '13']]) as (_, req):
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, [])
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, ['12:tags:13'])
        with self.remote_calling('add_pending_inserts', [['12', 'tags', '14']]) as (_, req):
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, [])
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, ['12:tags:13', '12:tags:14'])
            inserts = get_pending_inserts(req, 12)
            self.assertEqual(inserts, ['12:tags:13', '12:tags:14'])
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
        with self.remote_calling('add_pending_delete', ['12', 'tags', '14']) as (_, req):
            inserts = get_pending_inserts(req)
            self.assertEqual(inserts, [])
            deletes = get_pending_deletes(req)
            self.assertEqual(deletes, ['12:tags:13', '12:tags:14'])
            deletes = get_pending_deletes(req, 12)
            self.assertEqual(deletes, ['12:tags:13', '12:tags:14'])
            deletes = get_pending_deletes(req, 13)
            self.assertEqual(deletes, ['12:tags:13'])
            deletes = get_pending_deletes(req, 14)
            self.assertEqual(deletes, ['12:tags:14'])
            req.remove_pending_operations()

    def test_remove_pending_operations(self):
        with self.remote_calling('add_pending_delete', ['12', 'tags', '13']):
            pass
        with self.remote_calling('add_pending_inserts', [['12', 'tags', '14']]) as (_, req):
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
            self.assertEqual(inserts, ['12:tags:13', '12:tags:14'])
            req.remove_pending_operations()


    # silly tests
    def test_external_resource(self):
        with self.remote_calling('external_resource', 'RSS_LOGO') as (res, _):
            self.assertEqual(json_dumps(self.config.uiprops['RSS_LOGO']),
                             res)

    def test_i18n(self):
        with self.remote_calling('i18n', ['bimboom']) as (res, _):
            self.assertEqual(json_dumps(['bimboom']), res)

    def test_format_date(self):
        with self.remote_calling('format_date', '2007-01-01 12:00:00') as (res, _):
            self.assertEqual(json_dumps('2007/01/01'), res)

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


class JSonControllerTC(AjaxControllerTC):
    # NOTE: this class performs the same tests as AjaxController but with
    #       deprecated 'json' controller (i.e. check backward compatibility)
    tested_controller = 'json'

    def setUp(self):
        super(JSonControllerTC, self).setUp()
        self.exposed_remote_funcs = [fname for fname in dir(JSonController)
                                     if fname.startswith('js_')]

    def tearDown(self):
        super(JSonControllerTC, self).tearDown()
        for funcname in dir(JSonController):
            # remove functions added dynamically during tests
            if funcname.startswith('js_') and funcname not in self.exposed_remote_funcs:
                delattr(JSonController, funcname)

    def test_monkeypatch_jsoncontroller(self):
        with self.assertRaises(RemoteCallFailed):
            with self.remote_calling('foo'):
                pass
        @monkeypatch(JSonController)
        def js_foo(self):
            return u'hello'
        with self.remote_calling('foo') as (res, _):
            self.assertEqual(res, u'hello')

    def test_monkeypatch_jsoncontroller_xhtmlize(self):
        with self.assertRaises(RemoteCallFailed):
            with self.remote_calling('foo'):
                pass
        @monkeypatch(JSonController)
        @xhtmlize
        def js_foo(self):
            return u'hello'
        with self.remote_calling('foo') as (res, _):
            self.assertEqual(u'<div>hello</div>', res)

    def test_monkeypatch_jsoncontroller_jsonize(self):
        with self.assertRaises(RemoteCallFailed):
            with self.remote_calling('foo'):
                pass
        @monkeypatch(JSonController)
        @jsonize
        def js_foo(self):
            return 12
        with self.remote_calling('foo') as (res, _):
            self.assertEqual(res, '12')

    def test_monkeypatch_jsoncontroller_stdfunc(self):
        @monkeypatch(JSonController)
        @jsonize
        def js_reledit_form(self):
            return 12
        with self.remote_calling('reledit_form') as (res, _):
            self.assertEqual(res, '12')


class UndoControllerTC(CubicWebTC):

    def setUp(self):
        class Connection(OldConnection):
            """Force undo feature to be turned on in all case"""
            undo_actions = property(lambda tx: True, lambda x, y:None)
        cubicweb.server.session.Connection = Connection
        super(UndoControllerTC, self).setUp()

    def tearDown(self):
        super(UndoControllerTC, self).tearDown()
        cubicweb.server.session.Connection = OldConnection

    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            self.toto = self.create_user(cnx, 'toto',
                                         password='toto',
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
            query_dict = url_parse_query(query)
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

    def test_redirect_default(self):
        with self.admin_access.web_request() as req:
            txuuid = self.txuuid_toto_email
            req.form['txuuid'] = txuuid
            req.session.data['breadcrumbs'] = [ urljoin(req.base_url(), path)
                                                for path in ('tata', 'toto',)]
            controller = self.vreg['controllers'].select('undo', req)
            with self.assertRaises(Redirect) as cm:
                result = controller.publish(rset=None)
            self.assertURLPath(cm.exception.location, 'toto')


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

if __name__ == '__main__':
    unittest_main()
