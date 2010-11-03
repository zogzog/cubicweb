# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""functional tests for server'security"""

import sys

from logilab.common.testlib import unittest_main, TestCase
from cubicweb.devtools.testlib import CubicWebTC

from cubicweb import Unauthorized, ValidationError, QueryError
from cubicweb.server.querier import check_read_access

class BaseSecurityTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        self.create_user('iaminusersgrouponly')
        self.readoriggroups = self.schema['Personne'].permissions['read']
        self.addoriggroups = self.schema['Personne'].permissions['add']

    def tearDown(self):
        CubicWebTC.tearDown(self)
        self.schema['Personne'].set_action_permissions('read', self.readoriggroups)
        self.schema['Personne'].set_action_permissions('add', self.addoriggroups)


class LowLevelSecurityFunctionTC(BaseSecurityTC):

    def test_check_read_access(self):
        rql = u'Personne U where U nom "managers"'
        rqlst = self.repo.vreg.rqlhelper.parse(rql).children[0]
        origgroups = self.schema['Personne'].get_groups('read')
        self.schema['Personne'].set_action_permissions('read', ('users', 'managers'))
        self.repo.vreg.solutions(self.session, rqlst, None)
        solution = rqlst.solutions[0]
        check_read_access(self.session, rqlst, solution, {})
        cnx = self.login('anon')
        cu = cnx.cursor()
        self.assertRaises(Unauthorized,
                          check_read_access,
                          self.session, rqlst, solution, {})
        self.assertRaises(Unauthorized, cu.execute, rql)

    def test_upassword_not_selectable(self):
        self.assertRaises(Unauthorized,
                          self.execute, 'Any X,P WHERE X is CWUser, X upassword P')
        self.rollback()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        self.assertRaises(Unauthorized,
                          cu.execute, 'Any X,P WHERE X is CWUser, X upassword P')


class SecurityRewritingTC(BaseSecurityTC):
    def hijack_source_execute(self):
        def syntax_tree_search(*args, **kwargs):
            self.query = (args, kwargs)
            return []
        self.repo.system_source.syntax_tree_search = syntax_tree_search

    def tearDown(self):
        self.repo.system_source.__dict__.pop('syntax_tree_search', None)
        BaseSecurityTC.tearDown(self)

    def test_not_relation_read_security(self):
        cnx = self.login('iaminusersgrouponly')
        self.hijack_source_execute()
        self.execute('Any U WHERE NOT A todo_by U, A is Affaire')
        self.assertEqual(self.query[0][1].as_string(),
                          'Any U WHERE NOT EXISTS(A todo_by U), A is Affaire')
        self.execute('Any U WHERE NOT EXISTS(A todo_by U), A is Affaire')
        self.assertEqual(self.query[0][1].as_string(),
                          'Any U WHERE NOT EXISTS(A todo_by U), A is Affaire')

