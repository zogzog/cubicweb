"""Base class for dynamically loaded objects accessible through the vregistry.

You'll also find some convenience classes to build selectors.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import types
from logging import getLogger
from datetime import datetime, timedelta

from logilab.common.decorators import classproperty
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods

from cubicweb import Unauthorized, NoSelectableObject
from cubicweb.utils import UStringIO

ONESECOND = timedelta(0, 1, 0)
CACHE_REGISTRY = {}


class Cache(dict):
    def __init__(self):
        super(Cache, self).__init__()
        _now = datetime.now()
        self.cache_creation_date = _now
        self.latest_cache_lookup = _now


# selector base classes and operations ########################################

def objectify_selector(selector_func):
    """convenience decorator for simple selectors where a class definition
    would be overkill::

        @objectify_selector
        def yes(cls, *args, **kwargs):
            return 1

    """
    return type(selector_func.__name__, (Selector,),
                {'__call__': lambda self, *args, **kwargs: selector_func(*args, **kwargs)})


def _instantiate_selector(selector):
    """ensures `selector` is a `Selector` instance

    NOTE: This should only be used locally in build___select__()
    XXX: then, why not do it ??
    """
    if isinstance(selector, types.FunctionType):
        return objectify_selector(selector)()
    if isinstance(selector, type) and issubclass(selector, Selector):
        return selector()
    return selector


class Selector(object):
    """base class for selector classes providing implementation
    for operators ``&`` and ``|``

    This class is only here to give access to binary operators, the
    selector logic itself should be implemented in the __call__ method


    a selector is called to help choosing the correct object for a
    particular context by returning a score (`int`) telling how well
    the class given as first argument apply to the given context.

    0 score means that the class doesn't apply.
    """

    @property
    def func_name(self):
        # backward compatibility
        return self.__class__.__name__

    def search_selector(self, selector):
        """search for the given selector or selector instance in the selectors
        tree. Return it of None if not found
        """
        if self is selector:
            return self
        if isinstance(selector, type) and isinstance(self, selector):
            return self
        return None

    def __str__(self):
        return self.__class__.__name__

    def __and__(self, other):
        return AndSelector(self, other)
    def __rand__(self, other):
        return AndSelector(other, self)

    def __or__(self, other):
        return OrSelector(self, other)
    def __ror__(self, other):
        return OrSelector(other, self)

    def __invert__(self):
        return NotSelector(self)

    # XXX (function | function) or (function & function) not managed yet

    def __call__(self, cls, *args, **kwargs):
        return NotImplementedError("selector %s must implement its logic "
                                   "in its __call__ method" % self.__class__)


class MultiSelector(Selector):
    """base class for compound selector classes"""

    def __init__(self, *selectors):
        self.selectors = self.merge_selectors(selectors)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.selectors))

    @classmethod
    def merge_selectors(cls, selectors):
        """deal with selector instanciation when necessary and merge
        multi-selectors if possible:

        AndSelector(AndSelector(sel1, sel2), AndSelector(sel3, sel4))
        ==> AndSelector(sel1, sel2, sel3, sel4)
        """
        merged_selectors = []
        for selector in selectors:
            try:
                selector = _instantiate_selector(selector)
            except:
                pass
            #assert isinstance(selector, Selector), selector
            if isinstance(selector, cls):
                merged_selectors += selector.selectors
            else:
                merged_selectors.append(selector)
        return merged_selectors

    def search_selector(self, selector):
        """search for the given selector or selector instance in the selectors
        tree. Return it of None if not found
        """
        for childselector in self.selectors:
            if childselector is selector:
                return childselector
            found = childselector.search_selector(selector)
            if found is not None:
                return found
        return None


class AndSelector(MultiSelector):
    """and-chained selectors (formerly known as chainall)"""
    def __call__(self, cls, *args, **kwargs):
        score = 0
        for selector in self.selectors:
            partscore = selector(cls, *args, **kwargs)
            if not partscore:
                return 0
            score += partscore
        return score


class OrSelector(MultiSelector):
    """or-chained selectors (formerly known as chainfirst)"""
    def __call__(self, cls, *args, **kwargs):
        for selector in self.selectors:
            partscore = selector(cls, *args, **kwargs)
            if partscore:
                return partscore
        return 0

class NotSelector(Selector):
    """negation selector"""
    def __init__(self, selector):
        self.selector = selector

    def __call__(self, cls, *args, **kwargs):
        score = self.selector(cls, *args, **kwargs)
        return int(not score)

    def __str__(self):
        return 'NOT(%s)' % super(NotSelector, self).__str__()


class yes(Selector):
    """return arbitrary score

    default score of 0.5 so any other selector take precedence
    """
    def __init__(self, score=0.5):
        self.score = score

    def __call__(self, *args, **kwargs):
        return self.score


# the base class for all appobjects ############################################

class AppObject(object):
    """This is the base class for CubicWeb application objects which are
    selected according to a context (usually at least a request and a result
    set).

    Concrete application objects classes are designed to be loaded by the
    vregistry and should be accessed through it, not by direct instantiation.

    The following attributes should be set on concret appobject classes:
    :__registry__:
      name of the registry for this object (string like 'views',
      'templates'...)
    :id:
      object's identifier in the registry (string like 'main',
      'primary', 'folder_box')
    :__select__:
      class'selector

    Moreover, the `__abstract__` attribute may be set to True to indicate
    that a appobject is abstract and should not be registered.

    At registration time, the following attributes are set on the class:
    :vreg:
      the instance's registry
    :schema:
      the instance's schema
    :config:
      the instance's configuration

    At selection time, the following attributes are set on the instance:
    :req:
      current request
    :rset:
      context result set or None
    :row:
      if a result set is set and the context is about a particular cell in the
      result set, and not the result set as a whole, specify the row number we
      are interested in, else None
    :col:
      if a result set is set and the context is about a particular cell in the
      result set, and not the result set as a whole, specify the col number we
      are interested in, else None
    """
    __registry__ = None
    id = None
    __select__ = yes()

    @classmethod
    def classid(cls):
        """returns a unique identifier for the appobject"""
        return '%s.%s' % (cls.__module__, cls.__name__)

    # XXX bw compat code
    @classmethod
    def build___select__(cls):
        for klass in cls.mro():
            if klass.__name__ == 'AppObject':
                continue # the bw compat __selector__ is there
            klassdict = klass.__dict__
            if ('__select__' in klassdict and '__selectors__' in klassdict
                and '__selgenerated__' not in klassdict):
                raise TypeError("__select__ and __selectors__ can't be used together on class %s" % cls)
            if '__selectors__' in klassdict and '__selgenerated__' not in klassdict:
                cls.__selgenerated__ = True
                # case where __selectors__ is defined locally (but __select__
                # is in a parent class)
                selectors = klassdict['__selectors__']
                if len(selectors) == 1:
                    # micro optimization: don't bother with AndSelector if there's
                    # only one selector
                    select = _instantiate_selector(selectors[0])
                else:
                    select = AndSelector(*selectors)
                cls.__select__ = select

    @classmethod
    def registered(cls, registry):
        """called by the registry when the appobject has been registered.

        It must return the object that will be actually registered (this may be
        the right hook to create an instance for example). By default the
        appobject is returned without any transformation.
        """
        cls.build___select__()
        cls.vreg = registry.vreg
        cls.register_properties()
        return cls

    @classmethod
    def vreg_initialization_completed(cls):
        pass

    # properties definition:
    # key: id of the property (the actual CWProperty key is build using
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


    def __init__(self, req=None, rset=None, row=None, col=None, **extra):
        super(AppObject, self).__init__()
        self.req = req
        self.rset = rset
        self.row = row
        self.col = col
        self.extra_kwargs = extra

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
            cache = CACHE_REGISTRY[cachename] = Cache()
        _now = datetime.now()
        if _now > cache.latest_cache_lookup + ONESECOND:
            ecache = self.req.execute('Any C,T WHERE C is CWCache, C name %(name)s, C timestamp T',
                                      {'name':cachename}).get_entity(0,0)
            cache.latest_cache_lookup = _now
            if not ecache.valid(cache.cache_creation_date):
                cache.clear()
                cache.cache_creation_date = _now
        return cache

    def propval(self, propid):
        assert self.req
        return self.req.property_value(self.propkey(propid))

    def view(self, __vid, rset=None, __fallback_oid=None, __registry='views',
             **kwargs):
        """shortcut to self.vreg.view method avoiding to pass self.req"""
        return self.vreg[__registry].render(__vid, self.req, __fallback_oid,
                                            rset=rset, **kwargs)

    # url generation methods ##################################################

    controller = 'view'

    def build_url(self, *args, **kwargs):
        """return an absolute URL using params dictionary key/values as URL
        parameters. Values are automatically URL quoted, and the
        publishing method to use may be specified or will be guessed.
        """
        # use *args since we don't want first argument to be "anonymous" to
        # avoid potential clash with kwargs
        if args:
            assert len(args) == 1, 'only 0 or 1 non-named-argument expected'
            method = args[0]
        else:
            method = None
        # XXX I (adim) think that if method is passed explicitly, we should
        #     not try to process it and directly call req.build_url()
        if method is None:
            method = self.controller
            if method == 'view' and self.req.from_controller() == 'view' and \
                   not '_restpath' in kwargs:
                method = self.req.relative_path(includeparams=False) or 'view'
        return self.req.build_url(method, **kwargs)

    # deprecated ###############################################################

    @classproperty
    @deprecated('[3.4] use __select__ and & or | operators')
    def __selectors__(cls):
        selector = cls.__select__
        if isinstance(selector, AndSelector):
            return tuple(selector.selectors)
        if not isinstance(selector, tuple):
            selector = (selector,)
        return selector

    @classmethod
    @deprecated('[3.5] use vreg.schema')
    def schema(cls):
        return cls.vreg.schema

    @classmethod
    @deprecated('[3.5] use vreg.config')
    def schema(cls):
        return cls.vreg.config

    @deprecated('[3.5] use req.varmaker')
    def initialize_varmaker(self):
        self.varmaker = self.req.varmaker

    @deprecated('[3.5] use rset.limited_rql')
    def limited_rql(self):
        return self.rset.limited_rql()

    @deprecated('[3.5] use self.rset.complete_entity(row,col) instead')
    def complete_entity(self, row, col=0, skip_bytes=True):
        return self.rset.complete_entity(row, col, skip_bytes)

    @deprecated('[3.5] use self.rset.get_entity(row,col) instead')
    def entity(self, row, col=0):
        return self.rset.get_entity(row, col)

    @deprecated('[3.5] use req.user_rql_callback')
    def user_rql_callback(self, args, msg=None):
        return self.req.user_rql_callback(args, msg)

    @deprecated('[3.5] use req.user_callback')
    def user_callback(self, cb, args, msg=None, nonify=False):
        return self.req.user_callback(cb, args, msg, nonify)

    @deprecated('[3.5] use req.format_date')
    def format_date(self, date, date_format=None, time=False):
        return self.req.format_date(date, date_format, time)

    @deprecated('[3.5] use req.format_timoe')
    def format_time(self, time):
        return self.req.format_time(time)

    @deprecated('[3.5] use req.format_float')
    def format_float(self, num):
        return self.req.format_float(num)

    @deprecated('[3.5] use req.parse_datetime')
    def parse_datetime(self, value, etype='Datetime'):
        return self.req.parse_datetime(value, etype)

set_log_methods(AppObject, getLogger('cubicweb.appobject'))
