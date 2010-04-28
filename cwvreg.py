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
""".. VRegistry:

The `VRegistry`
---------------

The `VRegistry` can be seen as a two levels dictionary. It contains
all dynamically loaded objects (subclasses of :ref:`appobject`) to
build a |cubicweb| application. Basically:

* the first level key returns a *registry*. This key corresponds to the
  `__registry__` attribute of application object classes

* the second level key returns a list of application objects which
  share the same identifier. This key corresponds to the `__regid__`
  attribute of application object classes.

A *registry* holds a specific kind of application objects. There is
for instance a registry for entity classes, another for views, etc...

The `VRegistry` has two main responsibilities:

- being the access point to all registries

- handling the registration process at startup time, and during automatic
  reloading in debug mode.

.. _AppObjectRecording:

Details of the recording process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   vregistry: registration_callback

On startup |cubicweb| loads application objects defined in its library
and in cubes used by the instance. Application objects from the
library are loaded first, then those provided by cubes are loaded in
dependency order (e.g. if your cube depends on an other, objects from
the dependency will be loaded first). Cube's modules or packages where
appobject are looked for is explained in :ref:`cubelayout`.

For each module:

* by default all objects are registered automatically

* if some objects have to replace other objects, or have to be
  included only if some condition is met, you'll have to define a
  `registration_callback(vreg)` function in your module and explicitly
  register **all objects** in this module, using the api defined
  below.

.. Note::
    Once the function `registration_callback(vreg)` is implemented in a module,
    all the objects from this module have to be explicitly registered as it
    disables the automatic objects registration.


API for objects registration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here are the registration methods that you can use in the `registration_callback`
to register your objects to the `VRegistry` instance given as argument (usually
named `vreg`):

.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register_all
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register_and_replace
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register_if_interface_found
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.unregister

Examples:

.. sourcecode:: python

   # web/views/basecomponents.py
   def registration_callback(vreg):
      # register everything in the module except SeeAlsoComponent
      vreg.register_all(globals().values(), __name__, (SeeAlsoVComponent,))
      # conditionally register SeeAlsoVComponent
      if 'see_also' in vreg.schema:
          vreg.register(SeeAlsoVComponent)

In this example, we register all application object classes defined in the module
except `SeeAlsoVComponent`. This class is then registered only if the 'see_also'
relation type is defined in the instance'schema.

.. sourcecode:: python

   # goa/appobjects/sessions.py
   def registration_callback(vreg):
      vreg.register(SessionsCleaner)
      # replace AuthenticationManager by GAEAuthenticationManager
      vreg.register_and_replace(GAEAuthenticationManager, AuthenticationManager)
      # replace PersistentSessionManager by GAEPersistentSessionManager
      vreg.register_and_replace(GAEPersistentSessionManager, PersistentSessionManager)

In this example, we explicitly register classes one by one:

* the `SessionCleaner` class
* the `GAEAuthenticationManager` to replace the `AuthenticationManager`
* the `GAEPersistentSessionManager` to replace the `PersistentSessionManager`

If at some point we register a new appobject class in this module, it won't be
registered at all without modification to the `registration_callback`
implementation. The previous example will register it though, thanks to the call
to the `register_all` method.


.. _Selection:

Runtime objects selection
~~~~~~~~~~~~~~~~~~~~~~~~~

Now that we have all application objects loaded, the question is : when
I want some specific object, for instance the primary view for a given
entity, how do I get the proper object ? This is what we call the
**selection mechanism**.

As explained in the :ref:`Concepts` section:

* each application object has a **selector**, defined by its
  `__select__` class attribute

* this selector is responsible to return a **score** for a given context

  - 0 score means the object doesn't apply to this context

  - else, the higher the score, the better the object suits the context

* the object with the higher score is selected.

.. Note::

  When no score is higher than the others, an exception is raised in development
  mode to let you know that the engine was not able to identify the view to
  apply. This error is silenced in production mode and one of the objects with
  the higher score is picked.

  In such cases you would need to review your design and make sure your selectors
  or appobjects are properly defined.

For instance, if you are selecting the primary (eg `__regid__ =
'primary'`) view (eg `__registry__ = 'views'`) for a result set
containing a `Card` entity, two objects will probably be selectable:

* the default primary view (`__select__ = implements('Any')`), meaning
  that the object is selectable for any kind of entity type

* the specific `Card` primary view (`__select__ = implements('Card')`,
  meaning that the object is selectable for Card entities

Other primary views specific to other entity types won't be selectable in this
case. Among selectable objects, the implements selector will return a higher
score than the second view since it's more specific, so it will be selected as
expected.

.. _SelectionAPI:

API for objects selections
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is the selection API you'll get on every registry. Some of them, as the
'etypes' registry, containing entity classes, extend it. In those methods,
`*args, **kwargs` is what we call the **context**. Those arguments are given to
selectors that will inspect there content and return a score accordingly.

.. automethod:: cubicweb.vregistry.Registry.select

.. automethod:: cubicweb.vregistry.Registry.select_or_none

.. automethod:: cubicweb.vregistry.Registry.possible_objects

.. automethod:: cubicweb.vregistry.Registry.object_by_id
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.decorators import cached, clear_cache
from logilab.common.deprecation import  deprecated
from logilab.common.modutils import cleanup_sys_modules

from rql import RQLHelper

from cubicweb import (ETYPE_NAME_MAP, Binary, UnknownProperty, UnknownEid,
                      ObjectNotFound, NoSelectableObject, RegistryNotFound,
                      CW_EVENT_MANAGER, onevent)
from cubicweb.utils import dump_class
from cubicweb.vregistry import VRegistry, Registry, class_regid
from cubicweb.rtags import RTAGS

def clear_rtag_objects():
    for rtag in RTAGS:
        rtag.clear()

def use_interfaces(obj):
    """return interfaces used by the given object by searching for implements
    selectors, with a bw compat fallback to accepts_interfaces attribute
    """
    from cubicweb.selectors import implements
    try:
        # XXX deprecated
        return sorted(obj.accepts_interfaces)
    except AttributeError:
        try:
            impl = obj.__select__.search_selector(implements)
            if impl:
                return sorted(impl.expected_ifaces)
        except AttributeError:
            pass # old-style appobject classes with no accepts_interfaces
        except:
            print 'bad selector %s on %s' % (obj.__select__, obj)
            raise
        return ()


class CWRegistry(Registry):
    def __init__(self, vreg):
        super(CWRegistry, self).__init__(vreg.config)
        self.vreg = vreg

    @property
    def schema(self):
        return self.vreg.schema

    @deprecated('[3.6] select object, then use obj.render()')
    def render(self, __oid, req, __fallback_oid=None, rset=None, initargs=None,
               **kwargs):
        """Select object with the given id (`__oid`) then render it.  If the
        object isn't selectable, try to select fallback object if
        `__fallback_oid` is specified.

        If specified `initargs` is expected to be a dictionnary containing
        arguments that should be given to selection (hence to object's __init__
        as well), but not to render(). Other arbitrary keyword arguments will be
        given to selection *and* to render(), and so should be handled by
        object's call or cell_call method..
        """
        if initargs is None:
            initargs = kwargs
        else:
            initargs.update(kwargs)
        try:
            obj = self.select(__oid, req, rset=rset, **initargs)
        except NoSelectableObject:
            if __fallback_oid is None:
                raise
            obj = self.select(__fallback_oid, req, rset=rset, **initargs)
        return obj.render(**kwargs)

    @deprecated('[3.6] use select_or_none and test for obj.cw_propval("visible")')
    def select_vobject(self, oid, *args, **kwargs):
        selected = self.select_or_none(oid, *args, **kwargs)
        if selected and selected.cw_propval('visible'):
            return selected
        return None

    def poss_visible_objects(self, *args, **kwargs):
        """return an ordered list of possible app objects in a given registry,
        supposing they support the 'visible' and 'order' properties (as most
        visualizable objects)
        """
        return sorted([x for x in self.possible_objects(*args, **kwargs)
                       if x.cw_propval('visible')],
                      key=lambda x: x.cw_propval('order'))
    possible_vobjects = deprecated('[3.6] use poss_visible_objects()')(poss_visible_objects)


VRegistry.REGISTRY_FACTORY[None] = CWRegistry


class ETypeRegistry(CWRegistry):

    def initialization_completed(self):
        """on registration completed, clear etype_class internal cache
        """
        super(ETypeRegistry, self).initialization_completed()
        # clear etype cache if you don't want to run into deep weirdness
        clear_cache(self, 'etype_class')
        clear_cache(self, 'parent_classes')

    def register(self, obj, **kwargs):
        oid = kwargs.get('oid') or class_regid(obj)
        if oid != 'Any' and not oid in self.schema:
            self.error('don\'t register %s, %s type not defined in the '
                       'schema', obj, oid)
            return
        kwargs['clear'] = True
        super(ETypeRegistry, self).register(obj, **kwargs)

    @cached
    def parent_classes(self, etype):
        if etype == 'Any':
            return [self.etype_class('Any')]
        eschema = self.schema.eschema(etype)
        parents = [self.etype_class(e.type) for e in eschema.ancestors()]
        parents.append(self.etype_class('Any'))
        return parents

    @cached
    def etype_class(self, etype):
        """return an entity class for the given entity type.

        Try to find out a specific class for this kind of entity or default to a
        dump of the nearest parent class (in yams inheritance) registered.

        Fall back to 'Any' if not yams parent class found.
        """
        etype = str(etype)
        if etype == 'Any':
            objects = self['Any']
            assert len(objects) == 1, objects
            return objects[0]
        eschema = self.schema.eschema(etype)
        baseschemas = [eschema] + eschema.ancestors()
        # browse ancestors from most specific to most generic and try to find an
        # associated custom entity class
        for baseschema in baseschemas:
            try:
                btype = ETYPE_NAME_MAP[baseschema]
            except KeyError:
                btype = str(baseschema)
            try:
                objects = self[btype]
                assert len(objects) == 1, objects
                if btype == etype:
                    cls = objects[0]
                else:
                    # recurse to ensure issubclass(etype_class('Child'),
                    #                              etype_class('Parent'))
                    cls = self.etype_class(btype)
                break
            except ObjectNotFound:
                pass
        else:
            # no entity class for any of the ancestors, fallback to the default
            # one
            objects = self['Any']
            assert len(objects) == 1, objects
            cls = objects[0]
        # make a copy event if cls.__regid__ == etype, else we may have pb for
        # client application using multiple connections to different
        # repositories (eg shingouz)
        cls = dump_class(cls, etype)
        cls.__regid__ = etype
        cls.__initialize__(self.schema)
        return cls

VRegistry.REGISTRY_FACTORY['etypes'] = ETypeRegistry


class ViewsRegistry(CWRegistry):

    def main_template(self, req, oid='main-template', rset=None, **kwargs):
        """display query by calling the given template (default to main),
        and returning the output as a string instead of requiring the [w]rite
        method as argument
        """
        obj = self.select(oid, req, rset=rset, **kwargs)
        res = obj.render(**kwargs)
        if isinstance(res, unicode):
            return res.encode(req.encoding)
        assert isinstance(res, str)
        return res

    def possible_views(self, req, rset=None, **kwargs):
        """return an iterator on possible views for this result set

        views returned are classes, not instances
        """
        for vid, views in self.items():
            if vid[0] == '_':
                continue
            try:
                view = self._select_best(views, req, rset=rset, **kwargs)
                if view.linkable():
                    yield view
            except NoSelectableObject:
                continue
            except Exception:
                self.exception('error while trying to select %s view for %s',
                               vid, rset)

VRegistry.REGISTRY_FACTORY['views'] = ViewsRegistry


class ActionsRegistry(CWRegistry):
    def poss_visible_objects(self, *args, **kwargs):
        """return an ordered list of possible actions"""
        return sorted(self.possible_objects(*args, **kwargs),
                      key=lambda x: x.order)

    def possible_actions(self, req, rset=None, **kwargs):
        if rset is None:
            actions = self.poss_visible_objects(req, rset=rset, **kwargs)
        else:
            actions = rset.possible_actions(**kwargs) # cached implementation
        result = {}
        for action in actions:
            result.setdefault(action.category, []).append(action)
        return result

VRegistry.REGISTRY_FACTORY['actions'] = ActionsRegistry



class CubicWebVRegistry(VRegistry):
    """Central registry for the cubicweb instance, extending the generic
    VRegistry with some cubicweb specific stuff.

    This is one of the central object in cubicweb instance, coupling
    dynamically loaded objects with the schema and the configuration objects.

    It specializes the VRegistry by adding some convenience methods to access to
    stored objects. Currently we have the following registries of objects known
    by the web instance (library may use some others additional registries):

    * etypes
    * views
    * components
    * actions
    * forms
    * formrenderers
    * controllers, which are directly plugged into the application
      object to handle request publishing XXX to merge with views
    * contentnavigation XXX to merge with components? to kill?
    """

    def __init__(self, config, debug=None, initlog=True):
        if initlog:
            # first init log service
            config.init_log(debug=debug)
        super(CubicWebVRegistry, self).__init__(config)
        self.schema = None
        self.initialized = False
        self.reset()
        # XXX give force_reload (or refactor [re]loading...)
        if self.config.mode != 'test':
            # don't clear rtags during test, this may cause breakage with
            # manually imported appobject modules
            CW_EVENT_MANAGER.bind('before-registry-reload', clear_rtag_objects)

    def setdefault(self, regid):
        try:
            return self[regid]
        except RegistryNotFound:
            self[regid] = self.registry_class(regid)(self)
            return self[regid]

    def items(self):
        return [item for item in super(CubicWebVRegistry, self).items()
                if not item[0] in ('propertydefs', 'propertyvalues')]
    def iteritems(self):
        return (item for item in super(CubicWebVRegistry, self).iteritems()
                if not item[0] in ('propertydefs', 'propertyvalues'))

    def values(self):
        return [value for key, value in self.items()]
    def itervalues(self):
        return (value for key, value in self.items())

    def reset(self):
        super(CubicWebVRegistry, self).reset()
        self._needs_iface = {}
        # two special registries, propertydefs which care all the property
        # definitions, and propertyvals which contains values for those
        # properties
        if not self.initialized:
            self['propertydefs'] = {}
            self['propertyvalues'] = self.eprop_values = {}
            for key, propdef in self.config.eproperty_definitions():
                self.register_property(key, **propdef)

    def set_schema(self, schema):
        """set instance'schema and load application objects"""
        self._set_schema(schema)
        # now we can load application's web objects
        self.reload(self.config.vregistry_path(), force_reload=False)
        # map lowered entity type names to their actual name
        self.case_insensitive_etypes = {}
        for eschema in self.schema.entities():
            etype = str(eschema)
            self.case_insensitive_etypes[etype.lower()] = etype
            clear_cache(eschema, 'ordered_relations')
            clear_cache(eschema, 'meta_attributes')

    def reload_if_needed(self):
        path = self.config.vregistry_path()
        if self.is_reload_needed(path):
            self.reload(path)

    def reload(self, path, force_reload=True):
        """modification detected, reset and reload the vreg"""
        CW_EVENT_MANAGER.emit('before-registry-reload')
        if force_reload:
            cleanup_sys_modules(path)
            cubes = self.config.cubes()
            # if the fs code use some cubes not yet registered into the instance
            # we should cleanup sys.modules for those as well to avoid potential
            # bad class reference pb after reloading
            cfg = self.config
            for cube in cfg.expand_cubes(cubes, with_recommends=True):
                if not cube in cubes:
                    cpath = cfg.build_vregistry_cube_path([cfg.cube_dir(cube)])
                    cleanup_sys_modules(cpath)
        self.reset()
        self.register_objects(path, force_reload)
        CW_EVENT_MANAGER.emit('after-registry-reload')

    def _set_schema(self, schema):
        """set instance'schema"""
        self.schema = schema
        clear_cache(self, 'rqlhelper')

    def update_schema(self, schema):
        """update .schema attribute on registered objects, necessary for some
        tests
        """
        self.schema = schema
        for registry, regcontent in self.items():
            for objects in regcontent.values():
                for obj in objects:
                    obj.schema = schema

    def register_if_interface_found(self, obj, ifaces, **kwargs):
        """register `obj` but remove it if no entity class implements one of
        the given `ifaces` interfaces at the end of the registration process.

        Extra keyword arguments are given to the
        :meth:`~cubicweb.cwvreg.CubicWebVRegistry.register` function.
        """
        self.register(obj, **kwargs)
        if not isinstance(ifaces,  (tuple, list)):
            self._needs_iface[obj] = (ifaces,)
        else:
            self._needs_iface[obj] = ifaces

    def register(self, obj, *args, **kwargs):
        """register `obj` application object into `registryname` or
        `obj.__registry__` if not specified, with identifier `oid` or
        `obj.__regid__` if not specified.

        If `clear` is true, all objects with the same identifier will be
        previously unregistered.
        """
        super(CubicWebVRegistry, self).register(obj, *args, **kwargs)
        # XXX bw compat
        ifaces = use_interfaces(obj)
        if ifaces:
            self._needs_iface[obj] = ifaces

    def register_objects(self, path, force_reload=False):
        """overriden to remove objects requiring a missing interface"""
        super(CubicWebVRegistry, self).register_objects(
            path, force_reload, self.config.extrapath)

    def initialization_completed(self):
        """cw specific code once vreg initialization is completed:

        * remove objects requiring a missing interface, unless
          config.cleanup_interface_sobjects is false
        * init rtags
        """
        # we may want to keep interface dependent objects (e.g.for i18n
        # catalog generation)
        if self.config.cleanup_interface_sobjects:
            # remove appobjects that don't support any available interface
            implemented_interfaces = set()
            if 'Any' in self.get('etypes', ()):
                for etype in self.schema.entities():
                    if etype.final:
                        continue
                    cls = self['etypes'].etype_class(etype)
                    for iface in cls.__implements__:
                        implemented_interfaces.update(iface.__mro__)
                    implemented_interfaces.update(cls.__mro__)
            for obj, ifaces in self._needs_iface.items():
                ifaces = frozenset(isinstance(iface, basestring)
                                   and iface in self.schema
                                   and self['etypes'].etype_class(iface)
                                   or iface
                                   for iface in ifaces)
                if not ('Any' in ifaces or ifaces & implemented_interfaces):
                    self.debug('kicking appobject %s (no implemented '
                               'interface among %s)', obj, ifaces)
                    self.unregister(obj)
        # clear needs_iface so we don't try to remove some not-anymore-in
        # objects on automatic reloading
        self._needs_iface.clear()
        super(CubicWebVRegistry, self).initialization_completed()
        for rtag in RTAGS:
            # don't check rtags if we don't want to cleanup_interface_sobjects
            rtag.init(self.schema, check=self.config.cleanup_interface_sobjects)


    # rql parsing utilities ####################################################

    @property
    @cached
    def rqlhelper(self):
        return RQLHelper(self.schema,
                         special_relations={'eid': 'uid', 'has_text': 'fti'})

    def solutions(self, req, rqlst, args):
        def type_from_eid(eid, req=req):
            return req.describe(eid)[0]
        return self.rqlhelper.compute_solutions(rqlst, {'eid': type_from_eid}, args)

    def parse(self, req, rql, args=None):
        rqlst = self.rqlhelper.parse(rql)
        try:
            self.solutions(req, rqlst, args)
        except UnknownEid:
            for select in rqlst.children:
                select.solutions = []
        return rqlst

    # properties handling #####################################################

    def user_property_keys(self, withsitewide=False):
        if withsitewide:
            return sorted(k for k in self['propertydefs']
                          if not k.startswith('sources.'))
        return sorted(k for k, kd in self['propertydefs'].iteritems()
                      if not kd['sitewide'] and not k.startswith('sources.'))

    def register_property(self, key, type, help, default=None, vocabulary=None,
                          sitewide=False):
        """register a given property"""
        properties = self['propertydefs']
        assert type in YAMS_TO_PY
        properties[key] = {'type': type, 'vocabulary': vocabulary,
                           'default': default, 'help': help,
                           'sitewide': sitewide}

    def property_info(self, key):
        """return dictionary containing description associated to the given
        property key (including type, defaut value, help and a site wide
        boolean)
        """
        try:
            return self['propertydefs'][key]
        except KeyError:
            if key.startswith('system.version.'):
                soft = key.split('.')[-1]
                return {'type': 'String', 'sitewide': True,
                        'default': None, 'vocabulary': None,
                        'help': _('%s software version of the database') % soft}
            raise UnknownProperty('unregistered property %r' % key)

    def property_value(self, key):
        try:
            return self['propertyvalues'][key]
        except KeyError:
            return self.property_info(key)['default']

    def typed_value(self, key, value):
        """value is an unicode string, return it correctly typed. Let potential
        type error propagates.
        """
        pdef = self.property_info(key)
        try:
            value = YAMS_TO_PY[pdef['type']](value)
        except (TypeError, ValueError):
            raise ValueError(_('bad value'))
        vocab = pdef['vocabulary']
        if vocab is not None:
            if callable(vocab):
                vocab = vocab(key, None) # XXX need a req object
            if not value in vocab:
                raise ValueError(_('unauthorized value'))
        return value

    def init_properties(self, propvalues):
        """init the property values registry using the given set of couple (key, value)
        """
        self.initialized = True
        values = self['propertyvalues']
        for key, val in propvalues:
            try:
                values[key] = self.typed_value(key, val)
            except ValueError, ex:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)
            except UnknownProperty, ex:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)

    # deprecated code ####################################################

    @deprecated('[3.4] use vreg["etypes"].etype_class(etype)')
    def etype_class(self, etype):
        return self["etypes"].etype_class(etype)

    @deprecated('[3.4] use vreg["views"].main_template(*args, **kwargs)')
    def main_template(self, req, oid='main-template', **context):
        return self["views"].main_template(req, oid, **context)

    @deprecated('[3.4] use vreg[registry].possible_vobjects(*args, **kwargs)')
    def possible_vobjects(self, registry, *args, **kwargs):
        return self[registry].possible_vobjects(*args, **kwargs)

    @deprecated('[3.4] use vreg["actions"].possible_actions(*args, **kwargs)')
    def possible_actions(self, req, rset=None, **kwargs):
        return self["actions"].possible_actions(req, rest=rset, **kwargs)

    @deprecated('[3.4] use vreg["boxes"].select_object(...)')
    def select_box(self, oid, *args, **kwargs):
        return self['boxes'].select_object(oid, *args, **kwargs)

    @deprecated('[3.4] use vreg["components"].select_object(...)')
    def select_component(self, cid, *args, **kwargs):
        return self['components'].select_object(cid, *args, **kwargs)

    @deprecated('[3.4] use vreg["actions"].select_object(...)')
    def select_action(self, oid, *args, **kwargs):
        return self['actions'].select_object(oid, *args, **kwargs)

    @deprecated('[3.4] use vreg["views"].select(...)')
    def select_view(self, __vid, req, rset=None, **kwargs):
        return self['views'].select(__vid, req, rset=rset, **kwargs)


from datetime import datetime, date, time, timedelta

YAMS_TO_PY = {
    'Boolean':  bool,
    'String' :  unicode,
    'Password': str,
    'Bytes':    Binary,
    'Int':      int,
    'Float':    float,
    'Date':     date,
    'Datetime': datetime,
    'Time':     time,
    'Interval': timedelta,
    }