class SecurityTC(BaseSecurityTC):

    def setUp(self):
        BaseSecurityTC.setUp(self)
        # implicitly test manager can add some entities
        self.execute("INSERT Affaire X: X sujet 'cool'")
        self.execute("INSERT Societe X: X nom 'logilab'")
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute('INSERT CWGroup X: X name "staff"')
        self.commit()

    def test_insert_security(self):
        cnx = self.login('anon')
        cu = cnx.cursor()
        cu.execute("INSERT Personne X: X nom 'bidule'")
        self.assertRaises(Unauthorized, cnx.commit)
        self.assertEqual(cu.execute('Personne X').rowcount, 1)

    def test_insert_rql_permission(self):
        # test user can only add une affaire related to a societe he owns
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute("INSERT Affaire X: X sujet 'cool'")
        self.assertRaises(Unauthorized, cnx.commit)
        # test nothing has actually been inserted
        self.restore_connection()
        self.assertEqual(self.execute('Affaire X').rowcount, 1)
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute("INSERT Affaire X: X sujet 'cool'")
        cu.execute("INSERT Societe X: X nom 'chouette'")
        cu.execute("SET A concerne S WHERE A sujet 'cool', S nom 'chouette'")
        cnx.commit()

    def test_update_security_1(self):
        cnx = self.login('anon')
        cu = cnx.cursor()
        # local security check
        cu.execute( "SET X nom 'bidulechouette' WHERE X is Personne")
        self.assertRaises(Unauthorized, cnx.commit)
        self.restore_connection()
        self.assertEqual(self.execute('Personne X WHERE X nom "bidulechouette"').rowcount, 0)

    def test_update_security_2(self):
        cnx = self.login('anon')
        cu = cnx.cursor()
        self.repo.schema['Personne'].set_action_permissions('read', ('users', 'managers'))
        self.repo.schema['Personne'].set_action_permissions('add', ('guests', 'users', 'managers'))
        self.assertRaises(Unauthorized, cu.execute, "SET X nom 'bidulechouette' WHERE X is Personne")
        #self.assertRaises(Unauthorized, cnx.commit)
        # test nothing has actually been inserted
        self.restore_connection()
        self.assertEqual(self.execute('Personne X WHERE X nom "bidulechouette"').rowcount, 0)

    def test_update_security_3(self):
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute("INSERT Personne X: X nom 'biduuule'")
        cu.execute("INSERT Societe X: X nom 'looogilab'")
        cu.execute("SET X travaille S WHERE X nom 'biduuule', S nom 'looogilab'")

    def test_update_rql_permission(self):
        self.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        self.commit()
        # test user can only update une affaire related to a societe he owns
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute("SET X sujet 'pascool' WHERE X is Affaire")
        # this won't actually do anything since the selection query won't return anything
        cnx.commit()
        # to actually get Unauthorized exception, try to update an entity we can read
        cu.execute("SET X nom 'toto' WHERE X is Societe")
        self.assertRaises(Unauthorized, cnx.commit)
        cu.execute("INSERT Affaire X: X sujet 'pascool'")
        cu.execute("INSERT Societe X: X nom 'chouette'")
        cu.execute("SET A concerne S WHERE A sujet 'pascool', S nom 'chouette'")
        cu.execute("SET X sujet 'habahsicestcool' WHERE X sujet 'pascool'")
        cnx.commit()

    def test_delete_security(self):
        # FIXME: sample below fails because we don't detect "owner" can't delete
        # user anyway, and since no user with login == 'bidule' exists, no
        # exception is raised
        #user._groups = {'guests':1}
        #self.assertRaises(Unauthorized,
        #                  self.o.execute, user, "DELETE CWUser X WHERE X login 'bidule'")
        # check local security
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        self.assertRaises(Unauthorized, cu.execute, "DELETE CWGroup Y WHERE Y name 'staff'")

    def test_delete_rql_permission(self):
        self.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        self.commit()
        # test user can only dele une affaire related to a societe he owns
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        # this won't actually do anything since the selection query won't return anything
        cu.execute("DELETE Affaire X")
        cnx.commit()
        # to actually get Unauthorized exception, try to delete an entity we can read
        self.assertRaises(Unauthorized, cu.execute, "DELETE Societe S")
        self.assertRaises(QueryError, cnx.commit) # can't commit anymore
        cnx.rollback() # required after Unauthorized
        cu.execute("INSERT Affaire X: X sujet 'pascool'")
        cu.execute("INSERT Societe X: X nom 'chouette'")
        cu.execute("SET A concerne S WHERE A sujet 'pascool', S nom 'chouette'")
        cnx.commit()
