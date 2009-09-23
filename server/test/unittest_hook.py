# -*- coding: utf-8 -*-
"""unit/functional tests for cubicweb.server.hook

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main, mock_object


from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.selectors import implements
from cubicweb.server import hook
from cubicweb.hooks import integrity, syncschema


def clean_session_ops(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        finally:
            self.session.pending_operations[:] = []
    return wrapper

class OperationsTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        self.hm = self.repo.hm

    @clean_session_ops
    def test_late_operation(self):
        session = self.session
        l1 = hook.LateOperation(session)
        l2 = hook.LateOperation(session)
        l3 = hook.Operation(session)
        self.assertEquals(session.pending_operations, [l3, l1, l2])

    @clean_session_ops
    def test_single_last_operation(self):
        session = self.session
        l0 = hook.SingleLastOperation(session)
        l1 = hook.LateOperation(session)
        l2 = hook.LateOperation(session)
        l3 = hook.Operation(session)
        self.assertEquals(session.pending_operations, [l3, l1, l2, l0])
        l4 = hook.SingleLastOperation(session)
        self.assertEquals(session.pending_operations, [l3, l1, l2, l4])

    @clean_session_ops
    def test_global_operation_order(self):
        session = self.session
        op1 = integrity._DelayedDeleteOp(session)
        op2 = syncschema.MemSchemaRDefDel(session)
        # equivalent operation generated by op2 but replace it here by op3 so we
        # can check the result...
        op3 = syncschema.MemSchemaNotifyChanges(session)
        op4 = integrity._DelayedDeleteOp(session)
        op5 = integrity._CheckORelationOp(session)
        self.assertEquals(session.pending_operations, [op1, op2, op4, op5, op3])


class HookCalled(Exception): pass

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()

class AddAnyHook(hook.Hook):
    __regid__ = 'addany'
    category = 'cat1'
    events = ('before_add_entity',)
    def __call__(self):
        raise HookCalled()


class HooksManagerTC(TestCase):

    def setUp(self):
        """ called before each test from this class """
        self.vreg = mock_object(config=config, schema=schema)
        self.o = hook.HooksRegistry(self.vreg)

    def test_register_bad_hook1(self):
        class _Hook(hook.Hook):
            events = ('before_add_entiti',)
        ex = self.assertRaises(Exception, self.o.register, _Hook)
        self.assertEquals(str(ex), 'bad event before_add_entiti on unittest_hook._Hook')

    def test_register_bad_hook2(self):
        class _Hook(hook.Hook):
            events = None
        ex = self.assertRaises(Exception, self.o.register, _Hook)
        self.assertEquals(str(ex), 'bad .events attribute None on unittest_hook._Hook')

    def test_register_bad_hook3(self):
        class _Hook(hook.Hook):
            events = 'before_add_entity'
        ex = self.assertRaises(Exception, self.o.register, _Hook)
        self.assertEquals(str(ex), 'bad event b on unittest_hook._Hook')

    def test_call_hook(self):
        self.o.register(AddAnyHook)
        cw = mock_object(vreg=self.vreg)
        self.assertRaises(HookCalled, self.o.call_hooks, 'before_add_entity', cw)
        self.o.call_hooks('before_delete_entity', cw) # nothing to call
        config.disabled_hooks_categories.add('cat1')
        self.o.call_hooks('before_add_entity', cw) # disabled hooks category, not called
        config.disabled_hooks_categories.remove('cat1')
        self.assertRaises(HookCalled, self.o.call_hooks, 'before_add_entity', cw)
        self.o.unregister(AddAnyHook)
        self.o.call_hooks('before_add_entity', cw) # nothing to call


class SystemHooksTC(CubicWebTC):

    def test_startup_shutdown(self):
        import hooks # cubicweb/server/test/data/hooks.py
        self.assertEquals(hooks.CALLED_EVENTS['server_startup'], True)
        # don't actually call repository.shutdown !
        self.repo.hm.call_hooks('server_shutdown', repo=self.repo)
        self.assertEquals(hooks.CALLED_EVENTS['server_shutdown'], True)

    def test_session_open_close(self):
        import hooks # cubicweb/server/test/data/hooks.py
        cnx = self.login('anon')
        self.assertEquals(hooks.CALLED_EVENTS['session_open'], 'anon')
        cnx.close()
        self.assertEquals(hooks.CALLED_EVENTS['session_close'], 'anon')


# class RelationHookTC(TestCase):
#     """testcase for relation hooks grouping"""
#     def setUp(self):
#         """ called before each test from this class """
#         self.o = HooksManager(schema)
#         self.called = []

#     def test_before_add_relation(self):
#         """make sure before_xxx_relation hooks are called directly"""
#         self.o.register(self._before_relation_hook,
#                              'before_add_relation', 'concerne')
#         self.assertEquals(self.called, [])
#         self.o.call_hooks('before_add_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.assertEquals(self.called, [(1, 'concerne', 2)])

#     def test_after_add_relation(self):
#         """make sure after_xxx_relation hooks are deferred"""
#         self.o.register(self._after_relation_hook,
#                              'after_add_relation', 'concerne')
#         self.assertEquals(self.called, [])
#         self.o.call_hooks('after_add_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.o.call_hooks('after_add_relation', 'concerne', 'USER',
#                           3, 'concerne', 4)
#         self.assertEquals(self.called, [(1, 'concerne', 2), (3, 'concerne', 4)])

#     def test_before_delete_relation(self):
#         """make sure before_xxx_relation hooks are called directly"""
#         self.o.register(self._before_relation_hook,
#                              'before_delete_relation', 'concerne')
#         self.assertEquals(self.called, [])
#         self.o.call_hooks('before_delete_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.assertEquals(self.called, [(1, 'concerne', 2)])

#     def test_after_delete_relation(self):
#         """make sure after_xxx_relation hooks are deferred"""
#         self.o.register(self._after_relation_hook,
#                         'after_delete_relation', 'concerne')
#         self.o.call_hooks('after_delete_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.o.call_hooks('after_delete_relation', 'concerne', 'USER',
#                           3, 'concerne', 4)
#         self.assertEquals(self.called, [(1, 'concerne', 2), (3, 'concerne', 4)])


#     def _before_relation_hook(self, pool, subject, r_type, object):
#         self.called.append((subject, r_type, object))

#     def _after_relation_hook(self, pool, subject, r_type, object):
#         self.called.append((subject, r_type, object))


if __name__ == '__main__':
    unittest_main()
