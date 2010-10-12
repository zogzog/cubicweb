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
""".. _Selectors:

Selectors
---------

Using and combining existant selectors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can combine selectors using the `&`, `|` and `~` operators.

When two selectors are combined using the `&` operator, it means that
both should return a positive score. On success, the sum of scores is
returned.

When two selectors are combined using the `|` operator, it means that
one of them should return a positive score. On success, the first
positive score is returned.

You can also "negate" a selector by precedeing it by the `~` unary operator.

Of course you can use parenthesis to balance expressions.

Example
~~~~~~~

The goal: when on a blog, one wants the RSS link to refer to blog entries, not to
the blog entity itself.

To do that, one defines a method on entity classes that returns the
RSS stream url for a given entity. The default implementation on
:class:`~cubicweb.entities.AnyEntity` (the generic entity class used
as base for all others) and a specific implementation on `Blog` will
do what we want.

But when we have a result set containing several `Blog` entities (or
different entities), we don't know on which entity to call the
aforementioned method. In this case, we keep the generic behaviour.

Hence we have two cases here, one for a single-entity rsets, the other for
multi-entities rsets.

In web/views/boxes.py lies the RSSIconBox class. Look at its selector:

.. sourcecode:: python

  class RSSIconBox(box.Box):
    ''' just display the RSS icon on uniform result set '''
    __select__ = box.Box.__select__ & non_final_entity()

It takes into account:

* the inherited selection criteria (one has to look them up in the class
  hierarchy to know the details)

* :class:`~cubicweb.selectors.non_final_entity`, which filters on result sets
  containing non final entities (a 'final entity' being synonym for entity
  attributes type, eg `String`, `Int`, etc)

This matches our second case. Hence we have to provide a specific component for
the first case:

.. sourcecode:: python

  class EntityRSSIconBox(RSSIconBox):
    '''just display the RSS icon on uniform result set for a single entity'''
    __select__ = RSSIconBox.__select__ & one_line_rset()

Here, one adds the :class:`~cubicweb.selectors.one_line_rset` selector, which
filters result sets of size 1. Thus, on a result set containing multiple
entities, :class:`one_line_rset` makes the EntityRSSIconBox class non
selectable. However for a result set with one entity, the `EntityRSSIconBox`
class will have a higher score than `RSSIconBox`, which is what we wanted.

Of course, once this is done, you have to:

* fill in the call method of `EntityRSSIconBox`

* provide the default implementation of the method returning the RSS stream url
  on :class:`~cubicweb.entities.AnyEntity`

* redefine this method on `Blog`.


When to use selectors?
~~~~~~~~~~~~~~~~~~~~~~

Selectors are to be used whenever arises the need of dispatching on the shape or
content of a result set or whatever else context (value in request form params,
authenticated user groups, etc...). That is, almost all the time.

Here is a quick example:

.. sourcecode:: python

    class UserLink(component.Component):
	'''if the user is the anonymous user, build a link to login else a link
	to the connected user object with a logout link
	'''
	__regid__ = 'loggeduserlink'

	def call(self):
	    if self._cw.session.anonymous_session:
		# display login link
		...
	    else:
		# display a link to the connected user object with a loggout link
		...

The proper way to implement this with |cubicweb| is two have two different
classes sharing the same identifier but with different selectors so you'll get
the correct one according to the context.

.. sourcecode:: python

    class UserLink(component.Component):
	'''display a link to the connected user object with a loggout link'''
	__regid__ = 'loggeduserlink'
	__select__ = component.Component.__select__ & authenticated_user()

	def call(self):
            # display useractions and siteactions
	    ...

    class AnonUserLink(component.Component):
	'''build a link to login'''
	__regid__ = 'loggeduserlink'
	__select__ = component.Component.__select__ & anonymous_user()

	def call(self):
	    # display login link
            ...

The big advantage, aside readability once you're familiar with the
system, is that your cube becomes much more easily customizable by
improving componentization.


.. _CustomSelectors:

Defining your own selectors
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autodocstring:: cubicweb.appobject::objectify_selector

In other cases, you can take a look at the following abstract base classes:

.. autoclass:: cubicweb.selectors.ExpectedValueSelector
.. autoclass:: cubicweb.selectors.EClassSelector
.. autoclass:: cubicweb.selectors.EntitySelector

Also, think to use the :func:`lltrace` decorator on your selector class' :meth:`__call__` method
or below the :func:`objectify_selector` decorator of your selector function so it gets
traceable when :class:`traced_selection` is activated (see :ref:`DebuggingSelectors`).

.. autofunction:: cubicweb.appobject.lltrace

.. note::
  Selectors __call__ should *always* return a positive integer, and shall never
  return `None`.


.. _DebuggingSelectors:

Debugging selection
~~~~~~~~~~~~~~~~~~~

Once in a while, one needs to understand why a view (or any application object)
is, or is not selected appropriately. Looking at which selectors fired (or did
not) is the way. The :class:`cubicweb.appobject.traced_selection` context
manager to help with that, *if you're running your instance in debug mode*.

.. autoclass:: cubicweb.appobject.traced_selection

"""

__docformat__ = "restructuredtext en"

import logging
from warnings import warn
from operator import eq

from logilab.common.deprecation import class_renamed
from logilab.common.compat import all, any
from logilab.common.interface import implements as implements_iface

