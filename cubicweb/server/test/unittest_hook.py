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
"""unit/functional tests for cubicweb.server.hook"""

from logilab.common.testlib import TestCase, unittest_main, mock_object

from cubicweb.devtools import TestServerConfiguration, fake
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server import hook
from cubicweb.hooks import integrity, syncschema

class OperationsTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        self.hm = self.repo.hm

    def test_late_operation(self):
        with self.admin_access.repo_cnx() as cnx:
            l1 = hook.LateOperation(cnx)
            l2 = hook.LateOperation(cnx)
            l3 = hook.Operation(cnx)
            self.assertEqual(cnx.pending_operations, [l3, l1, l2])

    def test_single_last_operation(self):
        with self.admin_access.repo_cnx() as cnx:
            l0 = hook.SingleLastOperation(cnx)
            l1 = hook.LateOperation(cnx)
            l2 = hook.LateOperation(cnx)
            l3 = hook.Operation(cnx)
            self.assertEqual(cnx.pending_operations, [l3, l1, l2, l0])
            l4 = hook.SingleLastOperation(cnx)
            self.assertEqual(cnx.pending_operations, [l3, l1, l2, l4])

    def test_global_operation_order(self):
        with self.admin_access.repo_cnx() as cnx:
            op1 = syncschema.RDefDelOp(cnx)
            op2 = integrity._CheckORelationOp(cnx)
            op3 = syncschema.MemSchemaNotifyChanges(cnx)
            self.assertEqual([op1, op2, op3], cnx.pending_operations)

class HookCalled(Exception): pass

config = TestServerConfiguration('data', __file__)
config.bootstrap_cubes()
schema = config.load_schema()

def tearDownModule(*args):
    global config, schema
    del config, schema

class AddAnyHook(hook.Hook):
    __regid__ = 'addany'
    category = 'cat1'
    events = ('before_add_entity',)
    def __call__(self):
        raise HookCalled()


class HooksRegistryTC(TestCase):

    def setUp(self):
        """ called before each test from this class """
        self.vreg = mock_object(config=config, schema=schema)
        self.o = hook.HooksRegistry(self.vreg)

    def test_register_bad_hook1(self):
        class _Hook(hook.Hook):
            events = ('before_add_entiti',)
        with self.assertRaises(Exception) as cm:
            self.o.register(_Hook)
        self.assertEqual(str(cm.exception), 'bad event before_add_entiti on %s._Hook' % __name__)

    def test_register_bad_hook2(self):
        class _Hook(hook.Hook):
            events = None
        with self.assertRaises(Exception) as cm:
            self.o.register(_Hook)
        self.assertEqual(str(cm.exception), 'bad .events attribute None on %s._Hook' % __name__)

    def test_register_bad_hook3(self):
        class _Hook(hook.Hook):
            events = 'before_add_entity'
        with self.assertRaises(Exception) as cm:
            self.o.register(_Hook)
        self.assertEqual(str(cm.exception), 'bad event b on %s._Hook' % __name__)

    def test_call_hook(self):
        self.o.register(AddAnyHook)
        dis = set()
        cw = fake.FakeSession()
        cw.is_hook_activated = lambda cls: cls.category not in dis
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'before_add_entity', cw)
        dis.add('cat1')
        self.o.call_hooks('before_add_entity', cw) # disabled hooks category, not called
        dis.remove('cat1')
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'before_add_entity', cw)
        self.o.unregister(AddAnyHook)
        self.o.call_hooks('before_add_entity', cw) # nothing to call


class SystemHooksTC(CubicWebTC):

    def test_startup_shutdown(self):
        import hooks # cubicweb/server/test/data/hooks.py
        self.assertEqual(hooks.CALLED_EVENTS['server_startup'], True)
        # don't actually call repository.shutdown !
        self.repo.hm.call_hooks('server_shutdown', repo=self.repo)
        self.assertEqual(hooks.CALLED_EVENTS['server_shutdown'], True)

    def test_session_open_close(self):
        import hooks # cubicweb/server/test/data/hooks.py
        anonaccess = self.new_access('anon')
        with anonaccess.repo_cnx() as cnx:
            self.assertEqual(hooks.CALLED_EVENTS['session_open'], 'anon')
        anonaccess.close()
        self.assertEqual(hooks.CALLED_EVENTS['session_close'], 'anon')


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
#         self.assertEqual(self.called, [])
#         self.o.call_hooks('before_add_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.assertEqual(self.called, [(1, 'concerne', 2)])

#     def test_after_add_relation(self):
#         """make sure after_xxx_relation hooks are deferred"""
#         self.o.register(self._after_relation_hook,
#                              'after_add_relation', 'concerne')
#         self.assertEqual(self.called, [])
#         self.o.call_hooks('after_add_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.o.call_hooks('after_add_relation', 'concerne', 'USER',
#                           3, 'concerne', 4)
#         self.assertEqual(self.called, [(1, 'concerne', 2), (3, 'concerne', 4)])

#     def test_before_delete_relation(self):
#         """make sure before_xxx_relation hooks are called directly"""
#         self.o.register(self._before_relation_hook,
#                              'before_delete_relation', 'concerne')
#         self.assertEqual(self.called, [])
#         self.o.call_hooks('before_delete_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.assertEqual(self.called, [(1, 'concerne', 2)])

#     def test_after_delete_relation(self):
#         """make sure after_xxx_relation hooks are deferred"""
#         self.o.register(self._after_relation_hook,
#                         'after_delete_relation', 'concerne')
#         self.o.call_hooks('after_delete_relation', 'concerne', 'USER',
#                           1, 'concerne', 2)
#         self.o.call_hooks('after_delete_relation', 'concerne', 'USER',
#                           3, 'concerne', 4)
#         self.assertEqual(self.called, [(1, 'concerne', 2), (3, 'concerne', 4)])


#     def _before_relation_hook(self, cnxset, subject, r_type, object):
#         self.called.append((subject, r_type, object))

#     def _after_relation_hook(self, cnxset, subject, r_type, object):
#         self.called.append((subject, r_type, object))


if __name__ == '__main__':
    unittest_main()
