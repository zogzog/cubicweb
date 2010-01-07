"""Hooks management

Hooks are called before / after any individual update of entities / relations
in the repository.

Here is the prototype of the different hooks:

* filtered on the entity's type:

  before_add_entity    (session, entity)
  after_add_entity     (session, entity)
  before_update_entity (session, entity)
  after_update_entity  (session, entity)
  before_delete_entity (session, eid)
  after_delete_entity  (session, eid)

* filtered on the relation's type:

  before_add_relation    (session, fromeid, rtype, toeid)
  after_add_relation     (session, fromeid, rtype, toeid)
  before_delete_relation (session, fromeid, rtype, toeid)
  after_delete_relation  (session, fromeid, rtype, toeid)


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

ENTITIES_HOOKS = ('before_add_entity',    'after_add_entity',
                  'before_update_entity', 'after_update_entity',
                  'before_delete_entity', 'after_delete_entity')
RELATIONS_HOOKS = ('before_add_relation',   'after_add_relation' ,
                   'before_delete_relation','after_delete_relation')
SYSTEM_HOOKS = ('server_backup', 'server_restore',
                'server_startup', 'server_shutdown',
                'session_open', 'session_close')

ALL_HOOKS = frozenset(ENTITIES_HOOKS + RELATIONS_HOOKS + SYSTEM_HOOKS)

class HooksManager(object):
    """handle hooks registration and calls
    """
    verification_hooks_activated = True

    def __init__(self, schema):
        self.set_schema(schema)

    def set_schema(self, schema):
        self._hooks = {}
        self.schema = schema
        self._init_hooks(schema)

    def register_hooks(self, hooks):
        """register a dictionary of hooks :

             {'event': {'entity or relation type': [callbacks list]}}
        """
        for event, subevents in hooks.items():
            for subevent, callbacks in subevents.items():
                for callback in callbacks:
                    self.register_hook(callback, event, subevent)

    def register_hook(self, function, event, etype=''):
        """register a function to call when <event> occurs

        <etype> is an entity/relation type or an empty string.

        If etype is the empty string, the function will be called at each event,
        else the function will be called only when event occurs on an entity or
        relation of the given type.
        """
        assert event in ALL_HOOKS, '%r NOT IN %r' % (event, ALL_HOOKS)
        assert (not event in SYSTEM_HOOKS or not etype), (event, etype)
        etype = etype or ''
        try:
            self._hooks[event][etype].append(function)
            self.debug('registered hook %s on %s (%s)', event, etype or 'any',
                       function.func_name)

        except KeyError:
            self.error('can\'t register hook %s on %s (%s)',
                       event, etype or 'any', function.func_name)

    def unregister_hook(self, function_or_cls, event=None, etype=''):
        """unregister a function to call when <event> occurs, or a Hook subclass.
        In the later case, event/type information are extracted from the given
        class.
        """
        if isinstance(function_or_cls, type) and issubclass(function_or_cls, Hook):
            for event, ertype in function_or_cls.register_to():
                for hook in self._hooks[event][ertype]:
                    if getattr(hook, 'im_self', None).__class__ is function_or_cls:
                        self._hooks[event][ertype].remove(hook)
                        self.info('unregister hook %s on %s (%s)', event, etype,
                                  function_or_cls.__name__)
                        break
                else:
                    self.warning("can't unregister hook %s on %s (%s), not found",
                                 event, etype, function_or_cls.__name__)
        else:
            assert event in ALL_HOOKS, event
            etype = etype or ''
            self.info('unregister hook %s on %s (%s)', event, etype,
                      function_or_cls.func_name)
            self._hooks[event][etype].remove(function_or_cls)

    def call_hooks(self, __event, __type='', *args, **kwargs):
        """call hook matching event and optional type"""
        if __type:
            self.info('calling hooks for event %s (%s)', __event, __type)
        else:
            self.info('calling hooks for event %s', __event)
        # call generic hooks first
        for hook in self._hooks[__event]['']:
            #print '[generic]', hook.__name__
            hook(*args, **kwargs)
        if __type:
            for hook in self._hooks[__event][__type]:
                #print '[%s]'%__type, hook.__name__
                hook(*args, **kwargs)

    def _init_hooks(self, schema):
        """initialize the hooks map"""
        for hook_event in ENTITIES_HOOKS:
            self._hooks[hook_event] = {'': []}
            for etype in schema.entities():
                self._hooks[hook_event][etype] = []
        for hook_event in RELATIONS_HOOKS:
            self._hooks[hook_event] = {'': []}
            for r_type in schema.relations():
                self._hooks[hook_event][r_type] = []
        for hook_event in SYSTEM_HOOKS:
            self._hooks[hook_event] = {'': []}

    def register_system_hooks(self, config):
        """register system hooks according to the configuration"""
        self.info('register core hooks')
        from cubicweb.server.hooks import _register_metadata_hooks, _register_wf_hooks
        _register_metadata_hooks(self)
        self.info('register workflow hooks')
        _register_wf_hooks(self)
        if config.core_hooks:
            from cubicweb.server.hooks import _register_core_hooks
            _register_core_hooks(self)
        if config.schema_hooks:
            from cubicweb.server.schemahooks import _register_schema_hooks
            self.info('register schema hooks')
            _register_schema_hooks(self)
        if config.usergroup_hooks:
            from cubicweb.server.hooks import _register_usergroup_hooks
            from cubicweb.server.hooks import _register_eproperty_hooks
            self.info('register user/group hooks')
            _register_usergroup_hooks(self)
            _register_eproperty_hooks(self)
        if config.security_hooks:
            from cubicweb.server.securityhooks import register_security_hooks
            self.info('register security hooks')
            register_security_hooks(self)
        if not self.verification_hooks_activated:
            self.deactivate_verification_hooks()

    def deactivate_verification_hooks(self):
        from cubicweb.server.hooks import (cardinalitycheck_after_add_entity,
                                        cardinalitycheck_before_del_relation,
                                        cstrcheck_after_add_relation,
                                        uniquecstrcheck_before_modification)
        self.warning('deactivating verification hooks')
        self.verification_hooks_activated = False
        self.unregister_hook(cardinalitycheck_after_add_entity, 'after_add_entity', '')
        self.unregister_hook(cardinalitycheck_before_del_relation, 'before_delete_relation', '')
        self.unregister_hook(cstrcheck_after_add_relation, 'after_add_relation', '')
        self.unregister_hook(uniquecstrcheck_before_modification, 'before_add_entity', '')
        self.unregister_hook(uniquecstrcheck_before_modification, 'before_update_entity', '')
#         self.unregister_hook(tidy_html_fields('before_add_entity'), 'before_add_entity', '')
#         self.unregister_hook(tidy_html_fields('before_update_entity'), 'before_update_entity', '')

    def reactivate_verification_hooks(self):
        from cubicweb.server.hooks import (cardinalitycheck_after_add_entity,
                                        cardinalitycheck_before_del_relation,
                                        cstrcheck_after_add_relation,
                                        uniquecstrcheck_before_modification)
        self.warning('reactivating verification hooks')
        self.verification_hooks_activated = True
        self.register_hook(cardinalitycheck_after_add_entity, 'after_add_entity', '')
        self.register_hook(cardinalitycheck_before_del_relation, 'before_delete_relation', '')
        self.register_hook(cstrcheck_after_add_relation, 'after_add_relation', '')
        self.register_hook(uniquecstrcheck_before_modification, 'before_add_entity', '')
        self.register_hook(uniquecstrcheck_before_modification, 'before_update_entity', '')
#         self.register_hook(tidy_html_fields('before_add_entity'), 'before_add_entity', '')
#         self.register_hook(tidy_html_fields('before_update_entity'), 'before_update_entity', '')

from cubicweb.selectors import yes
from cubicweb.appobject import AppObject

class autoid(type):
    """metaclass to create an unique 'id' attribute on the class using it"""
    # XXX is this metaclass really necessary ?
    def __new__(mcs, name, bases, classdict):
        cls = super(autoid, mcs).__new__(mcs, name, bases, classdict)
        cls.id = str(id(cls))
        return cls

class Hook(AppObject):
    __metaclass__ = autoid
    __registry__ = 'hooks'
    __select__ = yes()
    # set this in derivated classes
    events = None
    accepts = None
    enabled = True

    def __init__(self, event=None):
        super(Hook, self).__init__()
        self.event = event

    @classmethod
    def registered(cls, vreg):
        super(Hook, cls).registered(vreg)
        return cls()

    @classmethod
    def register_to(cls):
        if not cls.enabled:
            cls.warning('%s hook has been disabled', cls)
            return
        done = set()
        assert isinstance(cls.events, (tuple, list)), \
               '%s: events is expected to be a tuple, not %s' % (
            cls, type(cls.events))
        for event in cls.events:
            if event in SYSTEM_HOOKS:
                assert not cls.accepts or cls.accepts == ('Any',), \
                       '%s doesnt make sense on %s' % (cls.accepts, event)
                cls.accepts = ('Any',)
            for ertype in cls.accepts:
                if (event, ertype) in done:
                    continue
                yield event, ertype
                done.add((event, ertype))
                try:
                    eschema = cls.schema.eschema(ertype)
                except KeyError:
                    # relation schema
                    pass
                else:
                    for eetype in eschema.specialized_by():
                        if (event, eetype) in done:
                            continue
                        yield event, str(eetype)
                        done.add((event, eetype))


    def make_callback(self, event):
        if len(self.events) == 1:
            return self.call
        return self.__class__(event=event).call

    def call(self):
        raise NotImplementedError

class SystemHook(Hook):
    accepts = ()

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(HooksManager, getLogger('cubicweb.hooksmanager'))
set_log_methods(Hook, getLogger('cubicweb.hooks'))

# base classes for relation propagation ########################################

from cubicweb.server.pool import PreCommitOperation


class PropagateSubjectRelationHook(Hook):
    """propagate permissions and nosy list when new entity are added"""
    events = ('after_add_relation',)
    # to set in concrete class
    rtype = None
    subject_relations = None
    object_relations = None
    accepts = None # subject_relations + object_relations

    def call(self, session, fromeid, rtype, toeid):
        for eid in (fromeid, toeid):
            etype = session.describe(eid)[0]
            if self.rtype not in self.schema.eschema(etype).subjrels:
                return
        if rtype in self.subject_relations:
            meid, seid = fromeid, toeid
        else:
            assert rtype in self.object_relations
            meid, seid = toeid, fromeid
        session.unsafe_execute(
            'SET E %s P WHERE X %s P, X eid %%(x)s, E eid %%(e)s, NOT E %s P'\
            % (self.rtype, self.rtype, self.rtype),
            {'x': meid, 'e': seid}, ('x', 'e'))


class PropagateSubjectRelationAddHook(Hook):
    """propagate on existing entities when a permission or nosy list is added"""
    events = ('after_add_relation',)
    # to set in concrete class
    rtype = None
    subject_relations = None
    object_relations = None
    accepts = None # (self.rtype,)

    def call(self, session, fromeid, rtype, toeid):
        eschema = self.schema.eschema(session.describe(fromeid)[0])
        execute = session.unsafe_execute
        for rel in self.subject_relations:
            if rel in eschema.subjrels:
                execute('SET R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'X %s R, NOT R %s P' % (rtype, rel, rtype),
                        {'x': fromeid, 'p': toeid}, 'x')
        for rel in self.object_relations:
            if rel in eschema.objrels:
                execute('SET R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'R %s X, NOT R %s P' % (rtype, rel, rtype),
                        {'x': fromeid, 'p': toeid}, 'x')


class PropagateSubjectRelationDelHook(Hook):
    """propagate on existing entities when a permission is deleted"""
    events = ('after_delete_relation',)
    # to set in concrete class
    rtype = None
    subject_relations = None
    object_relations = None
    accepts = None # (self.rtype,)

    def call(self, session, fromeid, rtype, toeid):
        eschema = self.schema.eschema(session.describe(fromeid)[0])
        execute = session.unsafe_execute
        for rel in self.subject_relations:
            if rel in eschema.subjrels:
                execute('DELETE R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'X %s R' % (rtype, rel),
                        {'x': fromeid, 'p': toeid}, 'x')
        for rel in self.object_relations:
            if rel in eschema.objrels:
                execute('DELETE R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'R %s X' % (rtype, rel),
                        {'x': fromeid, 'p': toeid}, 'x')