from yams.schema import BASE_TYPES, role_name
from rql.nodes import Function

from cubicweb import (Unauthorized, NoSelectableObject, NotAnEntity,
                      CW_EVENT_MANAGER, role)
# even if not used, let yes here so it's importable through this module
from cubicweb.uilib import eid_param
from cubicweb.appobject import Selector, objectify_selector, lltrace, yes
from cubicweb.schema import split_expression

from cubicweb.appobject import traced_selection # XXX for bw compat

def score_interface(etypesreg, eclass, iface):
    """Return XXX if the give object (maybe an instance or class) implements
    the interface.
    """
    if getattr(iface, '__registry__', None) == 'etypes':
        # adjust score if the interface is an entity class
        parents, any = etypesreg.parent_classes(eclass.__regid__)
        if iface is eclass:
            return len(parents) + 4
        if iface is any: # Any
            return 1
        for index, basecls in enumerate(reversed(parents)):
            if iface is basecls:
                return index + 3
        return 0
    # XXX iface in implements deprecated in 3.9
    if implements_iface(eclass, iface):
        # implementing an interface takes precedence other special Any interface
        return 2
    return 0


# abstract selectors / mixin helpers ###########################################

class PartialSelectorMixIn(object):
    """convenience mix-in for selectors that will look into the containing
    class to find missing information.

    cf. `cubicweb.web.action.LinkToEntityAction` for instance
    """
    def __call__(self, cls, *args, **kwargs):
        self.complete(cls)
        return super(PartialSelectorMixIn, self).__call__(cls, *args, **kwargs)


class EClassSelector(Selector):
    """abstract class for selectors working on *entity class(es)* specified
    explicitly or found of the result set.

    Here are entity lookup / scoring rules:

    * if `entity` is specified, return score for this entity's class

    * elif `row` is specified, return score for the class of the entity
      found in the specified cell, using column specified by `col` or 0

    * else return the sum of scores for each entity class found in the column
      specified specified by the `col` argument or in column 0 if not specified,
      unless:

      - `once_is_enough` is False (the default) and some entity class is scored
        to 0, in which case 0 is returned

      - `once_is_enough` is True, in which case the first non-zero score is
        returned

      - `accept_none` is False and some cell in the column has a None value
        (this may occurs with outer join)
    """
    def __init__(self, once_is_enough=False, accept_none=True):
        self.once_is_enough = once_is_enough
        self.accept_none = accept_none

    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, accept_none=None,
                 **kwargs):
        if kwargs.get('entity'):
            return self.score_class(kwargs['entity'].__class__, req)
        if not rset:
            return 0
        score = 0
        if row is None:
            if accept_none is None:
                accept_none = self.accept_none
            if not accept_none:
                if any(rset[i][col] is None for i in xrange(len(rset))):
                    return 0
            for etype in rset.column_types(col):
                if etype is None: # outer join
                    return 0
                escore = self.score(cls, req, etype)
                if not escore and not self.once_is_enough:
                    return 0
                elif self.once_is_enough:
                    return escore
                score += escore
        else:
            etype = rset.description[row][col]
            if etype is not None:
                score = self.score(cls, req, etype)
        return score

    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return self.score_class(req.vreg['etypes'].etype_class(etype), req)

    def score_class(self, eclass, req):
        raise NotImplementedError()


class EntitySelector(EClassSelector):
    """abstract class for selectors working on *entity instance(s)* specified
    explicitly or found of the result set.

    Here are entity lookup / scoring rules:

    * if `entity` is specified, return score for this entity

    * elif `row` is specified, return score for the entity found in the
      specified cell, using column specified by `col` or 0

    * else return the sum of scores for each entity found in the column
      specified specified by the `col` argument or in column 0 if not specified,
      unless:

      - `once_is_enough` is False (the default) and some entity is scored
        to 0, in which case 0 is returned

      - `once_is_enough` is True, in which case the first non-zero score is
        returned

      - `accept_none` is False and some cell in the column has a None value
        (this may occurs with outer join)

    .. Note::
       using :class:`EntitySelector` or :class:`EClassSelector` as base selector
       class impacts performance, since when no entity or row is specified the
       later works on every different *entity class* found in the result set,
       while the former works on each *entity* (eg each row of the result set),
       which may be much more costly.
    """

    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, accept_none=None,
                 **kwargs):
        if not rset and not kwargs.get('entity'):
            return 0
        score = 0
        if kwargs.get('entity'):
            score = self.score_entity(kwargs['entity'])
        elif row is None:
            col = col or 0
            if accept_none is None:
                accept_none = self.accept_none
            for row, rowvalue in enumerate(rset.rows):
                if rowvalue[col] is None: # outer join
                    if not accept_none:
                        return 0
                    continue
                escore = self.score(req, rset, row, col)
                if not escore and not self.once_is_enough:
                    return 0
                elif self.once_is_enough:
                    return escore
                score += escore
        else:
            col = col or 0
            etype = rset.description[row][col]
            if etype is not None: # outer join
                score = self.score(req, rset, row, col)
        return score

    def score(self, req, rset, row, col):
        try:
            return self.score_entity(rset.get_entity(row, col))
        except NotAnEntity:
            return 0

    def score_entity(self, entity):
        raise NotImplementedError()


