"""extend the generic VRegistry with some cubicweb specific stuff

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.decorators import cached, clear_cache, monkeypatch
from logilab.common.deprecation import  deprecated
from logilab.common.modutils import cleanup_sys_modules

from rql import RQLHelper

from cubicweb import (ETYPE_NAME_MAP, Binary, UnknownProperty, UnknownEid,
                      ObjectNotFound, NoSelectableObject, RegistryNotFound,
                      RegistryOutOfDate, CW_EVENT_MANAGER, onevent)
from cubicweb.utils import dump_class
from cubicweb.vregistry import VRegistry, Registry
from cubicweb.rtags import RTAGS


@onevent('before-registry-reload')
def clear_rtag_objects():
    for rtag in RTAGS:
        rtag.clear()


def use_interfaces(obj):
    """return interfaces used by the given object by searchinf for implements
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

    def initialization_completed(self):
        # call vreg_initialization_completed on appobjects and print
        # registry content
        for appobjects in self.itervalues():
            for appobject in appobjects:
                appobject.vreg_initialization_completed()

    def render(self, __oid, req, __fallback_oid=None, rset=None, **kwargs):
        """select object, or fallback object if specified and the first one
        isn't selectable, then render it
        """
        try:
            obj = self.select(__oid, req, rset=rset, **kwargs)
        except NoSelectableObject:
            if __fallback_oid is None:
                raise
            obj = self.select(__fallback_oid, req, rset=rset, **kwargs)
        return obj.render(**kwargs)

    def select_vobject(self, oid, *args, **kwargs):
        selected = self.select_object(oid, *args, **kwargs)
        if selected and selected.propval('visible'):
            return selected
        return None

    def possible_vobjects(self, *args, **kwargs):
        """return an ordered list of possible app objects in a given registry,
        supposing they support the 'visible' and 'order' properties (as most
        visualizable objects)
        """
        return sorted([x for x in self.possible_objects(*args, **kwargs)
                       if x.propval('visible')],
                      key=lambda x: x.propval('order'))


VRegistry.REGISTRY_FACTORY[None] = CWRegistry


class ETypeRegistry(CWRegistry):

    def initialization_completed(self):
        """on registration completed, clear etype_class internal cache
        """
        super(ETypeRegistry, self).initialization_completed()
        # clear etype cache if you don't want to run into deep weirdness
        clear_cache(self, 'etype_class')

    def register(self, obj, **kwargs):
        oid = kwargs.get('oid') or obj.id
        if oid != 'Any' and not oid in self.schema:
            self.error('don\'t register %s, %s type not defined in the '
                       'schema', obj, obj.id)
            return
        kwargs['clear'] = True
        super(ETypeRegistry, self).register(obj, **kwargs)

    @cached
    def etype_class(self, etype):
        """return an entity class for the given entity type.

        Try to find out a specific class for this kind of entity or default to a
        dump of the nearest parent class (in yams inheritance) registered.

        Fall back to 'Any' if not yams parent class found.
        """
        etype = str(etype)
        if etype == 'Any':
            return self.select('Any', 'Any')
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
        # make a copy event if cls.id == etype, else we may have pb for client
        # application using multiple connections to different repositories (eg
        # shingouz)
        cls = dump_class(cls, etype)
        cls.id = etype
        cls.__initialize__()
        return cls

VRegistry.REGISTRY_FACTORY['etypes'] = ETypeRegistry


class ViewsRegistry(CWRegistry):

    def main_template(self, req, oid='main-template', **kwargs):
        """display query by calling the given template (default to main),
        and returning the output as a string instead of requiring the [w]rite
        method as argument
        """
        res = self.render(oid, req, **kwargs)
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
                view = self.select_best(views, req, rset=rset, **kwargs)
                if view.linkable():
                    yield view
            except NoSelectableObject:
                continue
            except Exception:
                self.exception('error while trying to select %s view for %s',
                               vid, rset)

VRegistry.REGISTRY_FACTORY['views'] = ViewsRegistry