##         # this one should fail since it will try to delete two affaires, one authorized
##         # and the other not
##         self.assertRaises(Unauthorized, cu.execute, "DELETE Affaire X")
        cu.execute("DELETE Affaire X WHERE X sujet 'pascool'")
        cnx.commit()


    def test_insert_relation_rql_permission(self):
        cnx = self.login('iaminusersgrouponly')
        session = self.session
        cu = cnx.cursor(session)
        cu.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        # should raise Unauthorized since user don't own S
        # though this won't actually do anything since the selection query won't return anything
        cnx.commit()
        # to actually get Unauthorized exception, try to insert a relation were we can read both entities
        rset = cu.execute('Personne P')
        self.assertEqual(len(rset), 1)
        ent = rset.get_entity(0, 0)
        session.set_pool() # necessary
        self.assertRaises(Unauthorized, ent.cw_check_perm, 'update')
        self.assertRaises(Unauthorized,
                          cu.execute, "SET P travaille S WHERE P is Personne, S is Societe")
        self.assertRaises(QueryError, cnx.commit) # can't commit anymore
        cnx.rollback()
        # test nothing has actually been inserted:
        self.assertEqual(cu.execute('Any P,S WHERE P travaille S,P is Personne, S is Societe').rowcount, 0)
        cu.execute("INSERT Societe X: X nom 'chouette'")
        cu.execute("SET A concerne S WHERE A is Affaire, S nom 'chouette'")
        cnx.commit()

    def test_delete_relation_rql_permission(self):
        self.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        # this won't actually do anything since the selection query won't return anything
        cu.execute("DELETE A concerne S")
        cnx.commit()
        # to actually get Unauthorized exception, try to delete a relation we can read
        self.restore_connection()
        eid = self.execute("INSERT Affaire X: X sujet 'pascool'")[0][0]
        self.execute('SET X owned_by U WHERE X eid %(x)s, U login "iaminusersgrouponly"', {'x': eid})
        self.execute("SET A concerne S WHERE A sujet 'pascool', S is Societe")
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        self.assertRaises(Unauthorized, cu.execute, "DELETE A concerne S")
        self.assertRaises(QueryError, cnx.commit) # can't commit anymore
        cnx.rollback() # required after Unauthorized
        cu.execute("INSERT Societe X: X nom 'chouette'")
        cu.execute("SET A concerne S WHERE A is Affaire, S nom 'chouette'")
        cnx.commit()
        cu.execute("DELETE A concerne S WHERE S nom 'chouette'")


    def test_user_can_change_its_upassword(self):
        ueid = self.create_user('user').eid
        cnx = self.login('user')
        cu = cnx.cursor()
        cu.execute('SET X upassword %(passwd)s WHERE X eid %(x)s',
                   {'x': ueid, 'passwd': 'newpwd'})
        cnx.commit()
        cnx.close()
        cnx = self.login('user', password='newpwd')

    def test_user_cant_change_other_upassword(self):
        ueid = self.create_user('otheruser').eid
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute('SET X upassword %(passwd)s WHERE X eid %(x)s',
                   {'x': ueid, 'passwd': 'newpwd'})
        self.assertRaises(Unauthorized, cnx.commit)

    # read security test

    def test_read_base(self):
        self.schema['Personne'].set_action_permissions('read', ('users', 'managers'))
        cnx = self.login('anon')
        cu = cnx.cursor()
        self.assertRaises(Unauthorized,
                          cu.execute, 'Personne U where U nom "managers"')

    def test_read_erqlexpr_base(self):
        eid = self.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        rset = cu.execute('Affaire X')
        self.assertEqual(rset.rows, [])
        self.assertRaises(Unauthorized, cu.execute, 'Any X WHERE X eid %(x)s', {'x': eid})
        # cache test
        self.assertRaises(Unauthorized, cu.execute, 'Any X WHERE X eid %(x)s', {'x': eid})
        aff2 = cu.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
        soc1 = cu.execute("INSERT Societe X: X nom 'chouette'")[0][0]
        cu.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        cnx.commit()
        rset = cu.execute('Any X WHERE X eid %(x)s', {'x': aff2})
        self.assertEqual(rset.rows, [[aff2]])
        # more cache test w/ NOT eid
        rset = cu.execute('Affaire X WHERE NOT X eid %(x)s', {'x': eid})
        self.assertEqual(rset.rows, [[aff2]])
        rset = cu.execute('Affaire X WHERE NOT X eid %(x)s', {'x': aff2})
        self.assertEqual(rset.rows, [])
        # test can't update an attribute of an entity that can't be readen
        self.assertRaises(Unauthorized, cu.execute, 'SET X sujet "hacked" WHERE X eid %(x)s', {'x': eid})


    def test_entity_created_in_transaction(self):
        affschema = self.schema['Affaire']
        origperms = affschema.permissions['read']
        affschema.set_action_permissions('read', affschema.permissions['add'])
        try:
            cnx = self.login('iaminusersgrouponly')
            cu = cnx.cursor()
            aff2 = cu.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            # entity created in transaction are readable *by eid*
            self.failUnless(cu.execute('Any X WHERE X eid %(x)s', {'x':aff2}))
            # XXX would be nice if it worked
            rset = cu.execute("Affaire X WHERE X sujet 'cool'")
            self.assertEqual(len(rset), 0)
        finally:
            affschema.set_action_permissions('read', origperms)
            cnx.close()

    def test_read_erqlexpr_has_text1(self):
        aff1 = self.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
        card1 = self.execute("INSERT Card X: X title 'cool'")[0][0]
        self.execute('SET X owned_by U WHERE X eid %(x)s, U login "iaminusersgrouponly"', {'x': card1})
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        aff2 = cu.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
        soc1 = cu.execute("INSERT Societe X: X nom 'chouette'")[0][0]
        cu.execute("SET A concerne S WHERE A eid %(a)s, S eid %(s)s", {'a': aff2, 's': soc1})
        cnx.commit()
        self.assertRaises(Unauthorized, cu.execute, 'Any X WHERE X eid %(x)s', {'x':aff1})
        self.failUnless(cu.execute('Any X WHERE X eid %(x)s', {'x':aff2}))
        self.failUnless(cu.execute('Any X WHERE X eid %(x)s', {'x':card1}))
        rset = cu.execute("Any X WHERE X has_text 'cool'")
        self.assertEqual(sorted(eid for eid, in rset.rows),
                          [card1, aff2])

    def test_read_erqlexpr_has_text2(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe X: X nom 'bidule'")
        self.commit()
        self.schema['Personne'].set_action_permissions('read', ('managers',))
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        rset = cu.execute('Any N WHERE N has_text "bidule"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = cu.execute('Any N WITH N BEING (Any N WHERE N has_text "bidule")')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_read_erqlexpr_optional_rel(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe X: X nom 'bidule'")
        self.commit()
        self.schema['Personne'].set_action_permissions('read', ('managers',))
        cnx = self.login('anon')
        cu = cnx.cursor()
        rset = cu.execute('Any N,U WHERE N has_text "bidule", N owned_by U?')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_read_erqlexpr_aggregat(self):
        self.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        rset = cu.execute('Any COUNT(X) WHERE X is Affaire')
        self.assertEqual(rset.rows, [[0]])
        aff2 = cu.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
        soc1 = cu.execute("INSERT Societe X: X nom 'chouette'")[0][0]
        cu.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        cnx.commit()
        rset = cu.execute('Any COUNT(X) WHERE X is Affaire')
        self.assertEqual(rset.rows, [[1]])
        rset = cu.execute('Any ETN, COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN')
        values = dict(rset)
        self.assertEqual(values['Affaire'], 1)
        self.assertEqual(values['Societe'], 2)
        rset = cu.execute('Any ETN, COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN WITH X BEING ((Affaire X) UNION (Societe X))')
        self.assertEqual(len(rset), 2)
        values = dict(rset)
        self.assertEqual(values['Affaire'], 1)
        self.assertEqual(values['Societe'], 2)


    def test_attribute_security(self):
        # only managers should be able to edit the 'test' attribute of Personne entities
        eid = self.execute("INSERT Personne X: X nom 'bidule', X web 'http://www.debian.org', X test TRUE")[0][0]
        self.commit()
        self.execute('SET X test FALSE WHERE X eid %(x)s', {'x': eid})
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute("INSERT Personne X: X nom 'bidule', X web 'http://www.debian.org', X test TRUE")
        self.assertRaises(Unauthorized, cnx.commit)
        cu.execute("INSERT Personne X: X nom 'bidule', X web 'http://www.debian.org', X test FALSE")
        self.assertRaises(Unauthorized, cnx.commit)
        eid = cu.execute("INSERT Personne X: X nom 'bidule', X web 'http://www.debian.org'")[0][0]
        cnx.commit()
        cu.execute('SET X test FALSE WHERE X eid %(x)s', {'x': eid})
        self.assertRaises(Unauthorized, cnx.commit)
        cu.execute('SET X test TRUE WHERE X eid %(x)s', {'x': eid})
        self.assertRaises(Unauthorized, cnx.commit)
        cu.execute('SET X web "http://www.logilab.org" WHERE X eid %(x)s', {'x': eid})
        cnx.commit()
        cnx.close()

    def test_attribute_security_rqlexpr(self):
        # Note.para attribute editable by managers or if the note is in "todo" state
        note = self.execute("INSERT Note X: X para 'bidule'").get_entity(0, 0)
        self.commit()
        note.cw_adapt_to('IWorkflowable').fire_transition('markasdone')
        self.execute('SET X para "truc" WHERE X eid %(x)s', {'x': note.eid})
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute("SET X para 'chouette' WHERE X eid %(x)s", {'x': note.eid})
        self.assertRaises(Unauthorized, cnx.commit)
        note2 = cu.execute("INSERT Note X: X para 'bidule'").get_entity(0, 0)
        cnx.commit()
        note2.cw_adapt_to('IWorkflowable').fire_transition('markasdone')
        cnx.commit()
        self.assertEqual(len(cu.execute('Any X WHERE X in_state S, S name "todo", X eid %(x)s', {'x': note2.eid})),
                          0)
        cu.execute("SET X para 'chouette' WHERE X eid %(x)s", {'x': note2.eid})
        self.assertRaises(Unauthorized, cnx.commit)
        note2.cw_adapt_to('IWorkflowable').fire_transition('redoit')
        cnx.commit()
        cu.execute("SET X para 'chouette' WHERE X eid %(x)s", {'x': note2.eid})
        cnx.commit()

    def test_attribute_read_security(self):
        # anon not allowed to see users'login, but they can see users
        self.repo.schema['CWUser'].set_action_permissions('read', ('guests', 'users', 'managers'))
        self.repo.schema['CWUser'].rdef('login').set_action_permissions('read', ('users', 'managers'))
        cnx = self.login('anon')
        cu = cnx.cursor()
        rset = cu.execute('CWUser X')
        self.failUnless(rset)
        x = rset.get_entity(0, 0)
        self.assertEqual(x.login, None)
        self.failUnless(x.creation_date)
        x = rset.get_entity(1, 0)
        x.complete()
        self.assertEqual(x.login, None)
        self.failUnless(x.creation_date)
        cnx.rollback()

class BaseSchemaSecurityTC(BaseSecurityTC):
    """tests related to the base schema permission configuration"""

    def test_user_can_delete_object_he_created(self):
        # even if some other user have changed object'state
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        # due to security test, affaire has to concerne a societe the user owns
        cu.execute('INSERT Societe X: X nom "ARCTIA"')
        cu.execute('INSERT Affaire X: X ref "ARCT01", X concerne S WHERE S nom "ARCTIA"')
        cnx.commit()
        self.restore_connection()
        affaire = self.execute('Any X WHERE X ref "ARCT01"').get_entity(0, 0)
        affaire.cw_adapt_to('IWorkflowable').fire_transition('abort')
        self.commit()
        self.assertEqual(len(self.execute('TrInfo X WHERE X wf_info_for A, A ref "ARCT01"')),
                          1)
        self.assertEqual(len(self.execute('TrInfo X WHERE X wf_info_for A, A ref "ARCT01",'
                                           'X owned_by U, U login "admin"')),
                          1) # TrInfo at the above state change
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        cu.execute('DELETE Affaire X WHERE X ref "ARCT01"')
        cnx.commit()
        self.failIf(cu.execute('Affaire X'))

    def test_users_and_groups_non_readable_by_guests(self):
        cnx = self.login('anon')
        anon = cnx.user(self.session)
        cu = cnx.cursor()
        # anonymous user can only read itself
        rset = cu.execute('Any L WHERE X owned_by U, U login L')
        self.assertEqual(rset.rows, [['anon']])
        rset = cu.execute('CWUser X')
        self.assertEqual(rset.rows, [[anon.eid]])
        # anonymous user can read groups (necessary to check allowed transitions for instance)
        self.assert_(cu.execute('CWGroup X'))
        # should only be able to read the anonymous user, not another one
        origuser = self.adminsession.user
        self.assertRaises(Unauthorized,
                          cu.execute, 'CWUser X WHERE X eid %(x)s', {'x': origuser.eid})
        # nothing selected, nothing updated, no exception raised
        #self.assertRaises(Unauthorized,
        #                  cu.execute, 'SET X login "toto" WHERE X eid %(x)s',
        #                  {'x': self.user.eid})

        rset = cu.execute('CWUser X WHERE X eid %(x)s', {'x': anon.eid})
        self.assertEqual(rset.rows, [[anon.eid]])
        # but can't modify it
        cu.execute('SET X login "toto" WHERE X eid %(x)s', {'x': anon.eid})
        self.assertRaises(Unauthorized, cnx.commit)

    def test_in_group_relation(self):
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        rql = u"DELETE U in_group G WHERE U login 'admin'"
        self.assertRaises(Unauthorized, cu.execute, rql)
        rql = u"SET U in_group G WHERE U login 'admin', G name 'users'"
        self.assertRaises(Unauthorized, cu.execute, rql)

    def test_owned_by(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        cu = cnx.cursor()
        rql = u"SET X owned_by U WHERE U login 'iaminusersgrouponly', X is Personne"
        self.assertRaises(Unauthorized, cu.execute, rql)

    def test_bookmarked_by_guests_security(self):
        beid1 = self.execute('INSERT Bookmark B: B path "?vid=manage", B title "manage"')[0][0]
        beid2 = self.execute('INSERT Bookmark B: B path "?vid=index", B title "index", B bookmarked_by U WHERE U login "anon"')[0][0]
        self.commit()
        cnx = self.login('anon')
        cu = cnx.cursor()
        anoneid = self.session.user.eid
        self.assertEqual(cu.execute('Any T,P ORDERBY lower(T) WHERE B is Bookmark,B title T,B path P,'
                                     'B bookmarked_by U, U eid %s' % anoneid).rows,
                          [['index', '?vid=index']])
        self.assertEqual(cu.execute('Any T,P ORDERBY lower(T) WHERE B is Bookmark,B title T,B path P,'
                                     'B bookmarked_by U, U eid %(x)s', {'x': anoneid}).rows,
                          [['index', '?vid=index']])
        # can read others bookmarks as well
        self.assertEqual(cu.execute('Any B where B is Bookmark, NOT B bookmarked_by U').rows,
                          [[beid1]])
        self.assertRaises(Unauthorized, cu.execute,'DELETE B bookmarked_by U')
        self.assertRaises(Unauthorized,
                          cu.execute, 'SET B bookmarked_by U WHERE U eid %(x)s, B eid %(b)s',
                          {'x': anoneid, 'b': beid1})


    def test_ambigous_ordered(self):
        cnx = self.login('anon')
        cu = cnx.cursor()
        names = [t for t, in cu.execute('Any N ORDERBY lower(N) WHERE X name N')]
        self.assertEqual(names, sorted(names, key=lambda x: x.lower()))

    def test_in_state_without_update_perm(self):
        """check a user change in_state without having update permission on the
        subject
        """
        eid = self.execute('INSERT Affaire X: X ref "ARCT01"')[0][0]
        self.commit()
        cnx = self.login('iaminusersgrouponly')
        session = self.session
        # needed to avoid check_perm error
        session.set_pool()
        # needed to remove rql expr granting update perm to the user
        affaire_perms = self.schema['Affaire'].permissions.copy()
        self.schema['Affaire'].set_action_permissions('update', self.schema['Affaire'].get_groups('update'))
        try:
            self.assertRaises(Unauthorized,
                              self.schema['Affaire'].check_perm, session, 'update', eid=eid)
            cu = cnx.cursor()
            self.schema['Affaire'].set_action_permissions('read', ('users',))
            aff = cu.execute('Any X WHERE X ref "ARCT01"').get_entity(0, 0)
            aff.cw_adapt_to('IWorkflowable').fire_transition('abort')
            cnx.commit()
            # though changing a user state (even logged user) is reserved to managers
            user = cnx.user(self.session)
            # XXX wether it should raise Unauthorized or ValidationError is not clear
            # the best would probably ValidationError if the transition doesn't exist
            # from the current state but Unauthorized if it exists but user can't pass it
            self.assertRaises(ValidationError,
                              user.cw_adapt_to('IWorkflowable').fire_transition, 'deactivate')
        finally:
            # restore orig perms
            for action, perms in affaire_perms.iteritems():
                self.schema['Affaire'].set_action_permissions(action, perms)

    def test_trinfo_security(self):
        aff = self.execute('INSERT Affaire X: X ref "ARCT01"').get_entity(0, 0)
        iworkflowable = aff.cw_adapt_to('IWorkflowable')
        self.commit()
        iworkflowable.fire_transition('abort')
        self.commit()
        # can change tr info comment
        self.execute('SET TI comment %(c)s WHERE TI wf_info_for X, X ref "ARCT01"',
                     {'c': u'bouh!'})
        self.commit()
        aff.cw_clear_relation_cache('wf_info_for', 'object')
        trinfo = iworkflowable.latest_trinfo()
        self.assertEqual(trinfo.comment, 'bouh!')
        # but not from_state/to_state
        aff.cw_clear_relation_cache('wf_info_for', role='object')
        self.assertRaises(Unauthorized,
                          self.execute, 'SET TI from_state S WHERE TI eid %(ti)s, S name "ben non"',
                          {'ti': trinfo.eid})
        self.assertRaises(Unauthorized,
                          self.execute, 'SET TI to_state S WHERE TI eid %(ti)s, S name "pitetre"',
                          {'ti': trinfo.eid})

if __name__ == '__main__':
    unittest_main()