class ExpectedValueSelector(Selector):
    """Take a list of expected values as initializer argument and store them
    into the :attr:`expected` set attribute.

    You should implement the :meth:`_get_value(cls, req, **kwargs)` method
    which should return the value for the given context. The selector will then
    return 1 if the value is expected, else 0.
    """
    def __init__(self, *expected):
        assert expected, self
        self.expected = frozenset(expected)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(sorted(str(s) for s in self.expected)))

    @lltrace
    def __call__(self, cls, req, **kwargs):
        if self._get_value(cls, req, **kwargs) in self.expected:
            return 1
        return 0

    def _get_value(self, cls, req, **kwargs):
        raise NotImplementedError()


# bare selectors ##############################################################

class match_kwargs(ExpectedValueSelector):
    """Return non-zero score if parameter names specified as initializer
    arguments are specified in the input context. When multiple parameters are
    specified, all of them should be specified in the input context. Return a
    score corresponding to the number of expected parameters.
    """

    @lltrace
    def __call__(self, cls, req, **kwargs):
        for arg in self.expected:
            if not arg in kwargs:
                return 0
        return len(self.expected)


class appobject_selectable(Selector):
    """Return 1 if another appobject is selectable using the same input context.

    Initializer arguments:

    * `registry`, a registry name

    * `regids`, object identifiers in this registry, one of them should be
      selectable.
    """
    selectable_score = 1
    def __init__(self, registry, *regids):
        self.registry = registry
        self.regids = regids

    @lltrace
    def __call__(self, cls, req, **kwargs):
        for regid in self.regids:
            try:
                req.vreg[self.registry].select(regid, req, **kwargs)
                return self.selectable_score
            except NoSelectableObject:
                return 0


class adaptable(appobject_selectable):
    """Return 1 if another appobject is selectable using the same input context.

    Initializer arguments:

    * `regids`, adapter identifiers (e.g. interface names) to which the context
      (usually entities) should be adaptable. One of them should be selectable
      when multiple identifiers are given.
    """
    def __init__(self, *regids):
        super(adaptable, self).__init__('adapters', *regids)

    def __call__(self, cls, req, **kwargs):
        kwargs.setdefault('accept_none', False)
        # being adaptable to an interface should takes precedence other is_instance('Any'),
        # but not other explicit is_instance('SomeEntityType'), and:
        # * is_instance('Any') score is 1
        # * is_instance('SomeEntityType') score is at least 2
        score = super(adaptable, self).__call__(cls, req, **kwargs)
        if score >= 2:
            return score - 0.5
        if score == 1:
            return score + 0.5
        return score


class configuration_values(Selector):
    """Return 1 if the instance has an option set to a given value(s) in its
    configuration file.
    """
    # XXX this selector could be evaluated on startup
    def __init__(self, key, values):
        self._key = key
        if not isinstance(values, (tuple, list)):
            values = (values,)
        self._values = frozenset(values)

    @lltrace
    def __call__(self, cls, req, **kwargs):
        try:
            return self._score
        except AttributeError:
            if req is None:
                config = kwargs['repo'].config
            else:
                config = req.vreg.config
            self._score = config[self._key] in self._values
        return self._score


# rset selectors ##############################################################

@objectify_selector
@lltrace
def none_rset(cls, req, rset=None, **kwargs):
    """Return 1 if the result set is None (eg usually not specified)."""
    if rset is None:
        return 1
    return 0


# XXX == ~ none_rset
@objectify_selector
@lltrace
def any_rset(cls, req, rset=None, **kwargs):
    """Return 1 for any result set, whatever the number of rows in it, even 0."""
    if rset is not None:
        return 1
    return 0


@objectify_selector
@lltrace
def nonempty_rset(cls, req, rset=None, **kwargs):
    """Return 1 for result set containing one ore more rows."""
    if rset is not None and rset.rowcount:
        return 1
    return 0


# XXX == ~ nonempty_rset
@objectify_selector
@lltrace
def empty_rset(cls, req, rset=None, **kwargs):
    """Return 1 for result set which doesn't contain any row."""
    if rset is not None and rset.rowcount == 0:
        return 1
    return 0


# XXX == multi_lines_rset(1)
@objectify_selector
@lltrace
def one_line_rset(cls, req, rset=None, row=None, **kwargs):
    """Return 1 if the result set is of size 1, or greater but a specific row in
      the result set is specified ('row' argument).
    """
    if rset is not None and (row is not None or rset.rowcount == 1):
        return 1
    return 0


class multi_lines_rset(Selector):
    """Return 1 if the operator expression matches between `num` elements
    in the result set and the `expected` value if defined.

    By default, multi_lines_rset(expected) matches equality expression:
        `nb` row(s) in result set equals to expected value
    But, you can perform richer comparisons by overriding default operator:
        multi_lines_rset(expected, operator.gt)

    If `expected` is None, return 1 if the result set contains *at least*
    two rows.
    If rset is None, return 0.
    """
    def __init__(self, expected=None, operator=eq):
        self.expected = expected
        self.operator = operator

    def match_expected(self, num):
        if self.expected is None:
            return num > 1
        return self.operator(num, self.expected)

    @lltrace
    def __call__(self, cls, req, rset=None, **kwargs):
        return int(rset is not None and self.match_expected(rset.rowcount))


