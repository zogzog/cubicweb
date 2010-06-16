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
from __future__ import with_statement

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.transaction import *

class UndoableTransactionTC(CubicWebTC):

    def setup_database(self):
        self.session.undo_actions = set('CUDAR')
        self.toto = self.create_user('toto', password='toto', groups=('users',),
                                     commit=False)
        self.txuuid = self.commit()

    def tearDown(self):
        self.restore_connection()
        self.session.undo_support = set()
        super(UndoableTransactionTC, self).tearDown()

    def check_transaction_deleted(self, txuuid):
        # also check transaction actions have been properly deleted
        cu = self.session.system_sql(
            "SELECT * from tx_entity_actions WHERE tx_uuid='%s'" % txuuid)
        self.failIf(cu.fetchall())
        cu = self.session.system_sql(
            "SELECT * from tx_relation_actions WHERE tx_uuid='%s'" % txuuid)
        self.failIf(cu.fetchall())

    def test_undo_api(self):
        self.failUnless(self.txuuid)
        # test transaction api
        self.assertRaises(NoSuchTransaction,
                          self.cnx.transaction_info, 'hop')
        self.assertRaises(NoSuchTransaction,
                          self.cnx.transaction_actions, 'hop')
        self.assertRaises(NoSuchTransaction,
                          self.cnx.undo_transaction, 'hop')
        txinfo = self.cnx.transaction_info(self.txuuid)
        self.failUnless(txinfo.datetime)
        self.assertEquals(txinfo.user_eid, self.session.user.eid)
        self.assertEquals(txinfo.user().login, 'admin')
        actions = txinfo.actions_list()
        self.assertEquals(len(actions), 2)
        actions = txinfo.actions_list(public=False)
        self.assertEquals(len(actions), 6)
        a1 = actions[0]
        self.assertEquals(a1.action, 'C')
        self.assertEquals(a1.eid, self.toto.eid)
        self.assertEquals(a1.etype,'CWUser')
        self.assertEquals(a1.changes, None)
        self.assertEquals(a1.public, True)
        self.assertEquals(a1.order, 1)
        a4 = actions[3]
        self.assertEquals(a4.action, 'A')
        self.assertEquals(a4.rtype, 'in_group')
        self.assertEquals(a4.eid_from, self.toto.eid)
        self.assertEquals(a4.eid_to, self.toto.in_group[0].eid)
        self.assertEquals(a4.order, 4)
        for i, rtype in ((1, 'owned_by'), (2, 'owned_by'),
                         (4, 'in_state'), (5, 'created_by')):
            a = actions[i]
            self.assertEquals(a.action, 'A')
            self.assertEquals(a.eid_from, self.toto.eid)
            self.assertEquals(a.rtype, rtype)
            self.assertEquals(a.order, i+1)
        # test undoable_transactions
        txs = self.cnx.undoable_transactions()
        self.assertEquals(len(txs), 1)
        self.assertEquals(txs[0].uuid, self.txuuid)
        # test transaction_info / undoable_transactions security
        cnx = self.login('anon')
        self.assertRaises(NoSuchTransaction,
                          cnx.transaction_info, self.txuuid)
        self.assertRaises(NoSuchTransaction,
                          cnx.transaction_actions, self.txuuid)
        self.assertRaises(NoSuchTransaction,
                          cnx.undo_transaction, self.txuuid)
        txs = cnx.undoable_transactions()
        self.assertEquals(len(txs), 0)

    def test_undoable_transactions(self):
        toto = self.toto
        e = self.session.create_entity('EmailAddress',
                                       address=u'toto@logilab.org',
                                       reverse_use_email=toto)
        txuuid1 = self.commit()
        toto.cw_delete()
        txuuid2 = self.commit()
        undoable_transactions = self.cnx.undoable_transactions
        txs = undoable_transactions(action='D')
        self.assertEquals(len(txs), 1, txs)
        self.assertEquals(txs[0].uuid, txuuid2)
        txs = undoable_transactions(action='C')
        self.assertEquals(len(txs), 2, txs)
        self.assertEquals(txs[0].uuid, txuuid1)
        self.assertEquals(txs[1].uuid, self.txuuid)
        txs = undoable_transactions(eid=toto.eid)
        self.assertEquals(len(txs), 3)
        self.assertEquals(txs[0].uuid, txuuid2)
        self.assertEquals(txs[1].uuid, txuuid1)
        self.assertEquals(txs[2].uuid, self.txuuid)
        txs = undoable_transactions(etype='CWUser')
        self.assertEquals(len(txs), 2)
        txs = undoable_transactions(etype='CWUser', action='C')
        self.assertEquals(len(txs), 1)
        self.assertEquals(txs[0].uuid, self.txuuid)
        txs = undoable_transactions(etype='EmailAddress', action='D')
        self.assertEquals(len(txs), 0)
        txs = undoable_transactions(etype='EmailAddress', action='D',
                                    public=False)
        self.assertEquals(len(txs), 1)
        self.assertEquals(txs[0].uuid, txuuid2)
        txs = undoable_transactions(eid=toto.eid, action='R', public=False)
        self.assertEquals(len(txs), 1)
        self.assertEquals(txs[0].uuid, txuuid2)

    def test_undo_deletion_base(self):
        toto = self.toto
        e = self.session.create_entity('EmailAddress',
                                       address=u'toto@logilab.org',
                                       reverse_use_email=toto)
        # entity with inlined relation
        p = self.session.create_entity('CWProperty',
                                       pkey=u'ui.default-text-format',
                                       value=u'text/rest',
                                       for_user=toto)
        self.commit()
        txs = self.cnx.undoable_transactions()
        self.assertEquals(len(txs), 2)
        toto.cw_delete()
        txuuid = self.commit()
        actions = self.cnx.transaction_info(txuuid).actions_list()
        self.assertEquals(len(actions), 1)
        toto.clear_all_caches()
        e.clear_all_caches()
        errors = self.cnx.undo_transaction(txuuid)
        undotxuuid = self.commit()
        self.assertEquals(undotxuuid, None) # undo not undoable
        self.assertEquals(errors, [])
        self.failUnless(self.execute('Any X WHERE X eid %(x)s', {'x': toto.eid}))
        self.failUnless(self.execute('Any X WHERE X eid %(x)s', {'x': e.eid}))
        self.failUnless(self.execute('Any X WHERE X has_text "toto@logilab"'))
        self.assertEquals(toto.cw_adapt_to('IWorkflowable').state, 'activated')
        self.assertEquals(toto.cw_adapt_to('IEmailable').get_email(), 'toto@logilab.org')
        self.assertEquals([(p.pkey, p.value) for p in toto.reverse_for_user],
                          [('ui.default-text-format', 'text/rest')])
        self.assertEquals([g.name for g in toto.in_group],
                          ['users'])
        self.assertEquals([et.name for et in toto.related('is', entities=True)],
                          ['CWUser'])
        self.assertEquals([et.name for et in toto.is_instance_of],
                          ['CWUser'])
        # undoing shouldn't be visble in undoable transaction, and the undoed
        # transaction should be removed
        txs = self.cnx.undoable_transactions()
        self.assertEquals(len(txs), 2)
        self.assertRaises(NoSuchTransaction,
                          self.cnx.transaction_info, txuuid)
        self.check_transaction_deleted(txuuid)
        # the final test: check we can login with the previously deleted user
        self.login('toto')

    def test_undo_deletion_integrity_1(self):
        session = self.session
        # 'Personne fiche Card with' '??' cardinality
        c = session.create_entity('Card', title=u'hop', content=u'hop')
        p = session.create_entity('Personne', nom=u'louis', fiche=c)
        self.commit()
        c.cw_delete()
        txuuid = self.commit()
        c2 = session.create_entity('Card', title=u'hip', content=u'hip')
        p.set_relations(fiche=c2)
        self.commit()
        errors = self.cnx.undo_transaction(txuuid)
        self.commit()
        p.clear_all_caches()
        self.assertEquals(p.fiche[0].eid, c2.eid)
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0],
                          "Can't restore object relation fiche to entity "
                          "%s which is already linked using this relation." % p.eid)

    def test_undo_deletion_integrity_2(self):
        # test validation error raised if we can't restore a required relation
        session = self.session
        g = session.create_entity('CWGroup', name=u'staff')
        session.execute('DELETE U in_group G WHERE U eid %(x)s', {'x': self.toto.eid})
        self.toto.set_relations(in_group=g)
        self.commit()
        self.toto.cw_delete()
        txuuid = self.commit()
        g.cw_delete()
        self.commit()
        errors = self.cnx.undo_transaction(txuuid)
        self.assertEquals(errors,
                          [u"Can't restore relation in_group, object entity "
                          "%s doesn't exist anymore." % g.eid])
        ex = self.assertRaises(ValidationError, self.commit)
        self.assertEquals(ex.entity, self.toto.eid)
        self.assertEquals(ex.errors,
                          {'in_group-subject': u'at least one relation in_group is '
                           'required on CWUser (%s)' % self.toto.eid})

    def test_undo_creation_1(self):
        session = self.session
        c = session.create_entity('Card', title=u'hop', content=u'hop')
        p = session.create_entity('Personne', nom=u'louis', fiche=c)
        txuuid = self.commit()
        errors = self.cnx.undo_transaction(txuuid)
        self.commit()
        self.failIf(errors)
        self.failIf(self.execute('Any X WHERE X eid %(x)s', {'x': c.eid}))
        self.failIf(self.execute('Any X WHERE X eid %(x)s', {'x': p.eid}))
        self.failIf(self.execute('Any X,Y WHERE X fiche Y'))
        self.session.set_pool()
        for eid in (p.eid, c.eid):
            self.failIf(session.system_sql(
                'SELECT * FROM entities WHERE eid=%s' % eid).fetchall())
            self.failIf(session.system_sql(
                'SELECT 1 FROM owned_by_relation WHERE eid_from=%s' % eid).fetchall())
            # added by sql in hooks (except when using dataimport)
            self.failIf(session.system_sql(
                'SELECT 1 FROM is_relation WHERE eid_from=%s' % eid).fetchall())
            self.failIf(session.system_sql(
                'SELECT 1 FROM is_instance_of_relation WHERE eid_from=%s' % eid).fetchall())
        self.check_transaction_deleted(txuuid)


    def test_undo_creation_integrity_1(self):
        session = self.session
        tutu = self.create_user('tutu', commit=False)
        txuuid = self.commit()
        email = self.request().create_entity('EmailAddress', address=u'tutu@cubicweb.org')
        prop = self.request().create_entity('CWProperty', pkey=u'ui.default-text-format',
                                            value=u'text/html')
        tutu.set_relations(use_email=email, reverse_for_user=prop)
        self.commit()
        ex = self.assertRaises(ValidationError,
                               self.cnx.undo_transaction, txuuid)
        self.assertEquals(ex.entity, tutu.eid)
        self.assertEquals(ex.errors,
                          {None: 'some later transaction(s) touch entity, undo them first'})

    def test_undo_creation_integrity_2(self):
        session = self.session
        g = session.create_entity('CWGroup', name=u'staff')
        txuuid = self.commit()
        session.execute('DELETE U in_group G WHERE U eid %(x)s', {'x': self.toto.eid})
        self.toto.set_relations(in_group=g)
        self.commit()
        ex = self.assertRaises(ValidationError,
                               self.cnx.undo_transaction, txuuid)
        self.assertEquals(ex.entity, g.eid)
        self.assertEquals(ex.errors,
                          {None: 'some later transaction(s) touch entity, undo them first'})
        # self.assertEquals(errors,
        #                   [u"Can't restore relation in_group, object entity "
        #                   "%s doesn't exist anymore." % g.eid])
        # ex = self.assertRaises(ValidationError, self.commit)
        # self.assertEquals(ex.entity, self.toto.eid)
        # self.assertEquals(ex.errors,
        #                   {'in_group-subject': u'at least one relation in_group is '
        #                    'required on CWUser (%s)' % self.toto.eid})

    # test implicit 'replacement' of an inlined relation

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
