"""extend the generic VRegistry with some cubicweb specific stuff

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.decorators import cached, clear_cache
from logilab.common.interface import extend

from rql import RQLHelper

from cubicweb import Binary, UnknownProperty
from cubicweb.vregistry import VRegistry, ObjectNotFound, NoSelectableObject

_ = unicode

def use_interfaces(obj):
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

def expand_parent_classes(iface):
    res = [iface]
    for parent in iface.__bases__:
        res += expand_parent_classes(parent)
    return res


class CubicWebRegistry(VRegistry):
    """extend the generic VRegistry with some cubicweb specific stuff"""
    
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
        return [value for key,value in self._registries.items()
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
                self.error('don\'t register %s, %s type not defined in the schema',
                           obj, obj.id)
                return
            kwargs['clear'] = True
        super(CubicWebRegistry, self).register(obj, **kwargs)
        # XXX bw compat
        ifaces = use_interfaces(obj)
        if ifaces:
            self._needs_iface[obj] = ifaces
        
    def register_objects(self, path, force_reload=None):
        """overriden to remove objects requiring a missing interface"""
        if super(CubicWebRegistry, self).register_objects(path, force_reload):
            # clear etype cache if you don't want to run into deep weirdness
            clear_cache(self, 'etype_class')
            # we may want to keep interface dependent objects (e.g.for i18n
            # catalog generation)
            if not self.config.cleanup_interface_sobjects:
                return
            # remove vobjects that don't support any available interface
            interfaces = set()
            for classes in self.get('etypes', {}).values():
                for cls in classes:
                    for iface in cls.__implements__:
                        interfaces.update(expand_parent_classes(iface))
                    interfaces.update(expand_parent_classes(cls))
            for obj, ifaces in self._needs_iface.items():
                ifaces = frozenset(isinstance(iface, basestring) and iface in self.schema and self.etype_class(iface) or iface
                                   for iface in ifaces)
                if not ifaces & interfaces:
                    self.debug('kicking vobject %s (unsupported interface)', obj)
                    self.unregister(obj)
            
        
    
    def eid_rset(self, cursor, eid, etype=None):
        """return a result set for the given eid without doing actual query
        (we have the eid, we can suppose it exists and user has access to the
        entity)
        """
        msg = '.eid_rset is deprecated, use req.eid_rset'
        warn(msg, DeprecationWarning, stacklevel=2)
        try:
            return cursor.req.eid_rset(eid, etype)
        except AttributeError:
            # cursor is a session
            return cursor.eid_rset(eid, etype)
    
    @cached
    def etype_class(self, etype):
        """return an entity class for the given entity type.
        Try to find out a specific class for this kind of entity or
        default to a dump of the class registered for 'Any'
        """
        etype = str(etype)
        if etype == 'Any':
            return self.select(self.registry_objects('etypes', 'Any'), 'Any')
        eschema = self.schema.eschema(etype)
        baseschemas = [eschema] + eschema.ancestors()
        # browse ancestors from most specific to most generic and
        # try to find an associated custom entity class
        for baseschema in baseschemas:
            btype = str(baseschema)
            try:
                cls = self.select(self.registry_objects('etypes', btype), etype)
                break
            except ObjectNotFound:
                pass
        else:
            # no entity class for any of the ancestors, fallback to the default
            # one
            cls = self.select(self.registry_objects('etypes', 'Any'), etype)
        # add class itself to the list of implemented interfaces, as well as the
        # Any entity class so we can select according to class using the
        # `implements` selector
        extend(cls, cls)
        extend(cls, self.etype_class('Any'))
        return cls
    
    def render(self, registry, oid, req, **context):
        """select an object in a given registry and render it

        - registry: the registry's name
        - oid : the view to call
        - req : the HTTP request         
        """
        objclss = self.registry_objects(registry, oid)
        try:
            rset = context.pop('rset')
        except KeyError:
            rset = None
        selected = self.select(objclss, req, rset, **context)
        return selected.dispatch(**context)
        
    def main_template(self, req, oid='main-template', **context):
        """display query by calling the given template (default to main),
        and returning the output as a string instead of requiring the [w]rite
        method as argument
        """
        res = self.render('views', oid, req, **context)
        if isinstance(res, unicode):
            return res.encode(req.encoding)
        assert isinstance(res, str)
        return res

    def possible_vobjects(self, registry, *args, **kwargs):
        """return an ordered list of possible app objects in a given registry,
        supposing they support the 'visible' and 'order' properties (as most
        visualizable objects)
        """
        return [x for x in sorted(self.possible_objects(registry, *args, **kwargs),
                                  key=lambda x: x.propval('order'))
                if x.propval('visible')]
        
    def possible_actions(self, req, rset, **kwargs):
        if rset is None:
            actions = self.possible_vobjects('actions', req, rset)
        else:
            actions = rset.possible_actions() # cached implementation
        result = {}
        for action in actions:
            result.setdefault(action.category, []).append(action)
        return result
        
    def possible_views(self, req, rset, **kwargs):
        """return an iterator on possible views for this result set

        views returned are classes, not instances
        """
        for vid, views in self.registry('views').items():
            if vid[0] == '_':
                continue
            try:
                view = self.select(views, req, rset, **kwargs)
                if view.linkable():
                    yield view
            except NoSelectableObject:
                continue
            except Exception:
                self.exception('error while trying to list possible %s views for %s',
                               vid, rset)
                
    def select_box(self, oid, *args, **kwargs):
        """return the most specific view according to the result set"""
        try:
            return self.select_object('boxes', oid, *args, **kwargs)
        except NoSelectableObject:
            return

    def select_action(self, oid, *args, **kwargs):
        """return the most specific view according to the result set"""
        try:
            return self.select_object('actions', oid, *args, **kwargs)
        except NoSelectableObject:
            return
    
    def select_component(self, cid, *args, **kwargs):
        """return the most specific component according to the result set"""
        try:
            return self.select_object('components', cid, *args, **kwargs)
        except (NoSelectableObject, ObjectNotFound):
            return

    def select_view(self, __vid, req, rset, **kwargs):
        """return the most specific view according to the result set"""
        views = self.registry_objects('views', __vid)
        return self.select(views, req, rset, **kwargs)

    
    # properties handling #####################################################

    def user_property_keys(self, withsitewide=False):
        if withsitewide:
            return sorted(self['propertydefs'])
        return sorted(k for k, kd in self['propertydefs'].iteritems()
                      if not kd['sitewide'])

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


    def property_value_widget(self, propkey, req=None, **attrs):
        """return widget according to key's type / vocab"""
        from cubicweb.web.widgets import StaticComboBoxWidget, widget_factory
        if req is None:
            tr = unicode
        else:
            tr = req._
        try:
            pdef = self.property_info(propkey)
        except UnknownProperty, ex:
            self.warning('%s (you should probably delete that property '
                         'from the database)', ex)
            return widget_factory(self, 'EProperty', self.schema['value'], 'String',
                                  description=u'', **attrs)
        req.form['value'] = pdef['default'] # XXX hack to pass the default value
        vocab = pdef['vocabulary']
        if vocab is not None:
            if callable(vocab):
                # list() just in case its a generator function
                vocabfunc = lambda e: list(vocab(propkey, req))
            else:
                vocabfunc = lambda e: vocab
            w = StaticComboBoxWidget(self, 'EProperty', self.schema['value'], 'String',
                                     vocabfunc=vocabfunc, description=tr(pdef['help']),
                                     **attrs)
        else:
            w = widget_factory(self, 'EProperty', self.schema['value'], pdef['type'],
                               description=tr(pdef['help']), **attrs)
        return w

    def parse(self, session, rql, args=None):
        rqlst = self.rqlhelper.parse(rql)
        def type_from_eid(eid, session=session):
            return session.describe(eid)[0]
        self.rqlhelper.compute_solutions(rqlst, {'eid': type_from_eid}, args)
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
    shared.
    """
    def etype_class(self, etype):
        """return an entity class for the given entity type.
        Try to find out a specific class for this kind of entity or
        default to a dump of the class registered for 'Any'
        """
        usercls = super(MulCnxCubicWebRegistry, self).etype_class(etype)
        usercls.e_schema = self.schema.eschema(etype)
        return usercls

    def select(self, vobjects, *args, **kwargs):
        """return an instance of the most specific object according
        to parameters

        raise NoSelectableObject if not object apply
        """
        for vobject in vobjects:
            vobject.vreg = self
            vobject.schema = self.schema
            vobject.config = self.config
        return super(MulCnxCubicWebRegistry, self).select(vobjects, *args, **kwargs)
    
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

