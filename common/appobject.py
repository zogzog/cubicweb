"""Base class for dynamically loaded objects manipulated in the web interface

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from mx.DateTime import now, oneSecond
from simplejson import dumps

from logilab.common.deprecation import obsolete
from rql.stmts import Union, Select

from cubicweb import Unauthorized
from cubicweb.vregistry import VObject
from cubicweb.common.utils import UStringIO
from cubicweb.common.uilib import html_escape, ustrftime
from cubicweb.common.registerers import yes_registerer, priority_registerer
from cubicweb.common.selectors import yes

_MARKER = object()


class Cache(dict):    
    def __init__(self):
        super(Cache, self).__init__()
        self.cache_creation_date = None
        self.latest_cache_lookup = now()
    
CACHE_REGISTRY = {}

class AppRsetObject(VObject):
    """This is the base class for CubicWeb application objects
    which are selected according to a request and result set.
    
    Classes are kept in the vregistry and instantiation is done at selection
    time.
    
    At registration time, the following attributes are set on the class:
    :vreg:
      the application's registry
    :schema:
      the application's schema
    :config:
      the application's configuration

    At instantiation time, the following attributes are set on the instance:
    :req:
      current request
    :rset:
      result set on which the object is applied
    """

    @classmethod
    def registered(cls, vreg):
        cls.vreg = vreg
        cls.schema = vreg.schema
        cls.config = vreg.config
        cls.register_properties()
        return cls

    @classmethod
    def selected(cls, req, rset, row=None, col=None, **kwargs):
        """by default web app objects are usually instantiated on
        selection according to a request, a result set, and optional
        row and col
        """
        instance = cls(req, rset)
        instance.row = row
        instance.col = col
        return instance

    # Eproperties definition:
    # key: id of the property (the actual EProperty key is build using
    #      <registry name>.<obj id>.<property id>
    # value: tuple (property type, vocabfunc, default value, property description)
    #        possible types are those used by `logilab.common.configuration`
    #
    # notice that when it exists multiple objects with the same id (adaptation,
    # overriding) only the first encountered definition is considered, so those
    # objects can't try to have different default values for instance.
    
    property_defs = {}
    
    @classmethod
    def register_properties(cls):
        for propid, pdef in cls.property_defs.items():
            pdef = pdef.copy() # may be shared
            pdef['default'] = getattr(cls, propid, pdef['default'])
            pdef['sitewide'] = getattr(cls, 'site_wide', pdef.get('sitewide'))
            cls.vreg.register_property(cls.propkey(propid), **pdef)
        
    @classmethod
    def propkey(cls, propid):
        return '%s.%s.%s' % (cls.__registry__, cls.id, propid)
            
        
    def __init__(self, req, rset):
        super(AppRsetObject, self).__init__()
        self.req = req
        self.rset = rset

    @property
    def cursor(self): # XXX deprecate in favor of req.cursor?
        msg = '.cursor is deprecated, use req.execute (or req.cursor if necessary)'
        warn(msg, DeprecationWarning, stacklevel=2)
        return self.req.cursor
        
    def get_cache(self, cachename):
        """
        NOTE: cachename should be dotted names as in :
        - cubicweb.mycache
        - cubes.blog.mycache 
        - etc.
        """
        if cachename in CACHE_REGISTRY:
            cache = CACHE_REGISTRY[cachename]
        else:
            cache = Cache()
            CACHE_REGISTRY[cachename] = cache
        _now = now()
        if _now > cache.latest_cache_lookup + oneSecond:
            ecache = self.req.execute('Any C,T WHERE C is ECache, C name %(name)s, C timestamp T', 
                                      {'name':cachename}).get_entity(0,0)
            cache.latest_cache_lookup = _now
            if not ecache.valid(cache.cache_creation_date):
                cache.empty()
                cache.cache_creation_date = _now
        return cache

    def propval(self, propid):
        assert self.req
        return self.req.property_value(self.propkey(propid))

    
    def limited_rql(self):
        """return a printable rql for the result set associated to the object,
        with limit/offset correctly set according to maximum page size and
        currently displayed page when necessary
        """
        # try to get page boundaries from the navigation component
        # XXX we should probably not have a ref to this component here (eg in
        #     cubicweb.common)
        nav = self.vreg.select_component('navigation', self.req, self.rset)
        if nav:
            start, stop = nav.page_boundaries()
            rql = self._limit_offset_rql(stop - start, start)
        # result set may have be limited manually in which case navigation won't
        # apply
        elif self.rset.limited:
            rql = self._limit_offset_rql(*self.rset.limited)
        # navigation component doesn't apply and rset has not been limited, no
        # need to limit query
        else:
            rql = self.rset.printable_rql()
        return rql
    
    def _limit_offset_rql(self, limit, offset):
        rqlst = self.rset.syntax_tree()
        if len(rqlst.children) == 1:
            select = rqlst.children[0]
            olimit, ooffset = select.limit, select.offset
            select.limit, select.offset = limit, offset
            rql = rqlst.as_string(kwargs=self.rset.args)
            # restore original limit/offset
            select.limit, select.offset = olimit, ooffset
        else:
            newselect = Select()
            newselect.limit = limit
            newselect.offset = offset
            aliases = [VariableRef(newselect.get_variable(vref.name, i))
                       for i, vref in enumerate(rqlst.selection)]
            newselect.set_with([SubQuery(aliases, rqlst)], check=False)
            newunion = Union()
            newunion.append(newselect)
            rql = rqlst.as_string(kwargs=self.rset.args)
            rqlst.parent = None
        return rql
    
    # url generation methods ##################################################
    
    controller = 'view'
    
    def build_url(self, method=None, **kwargs):
        """return an absolute URL using params dictionary key/values as URL
        parameters. Values are automatically URL quoted, and the
        publishing method to use may be specified or will be guessed.
        """
        # XXX I (adim) think that if method is passed explicitly, we should
        #     not try to process it and directly call req.build_url()
        if method is None:
            method = self.controller
            if method == 'view' and self.req.from_controller() == 'view' and \
                   not '_restpath' in kwargs:
                method = self.req.relative_path(includeparams=False) or 'view'
        return self.req.build_url(method, **kwargs)

    # various resources accessors #############################################

    def etype_rset(self, etype, size=1):
        """return a fake result set for a particular entity type"""
        msg = '.etype_rset is deprecated, use req.etype_rset'
        warn(msg, DeprecationWarning, stacklevel=2)
        return self.req.etype_rset(etype, size=1)

    def eid_rset(self, eid, etype=None):
        """return a result set for the given eid"""
        msg = '.eid_rset is deprecated, use req.eid_rset'
        warn(msg, DeprecationWarning, stacklevel=2)
        return self.req.eid_rset(eid, etype)
    
    def entity(self, row, col=0):
        """short cut to get an entity instance for a particular row/column
        (col default to 0)
        """
        return self.rset.get_entity(row, col)
    
    def complete_entity(self, row, col=0, skip_bytes=True):
        """short cut to get an completed entity instance for a particular
        row (all instance's attributes have been fetched)
        """
        entity = self.entity(row, col)
        entity.complete(skip_bytes=skip_bytes)
        return entity

    def user_rql_callback(self, args, msg=None):
        """register a user callback to execute some rql query and return an url
        to call it ready to be inserted in html
        """
        def rqlexec(req, rql, args=None, key=None):
            req.execute(rql, args, key)
        return self.user_callback(rqlexec, args, msg)
        
    def user_callback(self, cb, args, msg=None, nonify=False):
        """register the given user callback and return an url to call it ready to be
        inserted in html
        """
        self.req.add_js('cubicweb.ajax.js')
        if nonify:
            # XXX < 2.48.3 bw compat
            warn('nonify argument is deprecated', DeprecationWarning, stacklevel=2)
            _cb = cb
            def cb(*args):
                _cb(*args)
        cbname = self.req.register_onetime_callback(cb, *args)
        msg = dumps(msg or '') 
        return "javascript:userCallbackThenReloadPage('%s', %s)" % (
            cbname, msg)

    # formating methods #######################################################

    def tal_render(self, template, variables):
        """render a precompiled page template with variables in the given
        dictionary as context
        """
        from cubicweb.common.tal import CubicWebContext
        context = CubicWebContext()
        context.update({'self': self, 'rset': self.rset, '_' : self.req._,
                        'req': self.req, 'user': self.req.user})
        context.update(variables)
        output = UStringIO()
        template.expand(context, output)
        return output.getvalue()

    def format_date(self, date, date_format=None, time=False):
        """return a string for a mx date time according to application's
        configuration
        """
        if date:
            if date_format is None:
                if time:
                    date_format = self.req.property_value('ui.datetime-format')
                else:
                    date_format = self.req.property_value('ui.date-format')
            return ustrftime(date, date_format)
        return u''

    def format_time(self, time):
        """return a string for a mx date time according to application's
        configuration
        """
        if time:
            return ustrftime(time, self.req.property_value('ui.time-format'))
        return u''

    def format_float(self, num):
        """return a string for floating point number according to application's
        configuration
        """
        if num:
            return self.req.property_value('ui.float-format') % num
        return u''
    
    # security related methods ################################################
    
    def ensure_ro_rql(self, rql):
        """raise an exception if the given rql is not a select query"""
        first = rql.split(' ', 1)[0].lower()
        if first in ('insert', 'set', 'delete'):
            raise Unauthorized(self.req._('only select queries are authorized'))

    # .accepts handling utilities #############################################
    
    accepts = ('Any',)

    @classmethod
    def accept_rset(cls, req, rset, row, col):
        """apply the following rules:
        * if row is None, return the sum of values returned by the method
          for each entity's type in the result set. If any score is 0,
          return 0.
        * if row is specified, return the value returned by the method with
          the entity's type of this row
        """
        if row is None:
            score = 0
            for etype in rset.column_types(0):
                accepted = cls.accept(req.user, etype)
                if not accepted:
                    return 0
                score += accepted
            return score
        return cls.accept(req.user, rset.description[row][col or 0])
        
    @classmethod
    def accept(cls, user, etype):
        """score etype, returning better score on exact match"""
        if 'Any' in cls.accepts:
            return 1
        eschema = cls.schema.eschema(etype)
        matching_types = [e.type for e in eschema.ancestors()]
        matching_types.append(etype)
        for index, basetype in enumerate(matching_types):
            if basetype in cls.accepts:
                return 2 + index
        return 0
    
    # .rtype  handling utilities ##############################################
    
    @classmethod
    def relation_possible(cls, etype):
        """tell if a relation with etype entity is possible according to 
        mixed class'.etype, .rtype and .target attributes

        XXX should probably be moved out to a function
        """
        schema = cls.schema
        rtype = cls.rtype
        eschema = schema.eschema(etype)
        if hasattr(cls, 'role'):
            role = cls.role
        elif cls.target == 'subject':
            role = 'object'
        else:
            role = 'subject'
        # check if this relation is possible according to the schema
        try:
            if role == 'object':
                rschema = eschema.object_relation(rtype)
            else:
                rschema = eschema.subject_relation(rtype)
        except KeyError:
            return False            
        if hasattr(cls, 'etype'):
            letype = cls.etype
            try:
                if role == 'object':
                    return etype in rschema.objects(letype)
                else:
                    return etype in rschema.subjects(letype)
            except KeyError, ex:
                return False
        return True

    
    # XXX deprecated (since 2.43) ##########################
    
    @obsolete('use req.datadir_url')
    def datadir_url(self):
        """return url of the application's data directory"""
        return self.req.datadir_url

    @obsolete('use req.external_resource()')
    def external_resource(self, rid, default=_MARKER):
        return self.req.external_resource(rid, default)

        
class AppObject(AppRsetObject):
    """base class for application objects which are not selected
    according to a result set, only by their identifier.
    
    Those objects may not have req, rset and cursor set.
    """
    
    @classmethod
    def selected(cls, *args, **kwargs):
        """by default web app objects are usually instantiated on
        selection
        """
        return cls(*args, **kwargs)

    def __init__(self, req=None, rset=None, **kwargs):
        self.req = req
        self.rset = rset
        self.__dict__.update(kwargs)


class ReloadableMixIn(object):
    """simple mixin for reloadable parts of UI"""
    
    def user_callback(self, cb, args, msg=None, nonify=False):
        """register the given user callback and return an url to call it ready to be
        inserted in html
        """
        self.req.add_js('cubicweb.ajax.js')
        if nonify:
            _cb = cb
            def cb(*args):
                _cb(*args)
        cbname = self.req.register_onetime_callback(cb, *args)
        return self.build_js(cbname, html_escape(msg or ''))
        
    def build_update_js_call(self, cbname, msg):
        rql = html_escape(self.rset.printable_rql())
        return "javascript:userCallbackThenUpdateUI('%s', '%s', '%s', '%s', '%s', '%s')" % (
            cbname, self.id, rql, msg, self.__registry__, self.div_id())
    
    def build_reload_js_call(self, cbname, msg):
        return "javascript:userCallbackThenReloadPage('%s', '%s')" % (cbname, msg)

    build_js = build_update_js_call # expect updatable component by default
    
    def div_id(self):
        return ''


class ComponentMixIn(ReloadableMixIn):
    """simple mixin for component object"""
    __registry__ = 'components'
    __registerer__ = yes_registerer
    __selectors__ = (yes,)
    __select__ = classmethod(*__selectors__)

    def div_class(self):
        return '%s %s' % (self.propval('htmlclass'), self.id)

    def div_id(self):
        return '%sComponent' % self.id


class Component(ComponentMixIn, AppObject):
    """base class for non displayable components
    """

class SingletonComponent(Component):
    """base class for non displayable unique components
    """
    __registerer__ = priority_registerer
