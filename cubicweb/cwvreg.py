# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
Cubicweb registries
"""

import sys
from os.path import join, dirname, realpath
from warnings import warn
from datetime import datetime, date, time, timedelta
from functools import reduce

from six import text_type, binary_type

from logilab.common.decorators import cached, clear_cache
from logilab.common.deprecation import class_deprecated
from logilab.common.modutils import clean_sys_modules
from logilab.common.registry import RegistryStore, Registry, ObjectNotFound, RegistryNotFound

from rql import RQLHelper
from yams.constraints import BASE_CONVERTERS

from cubicweb import _
from cubicweb import (CW_SOFTWARE_ROOT, ETYPE_NAME_MAP, CW_EVENT_MANAGER,
                      onevent, Binary, UnknownProperty, UnknownEid)
from cubicweb.predicates import appobject_selectable, _reset_is_instance_cache


@onevent('before-registry-reload')
def cleanup_uicfg_compat():
    """ backward compat: those modules are now refering to app objects in
    cw.web.views.uicfg and import * from backward compat. On registry reload, we
    should pop those modules from the cache so references are properly updated on
    subsequent reload
    """
    if 'cubicweb.web' in sys.modules:
        if getattr(sys.modules['cubicweb.web'], 'uicfg', None):
            del sys.modules['cubicweb.web'].uicfg
        if getattr(sys.modules['cubicweb.web'], 'uihelper', None):
            del sys.modules['cubicweb.web'].uihelper
    sys.modules.pop('cubicweb.web.uicfg', None)
    sys.modules.pop('cubicweb.web.uihelper', None)


def require_appobject(obj):
    """return appobjects required by the given object by searching for
    `appobject_selectable` predicate
    """
    impl = obj.__select__.search_selector(appobject_selectable)
    if impl:
        return (impl.registry, impl.regids)
    return None


class CWRegistry(Registry):
    def __init__(self, vreg):
        """
        :param vreg: the :py:class:`CWRegistryStore` managing this registry.
        """
        super(CWRegistry, self).__init__(True)
        self.vreg = vreg

    @property
    def schema(self):
        """The :py:class:`cubicweb.schema.CubicWebSchema`
        """
        return self.vreg.schema

    def poss_visible_objects(self, *args, **kwargs):
        """return an ordered list of possible app objects in a given registry,
        supposing they support the 'visible' and 'order' properties (as most
        visualizable objects)
        """
        return sorted([x for x in self.possible_objects(*args, **kwargs)
                       if x.cw_propval('visible')],
                      key=lambda x: x.cw_propval('order'))


def related_appobject(obj, appobjectattr='__appobject__'):
    """ adapts any object to a potential appobject bound to it
    through the __appobject__ attribute
    """
    return getattr(obj, appobjectattr, obj)


class InstancesRegistry(CWRegistry):

    def selected(self, winner, args, kwargs):
        """overriden to avoid the default 'instanciation' behaviour, ie
        `winner(*args, **kwargs)`
        """
        return winner


class ETypeRegistry(CWRegistry):

    def clear_caches(self):
        clear_cache(self, 'etype_class')
        clear_cache(self, 'parent_classes')
        _reset_is_instance_cache(self.vreg)

    def initialization_completed(self):
        """on registration completed, clear etype_class internal cache
        """
        super(ETypeRegistry, self).initialization_completed()
        # clear etype cache if you don't want to run into deep weirdness
        self.clear_caches()
        # rebuild all classes to avoid potential memory fragmentation
        # (see #2719113)
        for eschema in self.vreg.schema.entities():
            self.etype_class(eschema)

    def register(self, obj, **kwargs):
        obj = related_appobject(obj)
        oid = kwargs.get('oid') or obj.__regid__
        if oid != 'Any' and not oid in self.schema:
            self.error('don\'t register %s, %s type not defined in the '
                       'schema', obj, oid)
            return
        kwargs['clear'] = True
        super(ETypeRegistry, self).register(obj, **kwargs)

    def iter_classes(self):
        for etype in self.vreg.schema.entities():
            yield self.etype_class(etype)

    @cached
    def parent_classes(self, etype):
        if etype == 'Any':
            return (), self.etype_class('Any')
        parents = tuple(self.etype_class(e.type)
                        for e in self.schema.eschema(etype).ancestors())
        return parents, self.etype_class('Any')

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
        # __autogenerated__ attribute is just a marker
        cls = type(str(etype), (cls,), {'__autogenerated__': True,
                                        '__doc__': cls.__doc__,
                                        '__module__': cls.__module__})
        cls.__regid__ = etype
        cls.__initialize__(self.schema)
        return cls

    def fetch_attrs(self, targettypes):
        """return intersection of fetch_attrs of each entity type in
        `targettypes`
        """
        fetchattrs_list = []
        for ttype in targettypes:
            etypecls = self.etype_class(ttype)
            fetchattrs_list.append(set(etypecls.fetch_attrs))
        return reduce(set.intersection, fetchattrs_list)


class ViewsRegistry(CWRegistry):

    def main_template(self, req, oid='main-template', rset=None, **kwargs):
        """display query by calling the given template (default to main),
        and returning the output as a string instead of requiring the [w]rite
        method as argument
        """
        obj = self.select(oid, req, rset=rset, **kwargs)
        res = obj.render(**kwargs)
        if isinstance(res, text_type):
            return res.encode(req.encoding)
        assert isinstance(res, binary_type)
        return res

    def possible_views(self, req, rset=None, **kwargs):
        """return an iterator on possible views for this result set

        views returned are classes, not instances
        """
        for vid, views in self.items():
            if vid[0] == '_':
                continue
            views = [view for view in views
                     if not isinstance(view, class_deprecated)]
            try:
                view = self._select_best(views, req, rset=rset, **kwargs)
                if view is not None and view.linkable():
                    yield view
            except Exception:
                self.exception('error while trying to select %s view for %s',
                               vid, rset)


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


class CtxComponentsRegistry(CWRegistry):
    def poss_visible_objects(self, *args, **kwargs):
        """return an ordered list of possible components"""
        context = kwargs.pop('context')
        if '__cache' in kwargs:
            cache = kwargs.pop('__cache')
        elif kwargs.get('rset') is None:
            cache = args[0]
        else:
            cache = kwargs['rset']
        try:
            cached = cache.__components_cache
        except AttributeError:
            ctxcomps = super(CtxComponentsRegistry, self).poss_visible_objects(
                *args, **kwargs)
            if cache is None:
                components = []
                for component in ctxcomps:
                    cctx = component.cw_propval('context')
                    if cctx == context:
                        component.cw_extra_kwargs['context'] = cctx
                        components.append(component)
                return components
            cached = cache.__components_cache = {}
            for component in ctxcomps:
                cctx = component.cw_propval('context')
                component.cw_extra_kwargs['context'] = cctx
                cached.setdefault(cctx, []).append(component)
        thisctxcomps = cached.get(context, ())
        # XXX set context for bw compat (should now be taken by comp.render())
        for component in thisctxcomps:
            component.cw_extra_kwargs['context'] = context
        return thisctxcomps


class BwCompatCWRegistry(object):
    def __init__(self, vreg, oldreg, redirecttoreg):
        self.vreg = vreg
        self.oldreg = oldreg
        self.redirecto = redirecttoreg

    def __getattr__(self, attr):
        warn('[3.10] you should now use the %s registry instead of the %s registry'
             % (self.redirecto, self.oldreg), DeprecationWarning, stacklevel=2)
        return getattr(self.vreg[self.redirecto], attr)

    def clear(self): pass
    def initialization_completed(self): pass


class CWRegistryStore(RegistryStore):
    """Central registry for the cubicweb instance, extending the generic
    RegistryStore with some cubicweb specific stuff.

    This is one of the central object in cubicweb instance, coupling
    dynamically loaded objects with the schema and the configuration objects.

    It specializes the RegistryStore by adding some convenience methods to access to
    stored objects. Currently we have the following registries of objects known
    by the web instance (library may use some others additional registries):

    * 'etypes', entity type classes

    * 'views', views and templates (e.g. layout views)

    * 'components', non contextual components, like magic search, url evaluators

    * 'ctxcomponents', contextual components like boxes and dynamic section

    * 'actions', contextual actions, eg links to display in predefined places in
      the ui

    * 'forms', describing logic of HTML form

    * 'formrenderers', rendering forms to html

    * 'controllers', primary objects to handle request publishing, directly
      plugged into the application
    """

    REGISTRY_FACTORY = {None: CWRegistry,
                        'etypes': ETypeRegistry,
                        'views': ViewsRegistry,
                        'actions': ActionsRegistry,
                        'ctxcomponents': CtxComponentsRegistry,
                        'uicfg': InstancesRegistry,
                        }

    def __init__(self, config, initlog=True):
        if initlog:
            # first init log service
            config.init_log()
        super(CWRegistryStore, self).__init__(config.debugmode)
        self.config = config
        # need to clean sys.path this to avoid import confusion pb (i.e.  having
        # the same module loaded as 'cubicweb.web.views' subpackage and as
        # views' or 'web.views' subpackage. This is mainly for testing purpose,
        # we should'nt need this in production environment
        for webdir in (join(dirname(realpath(__file__)), 'web'),
                       join(dirname(__file__), 'web')):
            if webdir in sys.path:
                sys.path.remove(webdir)
        if CW_SOFTWARE_ROOT in sys.path:
            sys.path.remove(CW_SOFTWARE_ROOT)
        self.schema = None
        self.initialized = False
        self['boxes'] = BwCompatCWRegistry(self, 'boxes', 'ctxcomponents')
        self['contentnavigation'] = BwCompatCWRegistry(self, 'contentnavigation', 'ctxcomponents')

    def setdefault(self, regid):
        try:
            return self[regid]
        except RegistryNotFound:
            self[regid] = self.registry_class(regid)(self)
            return self[regid]

    def items(self):
        return [item for item in super(CWRegistryStore, self).items()
                if not item[0] in ('propertydefs', 'propertyvalues')]
    def iteritems(self):
        return (item for item in super(CWRegistryStore, self).items()
                if not item[0] in ('propertydefs', 'propertyvalues'))

    def values(self):
        return [value for key, value in self.items()]
    def itervalues(self):
        return (value for key, value in self.items())

    def reset(self):
        CW_EVENT_MANAGER.emit('before-registry-reset', self)
        super(CWRegistryStore, self).reset()
        self._needs_appobject = {}
        # two special registries, propertydefs which care all the property
        # definitions, and propertyvals which contains values for those
        # properties
        if not self.initialized:
            self['propertydefs'] = {}
            self['propertyvalues'] = self.eprop_values = {}
            for key, propdef in self.config.cwproperty_definitions():
                self.register_property(key, **propdef)
        CW_EVENT_MANAGER.emit('after-registry-reset', self)

    def register_all(self, objects, modname, butclasses=()):
        butclasses = set(related_appobject(obj)
                         for obj in butclasses)
        objects = [related_appobject(obj) for obj in objects]
        super(CWRegistryStore, self).register_all(objects, modname, butclasses)

    def register_and_replace(self, obj, replaced):
        obj = related_appobject(obj)
        replaced = related_appobject(replaced)
        super(CWRegistryStore, self).register_and_replace(obj, replaced)

    def set_schema(self, schema):
        """set instance'schema and load application objects"""
        self._set_schema(schema)
        # now we can load application's web objects
        self.reload(self.config.appobjects_modnames(), force_reload=False)
        # map lowered entity type names to their actual name
        self.case_insensitive_etypes = {}
        for eschema in self.schema.entities():
            etype = str(eschema)
            self.case_insensitive_etypes[etype.lower()] = etype
            clear_cache(eschema, 'ordered_relations')
            clear_cache(eschema, 'meta_attributes')

    def is_reload_needed(self, modnames):
        """overriden to handle modules names instead of directories"""
        lastmodifs = self._lastmodifs
        for modname in modnames:
            if modname not in sys.modules:
                # new module to load
                return True
            filepath = sys.modules[modname].__file__
            if filepath.endswith('.py'):
                mdate = self._mdate(filepath)
                if filepath not in lastmodifs or lastmodifs[filepath] < mdate:
                    self.info('File %s changed since last visit', filepath)
                    return True
        return False

    def reload_if_needed(self):
        modnames = self.config.appobjects_modnames()
        if self.is_reload_needed(modnames):
            self.reload(modnames)

    def _cleanup_sys_modules(self, modnames):
        """Remove modules and submodules of `modnames` from `sys.modules` and cleanup
        CW_EVENT_MANAGER accordingly.

        We take care to properly remove obsolete registry callbacks.

        """
        caches = {}
        callbackdata = CW_EVENT_MANAGER.callbacks.values()
        for callbacklist in callbackdata:
            for callback in callbacklist:
                func = callback[0]
                # for non-function callable, we do nothing interesting
                module = getattr(func, '__module__', None)
                caches[id(callback)] = module
        deleted_modules = set(clean_sys_modules(modnames))
        for callbacklist in callbackdata:
            for callback in callbacklist[:]:
                module = caches[id(callback)]
                if module and module in deleted_modules:
                    callbacklist.remove(callback)

    def reload(self, modnames, force_reload=True):
        """modification detected, reset and reload the vreg"""
        CW_EVENT_MANAGER.emit('before-registry-reload')
        if force_reload:
            self._cleanup_sys_modules(modnames)
            cubes = self.config.cubes()
            # if the fs code use some cubes not yet registered into the instance
            # we should cleanup sys.modules for those as well to avoid potential
            # bad class reference pb after reloading
            cfg = self.config
            for cube in cfg.expand_cubes(cubes, with_recommends=True):
                if not cube in cubes:
                    cube_modnames = cfg.appobjects_cube_modnames(cube)
                    self._cleanup_sys_modules(cube_modnames)
        self.register_modnames(modnames)
        CW_EVENT_MANAGER.emit('after-registry-reload')

    def load_file(self, filepath, modname):
        # override to allow some instrumentation (eg localperms)
        modpath = modname.split('.')
        try:
            self.currently_loading_cube = modpath[modpath.index('cubes') + 1]
        except ValueError:
            self.currently_loading_cube = 'cubicweb'
        return super(CWRegistryStore, self).load_file(filepath, modname)

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

    def register(self, obj, *args, **kwargs):
        """register `obj` application object into `registryname` or
        `obj.__registry__` if not specified, with identifier `oid` or
        `obj.__regid__` if not specified.

        If `clear` is true, all objects with the same identifier will be
        previously unregistered.
        """
        obj = related_appobject(obj)
        super(CWRegistryStore, self).register(obj, *args, **kwargs)
        depends_on = require_appobject(obj)
        if depends_on is not None:
            self._needs_appobject[obj] = depends_on

    def register_objects(self, path):
        """overriden to give cubicweb's extrapath (eg cubes package's __path__)
        """
        super(CWRegistryStore, self).register_objects(
            path, self.config.extrapath)

    def initialization_completed(self):
        """cw specific code once vreg initialization is completed:

        * remove objects requiring a missing appobject, unless
          config.cleanup_unused_appobjects is false
        * init rtags
        """
        # we may want to keep interface dependent objects (e.g.for i18n
        # catalog generation)
        if self.config.cleanup_unused_appobjects:
            # remove appobjects which depend on other, unexistant appobjects
            for obj, (regname, regids) in self._needs_appobject.items():
                try:
                    registry = self[regname]
                except RegistryNotFound:
                    self.debug('unregister %s (no registry %s)', obj, regname)
                    self.unregister(obj)
                    continue
                for regid in regids:
                    if registry.get(regid):
                        break
                else:
                    self.debug('unregister %s (no %s object in registry %s)',
                               registry.objid(obj), ' or '.join(regids), regname)
                    self.unregister(obj)
        super(CWRegistryStore, self).initialization_completed()
        if 'uicfg' in self: # 'uicfg' is not loaded in a pure repository mode
            for rtags in self['uicfg'].values():
                for rtag in rtags:
                    # don't check rtags if we don't want to cleanup_unused_appobjects
                    rtag.init(self.schema, check=self.config.cleanup_unused_appobjects)

    # rql parsing utilities ####################################################

    @property
    @cached
    def rqlhelper(self):
        return RQLHelper(self.schema,
                         special_relations={'eid': 'uid', 'has_text': 'fti'})

    def solutions(self, req, rqlst, args):
        def type_from_eid(eid, req=req):
            return req.entity_type(eid)
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
        return sorted(k for k, kd in self['propertydefs'].items()
                      if not kd['sitewide'] and not k.startswith('sources.'))

    def register_property(self, key, type, help, default=None, vocabulary=None,
                          sitewide=False):
        """register a given property"""
        properties = self['propertydefs']
        assert type in YAMS_TO_PY, 'unknown type %s' % type
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
        """value is a unicode string, return it correctly typed. Let potential
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
                vocab = vocab(None) # XXX need a req object
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
            except ValueError as ex:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)
            except UnknownProperty as ex:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)


# XXX unify with yams.constraints.BASE_CONVERTERS?
YAMS_TO_PY = BASE_CONVERTERS.copy()
YAMS_TO_PY.update({
    'Bytes':      Binary,
    'Date':       date,
    'Datetime':   datetime,
    'TZDatetime': datetime,
    'Time':       time,
    'TZTime':     time,
    'Interval':   timedelta,
    })