class multi_columns_rset(multi_lines_rset):
    """If `nb` is specified, return 1 if the result set has exactly `nb` column
    per row. Else (`nb` is None), return 1 if the result set contains *at least*
    two columns per row. Return 0 for empty result set.
    """

    @lltrace
    def __call__(self, cls, req, rset=None, **kwargs):
        # 'or 0' since we *must not* return None
        return rset and self.match_expected(len(rset.rows[0])) or 0


class paginated_rset(Selector):
    """Return 1 or more for result set with more rows than one or more page
    size.  You can specify expected number of pages to the initializer (default
    to one), and you'll get that number of pages as score if the result set is
    big enough.

    Page size is searched in (respecting order):
    * a `page_size` argument
    * a `page_size` form parameters
    * the :ref:`navigation.page-size` property
    """
    def __init__(self, nbpages=1):
        assert nbpages > 0
        self.nbpages = nbpages

    @lltrace
    def __call__(self, cls, req, rset=None, **kwargs):
        if rset is None:
            return 0
        page_size = kwargs.get('page_size')
        if page_size is None:
            page_size = req.form.get('page_size')
            if page_size is None:
                page_size = req.property_value('navigation.page-size')
            else:
                page_size = int(page_size)
        if rset.rowcount <= (page_size*self.nbpages):
            return 0
        return self.nbpages


@objectify_selector
@lltrace
def sorted_rset(cls, req, rset=None, **kwargs):
    """Return 1 for sorted result set (e.g. from an RQL query containing an
    ORDERBY clause), with exception that it will return 0 if the rset is
    'ORDERBY FTIRANK(VAR)' (eg sorted by rank value of the has_text index).
    """
    if rset is None:
        return 0
    selects = rset.syntax_tree().children
    if (len(selects) > 1 or
        not selects[0].orderby or
        (isinstance(selects[0].orderby[0].term, Function) and
         selects[0].orderby[0].term.name == 'FTIRANK')
        ):
        return 0
    return 2


# XXX == multi_etypes_rset(1)
@objectify_selector
@lltrace
def one_etype_rset(cls, req, rset=None, col=0, **kwargs):
    """Return 1 if the result set contains entities which are all of the same
    type in the column specified by the `col` argument of the input context, or
    in column 0.
    """
    if rset is None:
        return 0
    if len(rset.column_types(col)) != 1:
        return 0
    return 1


class multi_etypes_rset(multi_lines_rset):
    """If `nb` is specified, return 1 if the result set contains `nb` different
    types of entities in the column specified by the `col` argument of the input
    context, or in column 0. If `nb` is None, return 1 if the result set contains
    *at least* two different types of entities.
    """

    @lltrace
    def __call__(self, cls, req, rset=None, col=0, **kwargs):
        # 'or 0' since we *must not* return None
        return rset and self.match_expected(len(rset.column_types(col))) or 0


@objectify_selector
def logged_user_in_rset(cls, req, rset=None, row=None, col=0, **kwargs):
    """Return positive score if the result set at the specified row / col
    contains the eid of the logged user.
    """
    if rset is None:
        return 0
    return req.user.eid == rset[row or 0][col]


# entity selectors #############################################################

class non_final_entity(EClassSelector):
    """Return 1 for entity of a non final entity type(s). Remember, "final"
    entity types are String, Int, etc... This is equivalent to
    `is_instance('Any')` but more optimized.

    See :class:`~cubicweb.selectors.EClassSelector` documentation for entity
    class lookup / score rules according to the input context.
    """
    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return 1

    def score_class(self, eclass, req):
        return 1 # necessarily true if we're there


class implements(EClassSelector):
    """Return non-zero score for entity that are of the given type(s) or
    implements at least one of the given interface(s). If multiple arguments are
    given, matching one of them is enough.

    Entity types should be given as string, the corresponding class will be
    fetched from the entity types registry at selection time.

    See :class:`~cubicweb.selectors.EClassSelector` documentation for entity
    class lookup / score rules according to the input context.

    .. note:: when interface is an entity class, the score will reflect class
              proximity so the most specific object will be selected.

    .. note:: deprecated in cubicweb >= 3.9, use either
              :class:`~cubicweb.selectors.is_instance` or
              :class:`~cubicweb.selectors.adaptable`.
    """

    def __init__(self, *expected_ifaces, **kwargs):
        emit_warn = kwargs.pop('warn', True)
        super(implements, self).__init__(**kwargs)
        self.expected_ifaces = expected_ifaces
        if emit_warn:
            warn('[3.9] implements selector is deprecated, use either '
                 'is_instance or adaptable', DeprecationWarning, stacklevel=2)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.expected_ifaces))

    def score_class(self, eclass, req):
        score = 0
        etypesreg = req.vreg['etypes']
        for iface in self.expected_ifaces:
            if isinstance(iface, basestring):
                # entity type
                try:
                    iface = etypesreg.etype_class(iface)
                except KeyError:
                    continue # entity type not in the schema
            score += score_interface(etypesreg, eclass, iface)
        return score

def _reset_is_instance_cache(vreg):
    vreg._is_instance_selector_cache = {}

CW_EVENT_MANAGER.bind('before-registry-reset', _reset_is_instance_cache)

