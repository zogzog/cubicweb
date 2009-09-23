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
from warnings import warn

from logilab.common.decorators import classproperty
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods

from cubicweb import Unauthorized, NoSelectableObject


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
    def __iand__(self, other):
        raise NotImplementedError('cant use inplace & (binary and)')

    def __or__(self, other):
        return OrSelector(self, other)
    def __ror__(self, other):
        return OrSelector(other, self)
    def __ior__(self, other):
        raise NotImplementedError('cant use inplace | (binary or)')

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
    :__regid__:
      object's identifier in the registry (string like 'main',
      'primary', 'folder_box')
    :__select__:
      class'selector

    Moreover, the `__abstract__` attribute may be set to True to indicate
    that a appobject is abstract and should not be registered.

    At selection time, the following attributes are set on the instance:

    :_cw:
      current request
    :cw_extra_kwargs:
      other received arguments

    only if rset is found in arguments (in which case rset/row/col will be
    removed from cwextra_kwargs):

    :cw_rset:
      context result set or None
    :cw_row:
      if a result set is set and the context is about a particular cell in the
      result set, and not the result set as a whole, specify the row number we
      are interested in, else None
    :cw_col:
      if a result set is set and the context is about a particular cell in the
      result set, and not the result set as a whole, specify the col number we
      are interested in, else None
    """
    __registry__ = None
    __regid__ = None
    __select__ = yes()

    @classmethod
    def __registered__(cls, registry):
        """called by the registry when the appobject has been registered.

        It must return the object that will be actually registered (this may be
        the right hook to create an instance for example). By default the
        appobject is returned without any transformation.
        """
        try:
            pdefs = cls.property_defs
        except AttributeError:
            pdefs = getattr(cls, 'cw_property_defs', {})
        else:
            warn('property_defs is deprecated, use cw_property_defs in %s'
                 % cls, DeprecationWarning)
        for propid, pdef in pdefs.items():
            pdef = pdef.copy() # may be shared
            pdef['default'] = getattr(cls, propid, pdef['default'])
            pdef['sitewide'] = getattr(cls, 'site_wide', pdef.get('sitewide'))
            registry.vreg.register_property(cls._cwpropkey(propid), **pdef)
        return cls

    def __init__(self, req, **extra):
        super(AppObject, self).__init__()
        self._cw = req
        try:
            self.cw_rset = extra.pop('rset')
            self.cw_row = extra.pop('row', None)
            self.cw_col = extra.pop('col', None)
        except KeyError:
            pass
        self.cw_extra_kwargs = extra

    # persistent class properties ##############################################
    #
    # optional `cw_property_defs` dict on a class defines available persistent
    # properties for this class:
    #
    # * key: id of the property (the actual CWProperty key is build using
    #        <registry name>.<obj id>.<property id>
    # * value: tuple (property type, vocabfunc, default value, property description)
    #         possible types are those used by `logilab.common.configuration`
    #
    # notice that when it exists multiple objects with the same id (adaptation,
    # overriding) only the first encountered definition is considered, so those
    # objects can't try to have different default values for instance.
    #
    # you can then access to a property value using self.cw_propval, where self
    # is an instance of class

    @classmethod
    def _cwpropkey(cls, propid):
        """return cw property key for the property of the given id for this
        class
        """
        return '%s.%s.%s' % (cls.__registry__, cls.id, propid)

    def cw_propval(self, propid):
        """return cw property value associated to key

        <cls.__registry__>.<cls.id>.<propid>
        """
        return self.req.property_value(self._cwpropkey(propid))

    # deprecated ###############################################################

    @property
    @deprecated('[3.6] use self._cw.vreg')
    def vreg(self):
        return self._cw.vreg

    @property
    @deprecated('[3.6] use self._cw.vreg.schema')
    def schema(self):
        return self._cw.vreg.schema

    @property
    @deprecated('[3.6] use self._cw.vreg.config')
    def config(self):
        return self._cw.vreg.config

    @property
    @deprecated('[3.6] use self._cw')
    def req(self):
        return self._cw

    @deprecated('[3.6] use self.cw_rset')
    def get_rset(self):
        return self.cw_rset
    @deprecated('[3.6] use self.cw_rset')
    def set_rset(self, rset):
        self.cw_rset = rset
    rset = property(get_rset, set_rset)

    @property
    @deprecated('[3.6] use self.cw_row')
    def row(self):
        return self.cw_row

    @property
    @deprecated('[3.6] use self.cw_col')
    def col(self):
        return self.cw_col

    @property
    @deprecated('[3.6] use self.cw_extra_kwargs')
    def extra_kwargs(self):
        return self.cw_extra_kwargs

    @deprecated('[3.6] use self._cw.view')
    def view(self, *args, **kwargs):
        return self._cw.view(*args, **kwargs)

    @deprecated('[3.6] use self._cw.varmaker')
    def initialize_varmaker(self):
        self.varmaker = self._cw.varmaker

    @deprecated('[3.6] use self._cw.get_cache')
    def get_cache(self, cachename):
        return self._cw.get_cache(cachename)

    @deprecated('[3.6] use self._cw.build_url')
    def build_url(self, *args, **kwargs):
        return self._cw.build_url(*args, **kwargs)

    @deprecated('[3.6] use self.cw_rset.limited_rql')
    def limited_rql(self):
        return self.rset.limited_rql()

    @deprecated('[3.6] use self.rset.complete_entity(row,col) instead')
    def complete_entity(self, row, col=0, skip_bytes=True):
        return self.rset.complete_entity(row, col, skip_bytes)

    @deprecated('[3.6] use self.rset.get_entity(row,col) instead')
    def entity(self, row, col=0):
        return self.rset.get_entity(row, col)

    @deprecated('[3.6] use self._cw.user_rql_callback')
    def user_rql_callback(self, args, msg=None):
        return self._cw.user_rql_callback(args, msg)

    @deprecated('[3.6] use self._cw.user_callback')
    def user_callback(self, cb, args, msg=None, nonify=False):
        return self._cw.user_callback(cb, args, msg, nonify)

    @deprecated('[3.6] use self._cw.format_date')
    def format_date(self, date, date_format=None, time=False):
        return self._cw.format_date(date, date_format, time)

    @deprecated('[3.6] use self._cw.format_timoe')
    def format_time(self, time):
        return self._cw.format_time(time)

    @deprecated('[3.6] use self._cw.format_float')
    def format_float(self, num):
        return self._cw.format_float(num)

    @deprecated('[3.6] use self._cw.parse_datetime')
    def parse_datetime(self, value, etype='Datetime'):
        return self._cw.parse_datetime(value, etype)

    @deprecated('[3.6] use self.cw_propval')
    def propval(self, propid):
        return self._cw.property_value(self._cwpropkey(propid))

set_log_methods(AppObject, getLogger('cubicweb.appobject'))
