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
"""functional tests for server'security"""

from logilab.common.testlib import unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb import Unauthorized, ValidationError, QueryError, Binary
from cubicweb.schema import ERQLExpression
from cubicweb.server.querier import get_local_checks, check_relations_read_access
from cubicweb.server.utils import _CRYPTO_CTX


class BaseSecurityTC(CubicWebTC):

    def setup_database(self):
        super(BaseSecurityTC, self).setup_database()
        with self.admin_access.client_cnx() as cnx:
            self.create_user(cnx, 'iaminusersgrouponly')
            hash = _CRYPTO_CTX.encrypt('oldpassword', scheme='des_crypt')
            self.create_user(cnx, 'oldpassword', password=Binary(hash))

class LowLevelSecurityFunctionTC(BaseSecurityTC):

    def test_check_relation_read_access(self):
        rql = u'Personne U WHERE U nom "managers"'
        rqlst = self.repo.vreg.rqlhelper.parse(rql).children[0]
        nom = self.repo.schema['Personne'].rdef('nom')
        with self.temporary_permissions((nom, {'read': ('users', 'managers')})):
            with self.admin_access.repo_cnx() as cnx:
                self.repo.vreg.solutions(cnx, rqlst, None)
                check_relations_read_access(cnx, rqlst, {})
            with self.new_access('anon').repo_cnx() as cnx:
                self.assertRaises(Unauthorized,
                                  check_relations_read_access,
                                  cnx, rqlst, {})
                self.assertRaises(Unauthorized, cnx.execute, rql)

    def test_get_local_checks(self):
        rql = u'Personne U WHERE U nom "managers"'
        rqlst = self.repo.vreg.rqlhelper.parse(rql).children[0]
        with self.temporary_permissions(Personne={'read': ('users', 'managers')}):
            with self.admin_access.repo_cnx() as cnx:
                self.repo.vreg.solutions(cnx, rqlst, None)
                solution = rqlst.solutions[0]
                localchecks = get_local_checks(cnx, rqlst, solution)
                self.assertEqual({}, localchecks)
            with self.new_access('anon').repo_cnx() as cnx:
                self.assertRaises(Unauthorized,
                                  get_local_checks,
                                  cnx, rqlst, solution)
                self.assertRaises(Unauthorized, cnx.execute, rql)

    def test_upassword_not_selectable(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertRaises(Unauthorized,
                              cnx.execute, 'Any X,P WHERE X is CWUser, X upassword P')
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            self.assertRaises(Unauthorized,
                              cnx.execute, 'Any X,P WHERE X is CWUser, X upassword P')

    def test_update_password(self):
        """Ensure that if a user's password is stored with a deprecated hash,
        it will be updated on next login
        """
        with self.repo.internal_cnx() as cnx:
            oldhash = str(cnx.system_sql("SELECT cw_upassword FROM cw_CWUser "
                                         "WHERE cw_login = 'oldpassword'").fetchone()[0])
            self.repo.close(self.repo.connect('oldpassword', password='oldpassword'))
            newhash = str(cnx.system_sql("SELECT cw_upassword FROM cw_CWUser "
                                         "WHERE cw_login = 'oldpassword'").fetchone()[0])
            self.assertNotEqual(oldhash, newhash)
            self.assertTrue(newhash.startswith('$6$'))
            self.repo.close(self.repo.connect('oldpassword', password='oldpassword'))
            self.assertEqual(newhash,
                             str(cnx.system_sql("SELECT cw_upassword FROM cw_CWUser WHERE "
                                                "cw_login = 'oldpassword'").fetchone()[0]))


class SecurityRewritingTC(BaseSecurityTC):
    def hijack_source_execute(self):
        def syntax_tree_search(*args, **kwargs):
            self.query = (args, kwargs)
            return []
        self.repo.system_source.syntax_tree_search = syntax_tree_search

    def tearDown(self):
        self.repo.system_source.__dict__.pop('syntax_tree_search', None)
        super(SecurityRewritingTC, self).tearDown()

    def test_not_relation_read_security(self):
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            self.hijack_source_execute()
            cnx.execute('Any U WHERE NOT A todo_by U, A is Affaire')
            self.assertEqual(self.query[0][1].as_string(),
                              'Any U WHERE NOT EXISTS(A todo_by U), A is Affaire')
            cnx.execute('Any U WHERE NOT EXISTS(A todo_by U), A is Affaire')
            self.assertEqual(self.query[0][1].as_string(),
                              'Any U WHERE NOT EXISTS(A todo_by U), A is Affaire')

class SecurityTC(BaseSecurityTC):

    def setUp(self):
        super(SecurityTC, self).setUp()
        # implicitly test manager can add some entities
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("INSERT Affaire X: X sujet 'cool'")
            cnx.execute("INSERT Societe X: X nom 'logilab'")
            cnx.execute("INSERT Personne X: X nom 'bidule'")
            cnx.execute('INSERT CWGroup X: X name "staff"')
            cnx.commit()

    def test_insert_security(self):
        with self.new_access('anon').repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'bidule'")
            self.assertRaises(Unauthorized, cnx.commit)
            self.assertEqual(cnx.execute('Personne X').rowcount, 1)

    def test_insert_security_2(self):
        with self.new_access('anon').repo_cnx() as cnx:
            cnx.execute("INSERT Affaire X")
            self.assertRaises(Unauthorized, cnx.commit)
            # anon has no read permission on Affaire entities, so
            # rowcount == 0
            self.assertEqual(cnx.execute('Affaire X').rowcount, 0)

    def test_insert_rql_permission(self):
        # test user can only add une affaire related to a societe he owns
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("INSERT Affaire X: X sujet 'cool'")
            self.assertRaises(Unauthorized, cnx.commit)
        # test nothing has actually been inserted
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Affaire X').rowcount, 1)
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("INSERT Affaire X: X sujet 'cool'")
            cnx.execute("INSERT Societe X: X nom 'chouette'")
            cnx.execute("SET A concerne S WHERE A sujet 'cool', S nom 'chouette'")
            cnx.commit()

    def test_update_security_1(self):
        with self.new_access('anon').repo_cnx() as cnx:
            # local security check
            cnx.execute( "SET X nom 'bidulechouette' WHERE X is Personne")
            self.assertRaises(Unauthorized, cnx.commit)
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Personne X WHERE X nom "bidulechouette"').rowcount, 0)

    def test_update_security_2(self):
        with self.temporary_permissions(Personne={'read': ('users', 'managers'),
                                                  'add': ('guests', 'users', 'managers')}):
            with self.new_access('anon').repo_cnx() as cnx:
                self.assertRaises(Unauthorized, cnx.execute,
                                  "SET X nom 'bidulechouette' WHERE X is Personne")
        # test nothing has actually been inserted
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Personne X WHERE X nom "bidulechouette"').rowcount, 0)

    def test_update_security_3(self):
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'biduuule'")
            cnx.execute("INSERT Societe X: X nom 'looogilab'")
            cnx.execute("SET X travaille S WHERE X nom 'biduuule', S nom 'looogilab'")

    def test_insert_immutable_attribute_update(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('Old', name=u'Babar')
            cnx.commit()
            # this should be equivalent
            o = cnx.create_entity('Old')
            o.cw_set(name=u'Celeste')
            cnx.commit()

    def test_update_rql_permission(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("SET A concerne S WHERE A is Affaire, S is Societe")
            cnx.commit()
        # test user can only update une affaire related to a societe he owns
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("SET X sujet 'pascool' WHERE X is Affaire")
            # this won't actually do anything since the selection query won't return anything
            cnx.commit()
            # to actually get Unauthorized exception, try to update an entity we can read
            cnx.execute("SET X nom 'toto' WHERE X is Societe")
            self.assertRaises(Unauthorized, cnx.commit)
            cnx.execute("INSERT Affaire X: X sujet 'pascool'")
            cnx.execute("INSERT Societe X: X nom 'chouette'")
            cnx.execute("SET A concerne S WHERE A sujet 'pascool', S nom 'chouette'")
            cnx.execute("SET X sujet 'habahsicestcool' WHERE X sujet 'pascool'")
            cnx.commit()

    def test_delete_security(self):
        # FIXME: sample below fails because we don't detect "owner" can't delete
        # user anyway, and since no user with login == 'bidule' exists, no
        # exception is raised
        #user._groups = {'guests':1}
        #self.assertRaises(Unauthorized,
        #                  self.o.execute, user, "DELETE CWUser X WHERE X login 'bidule'")
        # check local security
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            self.assertRaises(Unauthorized, cnx.execute, "DELETE CWGroup Y WHERE Y name 'staff'")

    def test_delete_rql_permission(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("SET A concerne S WHERE A is Affaire, S is Societe")
            cnx.commit()
        # test user can only dele une affaire related to a societe he owns
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            # this won't actually do anything since the selection query won't return anything
            cnx.execute("DELETE Affaire X")
            cnx.commit()
            # to actually get Unauthorized exception, try to delete an entity we can read
            self.assertRaises(Unauthorized, cnx.execute, "DELETE Societe S")
            self.assertRaises(QueryError, cnx.commit) # can't commit anymore
            cnx.rollback()
            cnx.execute("INSERT Affaire X: X sujet 'pascool'")
            cnx.execute("INSERT Societe X: X nom 'chouette'")
            cnx.execute("SET A concerne S WHERE A sujet 'pascool', S nom 'chouette'")
            cnx.commit()
##         # this one should fail since it will try to delete two affaires, one authorized
##         # and the other not
##         self.assertRaises(Unauthorized, cnx.execute, "DELETE Affaire X")
            cnx.execute("DELETE Affaire X WHERE X sujet 'pascool'")
            cnx.commit()

    def test_insert_relation_rql_permission(self):
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("SET A concerne S WHERE A is Affaire, S is Societe")
            # should raise Unauthorized since user don't own S though this won't
            # actually do anything since the selection query won't return
            # anything
            cnx.commit()
            # to actually get Unauthorized exception, try to insert a relation
            # were we can read both entities
            rset = cnx.execute('Personne P')
            self.assertEqual(len(rset), 1)
            ent = rset.get_entity(0, 0)
            self.assertFalse(cnx.execute('Any P,S WHERE P travaille S,P is Personne, S is Societe'))
            self.assertRaises(Unauthorized, ent.cw_check_perm, 'update')
            self.assertRaises(Unauthorized,
                              cnx.execute, "SET P travaille S WHERE P is Personne, S is Societe")
            self.assertRaises(QueryError, cnx.commit) # can't commit anymore
            cnx.rollback()
            # test nothing has actually been inserted:
            self.assertFalse(cnx.execute('Any P,S WHERE P travaille S,P is Personne, S is Societe'))
            cnx.execute("INSERT Societe X: X nom 'chouette'")
            cnx.execute("SET A concerne S WHERE A is Affaire, S nom 'chouette'")
            cnx.commit()

    def test_delete_relation_rql_permission(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("SET A concerne S WHERE A is Affaire, S is Societe")
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            # this won't actually do anything since the selection query won't return anything
            cnx.execute("DELETE A concerne S")
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            # to actually get Unauthorized exception, try to delete a relation we can read
            eid = cnx.execute("INSERT Affaire X: X sujet 'pascool'")[0][0]
            cnx.execute('SET X owned_by U WHERE X eid %(x)s, U login "iaminusersgrouponly"',
                         {'x': eid})
            cnx.execute("SET A concerne S WHERE A sujet 'pascool', S is Societe")
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            self.assertRaises(Unauthorized, cnx.execute, "DELETE A concerne S")
            self.assertRaises(QueryError, cnx.commit) # can't commit anymore
            cnx.rollback()
            cnx.execute("INSERT Societe X: X nom 'chouette'")
            cnx.execute("SET A concerne S WHERE A is Affaire, S nom 'chouette'")
            cnx.commit()
            cnx.execute("DELETE A concerne S WHERE S nom 'chouette'")
            cnx.commit()


    def test_user_can_change_its_upassword(self):
        with self.admin_access.repo_cnx() as cnx:
            ueid = self.create_user(cnx, 'user').eid
        with self.new_access('user').repo_cnx() as cnx:
            cnx.execute('SET X upassword %(passwd)s WHERE X eid %(x)s',
                       {'x': ueid, 'passwd': 'newpwd'})
            cnx.commit()
        self.repo.close(self.repo.connect('user', password='newpwd'))

    def test_user_cant_change_other_upassword(self):
        with self.admin_access.repo_cnx() as cnx:
            ueid = self.create_user(cnx, 'otheruser').eid
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute('SET X upassword %(passwd)s WHERE X eid %(x)s',
                       {'x': ueid, 'passwd': 'newpwd'})
            self.assertRaises(Unauthorized, cnx.commit)

    # read security test

    def test_read_base(self):
        with self.temporary_permissions(Personne={'read': ('users', 'managers')}):
            with self.new_access('anon').repo_cnx() as cnx:
                self.assertRaises(Unauthorized,
                                  cnx.execute, 'Personne U where U nom "managers"')

    def test_read_erqlexpr_base(self):
        with self.admin_access.repo_cnx() as cnx:
            eid = cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            rset = cnx.execute('Affaire X')
            self.assertEqual(rset.rows, [])
            self.assertRaises(Unauthorized, cnx.execute, 'Any X WHERE X eid %(x)s', {'x': eid})
            # cache test
            self.assertRaises(Unauthorized, cnx.execute, 'Any X WHERE X eid %(x)s', {'x': eid})
            aff2 = cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            soc1 = cnx.execute("INSERT Societe X: X nom 'chouette'")[0][0]
            cnx.execute("SET A concerne S WHERE A is Affaire, S is Societe")
            cnx.commit()
            rset = cnx.execute('Any X WHERE X eid %(x)s', {'x': aff2})
            self.assertEqual(rset.rows, [[aff2]])
            # more cache test w/ NOT eid
            rset = cnx.execute('Affaire X WHERE NOT X eid %(x)s', {'x': eid})
            self.assertEqual(rset.rows, [[aff2]])
            rset = cnx.execute('Affaire X WHERE NOT X eid %(x)s', {'x': aff2})
            self.assertEqual(rset.rows, [])
            # test can't update an attribute of an entity that can't be readen
            self.assertRaises(Unauthorized, cnx.execute,
                              'SET X sujet "hacked" WHERE X eid %(x)s', {'x': eid})


    def test_entity_created_in_transaction(self):
        affschema = self.schema['Affaire']
        with self.temporary_permissions(Affaire={'read': affschema.permissions['add']}):
            with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
                aff2 = cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
                # entity created in transaction are readable *by eid*
                self.assertTrue(cnx.execute('Any X WHERE X eid %(x)s', {'x':aff2}))
                # XXX would be nice if it worked
                rset = cnx.execute("Affaire X WHERE X sujet 'cool'")
                self.assertEqual(len(rset), 0)
                self.assertRaises(Unauthorized, cnx.commit)

    def test_read_erqlexpr_has_text1(self):
        with self.admin_access.repo_cnx() as cnx:
            aff1 = cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            card1 = cnx.execute("INSERT Card X: X title 'cool'")[0][0]
            cnx.execute('SET X owned_by U WHERE X eid %(x)s, U login "iaminusersgrouponly"',
                        {'x': card1})
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            aff2 = cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            soc1 = cnx.execute("INSERT Societe X: X nom 'chouette'")[0][0]
            cnx.execute("SET A concerne S WHERE A eid %(a)s, S eid %(s)s", {'a': aff2, 's': soc1})
            cnx.commit()
            self.assertRaises(Unauthorized, cnx.execute, 'Any X WHERE X eid %(x)s', {'x':aff1})
            self.assertTrue(cnx.execute('Any X WHERE X eid %(x)s', {'x':aff2}))
            self.assertTrue(cnx.execute('Any X WHERE X eid %(x)s', {'x':card1}))
            rset = cnx.execute("Any X WHERE X has_text 'cool'")
            self.assertEqual(sorted(eid for eid, in rset.rows),
                              [card1, aff2])

    def test_read_erqlexpr_has_text2(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'bidule'")
            cnx.execute("INSERT Societe X: X nom 'bidule'")
            cnx.commit()
        with self.temporary_permissions(Personne={'read': ('managers',)}):
            with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
                rset = cnx.execute('Any N WHERE N has_text "bidule"')
                self.assertEqual(len(rset.rows), 1, rset.rows)
                rset = cnx.execute('Any N WITH N BEING (Any N WHERE N has_text "bidule")')
                self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_read_erqlexpr_optional_rel(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'bidule'")
            cnx.execute("INSERT Societe X: X nom 'bidule'")
            cnx.commit()
        with self.temporary_permissions(Personne={'read': ('managers',)}):
            with self.new_access('anon').repo_cnx() as cnx:
                rset = cnx.execute('Any N,U WHERE N has_text "bidule", N owned_by U?')
                self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_read_erqlexpr_aggregat(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            rset = cnx.execute('Any COUNT(X) WHERE X is Affaire')
            self.assertEqual(rset.rows, [[0]])
            aff2 = cnx.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
            soc1 = cnx.execute("INSERT Societe X: X nom 'chouette'")[0][0]
            cnx.execute("SET A concerne S WHERE A is Affaire, S is Societe")
            cnx.commit()
            rset = cnx.execute('Any COUNT(X) WHERE X is Affaire')
            self.assertEqual(rset.rows, [[1]])
            rset = cnx.execute('Any ETN, COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN')
            values = dict(rset)
            self.assertEqual(values['Affaire'], 1)
            self.assertEqual(values['Societe'], 2)
            rset = cnx.execute('Any ETN, COUNT(X) GROUPBY ETN WHERE X is ET, ET name ETN '
                              'WITH X BEING ((Affaire X) UNION (Societe X))')
            self.assertEqual(len(rset), 2)
            values = dict(rset)
            self.assertEqual(values['Affaire'], 1)
            self.assertEqual(values['Societe'], 2)


    def test_attribute_security(self):
        with self.admin_access.repo_cnx() as cnx:
            # only managers should be able to edit the 'test' attribute of Personne entities
            eid = cnx.execute("INSERT Personne X: X nom 'bidule', "
                               "X web 'http://www.debian.org', X test TRUE")[0][0]
            cnx.execute('SET X test FALSE WHERE X eid %(x)s', {'x': eid})
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'bidule', "
                       "X web 'http://www.debian.org', X test TRUE")
            self.assertRaises(Unauthorized, cnx.commit)
            cnx.execute("INSERT Personne X: X nom 'bidule', "
                       "X web 'http://www.debian.org', X test FALSE")
            self.assertRaises(Unauthorized, cnx.commit)
            eid = cnx.execute("INSERT Personne X: X nom 'bidule', "
                             "X web 'http://www.debian.org'")[0][0]
            cnx.commit()
            cnx.execute('SET X test FALSE WHERE X eid %(x)s', {'x': eid})
            self.assertRaises(Unauthorized, cnx.commit)
            cnx.execute('SET X test TRUE WHERE X eid %(x)s', {'x': eid})
            self.assertRaises(Unauthorized, cnx.commit)
            cnx.execute('SET X web "http://www.logilab.org" WHERE X eid %(x)s', {'x': eid})
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute('INSERT Frozable F: F name "Foo"')
            cnx.commit()
            cnx.execute('SET F name "Bar" WHERE F is Frozable')
            cnx.commit()
            cnx.execute('SET F name "BaBar" WHERE F is Frozable')
            cnx.execute('SET F frozen True WHERE F is Frozable')
            with self.assertRaises(Unauthorized):
                cnx.commit()
            cnx.rollback()
            cnx.execute('SET F frozen True WHERE F is Frozable')
            cnx.commit()
            cnx.execute('SET F name "Bar" WHERE F is Frozable')
            with self.assertRaises(Unauthorized):
                cnx.commit()

    def test_attribute_security_rqlexpr(self):
        with self.admin_access.repo_cnx() as cnx:
            # Note.para attribute editable by managers or if the note is in "todo" state
            note = cnx.execute("INSERT Note X: X para 'bidule'").get_entity(0, 0)
            cnx.commit()
            note.cw_adapt_to('IWorkflowable').fire_transition('markasdone')
            cnx.execute('SET X para "truc" WHERE X eid %(x)s', {'x': note.eid})
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute("SET X para 'chouette' WHERE X eid %(x)s", {'x': note.eid})
            self.assertRaises(Unauthorized, cnx.commit)
            note2 = cnx.execute("INSERT Note X: X para 'bidule'").get_entity(0, 0)
            cnx.commit()
            note2.cw_adapt_to('IWorkflowable').fire_transition('markasdone')
            cnx.commit()
            self.assertEqual(len(cnx.execute('Any X WHERE X in_state S, S name "todo", X eid %(x)s',
                                            {'x': note2.eid})),
                              0)
            cnx.execute("SET X para 'chouette' WHERE X eid %(x)s", {'x': note2.eid})
            self.assertRaises(Unauthorized, cnx.commit)
            note2.cw_adapt_to('IWorkflowable').fire_transition('redoit')
            cnx.commit()
            cnx.execute("SET X para 'chouette' WHERE X eid %(x)s", {'x': note2.eid})
            cnx.commit()
            cnx.execute("INSERT Note X: X something 'A'")
            self.assertRaises(Unauthorized, cnx.commit)
            cnx.execute("INSERT Note X: X para 'zogzog', X something 'A'")
            cnx.commit()
            note = cnx.execute("INSERT Note X").get_entity(0,0)
            cnx.commit()
            note.cw_set(something=u'B')
            cnx.commit()
            note.cw_set(something=None, para=u'zogzog')
            cnx.commit()

    def test_attribute_read_security(self):
        # anon not allowed to see users'login, but they can see users
        login_rdef = self.repo.schema['CWUser'].rdef('login')
        with self.temporary_permissions((login_rdef, {'read': ('users', 'managers')}),
                                        CWUser={'read': ('guests', 'users', 'managers')}):
            with self.new_access('anon').repo_cnx() as cnx:
                rset = cnx.execute('CWUser X')
                self.assertTrue(rset)
                x = rset.get_entity(0, 0)
                self.assertEqual(x.login, None)
                self.assertTrue(x.creation_date)
                x = rset.get_entity(1, 0)
                x.complete()
                self.assertEqual(x.login, None)
                self.assertTrue(x.creation_date)

    def test_yams_inheritance_and_security_bug(self):
        with self.temporary_permissions(Division={'read': ('managers',
                                                           ERQLExpression('X owned_by U'))}):
            with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
                querier = cnx.repo.querier
                rqlst = querier.parse('Any X WHERE X is_instance_of Societe')
                querier.solutions(cnx, rqlst, {})
                querier._annotate(rqlst)
                plan = querier.plan_factory(rqlst, {}, cnx)
                plan.preprocess(rqlst)
                self.assertEqual(
                    rqlst.as_string(),
                    '(Any X WHERE X is IN(SubDivision, Societe)) UNION '
                    '(Any X WHERE X is Division, EXISTS(X owned_by %(B)s))')


class BaseSchemaSecurityTC(BaseSecurityTC):
    """tests related to the base schema permission configuration"""

    def test_user_can_delete_object_he_created(self):
        # even if some other user have changed object'state
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            # due to security test, affaire has to concerne a societe the user owns
            cnx.execute('INSERT Societe X: X nom "ARCTIA"')
            cnx.execute('INSERT Affaire X: X ref "ARCT01", X concerne S WHERE S nom "ARCTIA"')
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            affaire = cnx.execute('Any X WHERE X ref "ARCT01"').get_entity(0, 0)
            affaire.cw_adapt_to('IWorkflowable').fire_transition('abort')
            cnx.commit()
            self.assertEqual(len(cnx.execute('TrInfo X WHERE X wf_info_for A, A ref "ARCT01"')),
                             1)
            self.assertEqual(len(cnx.execute('TrInfo X WHERE X wf_info_for A, A ref "ARCT01",'
                                              'X owned_by U, U login "admin"')),
                             1) # TrInfo at the above state change
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            cnx.execute('DELETE Affaire X WHERE X ref "ARCT01"')
            cnx.commit()
            self.assertFalse(cnx.execute('Affaire X'))

    def test_users_and_groups_non_readable_by_guests(self):
        with self.repo.internal_cnx() as cnx:
            admineid = cnx.execute('CWUser U WHERE U login "admin"').rows[0][0]
        with self.new_access('anon').repo_cnx() as cnx:
            anon = cnx.user
            # anonymous user can only read itself
            rset = cnx.execute('Any L WHERE X owned_by U, U login L')
            self.assertEqual([['anon']], rset.rows)
            rset = cnx.execute('CWUser X')
            self.assertEqual([[anon.eid]], rset.rows)
            # anonymous user can read groups (necessary to check allowed transitions for instance)
            self.assert_(cnx.execute('CWGroup X'))
            # should only be able to read the anonymous user, not another one
            self.assertRaises(Unauthorized,
                              cnx.execute, 'CWUser X WHERE X eid %(x)s', {'x': admineid})
            rset = cnx.execute('CWUser X WHERE X eid %(x)s', {'x': anon.eid})
            self.assertEqual([[anon.eid]], rset.rows)
            # but can't modify it
            cnx.execute('SET X login "toto" WHERE X eid %(x)s', {'x': anon.eid})
            self.assertRaises(Unauthorized, cnx.commit)

    def test_in_group_relation(self):
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            rql = u"DELETE U in_group G WHERE U login 'admin'"
            self.assertRaises(Unauthorized, cnx.execute, rql)
            rql = u"SET U in_group G WHERE U login 'admin', G name 'users'"
            self.assertRaises(Unauthorized, cnx.execute, rql)

    def test_owned_by(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'bidule'")
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            rql = u"SET X owned_by U WHERE U login 'iaminusersgrouponly', X is Personne"
            self.assertRaises(Unauthorized, cnx.execute, rql)

    def test_bookmarked_by_guests_security(self):
        with self.admin_access.repo_cnx() as cnx:
            beid1 = cnx.execute('INSERT Bookmark B: B path "?vid=manage", B title "manage"')[0][0]
            beid2 = cnx.execute('INSERT Bookmark B: B path "?vid=index", B title "index", '
                                'B bookmarked_by U WHERE U login "anon"')[0][0]
            cnx.commit()
        with self.new_access('anon').repo_cnx() as cnx:
            anoneid = cnx.user.eid
            self.assertEqual(cnx.execute('Any T,P ORDERBY lower(T) WHERE B is Bookmark,B title T,B path P,'
                                         'B bookmarked_by U, U eid %s' % anoneid).rows,
                              [['index', '?vid=index']])
            self.assertEqual(cnx.execute('Any T,P ORDERBY lower(T) WHERE B is Bookmark,B title T,B path P,'
                                         'B bookmarked_by U, U eid %(x)s', {'x': anoneid}).rows,
                              [['index', '?vid=index']])
            # can read others bookmarks as well
            self.assertEqual(cnx.execute('Any B where B is Bookmark, NOT B bookmarked_by U').rows,
                              [[beid1]])
            self.assertRaises(Unauthorized, cnx.execute,'DELETE B bookmarked_by U')
            self.assertRaises(Unauthorized,
                              cnx.execute, 'SET B bookmarked_by U WHERE U eid %(x)s, B eid %(b)s',
                              {'x': anoneid, 'b': beid1})

    def test_ambigous_ordered(self):
        with self.new_access('anon').repo_cnx() as cnx:
            names = [t for t, in cnx.execute('Any N ORDERBY lower(N) WHERE X name N')]
            self.assertEqual(names, sorted(names, key=lambda x: x.lower()))

    def test_in_state_without_update_perm(self):
        """check a user change in_state without having update permission on the
        subject
        """
        with self.admin_access.repo_cnx() as cnx:
            eid = cnx.execute('INSERT Affaire X: X ref "ARCT01"')[0][0]
            cnx.commit()
        with self.new_access('iaminusersgrouponly').repo_cnx() as cnx:
            # needed to remove rql expr granting update perm to the user
            affschema = self.schema['Affaire']
            with self.temporary_permissions(Affaire={'update': affschema.get_groups('update'),
                                                     'read': ('users',)}):
                self.assertRaises(Unauthorized,
                                  affschema.check_perm, cnx, 'update', eid=eid)
                aff = cnx.execute('Any X WHERE X ref "ARCT01"').get_entity(0, 0)
                aff.cw_adapt_to('IWorkflowable').fire_transition('abort')
                cnx.commit()
                # though changing a user state (even logged user) is reserved to managers
                user = cnx.user
                # XXX wether it should raise Unauthorized or ValidationError is not clear
                # the best would probably ValidationError if the transition doesn't exist
                # from the current state but Unauthorized if it exists but user can't pass it
                self.assertRaises(ValidationError,
                                  user.cw_adapt_to('IWorkflowable').fire_transition, 'deactivate')

    def test_trinfo_security(self):
        with self.admin_access.repo_cnx() as cnx:
            aff = cnx.execute('INSERT Affaire X: X ref "ARCT01"').get_entity(0, 0)
            iworkflowable = aff.cw_adapt_to('IWorkflowable')
            cnx.commit()
            iworkflowable.fire_transition('abort')
            cnx.commit()
            # can change tr info comment
            cnx.execute('SET TI comment %(c)s WHERE TI wf_info_for X, X ref "ARCT01"',
                         {'c': u'bouh!'})
            cnx.commit()
            aff.cw_clear_relation_cache('wf_info_for', 'object')
            trinfo = iworkflowable.latest_trinfo()
            self.assertEqual(trinfo.comment, 'bouh!')
            # but not from_state/to_state
            aff.cw_clear_relation_cache('wf_info_for', role='object')
            self.assertRaises(Unauthorized, cnx.execute,
                              'SET TI from_state S WHERE TI eid %(ti)s, S name "ben non"',
                              {'ti': trinfo.eid})
            self.assertRaises(Unauthorized, cnx.execute,
                              'SET TI to_state S WHERE TI eid %(ti)s, S name "pitetre"',
                              {'ti': trinfo.eid})

    def test_emailaddress_security(self):
        # check for prexisting email adresse
        with self.admin_access.repo_cnx() as cnx:
            if cnx.execute('Any X WHERE X is EmailAddress'):
                rset = cnx.execute('Any X, U WHERE X is EmailAddress, U use_email X')
                msg = ['Preexisting email readable by anon found!']
                tmpl = '  - "%s" used by user "%s"'
                for i in xrange(len(rset)):
                    email, user = rset.get_entity(i, 0), rset.get_entity(i, 1)
                    msg.append(tmpl % (email.dc_title(), user.dc_title()))
                raise RuntimeError('\n'.join(msg))
            # actual test
            cnx.execute('INSERT EmailAddress X: X address "hop"').get_entity(0, 0)
            cnx.execute('INSERT EmailAddress X: X address "anon", '
                         'U use_email X WHERE U login "anon"').get_entity(0, 0)
            cnx.commit()
            self.assertEqual(len(cnx.execute('Any X WHERE X is EmailAddress')), 2)
        with self.new_access('anon').repo_cnx() as cnx:
            self.assertEqual(len(cnx.execute('Any X WHERE X is EmailAddress')), 1)

if __name__ == '__main__':
    unittest_main()