class is_instance(EClassSelector):
    """Return non-zero score for entity that is an instance of the one of given
    type(s). If multiple arguments are given, matching one of them is enough.

    Entity types should be given as string, the corresponding class will be
    fetched from the registry at selection time.

    See :class:`~cubicweb.selectors.EClassSelector` documentation for entity
    class lookup / score rules according to the input context.

    .. note:: the score will reflect class proximity so the most specific object
              will be selected.
    """

    def __init__(self, *expected_etypes, **kwargs):
        super(is_instance, self).__init__(**kwargs)
        self.expected_etypes = expected_etypes
        for etype in self.expected_etypes:
            assert isinstance(etype, basestring), etype

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.expected_etypes))

    def score_class(self, eclass, req):
        # cache on vreg to avoid reloading issues
        cache = req.vreg._is_instance_selector_cache
        try:
            expected_eclasses = cache[self]
        except KeyError:
            # turn list of entity types as string into a list of
            #  (entity class, parent classes)
            etypesreg = req.vreg['etypes']
            expected_eclasses = cache[self] = []
            for etype in self.expected_etypes:
                try:
                    expected_eclasses.append(etypesreg.etype_class(etype))
                except KeyError:
                    continue # entity type not in the schema
        parents, any = req.vreg['etypes'].parent_classes(eclass.__regid__)
        score = 0
        for expectedcls in expected_eclasses:
            # adjust score according to class proximity
            if expectedcls is eclass:
                score += len(parents) + 4
            elif expectedcls is any: # Any
                score += 1
            else:
                for index, basecls in enumerate(reversed(parents)):
                    if expectedcls is basecls:
                        score += index + 3
                        break
        return score


class score_entity(EntitySelector):
    """Return score according to an arbitrary function given as argument which
    will be called with input content entity as argument.

    This is a very useful selector that will usually interest you since it
    allows a lot of things without having to write a specific selector.

    See :class:`~cubicweb.selectors.EntitySelector` documentation for entity
    lookup / score rules according to the input context.
    """
    def __init__(self, scorefunc, once_is_enough=False):
        super(score_entity, self).__init__(once_is_enough)
        def intscore(*args, **kwargs):
            score = scorefunc(*args, **kwargs)
            if not score:
                return 0
            if isinstance(score, (int, long)):
                return score
            return 1
        self.score_entity = intscore


class has_mimetype(EntitySelector):
    """Return 1 if the entity adapt to IDownloadable and has the given MIME type.

    You can give 'image/' to match any image for instance, or 'image/png' to match
    only PNG images.
    """
    def __init__(self, mimetype, once_is_enough=False):
        super(has_mimetype, self).__init__(once_is_enough)
        self.mimetype = mimetype

    def score_entity(self, entity):
        idownloadable = entity.cw_adapt_to('IDownloadable')
        if idownloadable is None:
            return 0
        mt = idownloadable.download_content_type()
        if not (mt and mt.startswith(self.mimetype)):
            return 0
        return 1


class relation_possible(EntitySelector):
    """Return 1 for entity that supports the relation, provided that the
    request's user may do some `action` on it (see below).

    The relation is specified by the following initializer arguments:

    * `rtype`, the name of the relation

    * `role`, the role of the entity in the relation, either 'subject' or
      'object', default to 'subject'

    * `target_etype`, optional name of an entity type that should be supported
      at the other end of the relation

    * `action`, a relation schema action (e.g. one of 'read', 'add', 'delete',
      default to 'read') which must be granted to the user, else a 0 score will
      be returned. Give None if you don't want any permission checking.

    * `strict`, boolean (default to False) telling what to do when the user has
      not globally the permission for the action (eg the action is not granted
      to one of the user's groups)

      - when strict is False, if there are some local role defined for this
        action (e.g. using rql expressions), then the permission will be
        considered as granted

      - when strict is True, then the permission will be actually checked for
        each entity

    Setting `strict` to True impacts performance for large result set since
    you'll then get the :class:`~cubicweb.selectors.EntitySelector` behaviour
    while otherwise you get the :class:`~cubicweb.selectors.EClassSelector`'s
    one. See those classes documentation for entity lookup / score rules
    according to the input context.
    """

    def __init__(self, rtype, role='subject', target_etype=None,
                 action='read', strict=False, **kwargs):
        super(relation_possible, self).__init__(**kwargs)
        self.rtype = rtype
        self.role = role
        self.target_etype = target_etype
        self.action = action
        self.strict = strict

    # hack hack hack
    def __call__(self, cls, req, **kwargs):
        if self.strict:
            return EntitySelector.__call__(self, cls, req, **kwargs)
        return EClassSelector.__call__(self, cls, req, **kwargs)

    def score(self, *args):
        if self.strict:
            return EntitySelector.score(self, *args)
        return EClassSelector.score(self, *args)

    def _get_rschema(self, eclass):
        eschema = eclass.e_schema
        try:
            if self.role == 'object':
                return eschema.objrels[self.rtype]
            else:
                return eschema.subjrels[self.rtype]
        except KeyError:
            return None

    def score_class(self, eclass, req):
        rschema = self._get_rschema(eclass)
        if rschema is None:
            return 0 # relation not supported
        eschema = eclass.e_schema
        if self.target_etype is not None:
            try:
                rdef = rschema.role_rdef(eschema, self.target_etype, self.role)
            except KeyError:
                return 0
            if self.action and not rdef.may_have_permission(self.action, req):
                return 0
            teschema = req.vreg.schema.eschema(self.target_etype)
            if not teschema.may_have_permission('read', req):
                return 0
        elif self.action:
            return rschema.may_have_permission(self.action, req, eschema, self.role)
        return 1

    def score_entity(self, entity):
        rschema = self._get_rschema(entity)
        if rschema is None:
            return 0 # relation not supported
        if self.action:
            if self.target_etype is not None:
                rschema = rschema.role_rdef(entity.e_schema, self.target_etype, self.role)
            if self.role == 'subject':
                if not rschema.has_perm(entity._cw, self.action, fromeid=entity.eid):
                    return 0
            elif not rschema.has_perm(entity._cw, self.action, toeid=entity.eid):
                return 0
        if self.target_etype is not None:
            req = entity._cw
            teschema = req.vreg.schema.eschema(self.target_etype)
            if not teschema.may_have_permission('read', req):
                return 0
        return 1


