"""cubicweb.web.views.basecontrollers unit tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import simplejson

from logilab.common.testlib import unittest_main, mock_object

from cubicweb import Binary, NoSelectableObject, ValidationError
from cubicweb.view import STRICT_DOCTYPE
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.uilib import rql_for_eid
from cubicweb.web import INTERNAL_FIELD_VALUE, Redirect, RequestError
from cubicweb.entities.authobjs import CWUser


class EditControllerTC(CubicWebTC):
    def setUp(self):
        CubicWebTC.setUp(self)
        self.failUnless('users' in self.schema.eschema('CWGroup').get_groups('read'))

    def tearDown(self):
        CubicWebTC.tearDown(self)
        self.failUnless('users' in self.schema.eschema('CWGroup').get_groups('read'))

    def test_noparam_edit(self):
        """check behaviour of this controller without any form parameter
        """
        self.assertRaises(ValidationError, self.publish, self.request())

    def test_validation_unique(self):
        """test creation of two linked entities
        """
        user = self.user()
        req = self.request()
        req.form = {'eid': 'X', '__type:X': 'CWUser',
                    'login:X': u'admin', 'edits-login:X': u'',
                    'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'',
                    }
        self.assertRaises(ValidationError, self.publish, req)


    def test_user_editing_itself(self):
        """checking that a manager user can edit itself
        """
        user = self.user()
        basegroups = [str(eid) for eid, in self.execute('CWGroup G WHERE X in_group G, X eid %(x)s', {'x': user.eid})]
        groupeids = [eid for eid, in self.execute('CWGroup G WHERE G name in ("managers", "users")')]
        groups = [str(eid) for eid in groupeids]
        stateeid = [eid for eid, in self.execute('State S WHERE S name "activated"')][0]
        req = self.request()
        req.form = {
            'eid':       `user.eid`,
            '__type:'+`user.eid`:    'CWUser',
            'login:'+`user.eid`:     unicode(user.login),
            'firstname:'+`user.eid`: u'Th\xe9nault',
            'surname:'+`user.eid`:   u'Sylvain',
            'in_group:'+`user.eid`:  groups,
            'in_state:'+`user.eid`:  `stateeid`,
            #
            'edits-login:'+`user.eid`:     unicode(user.login),
            'edits-firstname:'+`user.eid`: u'',
            'edits-surname:'+`user.eid`:   u'',
            'edits-in_group:'+`user.eid`:  basegroups,
            'edits-in_state:'+`user.eid`:  `stateeid`,
            }
        path, params = self.expect_redirect_publish(req)
        e = self.execute('Any X WHERE X eid %(x)s', {'x': user.eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.firstname, u'Th\xe9nault')
        self.assertEquals(e.surname, u'Sylvain')
        self.assertEquals(e.login, user.login)
        self.assertEquals([g.eid for g in e.in_group], groupeids)
        self.assertEquals(e.in_state[0].eid, stateeid)

    def test_user_can_change_its_password(self):
        user = self.create_user('user')
        cnx = self.login('user')
        req = self.request()
        req.form = {
            'eid': `user.eid`, '__type:'+`user.eid`: 'CWUser',
            '__maineid' : str(user.eid),
            'upassword:'+`user.eid`: 'tournicoton',
            'upassword-confirm:'+`user.eid`: 'tournicoton',
            'edits-upassword:'+`user.eid`:  '',
            }
        path, params = self.expect_redirect_publish(req)
        cnx.commit() # commit to check we don't get late validation error for instance
        self.assertEquals(path, 'cwuser/user')
        self.failIf('vid' in params)

    def testr_user_editing_itself_no_relation(self):
        """checking we can edit an entity without specifying some required
        relations (meaning no changes)
        """
        user = self.user()
        groupeids = [eid for eid, in self.execute('CWGroup G WHERE X in_group G, X eid %(x)s', {'x': user.eid})]
        req = self.request()
        req.form = {
            'eid':       `user.eid`,
            '__type:'+`user.eid`:    'CWUser',
            'login:'+`user.eid`:     unicode(user.login),
            'firstname:'+`user.eid`: u'Th\xe9nault',
            'surname:'+`user.eid`:   u'Sylvain',
            #
            'edits-login:'+`user.eid`:     unicode(user.login),
            'edits-firstname:'+`user.eid`: u'',
            'edits-surname:'+`user.eid`:   u'',
            }
        path, params = self.expect_redirect_publish(req)
        e = self.execute('Any X WHERE X eid %(x)s', {'x': user.eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.login, user.login)
        self.assertEquals(e.firstname, u'Th\xe9nault')
        self.assertEquals(e.surname, u'Sylvain')
        self.assertEquals([g.eid for g in e.in_group], groupeids)
        stateeids = [eid for eid, in self.execute('State S WHERE S name "activated"')]
        self.assertEquals([s.eid for s in e.in_state], stateeids)


    def test_create_multiple_linked(self):
        gueid = self.execute('CWGroup G WHERE G name "users"')[0][0]
        req = self.request()
        req.form = {'eid': ['X', 'Y'],

                    '__type:X': 'CWUser',
                    '__maineid' : 'X',
                    'login:X': u'adim', 'edits-login:X': u'',
                    'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'',
                    'surname:X': u'Di Mascio', 'edits-surname:X': '',

                    'in_group:X': `gueid`, 'edits-in_group:X': INTERNAL_FIELD_VALUE,

                    '__type:Y': 'EmailAddress',
                    'address:Y': u'dima@logilab.fr', 'edits-address:Y': '',
                    'use_email:X': 'Y', 'edits-use_email:X': INTERNAL_FIELD_VALUE,
                    }
        path, params = self.expect_redirect_publish(req)
        # should be redirected on the created person
        self.assertEquals(path, 'cwuser/adim')
        e = self.execute('Any P WHERE P surname "Di Mascio"').get_entity(0, 0)
        self.assertEquals(e.surname, 'Di Mascio')
        email = e.use_email[0]
        self.assertEquals(email.address, 'dima@logilab.fr')

    def test_edit_multiple_linked(self):
        peid = self.create_user('adim').eid
        req = self.request()
        req.form = {'eid': [`peid`, 'Y'],
                    '__type:%s'%peid: 'CWUser',
                    'surname:%s'%peid: u'Di Masci', 'edits-surname:%s'%peid: '',

                    '__type:Y': 'EmailAddress',
                    'address:Y': u'dima@logilab.fr', 'edits-address:Y': '',
                    'use_email:%s'%peid: 'Y', 'edits-use_email:%s'%peid: INTERNAL_FIELD_VALUE,

                    '__redirectrql': 'Any X WHERE X eid %s'%peid,
                    }
        path, params = self.expect_redirect_publish(req)
        # should be redirected on the created person
        eid = params['rql'].split()[-1]
        e = self.execute('Any X WHERE X eid %(x)s', {'x': eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.surname, 'Di Masci')
        email = e.use_email[0]
        self.assertEquals(email.address, 'dima@logilab.fr')

        emaileid = email.eid
        req = self.request()
        req.form = {'eid': [`peid`, `emaileid`],
                         '__type:%s'%peid: 'CWUser',
                         'surname:%s'%peid: u'Di Masci', 'edits-surname:%s'%peid: 'Di Masci',
                         '__type:%s'%emaileid: 'EmailAddress',
                         'address:%s'%emaileid: u'adim@logilab.fr', 'edits-address:%s'%emaileid: 'dima@logilab.fr',
                         'use_email:%s'%peid: `emaileid`, 'edits-use_email:%s'%peid: `emaileid`,
                         '__redirectrql': 'Any X WHERE X eid %s'%peid,
                         }
        path, params = self.expect_redirect_publish(req)
        # should be redirected on the created person
        eid = params['rql'].split()[-1]
        e = self.execute('Any X WHERE X eid %(x)s', {'x': eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.surname, 'Di Masci')
        email = e.use_email[0]
        self.assertEquals(email.address, 'adim@logilab.fr')


    def test_password_confirm(self):
        """test creation of two linked entities
        """
        user = self.user()
        req = self.request()
        req.form = {'__cloned_eid:X': user.eid,
                    'eid': 'X', '__type:X': 'CWUser',
                    'login:X': u'toto', 'edits-login:X': u'',
                    'upassword:X': u'toto', 'edits-upassword:X': u'',
                    }
        self.assertRaises(ValidationError, self.publish, req)
        req = self.request()
        req.form = {'__cloned_eid:X': user.eid,
                    'eid': 'X', '__type:X': 'CWUser',
                    'login:X': u'toto', 'edits-login:X': u'',
                    'upassword:X': u'toto',
                    'upassword-confirm:X': u'tutu', 'edits-upassword:X': u'',
                    }
        self.assertRaises(ValidationError, self.publish, req)


    def test_interval_bound_constraint_success(self):
        feid = self.execute('INSERT File X: X data_name "toto.txt", X data %(data)s',
                            {'data': Binary('yo')})[0][0]
        req = self.request()
        req.form = {'eid': ['X'],
                    '__type:X': 'Salesterm',
                    'amount:X': u'-10', 'edits-amount:X': '',
                    'described_by_test:X': str(feid), 'edits-described_by_test:X': INTERNAL_FIELD_VALUE,
                }
        self.assertRaises(ValidationError, self.publish, req)
        req = self.request()
        req.form = {'eid': ['X'],
                    '__type:X': 'Salesterm',
                    'amount:X': u'110', 'edits-amount:X': '',
                    'described_by_test:X': str(feid), 'edits-described_by_test:X': INTERNAL_FIELD_VALUE,
                    }
        self.assertRaises(ValidationError, self.publish, req)
        req = self.request()
        req.form = {'eid': ['X'],
                    '__type:X': 'Salesterm',
                    'amount:X': u'10', 'edits-amount:X': '',
                    'described_by_test:X': str(feid), 'edits-described_by_test:X': INTERNAL_FIELD_VALUE,
                    }
        self.expect_redirect_publish(req)
        # should be redirected on the created
        #eid = params['rql'].split()[-1]
        e = self.execute('Salesterm X').get_entity(0, 0)
        self.assertEquals(e.amount, 10)

    def test_req_pending_insert(self):
        """make sure req's pending insertions are taken into account"""
        tmpgroup = self.request().create_entity('CWGroup', name=u"test")
        user = self.user()
        req = self.request()
        req.set_session_data('pending_insert', set([(user.eid, 'in_group', tmpgroup.eid)]))
        path, params = self.expect_redirect_publish(req)
        usergroups = [gname for gname, in
                      self.execute('Any N WHERE G name N, U in_group G, U eid %(u)s', {'u': user.eid})]
        self.assertUnorderedIterableEquals(usergroups, ['managers', 'test'])
        self.assertEquals(req.get_pending_inserts(), [])


    def test_req_pending_delete(self):
        """make sure req's pending deletions are taken into account"""
        user = self.user()
        groupeid = self.execute('INSERT CWGroup G: G name "test", U in_group G WHERE U eid %(x)s',
                                {'x': user.eid})[0][0]
        usergroups = [gname for gname, in
                      self.execute('Any N WHERE G name N, U in_group G, U eid %(u)s', {'u': user.eid})]
        # just make sure everything was set correctly
        self.assertUnorderedIterableEquals(usergroups, ['managers', 'test'])
        # now try to delete the relation
        req = self.request()
        req.set_session_data('pending_delete', set([(user.eid, 'in_group', groupeid)]))
        path, params = self.expect_redirect_publish(req)
        usergroups = [gname for gname, in
                      self.execute('Any N WHERE G name N, U in_group G, U eid %(u)s', {'u': user.eid})]
        self.assertUnorderedIterableEquals(usergroups, ['managers'])
        self.assertEquals(req.get_pending_deletes(), [])

    def test_custom_attribute_handler(self):
        def custom_login_edit(self, formparams, value, relations):
            formparams['login'] = value.upper()
            relations.append('X login %(login)s')
        CWUser.custom_login_edit = custom_login_edit
        try:
            user = self.user()
            eid = repr(user.eid)
            req = self.request()
            req.form = {
                'eid': eid,
                '__type:'+eid:  'CWUser',
                'login:'+eid: u'foo',
                'edits-login:'+eid:  unicode(user.login),
                }
            path, params = self.expect_redirect_publish(req)
            rset = self.execute('Any L WHERE X eid %(x)s, X login L', {'x': user.eid}, 'x')
            self.assertEquals(rset[0][0], 'FOO')
        finally:
            del CWUser.custom_login_edit

    def test_redirect_apply_button(self):
        redirectrql = rql_for_eid(4012) # whatever
        req = self.request()
        req.form = {
            'eid': 'A', '__type:A': 'BlogEntry',
            '__maineid' : 'A',
            'content:A': u'"13:03:43"', 'edits-content:A': '',
            'title:A': u'huuu', 'edits-title:A': '',
            '__redirectrql': redirectrql,
            '__redirectvid': 'primary',
            '__redirectparams': 'toto=tutu&tata=titi',
            '__form_id': 'edition',
            '__action_apply': '',
            }
        path, params = self.expect_redirect_publish(req)
        self.failUnless(path.startswith('blogentry/'))
        eid = path.split('/')[1]
        self.assertEquals(params['vid'], 'edition')
        self.assertNotEquals(int(eid), 4012)
        self.assertEquals(params['__redirectrql'], redirectrql)
        self.assertEquals(params['__redirectvid'], 'primary')
        self.assertEquals(params['__redirectparams'], 'toto=tutu&tata=titi')

    def test_redirect_ok_button(self):
        redirectrql = rql_for_eid(4012) # whatever
        req = self.request()
        req.form = {
            'eid': 'A', '__type:A': 'BlogEntry',
            '__maineid' : 'A',
            'content:A': u'"13:03:43"', 'edits-content:A': '',
            'title:A': u'huuu', 'edits-title:A': '',
            '__redirectrql': redirectrql,
            '__redirectvid': 'primary',
            '__redirectparams': 'toto=tutu&tata=titi',
            '__form_id': 'edition',
            }
        path, params = self.expect_redirect_publish(req)
        self.assertEquals(path, 'view')
        self.assertEquals(params['rql'], redirectrql)
        self.assertEquals(params['vid'], 'primary')
        self.assertEquals(params['tata'], 'titi')
        self.assertEquals(params['toto'], 'tutu')

    def test_redirect_delete_button(self):
        req = self.request()
        eid = req.create_entity('BlogEntry', title=u'hop', content=u'hop').eid
        req.form = {'eid': str(eid), '__type:%s'%eid: 'BlogEntry',
                    '__action_delete': ''}
        path, params = self.expect_redirect_publish(req)
        self.assertEquals(path, 'blogentry')
        self.assertEquals(params, {u'__message': u'entity deleted'})
        eid = req.create_entity('EmailAddress', address=u'hop@logilab.fr').eid
        self.execute('SET X use_email E WHERE E eid %(e)s, X eid %(x)s',
                     {'x': self.session.user.eid, 'e': eid}, 'x')
        self.commit()
        req = req
        req.form = {'eid': str(eid), '__type:%s'%eid: 'EmailAddress',
                    '__action_delete': ''}
        path, params = self.expect_redirect_publish(req)
        self.assertEquals(path, 'cwuser/admin')
        self.assertEquals(params, {u'__message': u'entity deleted'})
        eid1 = req.create_entity('BlogEntry', title=u'hop', content=u'hop').eid
        eid2 = req.create_entity('EmailAddress', address=u'hop@logilab.fr').eid
        req = self.request()
        req.form = {'eid': [str(eid1), str(eid2)],
                    '__type:%s'%eid1: 'BlogEntry',
                    '__type:%s'%eid2: 'EmailAddress',
                    '__action_delete': ''}
        path, params = self.expect_redirect_publish(req)
        self.assertEquals(path, 'view')
        self.assertEquals(params, {u'__message': u'entities deleted'})

    def test_nonregr_egroup_etype_editing(self):
        """non-regression test checking that a manager user can edit a CWEType entity (CWGroup)
        """
        groupeids = [eid for eid, in self.execute('CWGroup G WHERE G name "managers"')]
        groups = [str(eid) for eid in groupeids]
        eeetypeeid = self.execute('CWEType X WHERE X name "CWGroup"')[0][0]
        basegroups = [str(eid) for eid, in self.execute('CWGroup G WHERE X read_permission G, X eid %(x)s', {'x': eeetypeeid})]
        req = self.request()
        req.form = {
            'eid':      `eeetypeeid`,
            '__type:'+`eeetypeeid`:   'CWEType',
            'name:'+`eeetypeeid`:     u'CWGroup',
            'final:'+`eeetypeeid`:    False,
            'meta:'+`eeetypeeid`:     True,
            'description:'+`eeetypeeid`:     u'users group',
            'read_permission:'+`eeetypeeid`:  groups,
            #
            'edits-name:'+`eeetypeeid`:     u'CWGroup',
            'edits-final:'+`eeetypeeid`:    False,
            'edits-meta:'+`eeetypeeid`:     True,
            'edits-description:'+`eeetypeeid`:     u'users group',
            'edits-read_permission:'+`eeetypeeid`:  basegroups,
            }
        try:
            path, params = self.expect_redirect_publish(req)
            e = self.execute('Any X WHERE X eid %(x)s', {'x': eeetypeeid}, 'x').get_entity(0, 0)
            self.assertEquals(e.name, 'CWGroup')
            self.assertEquals([g.eid for g in e.read_permission], groupeids)
        finally:
            # restore
            self.execute('SET X read_permission Y WHERE X name "CWGroup", Y eid IN (%s), NOT X read_permission Y' % (','.join(basegroups)))
            self.commit()

    def test_nonregr_eetype_etype_editing(self):
        """non-regression test checking that a manager user can edit a CWEType entity (CWEType)
        """
        groupeids = sorted(eid for eid, in self.execute('CWGroup G WHERE G name in ("managers", "users")'))
        groups = [str(eid) for eid in groupeids]
        eeetypeeid = self.execute('CWEType X WHERE X name "CWEType"')[0][0]
        basegroups = [str(eid) for eid, in self.execute('CWGroup G WHERE X read_permission G, X eid %(x)s', {'x': eeetypeeid})]
        req = self.request()
        req.form = {
            'eid':      `eeetypeeid`,
            '__type:'+`eeetypeeid`:  'CWEType',
            'name:'+`eeetypeeid`:     u'CWEType',
            'final:'+`eeetypeeid`:    False,
            'meta:'+`eeetypeeid`:     True,
            'description:'+`eeetypeeid`:     u'users group',
            'read_permission:'+`eeetypeeid`:  groups,

            'edits-name:'+`eeetypeeid`:     u'CWEType',
            'edits-final:'+`eeetypeeid`:    False,
            'edits-meta:'+`eeetypeeid`:     True,
            'edits-description:'+`eeetypeeid`:     u'users group',
            'edits-read_permission:'+`eeetypeeid`:  basegroups,
            }
        try:
            path, params = self.expect_redirect_publish(req)
            e = self.execute('Any X WHERE X eid %(x)s', {'x': eeetypeeid}, 'x').get_entity(0, 0)
            self.assertEquals(e.name, 'CWEType')
            self.assertEquals(sorted(g.eid for g in e.read_permission), groupeids)
        finally:
            # restore
            self.execute('SET X read_permission Y WHERE X name "CWEType", Y eid IN (%s), NOT X read_permission Y' % (','.join(basegroups)))
            self.commit()

    def test_nonregr_strange_text_input(self):
        """non-regression test checking text input containing "13:03:43"

        this seems to be postgres (tsearch?) specific
        """
        req = self.request()
        req.form = {
            'eid': 'A', '__type:A': 'BlogEntry',
            '__maineid' : 'A',
            'title:A': u'"13:03:40"', 'edits-title:A': '',
            'content:A': u'"13:03:43"', 'edits-content:A': ''}
        path, params = self.expect_redirect_publish(req)
        self.failUnless(path.startswith('blogentry/'))
        eid = path.split('/')[1]
        e = self.execute('Any C, T WHERE C eid %(x)s, C content T', {'x': eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.title, '"13:03:40"')
        self.assertEquals(e.content, '"13:03:43"')


    def test_nonregr_multiple_empty_email_addr(self):
        gueid = self.execute('CWGroup G WHERE G name "users"')[0][0]
        req = self.request()
        req.form = {'eid': ['X', 'Y'],

                    '__type:X': 'CWUser',
                    'login:X': u'adim', 'edits-login:X': u'',
                    'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'',
                    'in_group:X': `gueid`, 'edits-in_group:X': INTERNAL_FIELD_VALUE,

                    '__type:Y': 'EmailAddress',
                    'address:Y': u'', 'edits-address:Y': '',
                    'alias:Y': u'', 'edits-alias:Y': '',
                    'use_email:X': 'Y', 'edits-use_email:X': INTERNAL_FIELD_VALUE,
                    }
        self.assertRaises(ValidationError, self.publish, req)

    def test_nonregr_copy(self):
        user = self.user()
        req = self.request()
        req.form = {'__cloned_eid:X': user.eid,
                    'eid': 'X', '__type:X': 'CWUser',
                    '__maineid' : 'X',
                    'login:X': u'toto', 'edits-login:X': u'',
                    'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'',
                    }
        path, params = self.expect_redirect_publish(req)
        self.assertEquals(path, 'cwuser/toto')
        e = self.execute('Any X WHERE X is CWUser, X login "toto"').get_entity(0, 0)
        self.assertEquals(e.login, 'toto')
        self.assertEquals(e.in_group[0].name, 'managers')


    def test_nonregr_rollback_on_validation_error(self):
        p = self.create_user("doe")
        # do not try to skip 'primary_email' for this test
        old_skips = p.__class__.skip_copy_for
        p.__class__.skip_copy_for = ()
        try:
            e = self.request().create_entity('EmailAddress', address=u'doe@doe.com')
            self.execute('SET P use_email E, P primary_email E WHERE P eid %(p)s, E eid %(e)s',
                         {'p' : p.eid, 'e' : e.eid})
            req = self.request()
            req.form = {'__cloned_eid:X': p.eid,
                        'eid': 'X', '__type:X': 'CWUser',
                        'login': u'dodo', 'edits-login': u'dodo',
                        'surname:X': u'Boom', 'edits-surname:X': u'',
                        '__errorurl' : "whatever but required",
                             }
            # try to emulate what really happens in the web application
            # 1/ validate form => EditController.publish raises a ValidationError
            #    which fires a Redirect
            # 2/ When re-publishing the copy form, the publisher implicitly commits
            try:
                self.app.publish('edit', req)
            except Redirect:
                req.form['rql'] = 'Any X WHERE X eid %s' % p.eid
                req.form['vid'] = 'copy'
                self.app.publish('view', req)
            rset = self.execute('CWUser P WHERE P surname "Boom"')
            self.assertEquals(len(rset), 0)
        finally:
            p.__class__.skip_copy_for = old_skips


class EmbedControllerTC(CubicWebTC):

    def test_nonregr_embed_publish(self):
        # This test looks a bit stupid but at least it will probably
        # fail if the controller API changes and if EmbedController is not
        # updated (which is what happened before this test)
        req = self.request()
        req.form['url'] = 'http://intranet.logilab.fr/'
        controller = self.vreg['controllers'].select('embed', req)
        result = controller.publish(rset=None)


class ReportBugControllerTC(CubicWebTC):

    def test_usable_by_guets(self):
        self.login('anon')
        self.vreg['controllers'].select('reportbug', self.request())


class SendMailControllerTC(CubicWebTC):

    def test_not_usable_by_guets(self):
        self.login('anon')
        self.assertRaises(NoSelectableObject,
                          self.vreg['controllers'].select, 'sendmail', self.request())



class JSONControllerTC(CubicWebTC):

    def ctrl(self, req=None):
        req = req or self.request(url='http://whatever.fr/')
        return self.vreg['controllers'].select('json', req)

    def setup_database(self):
        req = self.request()
        self.pytag = req.create_entity('Tag', name=u'python')
        self.cubicwebtag = req.create_entity('Tag', name=u'cubicweb')
        self.john = self.create_user(u'John')


    ## tests ##################################################################
    def test_simple_exec(self):
        req = self.request(rql='CWUser P WHERE P login "John"',
                           pageid='123', fname='view')
        ctrl = self.ctrl(req)
        rset = self.john.as_rset()
        rset.req = req
        source = ctrl.publish()
        self.failUnless(source.startswith('<?xml version="1.0"?>\n' + STRICT_DOCTYPE +
                                          u'<div xmlns="http://www.w3.org/1999/xhtml" xmlns:cubicweb="http://www.logilab.org/2008/cubicweb">')
                        )
        req.xhtml_browser = lambda: False
        source = ctrl.publish()
        self.failUnless(source.startswith('<div>'))

#     def test_json_exec(self):
#         rql = 'Any T,N WHERE T is Tag, T name N'
#         ctrl = self.ctrl(self.request(mode='json', rql=rql, pageid='123'))
#         self.assertEquals(ctrl.publish(),
#                           simplejson.dumps(self.execute(rql).rows))

    def test_remote_add_existing_tag(self):
        self.remote_call('tag_entity', self.john.eid, ['python'])
        self.assertUnorderedIterableEquals([tname for tname, in self.execute('Any N WHERE T is Tag, T name N')],
                             ['python', 'cubicweb'])
        self.assertEquals(self.execute('Any N WHERE T tags P, P is CWUser, T name N').rows,
                          [['python']])

    def test_remote_add_new_tag(self):
        self.remote_call('tag_entity', self.john.eid, ['javascript'])
        self.assertUnorderedIterableEquals([tname for tname, in self.execute('Any N WHERE T is Tag, T name N')],
                             ['python', 'cubicweb', 'javascript'])
        self.assertEquals(self.execute('Any N WHERE T tags P, P is CWUser, T name N').rows,
                          [['javascript']])

    def test_pending_insertion(self):
        res, req = self.remote_call('add_pending_inserts', [['12', 'tags', '13']])
        deletes = req.get_pending_deletes()
        self.assertEquals(deletes, [])
        inserts = req.get_pending_inserts()
        self.assertEquals(inserts, ['12:tags:13'])
        res, req = self.remote_call('add_pending_inserts', [['12', 'tags', '14']])
        deletes = req.get_pending_deletes()
        self.assertEquals(deletes, [])
        inserts = req.get_pending_inserts()
        self.assertEquals(inserts, ['12:tags:13', '12:tags:14'])
        inserts = req.get_pending_inserts(12)
        self.assertEquals(inserts, ['12:tags:13', '12:tags:14'])
        inserts = req.get_pending_inserts(13)
        self.assertEquals(inserts, ['12:tags:13'])
        inserts = req.get_pending_inserts(14)
        self.assertEquals(inserts, ['12:tags:14'])
        req.remove_pending_operations()

    def test_pending_deletion(self):
        res, req = self.remote_call('add_pending_delete', ['12', 'tags', '13'])
        inserts = req.get_pending_inserts()
        self.assertEquals(inserts, [])
        deletes = req.get_pending_deletes()
        self.assertEquals(deletes, ['12:tags:13'])
        res, req = self.remote_call('add_pending_delete', ['12', 'tags', '14'])
        inserts = req.get_pending_inserts()
        self.assertEquals(inserts, [])
        deletes = req.get_pending_deletes()
        self.assertEquals(deletes, ['12:tags:13', '12:tags:14'])
        deletes = req.get_pending_deletes(12)
        self.assertEquals(deletes, ['12:tags:13', '12:tags:14'])
        deletes = req.get_pending_deletes(13)
        self.assertEquals(deletes, ['12:tags:13'])
        deletes = req.get_pending_deletes(14)
        self.assertEquals(deletes, ['12:tags:14'])
        req.remove_pending_operations()

    def test_remove_pending_operations(self):
        self.remote_call('add_pending_delete', ['12', 'tags', '13'])
        _, req = self.remote_call('add_pending_inserts', [['12', 'tags', '14']])
        inserts = req.get_pending_inserts()
        self.assertEquals(inserts, ['12:tags:14'])
        deletes = req.get_pending_deletes()
        self.assertEquals(deletes, ['12:tags:13'])
        req.remove_pending_operations()
        self.assertEquals(req.get_pending_deletes(), [])
        self.assertEquals(req.get_pending_inserts(), [])


    def test_add_inserts(self):
        res, req = self.remote_call('add_pending_inserts',
                                    [('12', 'tags', '13'), ('12', 'tags', '14')])
        inserts = req.get_pending_inserts()
        self.assertEquals(inserts, ['12:tags:13', '12:tags:14'])
        req.remove_pending_operations()


    # silly tests
    def test_external_resource(self):
        self.assertEquals(self.remote_call('external_resource', 'RSS_LOGO')[0],
                          simplejson.dumps(self.request().external_resource('RSS_LOGO')))
    def test_i18n(self):
        self.assertEquals(self.remote_call('i18n', ['bimboom'])[0],
                          simplejson.dumps(['bimboom']))

    def test_format_date(self):
        self.assertEquals(self.remote_call('format_date', '2007-01-01 12:00:00')[0],
                          simplejson.dumps('2007/01/01'))




if __name__ == '__main__':
    unittest_main()
