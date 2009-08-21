# -*- coding: utf-8 -*-
"""unit/functional tests for cubicweb.server.hookhelper

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.server.pool import LateOperation, Operation, SingleLastOperation
from cubicweb.server.hookhelper import *
from cubicweb.server import hooks, schemahooks


def clean_session_ops(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        finally:
            self.session.pending_operations[:] = []
    return wrapper

class HookHelpersTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        self.hm = self.repo.hm

    @clean_session_ops
    def test_late_operation(self):
        session = self.session
        l1 = LateOperation(session)
        l2 = LateOperation(session)
        l3 = Operation(session)
        self.assertEquals(session.pending_operations, [l3, l1, l2])

    @clean_session_ops
    def test_single_last_operation(self):
        session = self.session
        l0 = SingleLastOperation(session)
        l1 = LateOperation(session)
        l2 = LateOperation(session)
        l3 = Operation(session)
        self.assertEquals(session.pending_operations, [l3, l1, l2, l0])
        l4 = SingleLastOperation(session)
        self.assertEquals(session.pending_operations, [l3, l1, l2, l4])

    @clean_session_ops
    def test_global_operation_order(self):
        session = self.session
        op1 = hooks.DelayedDeleteOp(session)
        op2 = schemahooks.MemSchemaRDefDel(session)
        # equivalent operation generated by op2 but replace it here by op3 so we
        # can check the result...
        op3 = schemahooks.MemSchemaNotifyChanges(session)
        op4 = hooks.DelayedDeleteOp(session)
        op5 = hooks.CheckORelationOp(session)
        self.assertEquals(session.pending_operations, [op1, op2, op4, op5, op3])

if __name__ == '__main__':
    unittest_main()
