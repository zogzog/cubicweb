from cubicweb.goa.testlib import *

from urllib import unquote

from cubicweb.common import ValidationError
from cubicweb.common.uilib import rql_for_eid

from cubicweb.web import INTERNAL_FIELD_VALUE, Redirect

from cubicweb.goa.goaconfig import GAEConfiguration
from cubicweb.entities.authobjs import EUser


class EditControllerTC(GAEBasedTC):
    
    config = GAEConfiguration('toto')
    config.global_set_option('use-google-auth', False)
    config.global_set_option('schema-type', 'yams')
    config.global_set_option('included-cubes', ())
    config.global_set_option('included-yams-cubes', ('blog',))
    
    MODEL_CLASSES = ()
    from cubicweb.web.views import editcontroller
    from cubicweb.entities import lib
    LOAD_APP_MODULES = (editcontroller, lib)
    
    def setUp(self):
        GAEBasedTC.setUp(self)
        self.req = self.request()
        self.ctrl = self.get_ctrl(self.req)
        
    def get_ctrl(self, req):
        return self.vreg.select(self.vreg.registry_objects('controllers', 'edit'),
                                req=req, appli=self)

    def publish(self, req):
        assert req is self.ctrl.req
        try:
            result = self.ctrl.publish()
            req.cnx.commit()
        except Redirect:
            req.cnx.commit()
            raise
        except:
            req.cnx.rollback()
            raise
        return result

    def expect_redirect_publish(self, req=None):
        if req is not None:
            self.ctrl = self.get_ctrl(req)
        else:
            req = self.req
        try:
            res = self.publish(req)
        except Redirect, ex:
            try:
                path, params = ex.location.split('?', 1)
            except:
                path, params = ex.location, ""
            req._url = path
            cleanup = lambda p: (p[0], unquote(p[1]))
            params = dict(cleanup(p.split('=', 1)) for p in params.split('&') if p)
            return req.relative_path(False), params # path.rsplit('/', 1)[-1], params
        else:
            self.fail('expected a Redirect exception')

    def test_noparam_edit(self):
        """check behaviour of this controller without any form parameter"""
        self.req.form = {}
        self.assertRaises(ValidationError, self.publish, self.req)
        
    def test_validation_unique(self):
        """test creation of two linked entities"""        
        user = self.user
        self.req.form = {'eid': 'X', '__type:X': 'EUser',
                         'login:X': self.user.login, 'edits-login:X': u'', 
                         'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'', 
                         }
        self.assertRaises(ValidationError, self.publish, self.req)


    def test_user_editing_itself(self):
        """checking that a manager user can edit itself"""
        self.skip('missing actual gae support, retry latter')
        user = self.user
        basegroups = [str(eid) for eid, in self.req.execute('EGroup G WHERE X in_group G, X eid %(x)s', {'x': user.eid})]
        groupeids = [eid for eid, in self.req.execute('EGroup G WHERE G name in ("managers", "users")')]
        groups = [str(eid) for eid in groupeids]
        stateeid = [eid for eid, in self.req.execute('State S WHERE S name "activated"')][0]
        self.req.form = {
            'eid':       user.eid,
            '__type:'+user.eid:    'EUser',
            'login:'+user.eid:     unicode(user.login),
            'firstname:'+user.eid: u'Th\xe9nault',
            'surname:'+user.eid:   u'Sylvain',
            'in_group:'+user.eid:  groups,
            'in_state:'+user.eid:  stateeid,
            #
            'edits-login:'+user.eid:     unicode(user.login),
            'edits-firstname:'+user.eid: u'',
            'edits-surname:'+user.eid:   u'',
            'edits-in_group:'+user.eid:  basegroups,
            'edits-in_state:'+user.eid:  stateeid,
            }
        path, params = self.expect_redirect_publish()
        e = self.req.execute('Any X WHERE X eid %(x)s', {'x': user.eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.firstname, u'Th\xe9nault')
        self.assertEquals(e.surname, u'Sylvain')
        self.assertEquals(e.login, user.login)
        self.assertEquals([g.eid for g in e.in_group], groupeids)
        self.assertEquals(e.in_state[0].eid, stateeid)

    def test_user_can_change_its_password(self):
        user = self.create_user('user')
        cnx = self.login('user')
        req = self.request()
        #self.assertEquals(self.ctrl.schema['EUser']._groups['read'],
        #                  ('managers', 'users'))
        req.form = {
            'eid': user.eid, '__type:'+user.eid: 'EUser',
            '__maineid' : str(user.eid),
            'upassword:'+user.eid: 'tournicoton',
            'upassword-confirm:'+user.eid: 'tournicoton',
            'edits-upassword:'+user.eid:  '',
            }
        path, params = self.expect_redirect_publish(req)
        cnx.commit() # commit to check we don't get late validation error for instance
        self.assertEquals(path, 'euser/user')
        self.failIf('vid' in params)

    def test_user_editing_itself_no_relation(self):
        """checking we can edit an entity without specifying some required
        relations (meaning no changes)
        """
        user = self.user
        groupeids = [eid for eid, in self.req.execute('EGroup G WHERE X in_group G, X eid %(x)s', {'x': user.eid})]
        self.req.form = {
            'eid':       user.eid,
            '__type:'+user.eid:    'EUser',
            'login:'+user.eid:     unicode(user.login),
            'firstname:'+user.eid: u'Th\xe9nault',
            'surname:'+user.eid:   u'Sylvain',
            #
            'edits-login:'+user.eid:     unicode(user.login),
            'edits-firstname:'+user.eid: u'',
            'edits-surname:'+user.eid:   u'',
            }
        path, params = self.expect_redirect_publish()
        self.req.drop_entity_cache(user.eid)
        e = self.req.execute('Any X WHERE X eid %(x)s', {'x': user.eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.login, user.login)
        self.assertEquals(e.firstname, u'Th\xe9nault')
        self.assertEquals(e.surname, u'Sylvain')
        self.assertUnorderedIterableEquals([g.eid for g in e.in_group], groupeids)
        #stateeids = [eid for eid, in self.req.execute('State S WHERE S name "activated"')]
        #self.assertEquals([s.eid for s in e.in_state], stateeids)
        
        
    def test_create_multiple_linked(self):
        gueid = self.req.execute('EGroup G WHERE G name "users"')[0][0]
        self.req.form = {'eid': ['X', 'Y'],
                         
                         '__type:X': 'EUser',
                         '__maineid' : 'X',
                         'login:X': u'adim', 'edits-login:X': u'', 
                         'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'', 
                         'surname:X': u'Di Mascio', 'edits-surname:X': '',

                         'in_group:X': gueid, 'edits-in_group:X': INTERNAL_FIELD_VALUE, 
                         
                         '__type:Y': 'EmailAddress',
                         'address:Y': u'dima@logilab.fr', 'edits-address:Y': '',
                         'use_email:X': 'Y', 'edits-use_email:X': INTERNAL_FIELD_VALUE, 
                         }
        path, params = self.expect_redirect_publish()
        # should be redirected on the created person
        self.assertEquals(path, 'euser/adim')
        e = self.req.execute('Any P WHERE P surname "Di Mascio"').get_entity(0, 0)
        self.assertEquals(e.surname, 'Di Mascio')
        email = e.use_email[0]
        self.assertEquals(email.address, 'dima@logilab.fr')
        
    def test_edit_multiple_linked(self):
        peid = self.create_user('adim').eid
        self.req.form = {'eid': [peid, 'Y'],
                         '__type:%s'%peid: 'EUser',
                         'surname:%s'%peid: u'Di Masci', 'edits-surname:%s'%peid: '',
                         
                         '__type:Y': 'EmailAddress',
                         'address:Y': u'dima@logilab.fr', 'edits-address:Y': '',
                         'use_email:%s'%peid: 'Y', 'edits-use_email:%s'%peid: INTERNAL_FIELD_VALUE,
                         
                         '__redirectrql': 'Any X WHERE X eid %s'%peid,
                         }
        path, params = self.expect_redirect_publish()
        # should be redirected on the created person
        eid = params['rql'].split()[-1]
        e = self.req.execute('Any X WHERE X eid %(x)s', {'x': eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.surname, 'Di Masci')
        email = e.use_email[0]
        self.assertEquals(email.address, 'dima@logilab.fr')
        
        emaileid = email.eid
        self.req.form = {'eid': [peid, emaileid],
                         '__type:%s'%peid: 'EUser',
                         'surname:%s'%peid: u'Di Masci', 'edits-surname:%s'%peid: 'Di Masci',
                         '__type:%s'%emaileid: 'EmailAddress',
                         'address:%s'%emaileid: u'adim@logilab.fr', 'edits-address:%s'%emaileid: 'dima@logilab.fr',
                         'use_email:%s'%peid: emaileid, 'edits-use_email:%s'%peid: emaileid, 
                         '__redirectrql': 'Any X WHERE X eid %s'%peid,
                         }
        path, params = self.expect_redirect_publish()
        # should be redirected on the created person
        eid = params['rql'].split()[-1]
        # XXX this should not be necessary, it isn't with regular cubicweb
        self.req._eid_cache = {}
        e = self.req.execute('Any X WHERE X eid %(x)s', {'x': eid}, 'x').get_entity(0, 0)
        self.assertEquals(e.surname, 'Di Masci')
        email = e.use_email[0]
        self.assertEquals(email.address, 'adim@logilab.fr')

        
    def test_password_confirm(self):
        """test creation of two linked entities
        """        
        user = self.user
        self.req.form = {'__cloned_eid:X': user.eid,
                         'eid': 'X', '__type:X': 'EUser',
                         'login:X': u'toto', 'edits-login:X': u'', 
                         'upassword:X': u'toto', 'edits-upassword:X': u'', 
                         }
        self.assertRaises(ValidationError, self.publish, self.req)
        self.req.form = {'__cloned_eid:X': user.eid,
                         'eid': 'X', '__type:X': 'EUser',
                         'login:X': u'toto', 'edits-login:X': u'', 
                         'upassword:X': u'toto', 'upassword-confirm:X': u'tutu', 'edits-upassword:X': u'', 
                         }
        self.assertRaises(ValidationError, self.publish, self.req)


    def test_req_pending_insert(self):
        """make sure req's pending insertions are taken into account"""
        tmpgroup = self.add_entity('EGroup', name=u"test")
        user = self.user
        self.req.set_session_data('pending_insert', set([(user.eid, 'in_group', tmpgroup.eid)]))
        path, params = self.expect_redirect_publish()
        usergroups = [gname for gname, in
                      self.req.execute('Any N WHERE G name N, U in_group G, U eid %(u)s', {'u': user.eid})]
        self.assertUnorderedIterableEquals(usergroups, ['managers', 'users', 'test'])
        self.assertEquals(self.req.get_pending_inserts(), [])


    def test_req_pending_delete(self):
        """make sure req's pending deletions are taken into account"""
        user = self.user
        groupeid = self.req.execute('INSERT EGroup G: G name "test", U in_group G WHERE U eid %(x)s',
                                    {'x': user.eid})[0][0]
        usergroups = [gname for gname, in
                      self.req.execute('Any N WHERE G name N, U in_group G, U eid %(u)s', {'u': user.eid})]
        # just make sure everything was set correctly
        self.assertUnorderedIterableEquals(usergroups, ['managers', 'users', 'test'])
        # now try to delete the relation
        self.req.set_session_data('pending_delete', set([(user.eid, 'in_group', groupeid)]))
        path, params = self.expect_redirect_publish()
        usergroups = [gname for gname, in
                      self.req.execute('Any N WHERE G name N, U in_group G, U eid %(u)s', {'u': user.eid})]
        self.assertUnorderedIterableEquals(usergroups, ['managers', 'users'])
        #self.assertUnorderedIterableEquals(usergroups, ['managers'])
        self.assertEquals(self.req.get_pending_deletes(), [])

    def test_custom_attribute_handler(self):
        def custom_login_edit(self, formparams, value, relations):
            formparams['login'] = value.upper()
            relations.append('X login %(login)s')
        EUser.custom_login_edit = custom_login_edit
        try:
            user = self.user
            eid = repr(user.eid)
            self.req.form = {
                'eid': eid,
                '__type:'+eid:  'EUser',
                'login:'+eid: u'foo',
                'edits-login:'+eid:  unicode(user.login),
                }
            path, params = self.expect_redirect_publish()
            rset = self.req.execute('Any L WHERE X eid %(x)s, X login L', {'x': user.eid}, 'x')
            self.assertEquals(rset[0][0], 'FOO')
        finally:
            del EUser.custom_login_edit
        
    def test_redirect_apply_button(self):
        redirectrql = rql_for_eid(4012) # whatever
        self.req.form = {
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
        path, params = self.expect_redirect_publish()
        self.failUnless(path.startswith('blogentry/'))
        eid = path.split('/')[1]
        self.assertEquals(params['vid'], 'edition')
        self.assertNotEquals(eid, '4012')
        self.assertEquals(params['__redirectrql'], redirectrql)
        self.assertEquals(params['__redirectvid'], 'primary')
        self.assertEquals(params['__redirectparams'], 'toto=tutu&tata=titi')

    def test_redirect_ok_button(self):
        redirectrql = rql_for_eid(4012) # whatever
        self.req.form = {
                         'eid': 'A', '__type:A': 'BlogEntry',
                         '__maineid' : 'A',
                         'content:A': u'"13:03:43"', 'edits-content:A': '',
                         'title:A': u'huuu', 'edits-title:A': '',
                         '__redirectrql': redirectrql,
                         '__redirectvid': 'primary',
                         '__redirectparams': 'toto=tutu&tata=titi',
                         '__form_id': 'edition',
                         }
        path, params = self.expect_redirect_publish()
        self.assertEquals(path, 'view')
        self.assertEquals(params['rql'], redirectrql)
        self.assertEquals(params['vid'], 'primary')
        self.assertEquals(params['tata'], 'titi')
        self.assertEquals(params['toto'], 'tutu')

    def test_redirect_delete_button(self):
        eid = self.add_entity('BlogEntry', title=u'hop', content=u'hop').eid
        self.req.form = {'eid': str(eid), '__type:%s'%eid: 'BlogEntry',
                         '__action_delete': ''}
        path, params = self.expect_redirect_publish()
        self.assertEquals(path, 'blogentry')
        self.assertEquals(params, {u'__message': u'entity deleted'})
        eid = self.add_entity('EmailAddress', address=u'hop@logilab.fr').eid
        self.req.execute('SET X use_email E WHERE E eid %(e)s, X eid %(x)s',
                         {'x': self.user.eid, 'e': eid}, 'x')
        self.commit()
        self.req.form = {'eid': str(eid), '__type:%s'%eid: 'EmailAddress',
                         '__action_delete': ''}
        path, params = self.expect_redirect_publish()
        self.assertEquals(unquote(path), 'euser/'+self.user.login)
        self.assertEquals(params, {u'__message': u'entity deleted'})
        eid1 = self.add_entity('BlogEntry', title=u'hop', content=u'hop').eid
        eid2 = self.add_entity('EmailAddress', address=u'hop@logilab.fr').eid
        self.req.form = {'eid': [str(eid1), str(eid2)],
                         '__type:%s'%eid1: 'BlogEntry',
                         '__type:%s'%eid2: 'EmailAddress',
                         '__action_delete': ''}
        path, params = self.expect_redirect_publish()
        self.assertEquals(path, 'view')
        self.assertEquals(params, {u'__message': u'entities deleted'})
        

    def test_nonregr_multiple_empty_email_addr(self):
        gueid = self.req.execute('EGroup G WHERE G name "users"')[0][0]
        self.req.form = {'eid': ['X', 'Y'],
                         
                         '__type:X': 'EUser',
                         'login:X': u'adim', 'edits-login:X': u'', 
                         'upassword:X': u'toto', 'upassword-confirm:X': u'toto', 'edits-upassword:X': u'', 
                         'in_group:X': gueid, 'edits-in_group:X': INTERNAL_FIELD_VALUE, 
                         
                         '__type:Y': 'EmailAddress',
                         'address:Y': u'', 'edits-address:Y': '',
                         'alias:Y': u'', 'edits-alias:Y': '',
                         'use_email:X': 'Y', 'edits-use_email:X': INTERNAL_FIELD_VALUE, 
                         }
        self.assertRaises(ValidationError, self.publish, self.req)


    def test_nonregr_rollback_on_validation_error(self):
        self.skip('lax fix me')
        p = self.create_user("doe")
        # do not try to skip 'primary_email' for this test
        old_skips = p.__class__.skip_copy_for
        p.__class__.skip_copy_for = ()
        try:
            e = self.add_entity('EmailAddress', address=u'doe@doe.com')
            self.req.execute('SET P use_email E, P primary_email E WHERE P eid %(p)s, E eid %(e)s',
                         {'p' : p.eid, 'e' : e.eid})
            self.req.form = {'__cloned_eid:X': p.eid,
                             'eid': 'X', '__type:X': 'EUser',
                             'login': u'dodo', 'edits-login': u'dodo', 
                             'surname:X': u'Boom', 'edits-surname:X': u'',
                             '__errorurl' : "whatever but required",
                             }
            # try to emulate what really happens in the web application
            # 1/ validate form => EditController.publish raises a ValidationError
            #    which fires a Redirect
            # 2/ When re-publishing the copy form, the publisher implicitly commits
            try:
                self.env.app.publish('edit', self.req)
            except Redirect:
                self.req.form['rql'] = 'Any X WHERE X eid %s' % p.eid
                self.req.form['vid'] = 'copy'
                self.env.app.publish('view', self.req)
            rset = self.req.execute('EUser P WHERE P surname "Boom"')
            self.assertEquals(len(rset), 0)
        finally:
            p.__class__.skip_copy_for = old_skips

        
if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