class partial_relation_possible(PartialSelectorMixIn, relation_possible):
    """Same as :class:~`cubicweb.selectors.relation_possible`, but will look for
    attributes of the selected class to get information which is otherwise
    expected by the initializer, except for `action` and `strict` which are kept
    as initializer arguments.

    This is useful to predefine selector of an abstract class designed to be
    customized.
    """
    def __init__(self, action='read', **kwargs):
        super(partial_relation_possible, self).__init__(None, None, None,
                                                        action, **kwargs)

    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)
        self.target_etype = getattr(cls, 'etype', None)
        if self.target_etype is not None:
            warn('[3.6] please rename etype to target_etype on %s' % cls,
                 DeprecationWarning)
        else:
            self.target_etype = getattr(cls, 'target_etype', None)


class has_related_entities(EntitySelector):
    """Return 1 if entity support the specified relation and has some linked
    entities by this relation , optionaly filtered according to the specified
    target type.

    The relation is specified by the following initializer arguments:

    * `rtype`, the name of the relation

    * `role`, the role of the entity in the relation, either 'subject' or
      'object', default to 'subject'.

    * `target_etype`, optional name of an entity type that should be found
      at the other end of the relation

    See :class:`~cubicweb.selectors.EntitySelector` documentation for entity
    lookup / score rules according to the input context.
    """
    def __init__(self, rtype, role='subject', target_etype=None, **kwargs):
        super(has_related_entities, self).__init__(**kwargs)
        self.rtype = rtype
        self.role = role
        self.target_etype = target_etype

    def score_entity(self, entity):
        relpossel = relation_possible(self.rtype, self.role, self.target_etype)
        if not relpossel.score_class(entity.__class__, entity._cw):
            return 0
        rset = entity.related(self.rtype, self.role)
        if self.target_etype:
            return any(r for r in rset.description if r[0] == self.target_etype)
        return rset and 1 or 0


class partial_has_related_entities(PartialSelectorMixIn, has_related_entities):
    """Same as :class:~`cubicweb.selectors.has_related_entity`, but will look
    for attributes of the selected class to get information which is otherwise
    expected by the initializer.

    This is useful to predefine selector of an abstract class designed to be
    customized.
    """
    def __init__(self, **kwargs):
        super(partial_has_related_entities, self).__init__(None, None, None,
                                                           **kwargs)

    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)
        self.target_etype = getattr(cls, 'etype', None)
        if self.target_etype is not None:
            warn('[3.6] please rename etype to target_etype on %s' % cls,
                 DeprecationWarning)
        else:
            self.target_etype = getattr(cls, 'target_etype', None)


class has_permission(EntitySelector):
    """Return non-zero score if request's user has the permission to do the
    requested action on the entity. `action` is an entity schema action (eg one
    of 'read', 'add', 'delete', 'update').

    Here are entity lookup / scoring rules:

    * if `entity` is specified, check permission is granted for this entity

    * elif `row` is specified, check permission is granted for the entity found
      in the specified cell

    * else check permission is granted for each entity found in the column
      specified specified by the `col` argument or in column 0
    """
    def __init__(self, action):
        self.action = action

    # don't use EntitySelector.__call__ but this optimized implementation to
    # avoid considering each entity when it's not necessary
    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        if kwargs.get('entity'):
            return self.score_entity(kwargs['entity'])
        if rset is None:
            return 0
        if row is None:
            score = 0
            need_local_check = []
            geteschema = req.vreg.schema.eschema
            user = req.user
            action = self.action
            for etype in rset.column_types(0):
                if etype in BASE_TYPES:
                    return 0
                eschema = geteschema(etype)
                if not user.matching_groups(eschema.get_groups(action)):
                    if eschema.has_local_role(action):
                        # have to ckeck local roles
                        need_local_check.append(eschema)
                        continue
                    else:
                        # even a local role won't be enough
                        return 0
                score += 1
            if need_local_check:
                # check local role for entities of necessary types
                for i, row in enumerate(rset):
                    if not rset.description[i][col] in need_local_check:
                        continue
                    # micro-optimisation instead of calling self.score(req,
                    # rset, i, col): rset may be large
                    if not rset.get_entity(i, col).cw_has_perm(action):
                        return 0
                score += 1
            return score
        return self.score(req, rset, row, col)

    def score_entity(self, entity):
        if entity.cw_has_perm(self.action):
            return 1
        return 0