class ActionsRegistry(CWRegistry):

    def possible_actions(self, req, rset=None, **kwargs):
        if rset is None:
            actions = self.possible_vobjects(req, rset=rset, **kwargs)
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

    def reset(self, path=None, force_reload=None):
        super(CubicWebVRegistry, self).reset(path, force_reload)
        self._needs_iface = {}
        # two special registries, propertydefs which care all the property
        # definitions, and propertyvals which contains values for those
        # properties
        if not self.initialized:
            self['propertydefs'] = {}
            self['propertyvalues'] = self.eprop_values = {}
            for key, propdef in self.config.eproperty_definitions():
                self.register_property(key, **propdef)
        if path is not None and force_reload:
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

    def set_schema(self, schema):
        """set instance'schema and load application objects"""
        self.schema = schema
        clear_cache(self, 'rqlhelper')
        # now we can load application's web objects
        searchpath = self.config.vregistry_path()
        self.reset(searchpath, force_reload=False)
        self.register_objects(searchpath, force_reload=False)
        # map lowered entity type names to their actual name
        self.case_insensitive_etypes = {}
        for etype in self.schema.entities():
            etype = str(etype)
            self.case_insensitive_etypes[etype.lower()] = etype

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
        """register an object but remove it if no entity class implements one of
        the given interfaces
        """
        self.register(obj, **kwargs)
        if not isinstance(ifaces,  (tuple, list)):
            self._needs_iface[obj] = (ifaces,)
        else:
            self._needs_iface[obj] = ifaces

    def register(self, obj, *args, **kwargs):
        super(CubicWebVRegistry, self).register(obj, *args, **kwargs)
        # XXX bw compat
        ifaces = use_interfaces(obj)
        if ifaces:
            self._needs_iface[obj] = ifaces

    def register_objects(self, path, force_reload=None):
        """overriden to remove objects requiring a missing interface"""
        if force_reload is None:
            force_reload = self.config.mode == 'dev'
        try:
            self._register_objects(path, force_reload)
        except RegistryOutOfDate:
            CW_EVENT_MANAGER.emit('before-registry-reload')
            # modification detected, reset and reload
            self.reset(path, force_reload)
            self._register_objects(path, force_reload)
            CW_EVENT_MANAGER.emit('after-registry-reload')

    def _register_objects(self, path, force_reload=None):
        """overriden to remove objects requiring a missing interface"""
        extrapath = {}
        for cubesdir in self.config.cubes_search_path():
            if cubesdir != self.config.CUBES_DIR:
                extrapath[cubesdir] = 'cubes'
        if super(CubicWebVRegistry, self).register_objects(path, force_reload,
                                                          extrapath):
            self.initialization_completed()
            # don't check rtags if we don't want to cleanup_interface_sobjects
            for rtag in RTAGS:
                rtag.init(self.schema,
                          check=self.config.cleanup_interface_sobjects)

    def initialization_completed(self):
        for regname, reg in self.items():
            self.debug('available in registry %s: %s', regname, sorted(reg))
            reg.initialization_completed()
        # we may want to keep interface dependent objects (e.g.for i18n
        # catalog generation)
        if self.config.cleanup_interface_sobjects:
            # remove appobjects that don't support any available interface
            implemented_interfaces = set()
            if 'Any' in self.get('etypes', ()):
                for etype in self.schema.entities():
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

    def parse(self, session, rql, args=None):
        rqlst = self.rqlhelper.parse(rql)
        def type_from_eid(eid, session=session):
            return session.describe(eid)[0]
        try:
            self.rqlhelper.compute_solutions(rqlst, {'eid': type_from_eid}, args)
        except UnknownEid:
            for select in rqlst.children:
                select.solutions = []
        return rqlst

    @property
    @cached
    def rqlhelper(self):
        return RQLHelper(self.schema,
                         special_relations={'eid': 'uid', 'has_text': 'fti'})


    @deprecated('use vreg["etypes"].etype_class(etype)')
    def etype_class(self, etype):
        return self["etypes"].etype_class(etype)

    @deprecated('use vreg["views"].main_template(*args, **kwargs)')
    def main_template(self, req, oid='main-template', **context):
        return self["views"].main_template(req, oid, **context)

    @deprecated('use vreg[registry].possible_vobjects(*args, **kwargs)')
    def possible_vobjects(self, registry, *args, **kwargs):
        return self[registry].possible_vobjects(*args, **kwargs)

    @deprecated('use vreg["actions"].possible_actions(*args, **kwargs)')
    def possible_actions(self, req, rset=None, **kwargs):
        return self["actions"].possible_actions(req, rest=rset, **kwargs)

    @deprecated("use vreg['boxes'].select_object(...)")
    def select_box(self, oid, *args, **kwargs):
        return self['boxes'].select_object(oid, *args, **kwargs)

    @deprecated("use vreg['components'].select_object(...)")
    def select_component(self, cid, *args, **kwargs):
        return self['components'].select_object(cid, *args, **kwargs)

    @deprecated("use vreg['actions'].select_object(...)")
    def select_action(self, oid, *args, **kwargs):
        return self['actions'].select_object(oid, *args, **kwargs)

    @deprecated("use vreg['views'].select(...)")
    def select_view(self, __vid, req, rset=None, **kwargs):
        return self['views'].select(__vid, req, rset=rset, **kwargs)

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
            return self['propertydefs'][key]['default']

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
            except ValueError:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)
            except UnknownProperty, ex:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)


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

