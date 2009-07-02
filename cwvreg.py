"""extend the generic VRegistry with some cubicweb specific stuff

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.decorators import cached, clear_cache
from logilab.common.deprecation import  obsolete

from rql import RQLHelper

from cubicweb import ETYPE_NAME_MAP, Binary, UnknownProperty, UnknownEid
from cubicweb.vregistry import VRegistry, ObjectNotFound, NoSelectableObject
from cubicweb.rtags import RTAGS


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
            pass # old-style vobject classes with no accepts_interfaces
        except:
            print 'bad selector %s on %s' % (obj.__select__, obj)
            raise
        return ()


class CubicWebRegistry(VRegistry):
    """Central registry for the cubicweb application, extending the generic
    VRegistry with some cubicweb specific stuff.

    This is one of the central object in cubicweb application, coupling
    dynamically loaded objects with the schema and the configuration objects.

    It specializes the VRegistry by adding some convenience methods to access to
    stored objects. Currently we have the following registries of objects known
    by the web application (library may use some others additional registries):

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
        super(CubicWebRegistry, self).__init__(config)
        self.schema = None
        self.reset()
        self.initialized = False

    def items(self):
        return [item for item in self._registries.items()
                if not item[0] in ('propertydefs', 'propertyvalues')]

    def values(self):
        return [value for key, value in self._registries.items()
                if not key in ('propertydefs', 'propertyvalues')]

    def reset(self):
        self._registries = {}
        self._lastmodifs = {}
        self._needs_iface = {}
        # two special registries, propertydefs which care all the property
        # definitions, and propertyvals which contains values for those
        # properties
        self._registries['propertydefs'] = {}
        self._registries['propertyvalues'] = self.eprop_values = {}
        for key, propdef in self.config.eproperty_definitions():
            self.register_property(key, **propdef)

    def set_schema(self, schema):
        """set application'schema and load application objects"""
        self.schema = schema
        clear_cache(self, 'rqlhelper')
        # now we can load application's web objects
        self.register_objects(self.config.vregistry_path())

    def update_schema(self, schema):
        """update .schema attribute on registered objects, necessary for some
        tests
        """
        self.schema = schema
        for registry, regcontent in self._registries.items():
            if registry in ('propertydefs', 'propertyvalues'):
                continue
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

    def register(self, obj, **kwargs):
        if kwargs.get('registryname', obj.__registry__) == 'etypes':
            if obj.id != 'Any' and not obj.id in self.schema:
                self.error('don\'t register %s, %s type not defined in the '
                           'schema', obj, obj.id)
                return
            kwargs['clear'] = True
        super(CubicWebRegistry, self).register(obj, **kwargs)
        # XXX bw compat
        ifaces = use_interfaces(obj)
        if ifaces:
            self._needs_iface[obj] = ifaces

    def register_objects(self, path, force_reload=None):
        """overriden to remove objects requiring a missing interface"""
        extrapath = {}
        for cubesdir in self.config.cubes_search_path():
            if cubesdir != self.config.CUBES_DIR:
                extrapath[cubesdir] = 'cubes'
        if super(CubicWebRegistry, self).register_objects(path, force_reload,
                                                          extrapath):
            self.initialization_completed()
            # call vreg_initialization_completed on appobjects and print
            # registry content
            for registry, objects in self.items():
                self.debug('available in registry %s: %s', registry,
                           sorted(objects))
                for appobjects in objects.itervalues():
                    for appobject in appobjects:
                        appobject.vreg_initialization_completed()
            # don't check rtags if we don't want to cleanup_interface_sobjects
            for rtag in RTAGS:
                rtag.init(self.schema,
                          check=self.config.cleanup_interface_sobjects)

    def initialization_completed(self):
        # clear etype cache if you don't want to run into deep weirdness
        clear_cache(self, 'etype_class')
        # we may want to keep interface dependent objects (e.g.for i18n
        # catalog generation)
        if self.config.cleanup_interface_sobjects:
            # remove vobjects that don't support any available interface
            implemented_interfaces = set()
            if 'Any' in self.get('etypes', ()):
                for etype in self.schema.entities():
                    cls = self.etype_class(etype)
                    for iface in cls.__implements__:
                        implemented_interfaces.update(iface.__mro__)
                    implemented_interfaces.update(cls.__mro__)
            for obj, ifaces in self._needs_iface.items():
                ifaces = frozenset(isinstance(iface, basestring)
                                   and iface in self.schema
                                   and self.etype_class(iface)
                                   or iface
                                   for iface in ifaces)
                if not ('Any' in ifaces or ifaces & implemented_interfaces):
                    self.debug('kicking vobject %s (no implemented '
                               'interface among %s)', obj, ifaces)
                    self.unregister(obj)
        # clear needs_iface so we don't try to remove some not-anymore-in
        # objects on automatic reloading
        self._needs_iface.clear()

    @cached
    def etype_class(self, etype):
        """return an entity class for the given entity type.
        Try to find out a specific class for this kind of entity or
        default to a dump of the class registered for 'Any'
        """
        etype = str(etype)
        if etype == 'Any':
            return self.select('etypes', 'Any', 'Any')
        eschema = self.schema.eschema(etype)
        baseschemas = [eschema] + eschema.ancestors()
        # browse ancestors from most specific to most generic and
        # try to find an associated custom entity class
        for baseschema in baseschemas:
            try:
                btype = ETYPE_NAME_MAP[baseschema]
            except KeyError:
                btype = str(baseschema)
            try:
                cls = self.select('etypes', btype, etype)
                break
            except ObjectNotFound:
                pass
        else:
            # no entity class for any of the ancestors, fallback to the default
            # one
            cls = self.select('etypes', 'Any', etype)
        return cls

    def render(self, __oid, req, __fallback_oid=None, __registry='views',
               rset=None, **kwargs):
        """select object, or fallback object if specified and the first one
        isn't selectable, then render it
        """
        try:
            obj = self.select(__registry, __oid, req, rset=rset, **kwargs)
        except NoSelectableObject:
            if __fallback_oid is None:
                raise
            obj = self.select(__registry, __fallback_oid, req, rset=rset,
                              **kwargs)
        return obj.render(**kwargs)

    def main_template(self, req, oid='main-template', **context):
        """display query by calling the given template (default to main),
        and returning the output as a string instead of requiring the [w]rite
        method as argument
        """
        res = self.render(oid, req, **context)
        if isinstance(res, unicode):
            return res.encode(req.encoding)
        assert isinstance(res, str)
        return res

    def select_vobject(self, registry, oid, *args, **kwargs):
        selected = self.select_object(registry, oid, *args, **kwargs)
        if selected and selected.propval('visible'):
            return selected
        return None

    def possible_vobjects(self, registry, *args, **kwargs):
        """return an ordered list of possible app objects in a given registry,
        supposing they support the 'visible' and 'order' properties (as most
        visualizable objects)
        """
        return [x for x in sorted(self.possible_objects(registry, *args, **kwargs),
                                  key=lambda x: x.propval('order'))
                if x.propval('visible')]

    def possible_actions(self, req, rset=None, **kwargs):
        if rset is None:
            actions = self.possible_vobjects('actions', req, rset=rset, **kwargs)
        else:
            actions = rset.possible_actions(**kwargs) # cached implementation
        result = {}
        for action in actions:
            result.setdefault(action.category, []).append(action)
        return result

    def possible_views(self, req, rset=None, **kwargs):
        """return an iterator on possible views for this result set

        views returned are classes, not instances
        """
        for vid, views in self.registry('views').items():
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

    @obsolete("use .select_object('boxes', ...)")
    def select_box(self, oid, *args, **kwargs):
        """return the most specific view according to the result set"""
        return self.select_object('boxes', oid, *args, **kwargs)

    @obsolete("use .select_object('components', ...)")
    def select_component(self, cid, *args, **kwargs):
        """return the most specific component according to the result set"""
        return self.select_object('components', cid, *args, **kwargs)

    @obsolete("use .select_object('actions', ...)")
    def select_action(self, oid, *args, **kwargs):
        """return the most specific view according to the result set"""
        return self.select_object('actions', oid, *args, **kwargs)

    @obsolete("use .select('views', ...)")
    def select_view(self, __vid, req, rset=None, **kwargs):
        """return the most specific view according to the result set"""
        return self.select('views', __vid, req, rset=rset, **kwargs)

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
        properties = self._registries['propertydefs']
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
            return self._registries['propertydefs'][key]
        except KeyError:
            if key.startswith('system.version.'):
                soft = key.split('.')[-1]
                return {'type': 'String', 'sitewide': True,
                        'default': None, 'vocabulary': None,
                        'help': _('%s software version of the database') % soft}
            raise UnknownProperty('unregistered property %r' % key)

    def property_value(self, key):
        try:
            return self._registries['propertyvalues'][key]
        except KeyError:
            return self._registries['propertydefs'][key]['default']

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
        values = self._registries['propertyvalues']
        for key, val in propvalues:
            try:
                values[key] = self.typed_value(key, val)
            except ValueError:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)
            except UnknownProperty, ex:
                self.warning('%s (you should probably delete that property '
                             'from the database)', ex)

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


class MulCnxCubicWebRegistry(CubicWebRegistry):
    """special registry to be used when an application has to deal with
    connections to differents repository. This class add some additional wrapper
    trying to hide buggy class attributes since classes are not designed to be
    shared among multiple registries.
    """
    def etype_class(self, etype):
        """return an entity class for the given entity type.
        Try to find out a specific class for this kind of entity or
        default to a dump of the class registered for 'Any'
        """
        usercls = super(MulCnxCubicWebRegistry, self).etype_class(etype)
        if etype == 'Any':
            return usercls
        usercls.e_schema = self.schema.eschema(etype)
        return usercls

    def select_best(self, vobjects, *args, **kwargs):
        """return an instance of the most specific object according
        to parameters

        raise NoSelectableObject if not object apply
        """
        for vobjectcls in vobjects:
            self._fix_cls_attrs(vobjectcls)
        selected = super(MulCnxCubicWebRegistry, self).select_best(
            vobjects, *args, **kwargs)
        # redo the same thing on the instance so it won't use equivalent class
        # attributes (which may change)
        self._fix_cls_attrs(selected)
        return selected

    def _fix_cls_attrs(self, vobject):
        vobject.vreg = self
        vobject.schema = self.schema
        vobject.config = self.config


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

