# -*- coding: utf-8 -*-
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

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC
import cubicweb.server.session
from cubicweb.server.session import Connection as OldConnection

from cubicweb.server.sources.native import UndoTransactionException, _UndoException

from cubicweb.transaction import NoSuchTransaction

class UndoableTransactionTC(CubicWebTC):

    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            self.totoeid = self.create_user(cnx, 'toto',
                                            password='toto',
                                            groups=('users',),
                                            commit=False).eid
            self.txuuid = cnx.commit()

    def toto(self, cnx):
        return cnx.entity_from_eid(self.totoeid)

    def setUp(self):
        class Connection(OldConnection):
            """Force undo feature to be turned on in all case"""
            undo_actions = property(lambda tx: True, lambda x, y:None)
        cubicweb.server.session.Connection = Connection
        super(UndoableTransactionTC, self).setUp()

    def tearDown(self):
        cubicweb.server.session.Connection = OldConnection
        self.restore_connection()
        super(UndoableTransactionTC, self).tearDown()

    def check_transaction_deleted(self, cnx, txuuid):
        # also check transaction actions have been properly deleted
        cu = cnx.system_sql(
            "SELECT * from tx_entity_actions WHERE tx_uuid='%s'" % txuuid)
        self.assertFalse(cu.fetchall())
        cu = cnx.system_sql(
            "SELECT * from tx_relation_actions WHERE tx_uuid='%s'" % txuuid)
        self.assertFalse(cu.fetchall())

    def assertUndoTransaction(self, cnx, txuuid, expected_errors=None):
        if expected_errors is None :
            expected_errors = []
        try:
            cnx.undo_transaction(txuuid)
        except UndoTransactionException as exn:
            errors = exn.errors
        else:
            errors = []
        self.assertEqual(errors, expected_errors)

    def test_undo_api(self):
        self.assertTrue(self.txuuid)
        # test transaction api
        with self.admin_access.client_cnx() as cnx:
            tx_actions = cnx.transaction_actions(self.txuuid)
            self.assertEqual(len(tx_actions), 2, tx_actions)
            self.assertRaises(NoSuchTransaction,
                              cnx.transaction_info, 'hop')
            self.assertRaises(NoSuchTransaction,
                              cnx.transaction_actions, 'hop')
            self.assertRaises(NoSuchTransaction,
                              cnx.undo_transaction, 'hop')
            txinfo = cnx.transaction_info(self.txuuid)
            self.assertTrue(txinfo.datetime)
            self.assertEqual(txinfo.user_eid, cnx.user.eid)
            self.assertEqual(txinfo.user().login, 'admin')
            actions = txinfo.actions_list()
            self.assertEqual(len(actions), 2)
            actions = txinfo.actions_list(public=False)
            self.assertEqual(len(actions), 6)
            a1 = actions[0]
            self.assertEqual(a1.action, 'C')
            self.assertEqual(a1.eid, self.totoeid)
            self.assertEqual(a1.etype,'CWUser')
            self.assertEqual(a1.ertype, 'CWUser')
            self.assertEqual(a1.changes, None)
            self.assertEqual(a1.public, True)
            self.assertEqual(a1.order, 1)
            a4 = actions[3]
            self.assertEqual(a4.action, 'A')
            self.assertEqual(a4.rtype, 'in_group')
            self.assertEqual(a4.ertype, 'in_group')
            self.assertEqual(a4.eid_from, self.totoeid)
            self.assertEqual(a4.eid_to, self.toto(cnx).in_group[0].eid)
            self.assertEqual(a4.order, 4)
            for i, rtype in ((1, 'owned_by'), (2, 'owned_by')):
                a = actions[i]
                self.assertEqual(a.action, 'A')
                self.assertEqual(a.eid_from, self.totoeid)
                self.assertEqual(a.rtype, rtype)
                self.assertEqual(a.order, i+1)
            self.assertEqual(set((actions[4].rtype, actions[5].rtype)),
                             set(('in_state', 'created_by')))
            for i in (4, 5):
                a = actions[i]
                self.assertEqual(a.action, 'A')
                self.assertEqual(a.eid_from, self.totoeid)
                self.assertEqual(a.order, i+1)

            # test undoable_transactions
            txs = cnx.undoable_transactions()
            self.assertEqual(len(txs), 1)
            self.assertEqual(txs[0].uuid, self.txuuid)
            # test transaction_info / undoable_transactions security
        with self.new_access('anon').client_cnx() as cnx:
            self.assertRaises(NoSuchTransaction,
                              cnx.transaction_info, self.txuuid)
            self.assertRaises(NoSuchTransaction,
                              cnx.transaction_actions, self.txuuid)
            self.assertRaises(NoSuchTransaction,
                              cnx.undo_transaction, self.txuuid)
            txs = cnx.undoable_transactions()
            self.assertEqual(len(txs), 0)

    def test_undoable_transactions(self):
        with self.admin_access.client_cnx() as cnx:
            toto = self.toto(cnx)
            e = cnx.create_entity('EmailAddress',
                                  address=u'toto@logilab.org',
                                  reverse_use_email=toto)
            txuuid1 = cnx.commit()
            toto.cw_delete()
            txuuid2 = cnx.commit()
            undoable_transactions = cnx.undoable_transactions
            txs = undoable_transactions(action='D')
            self.assertEqual(len(txs), 1, txs)
            self.assertEqual(txs[0].uuid, txuuid2)
            txs = undoable_transactions(action='C')
            self.assertEqual(len(txs), 2, txs)
            self.assertEqual(txs[0].uuid, txuuid1)
            self.assertEqual(txs[1].uuid, self.txuuid)
            txs = undoable_transactions(eid=toto.eid)
            self.assertEqual(len(txs), 3)
            self.assertEqual(txs[0].uuid, txuuid2)
            self.assertEqual(txs[1].uuid, txuuid1)
            self.assertEqual(txs[2].uuid, self.txuuid)
            txs = undoable_transactions(etype='CWUser')
            self.assertEqual(len(txs), 2)
            txs = undoable_transactions(etype='CWUser', action='C')
            self.assertEqual(len(txs), 1)
            self.assertEqual(txs[0].uuid, self.txuuid)
            txs = undoable_transactions(etype='EmailAddress', action='D')
            self.assertEqual(len(txs), 0)
            txs = undoable_transactions(etype='EmailAddress', action='D',
                                        public=False)
            self.assertEqual(len(txs), 1)
            self.assertEqual(txs[0].uuid, txuuid2)
            txs = undoable_transactions(eid=toto.eid, action='R', public=False)
            self.assertEqual(len(txs), 1)
            self.assertEqual(txs[0].uuid, txuuid2)

    def test_undo_deletion_base(self):
        with self.admin_access.client_cnx() as cnx:
            toto = self.toto(cnx)
            e = cnx.create_entity('EmailAddress',
                                  address=u'toto@logilab.org',
                                  reverse_use_email=toto)
            # entity with inlined relation
            p = cnx.create_entity('CWProperty',
                                  pkey=u'ui.default-text-format',
                                  value=u'text/rest',
                                  for_user=toto)
            cnx.commit()
            txs = cnx.undoable_transactions()
            self.assertEqual(len(txs), 2)
            toto.cw_delete()
            txuuid = cnx.commit()
            actions = cnx.transaction_info(txuuid).actions_list()
            self.assertEqual(len(actions), 1)
            toto.cw_clear_all_caches()
            e.cw_clear_all_caches()
            self.assertUndoTransaction(cnx, txuuid)
            undotxuuid = cnx.commit()
            self.assertEqual(undotxuuid, None) # undo not undoable
            self.assertTrue(cnx.execute('Any X WHERE X eid %(x)s', {'x': toto.eid}))
            self.assertTrue(cnx.execute('Any X WHERE X eid %(x)s', {'x': e.eid}))
            self.assertTrue(cnx.execute('Any X WHERE X has_text "toto@logilab"'))
            self.assertEqual(toto.cw_adapt_to('IWorkflowable').state, 'activated')
            self.assertEqual(toto.cw_adapt_to('IEmailable').get_email(), 'toto@logilab.org')
            self.assertEqual([(p.pkey, p.value) for p in toto.reverse_for_user],
                              [('ui.default-text-format', 'text/rest')])
            self.assertEqual([g.name for g in toto.in_group],
                              ['users'])
            self.assertEqual([et.name for et in toto.related('is', entities=True)],
                              ['CWUser'])
            self.assertEqual([et.name for et in toto.is_instance_of],
                              ['CWUser'])
            # undoing shouldn't be visble in undoable transaction, and the undone
            # transaction should be removed
            txs = self.cnx.undoable_transactions()
            self.assertEqual(len(txs), 2)
            self.assertRaises(NoSuchTransaction,
                              self.cnx.transaction_info, txuuid)
        with self.admin_access.repo_cnx() as cnx:
            with cnx.ensure_cnx_set:
                self.check_transaction_deleted(cnx, txuuid)
            # the final test: check we can login with the previously deleted user
        with self.new_access('toto').client_cnx():
            pass

    def test_undo_deletion_integrity_1(self):
        with self.admin_access.client_cnx() as cnx:
            # 'Personne fiche Card with' '??' cardinality
            c = cnx.create_entity('Card', title=u'hop', content=u'hop')
            p = cnx.create_entity('Personne', nom=u'louis', fiche=c)
            cnx.commit()
            c.cw_delete()
            txuuid = cnx.commit()
            c2 = cnx.create_entity('Card', title=u'hip', content=u'hip')
            p.cw_set(fiche=c2)
            cnx.commit()
            self.assertUndoTransaction(cnx, txuuid, [
                "Can't restore object relation fiche to entity "
                "%s which is already linked using this relation." % p.eid])
            cnx.commit()
            p.cw_clear_all_caches()
            self.assertEqual(p.fiche[0].eid, c2.eid)

    def test_undo_deletion_integrity_2(self):
        with self.admin_access.client_cnx() as cnx:
            # test validation error raised if we can't restore a required relation
            g = cnx.create_entity('CWGroup', name=u'staff')
            cnx.execute('DELETE U in_group G WHERE U eid %(x)s', {'x': self.totoeid})
            self.toto(cnx).cw_set(in_group=g)
            cnx.commit()
            self.toto(cnx).cw_delete()
            txuuid = cnx.commit()
            g.cw_delete()
            cnx.commit()
            self.assertUndoTransaction(cnx, txuuid, [
                u"Can't restore relation in_group, object entity "
                "%s doesn't exist anymore." % g.eid])
            with self.assertRaises(ValidationError) as cm:
                cnx.commit()
            cm.exception.translate(unicode)
            self.assertEqual(cm.exception.entity, self.totoeid)
            self.assertEqual(cm.exception.errors,
                              {'in_group-subject': u'at least one relation in_group is '
                               'required on CWUser (%s)' % self.totoeid})

    def test_undo_creation_1(self):
        with self.admin_access.client_cnx() as cnx:
            c = cnx.create_entity('Card', title=u'hop', content=u'hop')
            p = cnx.create_entity('Personne', nom=u'louis', fiche=c)
            txuuid = cnx.commit()
            self.assertUndoTransaction(cnx, txuuid)
            cnx.commit()
            self.assertFalse(cnx.execute('Any X WHERE X eid %(x)s', {'x': c.eid}))
            self.assertFalse(cnx.execute('Any X WHERE X eid %(x)s', {'x': p.eid}))
            self.assertFalse(cnx.execute('Any X,Y WHERE X fiche Y'))
        with self.admin_access.repo_cnx() as cnx:
            with cnx.ensure_cnx_set:
                for eid in (p.eid, c.eid):
                    self.assertFalse(cnx.system_sql(
                        'SELECT * FROM entities WHERE eid=%s' % eid).fetchall())
                    self.assertFalse(cnx.system_sql(
                        'SELECT 1 FROM owned_by_relation WHERE eid_from=%s' % eid).fetchall())
                    # added by sql in hooks (except when using dataimport)
                    self.assertFalse(cnx.system_sql(
                        'SELECT 1 FROM is_relation WHERE eid_from=%s' % eid).fetchall())
                    self.assertFalse(cnx.system_sql(
                        'SELECT 1 FROM is_instance_of_relation WHERE eid_from=%s' % eid).fetchall())
                self.check_transaction_deleted(cnx, txuuid)

    def test_undo_creation_integrity_1(self):
        with self.admin_access.client_cnx() as cnx:
            tutu = self.create_user(cnx, 'tutu', commit=False)
            txuuid = cnx.commit()
            email = cnx.create_entity('EmailAddress', address=u'tutu@cubicweb.org')
            prop = cnx.create_entity('CWProperty', pkey=u'ui.default-text-format',
                                     value=u'text/html')
            tutu.cw_set(use_email=email, reverse_for_user=prop)
            cnx.commit()
            with self.assertRaises(ValidationError) as cm:
                cnx.undo_transaction(txuuid)
            self.assertEqual(cm.exception.entity, tutu.eid)
            self.assertEqual(cm.exception.errors,
                             {None: 'some later transaction(s) touch entity, undo them first'})

    def test_undo_creation_integrity_2(self):
        with self.admin_access.client_cnx() as cnx:
            g = cnx.create_entity('CWGroup', name=u'staff')
            txuuid = cnx.commit()
            cnx.execute('DELETE U in_group G WHERE U eid %(x)s', {'x': self.totoeid})
            self.toto(cnx).cw_set(in_group=g)
            cnx.commit()
            with self.assertRaises(ValidationError) as cm:
                cnx.undo_transaction(txuuid)
            self.assertEqual(cm.exception.entity, g.eid)
            self.assertEqual(cm.exception.errors,
                             {None: 'some later transaction(s) touch entity, undo them first'})
        # self.assertEqual(errors,
        #                   [u"Can't restore relation in_group, object entity "
        #                   "%s doesn't exist anymore." % g.eid])
        # with self.assertRaises(ValidationError) as cm: cnx.commit()
        # self.assertEqual(cm.exception.entity, self.totoeid)
        # self.assertEqual(cm.exception.errors,
        #                   {'in_group-subject': u'at least one relation in_group is '
        #                    'required on CWUser (%s)' % self.totoeid})

    # test implicit 'replacement' of an inlined relation

    def test_undo_inline_rel_remove_ok(self):
        """Undo remove relation  Personne (?) fiche (?) Card

        NB: processed by `_undo_r` as expected"""
        with self.admin_access.client_cnx() as cnx:
            c = cnx.create_entity('Card', title=u'hop', content=u'hop')
            p = cnx.create_entity('Personne', nom=u'louis', fiche=c)
            cnx.commit()
            p.cw_set(fiche=None)
            txuuid = cnx.commit()
            self.assertUndoTransaction(cnx, txuuid)
            cnx.commit()
            p.cw_clear_all_caches()
            self.assertEqual(p.fiche[0].eid, c.eid)

    def test_undo_inline_rel_remove_ko(self):
        """Restore an inlined relation to a deleted entity, with an error.

        NB: processed by `_undo_r` as expected"""
        with self.admin_access.client_cnx() as cnx:
            c = cnx.create_entity('Card', title=u'hop', content=u'hop')
            p = cnx.create_entity('Personne', nom=u'louis', fiche=c)
            cnx.commit()
            p.cw_set(fiche=None)
            txuuid = cnx.commit()
            c.cw_delete()
            cnx.commit()
            self.assertUndoTransaction(cnx, txuuid, [
                "Can't restore relation fiche, object entity %d doesn't exist anymore." % c.eid])
            cnx.commit()
            p.cw_clear_all_caches()
            self.assertFalse(p.fiche)
        with self.admin_access.repo_cnx() as cnx:
            with cnx.ensure_cnx_set:
                self.assertIsNone(cnx.system_sql(
                    'SELECT cw_fiche FROM cw_Personne WHERE cw_eid=%s' % p.eid).fetchall()[0][0])

    def test_undo_inline_rel_add_ok(self):
        """Undo add relation  Personne (?) fiche (?) Card

        Caution processed by `_undo_u`, not `_undo_a` !"""
        with self.admin_access.client_cnx() as cnx:
            c = cnx.create_entity('Card', title=u'hop', content=u'hop')
            p = cnx.create_entity('Personne', nom=u'louis')
            cnx.commit()
            p.cw_set(fiche=c)
            txuuid = cnx.commit()
            self.assertUndoTransaction(cnx, txuuid)
            cnx.commit()
            p.cw_clear_all_caches()
            self.assertFalse(p.fiche)

    def test_undo_inline_rel_add_ko(self):
        """Undo add relation  Personne (?) fiche (?) Card

        Caution processed by `_undo_u`, not `_undo_a` !"""
        with self.admin_access.client_cnx() as cnx:
            c = cnx.create_entity('Card', title=u'hop', content=u'hop')
            p = cnx.create_entity('Personne', nom=u'louis')
            cnx.commit()
            p.cw_set(fiche=c)
            txuuid = cnx.commit()
            c.cw_delete()
            cnx.commit()
            self.assertUndoTransaction(cnx, txuuid)

    def test_undo_inline_rel_replace_ok(self):
        """Undo changing relation  Personne (?) fiche (?) Card

        Caution processed by `_undo_u` """
        with self.admin_access.client_cnx() as cnx:
            c1 = cnx.create_entity('Card', title=u'hop', content=u'hop')
            c2 = cnx.create_entity('Card', title=u'hip', content=u'hip')
            p = cnx.create_entity('Personne', nom=u'louis', fiche=c1)
            cnx.commit()
            p.cw_set(fiche=c2)
            txuuid = cnx.commit()
            self.assertUndoTransaction(cnx, txuuid)
            cnx.commit()
            p.cw_clear_all_caches()
            self.assertEqual(p.fiche[0].eid, c1.eid)

    def test_undo_inline_rel_replace_ko(self):
        """Undo changing relation  Personne (?) fiche (?) Card, with an error

        Caution processed by `_undo_u` """
        with self.admin_access.client_cnx() as cnx:
            c1 = cnx.create_entity('Card', title=u'hop', content=u'hop')
            c2 = cnx.create_entity('Card', title=u'hip', content=u'hip')
            p = cnx.create_entity('Personne', nom=u'louis', fiche=c1)
            cnx.commit()
            p.cw_set(fiche=c2)
            txuuid = cnx.commit()
            c1.cw_delete()
            cnx.commit()
            self.assertUndoTransaction(cnx, txuuid, [
                "can't restore entity %s of type Personne, target of fiche (eid %s)"
                " does not exist any longer" % (p.eid, c1.eid)])
            cnx.commit()
            p.cw_clear_all_caches()
            self.assertFalse(p.fiche)

    def test_undo_attr_update_ok(self):
        with self.admin_access.client_cnx() as cnx:
            p = cnx.create_entity('Personne', nom=u'toto')
            cnx.commit()
            p.cw_set(nom=u'titi')
            txuuid = cnx.commit()
            self.assertUndoTransaction(cnx, txuuid)
            p.cw_clear_all_caches()
            self.assertEqual(p.nom, u'toto')

    def test_undo_attr_update_ko(self):
        with self.admin_access.client_cnx() as cnx:
            p = cnx.create_entity('Personne', nom=u'toto')
            cnx.commit()
            p.cw_set(nom=u'titi')
            txuuid = cnx.commit()
            p.cw_delete()
            cnx.commit()
            self.assertUndoTransaction(cnx, txuuid, [
                u"can't restore state of entity %s, it has been deleted inbetween" % p.eid])


class UndoExceptionInUnicode(CubicWebTC):

    # problem occurs in string manipulation for python < 2.6
    def test___unicode__method(self):
        u = _UndoException(u"voilà")
        self.assertIsInstance(unicode(u), unicode)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
