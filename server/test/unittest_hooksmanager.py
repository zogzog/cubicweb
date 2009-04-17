"""unit tests for the hooks manager
"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.server.hooksmanager import HooksManager, Hook
from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.apptest import RepositoryBasedTC

class HookCalled(Exception): pass

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()

class HooksManagerTC(TestCase):
    args = (None,)
    kwargs = {'a': 1}
    
    def setUp(self):
        """ called before each test from this class """
        self.o = HooksManager(schema)

    def test_register_hook_raise_keyerror(self):
        self.assertRaises(AssertionError,
                          self.o.register_hook, self._hook, 'before_add_entiti')
        self.assertRaises(AssertionError,
                          self.o.register_hook, self._hook, 'session_login', 'CWEType')
        self.assertRaises(AssertionError,
                          self.o.register_hook, self._hook, 'session_logout', 'CWEType')
        self.assertRaises(AssertionError,
                          self.o.register_hook, self._hook, 'server_startup', 'CWEType')
        self.assertRaises(AssertionError,
                          self.o.register_hook, self._hook, 'server_shutdown', 'CWEType')
        
    def test_register_hook1(self):
        self.o.register_hook(self._hook, 'before_add_entity')
        self.o.register_hook(self._hook, 'before_delete_entity', 'Personne')
        self._test_called_hooks()
        
    def test_register_hook2(self):
        self.o.register_hook(self._hook, 'before_add_entity', '')
        self.o.register_hook(self._hook, 'before_delete_entity', 'Personne')
        self._test_called_hooks()
        
    def test_register_hook3(self):
        self.o.register_hook(self._hook, 'before_add_entity', None)
        self.o.register_hook(self._hook, 'before_delete_entity', 'Personne')
        self._test_called_hooks()
        
    def test_register_hooks(self):
        self.o.register_hooks({'before_add_entity' : {'': [self._hook]},
                               'before_delete_entity' : {'Personne': [self._hook]},
                               })
        self._test_called_hooks()

    def test_unregister_hook(self):
        self.o.register_hook(self._hook, 'after_delete_entity', 'Personne')
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'after_delete_entity', 'Personne',
                          *self.args, **self.kwargs)
        self.o.unregister_hook(self._hook, 'after_delete_entity', 'Personne')
        # no hook should be called there
        self.o.call_hooks('after_delete_entity', 'Personne')
        

    def _test_called_hooks(self):
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'before_add_entity', '',
                          *self.args, **self.kwargs)
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'before_add_entity', None,
                          *self.args, **self.kwargs)
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'before_add_entity', 'Personne',
                          *self.args, **self.kwargs)
        self.assertRaises(HookCalled,
                          self.o.call_hooks, 'before_delete_entity', 'Personne',
                          *self.args, **self.kwargs)
        # no hook should be called there
        self.o.call_hooks('before_delete_entity', None)
        self.o.call_hooks('before_delete_entity', 'Societe')


    def _hook(self, *args, **kwargs):
        # check arguments
        self.assertEqual(args, self.args)
        self.assertEqual(kwargs, self.kwargs)
        raise HookCalled()


class RelationHookTC(TestCase):
    """testcase for relation hooks grouping"""
    def setUp(self):
        """ called before each test from this class """
        self.o = HooksManager(schema)
        self.called = []

    def test_before_add_relation(self):
        """make sure before_xxx_relation hooks are called directly"""
        self.o.register_hook(self._before_relation_hook,
                             'before_add_relation', 'concerne')
        self.assertEquals(self.called, [])
        self.o.call_hooks('before_add_relation', 'concerne', 'USER',
                          1, 'concerne', 2)        
        self.assertEquals(self.called, [(1, 'concerne', 2)])
        
    def test_after_add_relation(self):
        """make sure after_xxx_relation hooks are deferred"""
        self.o.register_hook(self._after_relation_hook,
                             'after_add_relation', 'concerne')
        self.assertEquals(self.called, [])
        self.o.call_hooks('after_add_relation', 'concerne', 'USER',
                          1, 'concerne', 2)
        self.o.call_hooks('after_add_relation', 'concerne', 'USER',
                          3, 'concerne', 4)
        self.assertEquals(self.called, [(1, 'concerne', 2), (3, 'concerne', 4)])
    
    def test_before_delete_relation(self):
        """make sure before_xxx_relation hooks are called directly"""
        self.o.register_hook(self._before_relation_hook,
                             'before_delete_relation', 'concerne')
        self.assertEquals(self.called, [])
        self.o.call_hooks('before_delete_relation', 'concerne', 'USER',
                          1, 'concerne', 2)        
        self.assertEquals(self.called, [(1, 'concerne', 2)])

    def test_after_delete_relation(self):
        """make sure after_xxx_relation hooks are deferred"""
        self.o.register_hook(self._after_relation_hook,
                             'after_delete_relation', 'concerne')
        self.o.call_hooks('after_delete_relation', 'concerne', 'USER',
                          1, 'concerne', 2)
        self.o.call_hooks('after_delete_relation', 'concerne', 'USER',
                          3, 'concerne', 4)
        self.assertEquals(self.called, [(1, 'concerne', 2), (3, 'concerne', 4)])


    def _before_relation_hook(self, pool, subject, r_type, object):
        self.called.append((subject, r_type, object))

    def _after_relation_hook(self, pool, subject, r_type, object):
        self.called.append((subject, r_type, object))


class SystemHooksTC(RepositoryBasedTC):

    def test_startup_shutdown(self):
        import hooks # cubicweb/server/test/data/hooks.py
        self.assertEquals(hooks.CALLED_EVENTS['server_startup'], True)
        # don't actually call repository.shutdown !
        self.repo.hm.call_hooks('server_shutdown', repo=None)
        self.assertEquals(hooks.CALLED_EVENTS['server_shutdown'], True)

    def test_session_open_close(self):
        import hooks # cubicweb/server/test/data/hooks.py
        cnx = self.login('anon')
        self.assertEquals(hooks.CALLED_EVENTS['session_open'], 'anon')
        cnx.close()
        self.assertEquals(hooks.CALLED_EVENTS['session_close'], 'anon')


from itertools import repeat

class MyHook(Hook):
    schema = schema # set for actual hooks at registration time
    events = ('whatever', 'another')
    accepts = ('Societe', 'Division')
    
class HookTC(RepositoryBasedTC):
    def test_inheritance(self):
        self.assertEquals(list(MyHook.register_to()),
                          zip(repeat('whatever'), ('Societe', 'Division', 'SubDivision'))
                          + zip(repeat('another'), ('Societe', 'Division', 'SubDivision')))


if __name__ == '__main__':
    unittest_main()