class has_add_permission(EClassSelector):
    """Return 1 if request's user has the add permission on entity type
    specified in the `etype` initializer argument, or according to entity found
    in the input content if not specified.

    It also check that then entity type is not a strict subobject (e.g. may only
    be used as a composed of another entity).

    See :class:`~cubicweb.selectors.EClassSelector` documentation for entity
    class lookup / score rules according to the input context when `etype` is
    not specified.
    """
    def __init__(self, etype=None, **kwargs):
        super(has_add_permission, self).__init__(**kwargs)
        self.etype = etype

    @lltrace
    def __call__(self, cls, req, **kwargs):
        if self.etype is None:
            return super(has_add_permission, self).__call__(cls, req, **kwargs)
        return self.score(cls, req, self.etype)

    def score_class(self, eclass, req):
        eschema = eclass.e_schema
        if eschema.final or eschema.is_subobject(strict=True) \
               or not eschema.has_perm(req, 'add'):
            return 0
        return 1


class rql_condition(EntitySelector):
    """Return non-zero score if arbitrary rql specified in `expression`
    initializer argument return some results for entity found in the input
    context. Returned score is the number of items returned by the rql
    condition.

    `expression` is expected to be a string containing an rql expression, which
    must use 'X' variable to represent the context entity and may use 'U' to
    represent the request's user.

    See :class:`~cubicweb.selectors.EntitySelector` documentation for entity
    lookup / score rules according to the input context.
    """
    def __init__(self, expression, once_is_enough=False):
        super(rql_condition, self).__init__(once_is_enough)
        if 'U' in frozenset(split_expression(expression)):
            rql = 'Any COUNT(X) WHERE X eid %%(x)s, U eid %%(u)s, %s' % expression
        else:
            rql = 'Any COUNT(X) WHERE X eid %%(x)s, %s' % expression
        self.rql = rql

    def __repr__(self):
        return u'<rql_condition "%s" at %x>' % (self.rql, id(self))

    def score(self, req, rset, row, col):
        try:
            return req.execute(self.rql, {'x': rset[row][col],
                                          'u': req.user.eid})[0][0]
        except Unauthorized:
            return 0


class is_in_state(score_entity):
    """return 1 if entity is in one of the states given as argument list

    you should use this instead of your own :class:`score_entity` selector to
    avoid some gotchas:

    * possible views gives a fake entity with no state
    * you must use the latest tr info, not entity.in_state for repository side
      checking of the current state
    """
    def __init__(self, *states):
        def score(entity, states=set(states)):
            trinfo = entity.cw_adapt_to('IWorkflowable').latest_trinfo()
            try:
                return trinfo.new_state.name in states
            except AttributeError:
                return None
        super(is_in_state, self).__init__(score)


# logged user selectors ########################################################

@objectify_selector
@lltrace
def no_cnx(cls, req, **kwargs):
    """Return 1 if the web session has no connection set. This occurs when
    anonymous access is not allowed and user isn't authenticated.

    May only be used on the web side, not on the data repository side.
    """
    if not req.cnx:
        return 1
    return 0

@objectify_selector
@lltrace
def authenticated_user(cls, req, **kwargs):
    """Return 1 if the user is authenticated (e.g. not the anonymous user).

    May only be used on the web side, not on the data repository side.
    """
    if req.session.anonymous_session:
        return 0
    return 1


# XXX == ~ authenticated_user()
def anonymous_user():
    """Return 1 if the user is not authenticated (e.g. is the anonymous user).

    May only be used on the web side, not on the data repository side.
    """
    return ~ authenticated_user()

class match_user_groups(ExpectedValueSelector):
    """Return a non-zero score if request's user is in at least one of the
    groups given as initializer argument. Returned score is the number of groups
    in which the user is.

    If the special 'owners' group is given and `rset` is specified in the input
    context:

    * if `row` is specified check the entity at the given `row`/`col` (default
      to 0) is owned by the user

    * else check all entities in `col` (default to 0) are owned by the user
    """

    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        user = req.user
        if user is None:
            return int('guests' in self.expected)
        score = user.matching_groups(self.expected)
        if not score and 'owners' in self.expected and rset:
            if row is not None:
                if not user.owns(rset[row][col]):
                    return 0
                score = 1
            else:
                score = all(user.owns(r[col]) for r in rset)
        return score

# Web request selectors ########################################################

# XXX deprecate
@objectify_selector
@lltrace
def primary_view(cls, req, view=None, **kwargs):
    """Return 1 if:

    * *no view is specified* in the input context

    * a view is specified and its `.is_primary()` method return True

    This selector is usually used by contextual components that only want to
    appears for the primary view of an entity.
    """
    if view is not None and not view.is_primary():
        return 0
    return 1


@objectify_selector
@lltrace
def contextual(cls, req, view=None, **kwargs):
    """Return 1 if view's contextual property is true"""
    if view is not None and view.contextual:
        return 1
    return 0


class match_view(ExpectedValueSelector):
    """Return 1 if a view is specified an as its registry id is in one of the
    expected view id given to the initializer.
    """
    @lltrace
    def __call__(self, cls, req, view=None, **kwargs):
        if view is None or not view.__regid__ in self.expected:
            return 0
        return 1


class match_context(ExpectedValueSelector):

    @lltrace
    def __call__(self, cls, req, context=None, **kwargs):
        try:
            if not context in self.expected:
                return 0
        except AttributeError:
            return 1 # class doesn't care about search state, accept it
        return 1


# XXX deprecate
@objectify_selector
@lltrace
def match_context_prop(cls, req, context=None, **kwargs):
    """Return 1 if:

    * no `context` is specified in input context (take care to confusion, here
      `context` refers to a string given as an argument to the input context...)

    * specified `context` is matching the context property value for the
      appobject using this selector

    * the appobject's context property value is None

    This selector is usually used by contextual components that want to appears
    in a configurable place.
    """
    if context is None:
        return 1
    propval = req.property_value('%s.%s.context' % (cls.__registry__,
                                                    cls.__regid__))
    if propval and context != propval:
        return 0
    return 1


class match_search_state(ExpectedValueSelector):
    """Return 1 if the current request search state is in one of the expected
    states given to the initializer.

    Known search states are either 'normal' or 'linksearch' (eg searching for an
    object to create a relation with another).

    This selector is usually used by action that want to appears or not according
    to the ui search state.
    """

    @lltrace
    def __call__(self, cls, req, **kwargs):
        try:
            if not req.search_state[0] in self.expected:
                return 0
        except AttributeError:
            return 1 # class doesn't care about search state, accept it
        return 1


class match_form_params(ExpectedValueSelector):
    """Return non-zero score if parameter names specified as initializer
    arguments are specified in request's form parameters. When multiple
    parameters are specified, all of them should be found in req.form. Return a
    score corresponding to the number of expected parameters.
    """

    @lltrace
    def __call__(self, cls, req, **kwargs):
        for param in self.expected:
            if not param in req.form:
                return 0
        return len(self.expected)


class specified_etype_implements(is_instance):
    """Return non-zero score if the entity type specified by an 'etype' key
    searched in (by priority) input context kwargs and request form parameters
    match a known entity type (case insensitivly), and it's associated entity
    class is of one of the type(s) given to the initializer. If multiple
    arguments are given, matching one of them is enough.

    .. note:: as with :class:`~cubicweb.selectors.is_instance`, entity types
              should be given as string and the score will reflect class
              proximity so the most specific object will be selected.

    This selector is usually used by views holding entity creation forms (since
    we've no result set to work on).
    """

    @lltrace
    def __call__(self, cls, req, **kwargs):
        try:
            etype = kwargs['etype']
        except KeyError:
            try:
                etype = req.form['etype']
            except KeyError:
                return 0
            else:
                # only check this is a known type if etype comes from req.form,
                # else we want the error to propagate
                try:
                    etype = req.vreg.case_insensitive_etypes[etype.lower()]
                    req.form['etype'] = etype
                except KeyError:
                    return 0
        score = self.score_class(req.vreg['etypes'].etype_class(etype), req)
        if score:
            eschema = req.vreg.schema.eschema(etype)
            if eschema.has_local_role('add') or eschema.has_perm(req, 'add'):
                return score
        return 0


class attribute_edited(EntitySelector):
    """Scores if the specified attribute has been edited This is useful for
    selection of forms by the edit controller.

    The initial use case is on a form, in conjunction with match_transition,
    which will not score at edit time::

     is_instance('Version') & (match_transition('ready') |
                               attribute_edited('publication_date'))
    """
    def __init__(self, attribute, once_is_enough=False):
        super(attribute_edited, self).__init__(once_is_enough)
        self._attribute = attribute

    def score_entity(self, entity):
        return eid_param(role_name(self._attribute, 'subject'), entity.eid) in entity._cw.form


# Other selectors ##############################################################


class match_transition(ExpectedValueSelector):
    """Return 1 if `transition` argument is found in the input context which has
    a `.name` attribute matching one of the expected names given to the
    initializer.
    """
    @lltrace
    def __call__(self, cls, req, transition=None, **kwargs):
        # XXX check this is a transition that apply to the object?
        if transition is not None and getattr(transition, 'name', None) in self.expected:
            return 1
        return 0


class match_exception(ExpectedValueSelector):
    """Return 1 if a view is specified an as its registry id is in one of the
    expected view id given to the initializer.
    """
    def __init__(self, *expected):
        assert expected, self
        self.expected = expected

    @lltrace
    def __call__(self, cls, req, exc=None, **kwargs):
        if exc is not None and isinstance(exc, self.expected):
            return 1
        return 0


@objectify_selector
def debug_mode(cls, req, rset=None, **kwargs):
    """Return 1 if running in debug mode."""
    return req.vreg.config.debugmode and 1 or 0

## deprecated stuff ############################################################

entity_implements = class_renamed('entity_implements', is_instance)

class _but_etype(EntitySelector):
    """accept if the given entity types are not found in the result set.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param *etypes: entity types (`basestring`) which should be refused
    """
    def __init__(self, *etypes):
        super(_but_etype, self).__init__()
        self.but_etypes = etypes

    def score(self, req, rset, row, col):
        if rset.description[row][col] in self.but_etypes:
            return 0
        return 1

but_etype = class_renamed('but_etype', _but_etype, 'use ~is_instance(*etypes) instead')


# XXX deprecated the one_* variants of selectors below w/ multi_xxx(nb=1)?
#     take care at the implementation though (looking for the 'row' argument's
#     value)
two_lines_rset = class_renamed('two_lines_rset', multi_lines_rset)
two_cols_rset = class_renamed('two_cols_rset', multi_columns_rset)
two_etypes_rset = class_renamed('two_etypes_rset', multi_etypes_rset)
