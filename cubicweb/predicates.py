# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Predicate classes
"""



import logging
from warnings import warn
from operator import eq

from six import string_types, integer_types
from six.moves import range

from logilab.common.deprecation import deprecated
from logilab.common.registry import Predicate, objectify_predicate, yes

from yams.schema import BASE_TYPES, role_name
from rql.nodes import Function

from cubicweb import (Unauthorized, NoSelectableObject, NotAnEntity,
                      CW_EVENT_MANAGER, role)
from cubicweb.uilib import eid_param
from cubicweb.schema import split_expression

yes = deprecated('[3.15] import yes() from use logilab.common.registry')(yes)


# abstract predicates / mixin helpers ###########################################

class PartialPredicateMixIn(object):
    """convenience mix-in for predicates that will look into the containing
    class to find missing information.

    cf. `cubicweb.web.action.LinkToEntityAction` for instance
    """
    def __call__(self, cls, *args, **kwargs):
        self.complete(cls)
        return super(PartialPredicateMixIn, self).__call__(cls, *args, **kwargs)


class EClassPredicate(Predicate):
    """abstract class for predicates working on *entity class(es)* specified
    explicitly or found of the result set.

    Here are entity lookup / scoring rules:

    * if `entity` is specified, return score for this entity's class

    * elif `rset`, `select` and `filtered_variable` are specified, return score
      for the possible classes for variable in the given rql :class:`Select`
      node

    * elif `rset` and `row` are specified, return score for the class of the
      entity found in the specified cell, using column specified by `col` or 0

    * elif `rset` is specified return score for each entity class found in the
      column specified specified by the `col` argument or in column 0 if not
      specified

    When there are several classes to be evaluated, return the sum of scores for
    each entity class unless:

      - `mode` == 'all' (the default) and some entity class is scored
        to 0, in which case 0 is returned

      - `mode` == 'any', in which case the first non-zero score is
        returned

      - `accept_none` is False and some cell in the column has a None value
        (this may occurs with outer join)
    """
    def __init__(self, once_is_enough=None, accept_none=True, mode='all'):
        if once_is_enough is not None:
            warn("[3.14] once_is_enough is deprecated, use mode='any'",
                 DeprecationWarning, stacklevel=2)
            if once_is_enough:
                mode = 'any'
        assert mode in ('any', 'all'), 'bad mode %s' % mode
        self.once_is_enough = mode == 'any'
        self.accept_none = accept_none

    def __call__(self, cls, req, rset=None, row=None, col=0, entity=None,
                 select=None, filtered_variable=None,
                 accept_none=None,
                 **kwargs):
        if entity is not None:
            return self.score_class(entity.__class__, req)
        if not rset:
            return 0
        if select is not None and filtered_variable is not None:
            etypes = set(sol[filtered_variable.name] for sol in select.solutions)
        elif row is None:
            if accept_none is None:
                accept_none = self.accept_none
            if not accept_none and \
                   any(row[col] is None for row in rset):
                return 0
            etypes = rset.column_types(col)
        else:
            etype = rset.description[row][col]
            # may have None in rset.description on outer join
            if etype is None or rset.rows[row][col] is None:
                return 0
            etypes = (etype,)
        score = 0
        for etype in etypes:
            escore = self.score(cls, req, etype)
            if not escore and not self.once_is_enough:
                return 0
            elif self.once_is_enough:
                return escore
            score += escore
        return score

    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return self.score_class(req.vreg['etypes'].etype_class(etype), req)

    def score_class(self, eclass, req):
        raise NotImplementedError()


class EntityPredicate(EClassPredicate):
    """abstract class for predicates working on *entity instance(s)* specified
    explicitly or found of the result set.

    Here are entity lookup / scoring rules:

    * if `entity` is specified, return score for this entity

    * elif `row` is specified, return score for the entity found in the
      specified cell, using column specified by `col` or 0

    * else return the sum of scores for each entity found in the column
      specified specified by the `col` argument or in column 0 if not specified,
      unless:

      - `mode` == 'all' (the default) and some entity class is scored
        to 0, in which case 0 is returned

      - `mode` == 'any', in which case the first non-zero score is
        returned

      - `accept_none` is False and some cell in the column has a None value
        (this may occurs with outer join)

    .. Note::
       using :class:`EntityPredicate` or :class:`EClassPredicate` as base predicate
       class impacts performance, since when no entity or row is specified the
       later works on every different *entity class* found in the result set,
       while the former works on each *entity* (eg each row of the result set),
       which may be much more costly.
    """

    def __call__(self, cls, req, rset=None, row=None, col=0, accept_none=None,
                 entity=None, **kwargs):
        if not rset and entity is None:
            return 0
        score = 0
        if entity is not None:
            score = self.score_entity(entity)
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


class ExpectedValuePredicate(Predicate):
    """Take a list of expected values as initializer argument and store them
    into the :attr:`expected` set attribute. You may also give a set as single
    argument, which will then be referenced as set of expected values,
    allowing modifications to the given set to be considered.

    You should implement one of :meth:`_values_set(cls, req, **kwargs)` or
    :meth:`_get_value(cls, req, **kwargs)` method which should respectively
    return the set of values or the unique possible value for the given context.

    You may also specify a `mode` behaviour as argument, as explained below.

    Returned score is:

    - 0 if `mode` == 'all' (the default) and at least one expected
      values isn't found

    - 0 if `mode` == 'any' and no expected values isn't found at all

    - else the number of matching values

    Notice `mode` = 'any' with a single expected value has no effect at all.
    """
    def __init__(self, *expected, **kwargs):
        assert expected, self
        if len(expected) == 1 and isinstance(expected[0], (set, dict)):
            self.expected = expected[0]
        else:
            self.expected = frozenset(expected)
        mode = kwargs.pop('mode', 'all')
        assert mode in ('any', 'all'), 'bad mode %s' % mode
        self.once_is_enough = mode == 'any'
        assert not kwargs, 'unexpected arguments %s' % kwargs

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(sorted(str(s) for s in self.expected)))

    def __call__(self, cls, req, **kwargs):
        values = self._values_set(cls, req, **kwargs)
        if isinstance(values, dict):
            if isinstance(self.expected, dict):
                matching = 0
                for key, expected_value in self.expected.items():
                    if key in values:
                        if (isinstance(expected_value, (list, tuple, frozenset, set))
                            and values[key] in expected_value):
                            matching += 1
                        elif values[key] == expected_value:
                            matching += 1
            if isinstance(self.expected, (set, frozenset)):
                values = frozenset(values)
                matching = len(values & self.expected)
        else:
            matching = len(values & self.expected)
        if self.once_is_enough:
            return matching
        if matching == len(self.expected):
            return matching
        return 0

    def _values_set(self, cls, req, **kwargs):
        return frozenset( (self._get_value(cls, req, **kwargs),) )

    def _get_value(self, cls, req, **kwargs):
        raise NotImplementedError()


# bare predicates ##############################################################

class match_kwargs(ExpectedValuePredicate):
    """Return non-zero score if parameter names specified as initializer
    arguments are specified in the input context.


    Return a score corresponding to the number of expected parameters.

    When multiple parameters are expected, all of them should be found in
    the input context unless `mode` keyword argument is given to 'any',
    in which case a single matching parameter is enough.
    """

    def _values_set(self, cls, req, **kwargs):
        return kwargs


class appobject_selectable(Predicate):
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

    def __call__(self, cls, req, **kwargs):
        for regid in self.regids:
            if req.vreg[self.registry].select_or_none(regid, req, **kwargs) is not None:
                return self.selectable_score
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
        score = super(adaptable, self).__call__(cls, req, **kwargs)
        if score == 0 and kwargs.get('rset') and len(kwargs['rset']) > 1 and not 'row' in kwargs:
            # on rset containing several entity types, each row may be
            # individually adaptable, while the whole rset won't be if the
            # same adapter can't be used for each type
            for row in range(len(kwargs['rset'])):
                kwargs.setdefault('col', 0)
                _score = super(adaptable, self).__call__(cls, req, row=row, **kwargs)
                if not _score:
                    return 0
                # adjust score per row as expected by default adjust_score
                # implementation
                score += self.adjust_score(_score)
        else:
            score = self.adjust_score(score)
        return score

    @staticmethod
    def adjust_score(score):
        # being adaptable to an interface should takes precedence other
        # is_instance('Any'), but not other explicit
        # is_instance('SomeEntityType'), and, for **a single entity**:
        # * is_instance('Any') score is 1
        # * is_instance('SomeEntityType') score is at least 2
        if score >= 2:
            return score - 0.5
        if score == 1:
            return score + 0.5
        return score


class configuration_values(Predicate):
    """Return 1 if the instance has an option set to a given value(s) in its
    configuration file.
    """
    # XXX this predicate could be evaluated on startup
    def __init__(self, key, values):
        self._key = key
        if not isinstance(values, (tuple, list)):
            values = (values,)
        self._values = frozenset(values)

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


# rset predicates ##############################################################

@objectify_predicate
def none_rset(cls, req, rset=None, **kwargs):
    """Return 1 if the result set is None (eg usually not specified)."""
    if rset is None:
        return 1
    return 0


# XXX == ~ none_rset
@objectify_predicate
def any_rset(cls, req, rset=None, **kwargs):
    """Return 1 for any result set, whatever the number of rows in it, even 0."""
    if rset is not None:
        return 1
    return 0


@objectify_predicate
def nonempty_rset(cls, req, rset=None, **kwargs):
    """Return 1 for result set containing one ore more rows."""
    if rset:
        return 1
    return 0


# XXX == ~ nonempty_rset
@objectify_predicate
def empty_rset(cls, req, rset=None, **kwargs):
    """Return 1 for result set which doesn't contain any row."""
    if rset is not None and len(rset) == 0:
        return 1
    return 0


# XXX == multi_lines_rset(1)
@objectify_predicate
def one_line_rset(cls, req, rset=None, row=None, **kwargs):
    """Return 1 if the result set is of size 1, or greater but a specific row in
      the result set is specified ('row' argument).
    """
    if rset is None and 'entity' in kwargs:
        return 1
    if rset is not None and (row is not None or len(rset) == 1):
        return 1
    return 0


class multi_lines_rset(Predicate):
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

    def __call__(self, cls, req, rset=None, **kwargs):
        return int(rset is not None and self.match_expected(len(rset)))


class multi_columns_rset(multi_lines_rset):
    """If `nb` is specified, return 1 if the result set has exactly `nb` column
    per row. Else (`nb` is None), return 1 if the result set contains *at least*
    two columns per row. Return 0 for empty result set.
    """

    def __call__(self, cls, req, rset=None, **kwargs):
        # 'or 0' since we *must not* return None. Also don't use rset.rows so
        # this selector will work if rset is a simple list of list.
        return rset and self.match_expected(len(rset[0])) or 0


class paginated_rset(Predicate):
    """Return 1 or more for result set with more rows than one or more page
    size.  You can specify expected number of pages to the initializer (default
    to one), and you'll get that number of pages as score if the result set is
    big enough.

    Page size is searched in (respecting order):
    * a `page_size` argument
    * a `page_size` form parameters
    * the `navigation.page-size` property (see :ref:`PersistentProperties`)
    """
    def __init__(self, nbpages=1):
        assert nbpages > 0
        self.nbpages = nbpages

    def __call__(self, cls, req, rset=None, **kwargs):
        if rset is None:
            return 0
        page_size = kwargs.get('page_size')
        if page_size is None:
            page_size = req.form.get('page_size')
            if page_size is not None:
                try:
                    page_size = int(page_size)
                except ValueError:
                    page_size = None
            if page_size is None:
                page_size_prop = getattr(cls, 'page_size_property', 'navigation.page-size')
                page_size = req.property_value(page_size_prop)
        if len(rset) <= (page_size*self.nbpages):
            return 0
        return self.nbpages


@objectify_predicate
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
@objectify_predicate
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

    def __call__(self, cls, req, rset=None, col=0, **kwargs):
        # 'or 0' since we *must not* return None
        return rset and self.match_expected(len(rset.column_types(col))) or 0


@objectify_predicate
def logged_user_in_rset(cls, req, rset=None, row=None, col=0, **kwargs):
    """Return positive score if the result set at the specified row / col
    contains the eid of the logged user.
    """
    if rset is None:
        return 0
    return req.user.eid == rset[row or 0][col]


# entity predicates #############################################################

class composite_etype(Predicate):
    """Return 1 for composite entities.

    A composite entity has an etype for which at least one relation
    definition points in its direction with the
    composite='subject'/'object' notation.
    """

    def __call__(self, cls, req, **kwargs):
        entity = kwargs.pop('entity', None)
        if entity is None:
            return 0
        return entity.e_schema.is_composite



class non_final_entity(EClassPredicate):
    """Return 1 for entity of a non final entity type(s). Remember, "final"
    entity types are String, Int, etc... This is equivalent to
    `is_instance('Any')` but more optimized.

    See :class:`~cubicweb.predicates.EClassPredicate` documentation for entity
    class lookup / score rules according to the input context.
    """
    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return 1

    def score_class(self, eclass, req):
        return 1 # necessarily true if we're there



def _reset_is_instance_cache(vreg):
    vreg._is_instance_predicate_cache = {}

CW_EVENT_MANAGER.bind('before-registry-reset', _reset_is_instance_cache)

class is_instance(EClassPredicate):
    """Return non-zero score for entity that is an instance of the one of given
    type(s). If multiple arguments are given, matching one of them is enough.

    Entity types should be given as string, the corresponding class will be
    fetched from the registry at selection time.

    See :class:`~cubicweb.predicates.EClassPredicate` documentation for entity
    class lookup / score rules according to the input context.

    .. note:: the score will reflect class proximity so the most specific object
              will be selected.
    """

    def __init__(self, *expected_etypes, **kwargs):
        super(is_instance, self).__init__(**kwargs)
        self.expected_etypes = expected_etypes
        for etype in self.expected_etypes:
            assert isinstance(etype, string_types), etype

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.expected_etypes))

    def score_class(self, eclass, req):
        # cache on vreg to avoid reloading issues
        try:
            cache = req.vreg._is_instance_predicate_cache
        except AttributeError:
            # XXX 'before-registry-reset' not called for db-api connections
            cache = req.vreg._is_instance_predicate_cache = {}
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


class score_entity(EntityPredicate):
    """Return score according to an arbitrary function given as argument which
    will be called with input content entity as argument.

    This is a very useful predicate that will usually interest you since it
    allows a lot of things without having to write a specific predicate.

    The function can return arbitrary value which will be casted to an integer
    value at the end.

    See :class:`~cubicweb.predicates.EntityPredicate` documentation for entity
    lookup / score rules according to the input context.
    """
    def __init__(self, scorefunc, once_is_enough=None, mode='all'):
        super(score_entity, self).__init__(mode=mode, once_is_enough=once_is_enough)
        def intscore(*args, **kwargs):
            score = scorefunc(*args, **kwargs)
            if not score:
                return 0
            if isinstance(score, integer_types):
                return score
            return 1
        self.score_entity = intscore


class has_mimetype(EntityPredicate):
    """Return 1 if the entity adapt to IDownloadable and has the given MIME type.

    You can give 'image/' to match any image for instance, or 'image/png' to match
    only PNG images.
    """
    def __init__(self, mimetype, once_is_enough=None, mode='all'):
        super(has_mimetype, self).__init__(mode=mode, once_is_enough=once_is_enough)
        self.mimetype = mimetype

    def score_entity(self, entity):
        idownloadable = entity.cw_adapt_to('IDownloadable')
        if idownloadable is None:
            return 0
        mt = idownloadable.download_content_type()
        if not (mt and mt.startswith(self.mimetype)):
            return 0
        return 1


class relation_possible(EntityPredicate):
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
    you'll then get the :class:`~cubicweb.predicates.EntityPredicate` behaviour
    while otherwise you get the :class:`~cubicweb.predicates.EClassPredicate`'s
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
        # hack hack hack
        if self.strict:
            return EntityPredicate.__call__(self, cls, req, **kwargs)
        return EClassPredicate.__call__(self, cls, req, **kwargs)

    def score(self, *args):
        if self.strict:
            return EntityPredicate.score(self, *args)
        return EClassPredicate.score(self, *args)

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
                try:
                    rschema = rschema.role_rdef(entity.e_schema,
                                                self.target_etype, self.role)
                except KeyError:
                    return 0
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


class partial_relation_possible(PartialPredicateMixIn, relation_possible):
    """Same as :class:~`cubicweb.predicates.relation_possible`, but will look for
    attributes of the selected class to get information which is otherwise
    expected by the initializer, except for `action` and `strict` which are kept
    as initializer arguments.

    This is useful to predefine predicate of an abstract class designed to be
    customized.
    """
    def __init__(self, action='read', **kwargs):
        super(partial_relation_possible, self).__init__(None, None, None,
                                                        action, **kwargs)

    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)
        self.target_etype = getattr(cls, 'target_etype', None)


class has_related_entities(EntityPredicate):
    """Return 1 if entity support the specified relation and has some linked
    entities by this relation , optionally filtered according to the specified
    target type.

    The relation is specified by the following initializer arguments:

    * `rtype`, the name of the relation

    * `role`, the role of the entity in the relation, either 'subject' or
      'object', default to 'subject'.

    * `target_etype`, optional name of an entity type that should be found
      at the other end of the relation

    See :class:`~cubicweb.predicates.EntityPredicate` documentation for entity
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


class partial_has_related_entities(PartialPredicateMixIn, has_related_entities):
    """Same as :class:~`cubicweb.predicates.has_related_entities`, but will look
    for attributes of the selected class to get information which is otherwise
    expected by the initializer.

    This is useful to predefine predicate of an abstract class designed to be
    customized.
    """
    def __init__(self, **kwargs):
        super(partial_has_related_entities, self).__init__(None, None, None,
                                                           **kwargs)

    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)
        self.target_etype = getattr(cls, 'target_etype', None)


class has_permission(EntityPredicate):
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

    # don't use EntityPredicate.__call__ but this optimized implementation to
    # avoid considering each entity when it's not necessary
    def __call__(self, cls, req, rset=None, row=None, col=0, entity=None, **kwargs):
        if entity is not None:
            return self.score_entity(entity)
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


class has_add_permission(EClassPredicate):
    """Return 1 if request's user has the add permission on entity type
    specified in the `etype` initializer argument, or according to entity found
    in the input content if not specified.

    It also check that then entity type is not a strict subobject (e.g. may only
    be used as a composed of another entity).

    See :class:`~cubicweb.predicates.EClassPredicate` documentation for entity
    class lookup / score rules according to the input context when `etype` is
    not specified.
    """
    def __init__(self, etype=None, **kwargs):
        super(has_add_permission, self).__init__(**kwargs)
        self.etype = etype

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


class rql_condition(EntityPredicate):
    """Return non-zero score if arbitrary rql specified in `expression`
    initializer argument return some results for entity found in the input
    context. Returned score is the number of items returned by the rql
    condition.

    `expression` is expected to be a string containing an rql expression, which
    must use 'X' variable to represent the context entity and may use 'U' to
    represent the request's user.

    .. warning::
        If simply testing value of some attribute/relation of context entity (X),
        you should rather use the :class:`score_entity` predicate which will
        benefit from the ORM's request entities cache.

    See :class:`~cubicweb.predicates.EntityPredicate` documentation for entity
    lookup / score rules according to the input context.
    """
    def __init__(self, expression, once_is_enough=None, mode='all', user_condition=False):
        super(rql_condition, self).__init__(mode=mode, once_is_enough=once_is_enough)
        self.user_condition = user_condition
        if user_condition:
            rql = 'Any COUNT(U) WHERE U eid %%(u)s, %s' % expression
        elif 'U' in frozenset(split_expression(expression)):
            rql = 'Any COUNT(X) WHERE X eid %%(x)s, U eid %%(u)s, %s' % expression
        else:
            rql = 'Any COUNT(X) WHERE X eid %%(x)s, %s' % expression
        self.rql = rql

    def __str__(self):
        return '%s(%r)' % (self.__class__.__name__, self.rql)

    def __call__(self, cls, req, **kwargs):
        if self.user_condition:
            try:
                return req.execute(self.rql, {'u': req.user.eid})[0][0]
            except Unauthorized:
                return 0
        else:
            return super(rql_condition, self).__call__(cls, req, **kwargs)

    def _score(self, req, eid):
        try:
            return req.execute(self.rql, {'x': eid, 'u': req.user.eid})[0][0]
        except Unauthorized:
            return 0

    def score(self, req, rset, row, col):
        return self._score(req, rset[row][col])

    def score_entity(self, entity):
        return self._score(entity._cw, entity.eid)


# workflow predicates ###########################################################

class is_in_state(score_entity):
    """Return 1 if entity is in one of the states given as argument list

    You should use this instead of your own :class:`score_entity` predicate to
    avoid some gotchas:

    * possible views gives a fake entity with no state
    * you must use the latest tr info thru the workflow adapter for repository
      side checking of the current state

    In debug mode, this predicate can raise :exc:`ValueError` for unknown states names
    (only checked on entities without a custom workflow)

    :rtype: int
    """
    def __init__(self, *expected):
        assert expected, self
        self.expected = frozenset(expected)
        def score(entity, expected=self.expected):
            adapted = entity.cw_adapt_to('IWorkflowable')
            # in debug mode only (time consuming)
            if entity._cw.vreg.config.debugmode:
                # validation can only be done for generic etype workflow because
                # expected transition list could have been changed for a custom
                # workflow (for the current entity)
                if not entity.custom_workflow:
                    self._validate(adapted)
            return self._score(adapted)
        super(is_in_state, self).__init__(score)

    def _score(self, adapted):
        trinfo = adapted.latest_trinfo()
        if trinfo is None: # entity is probably in it's initial state
            statename = adapted.state
        else:
            statename = trinfo.new_state.name
        return statename in self.expected

    def _validate(self, adapted):
        wf = adapted.current_workflow
        valid = [n.name for n in wf.reverse_state_of]
        unknown = sorted(self.expected.difference(valid))
        if unknown:
            raise ValueError("%s: unknown state(s): %s"
                             % (wf.name, ",".join(unknown)))

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.expected))


def on_fire_transition(etype, tr_names, from_state_name=None):
    """Return 1 when entity of the type `etype` is going through transition of
    a name included in `tr_names`.

    You should use this predicate on 'after_add_entity' hook, since it's actually
    looking for addition of `TrInfo` entities. Hence in the hook, `self.entity`
    will reference the matching `TrInfo` entity, allowing to get all the
    transition details (including the entity to which is applied the transition
    but also its original state, transition, destination state, user...).

    See :class:`cubicweb.entities.wfobjs.TrInfo` for more information.
    """
    if from_state_name is not None:
        warn("on_fire_transition's from_state_name argument is unused", DeprecationWarning)
    if isinstance(tr_names, string_types):
        tr_names = set((tr_names,))
    def match_etype_and_transition(trinfo):
        # take care trinfo.transition is None when calling change_state
        return (trinfo.transition and trinfo.transition.name in tr_names
                # is_instance() first two arguments are 'cls' (unused, so giving
                # None is fine) and the request/session
                and is_instance(etype)(None, trinfo._cw, entity=trinfo.for_entity))

    return is_instance('TrInfo') & score_entity(match_etype_and_transition)


class match_transition(ExpectedValuePredicate):
    """Return 1 if `transition` argument is found in the input context which has
    a `.name` attribute matching one of the expected names given to the
    initializer.

    This predicate is expected to be used to customise the status change form in
    the web ui.
    """
    def __call__(self, cls, req, transition=None, **kwargs):
        # XXX check this is a transition that apply to the object?
        if transition is None:
            treid = req.form.get('treid', None)
            if treid:
                transition = req.entity_from_eid(treid)
        if transition is not None and getattr(transition, 'name', None) in self.expected:
            return 1
        return 0


# logged user predicates ########################################################

@objectify_predicate
def no_cnx(cls, req, **kwargs):
    """Return 1 if the web session has no connection set. This occurs when
    anonymous access is not allowed and user isn't authenticated.
    """
    if not req.cnx:
        return 1
    return 0


@objectify_predicate
def authenticated_user(cls, req, **kwargs):
    """Return 1 if the user is authenticated (i.e. not the anonymous user).
    """
    if req.session.anonymous_session:
        return 0
    return 1


@objectify_predicate
def anonymous_user(cls, req, **kwargs):
    """Return 1 if the user is not authenticated (i.e. is the anonymous user).
    """
    if req.session.anonymous_session:
        return 1
    return 0


class match_user_groups(ExpectedValuePredicate):
    """Return a non-zero score if request's user is in at least one of the
    groups given as initializer argument. Returned score is the number of groups
    in which the user is.

    If the special 'owners' group is given and `rset` is specified in the input
    context:

    * if `row` is specified check the entity at the given `row`/`col` (default
      to 0) is owned by the user

    * else check all entities in `col` (default to 0) are owned by the user
    """

    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        if not getattr(req, 'cnx', True): # default to True for repo session instances
            return 0
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

# Web request predicates ########################################################

# XXX deprecate
@objectify_predicate
def primary_view(cls, req, view=None, **kwargs):
    """Return 1 if:

    * *no view is specified* in the input context

    * a view is specified and its `.is_primary()` method return True

    This predicate is usually used by contextual components that only want to
    appears for the primary view of an entity.
    """
    if view is not None and not view.is_primary():
        return 0
    return 1


@objectify_predicate
def contextual(cls, req, view=None, **kwargs):
    """Return 1 if view's contextual property is true"""
    if view is not None and view.contextual:
        return 1
    return 0


class match_view(ExpectedValuePredicate):
    """Return 1 if a view is specified an as its registry id is in one of the
    expected view id given to the initializer.
    """
    def __call__(self, cls, req, view=None, **kwargs):
        if view is None or not view.__regid__ in self.expected:
            return 0
        return 1


class match_context(ExpectedValuePredicate):

    def __call__(self, cls, req, context=None, **kwargs):
        if not context in self.expected:
            return 0
        return 1


# XXX deprecate
@objectify_predicate
def match_context_prop(cls, req, context=None, **kwargs):
    """Return 1 if:

    * no `context` is specified in input context (take care to confusion, here
      `context` refers to a string given as an argument to the input context...)

    * specified `context` is matching the context property value for the
      appobject using this predicate

    * the appobject's context property value is None

    This predicate is usually used by contextual components that want to appears
    in a configurable place.
    """
    if context is None:
        return 1
    propval = req.property_value('%s.%s.context' % (cls.__registry__,
                                                    cls.__regid__))
    if propval and context != propval:
        return 0
    return 1


class match_search_state(ExpectedValuePredicate):
    """Return 1 if the current request search state is in one of the expected
    states given to the initializer.

    Known search states are either 'normal' or 'linksearch' (eg searching for an
    object to create a relation with another).

    This predicate is usually used by action that want to appears or not according
    to the ui search state.
    """

    def __call__(self, cls, req, **kwargs):
        try:
            if not req.search_state[0] in self.expected:
                return 0
        except AttributeError:
            return 1 # class doesn't care about search state, accept it
        return 1


class match_form_params(ExpectedValuePredicate):
    """Return non-zero score if parameter names specified as initializer
    arguments are specified in request's form parameters.

    Return a score corresponding to the number of expected parameters.

    When multiple parameters are expected, all of them should be found in
    the input context unless `mode` keyword argument is given to 'any',
    in which case a single matching parameter is enough.
    """

    def __init__(self, *expected, **kwargs):
        """override default __init__ to allow either named or positional
        parameters.
        """
        if kwargs and expected:
            raise ValueError("match_form_params() can't be called with both "
                             "positional and named arguments")
        if expected:
            if len(expected) == 1 and not isinstance(expected[0], string_types):
                raise ValueError("match_form_params() positional arguments "
                                 "must be strings")
            super(match_form_params, self).__init__(*expected)
        else:
            super(match_form_params, self).__init__(kwargs)

    def _values_set(self, cls, req, **kwargs):
        return req.form


class match_http_method(ExpectedValuePredicate):
    """Return non-zero score if one of the HTTP methods specified as
    initializer arguments is the HTTP method of the request (GET, POST, ...).
    """

    def __call__(self, cls, req, **kwargs):
        return int(req.http_method() in self.expected)


class match_edited_type(ExpectedValuePredicate):
    """return non-zero if main edited entity type is the one specified as
    initializer argument, or is among initializer arguments if `mode` == 'any'.
    """

    def _values_set(self, cls, req, **kwargs):
        try:
            return frozenset((req.form['__type:%s' % req.form['__maineid']],))
        except KeyError:
            return frozenset()


class match_form_id(ExpectedValuePredicate):
    """return non-zero if request form identifier is the one specified as
    initializer argument, or is among initializer arguments if `mode` == 'any'.
    """

    def _values_set(self, cls, req, **kwargs):
        try:
            return frozenset((req.form['__form_id'],))
        except KeyError:
            return frozenset()


class specified_etype_implements(is_instance):
    """Return non-zero score if the entity type specified by an 'etype' key
    searched in (by priority) input context kwargs and request form parameters
    match a known entity type (case insensitivly), and it's associated entity
    class is of one of the type(s) given to the initializer. If multiple
    arguments are given, matching one of them is enough.

    .. note:: as with :class:`~cubicweb.predicates.is_instance`, entity types
              should be given as string and the score will reflect class
              proximity so the most specific object will be selected.

    This predicate is usually used by views holding entity creation forms (since
    we've no result set to work on).
    """

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
            if eschema.may_have_permission('add', req):
                return score
        return 0


class attribute_edited(EntityPredicate):
    """Scores if the specified attribute has been edited This is useful for
    selection of forms by the edit controller.

    The initial use case is on a form, in conjunction with match_transition,
    which will not score at edit time::

     is_instance('Version') & (match_transition('ready') |
                               attribute_edited('publication_date'))
    """
    def __init__(self, attribute, once_is_enough=None, mode='all'):
        super(attribute_edited, self).__init__(mode=mode, once_is_enough=once_is_enough)
        self._attribute = attribute

    def score_entity(self, entity):
        return eid_param(role_name(self._attribute, 'subject'), entity.eid) in entity._cw.form


# Other predicates ##############################################################

class match_exception(ExpectedValuePredicate):
    """Return 1 if exception given as `exc` in the input context is an instance
    of one of the class given on instanciation of this predicate.
    """
    def __init__(self, *expected):
        assert expected, self
        # we want a tuple, not a set as done in the parent class
        self.expected = expected

    def __call__(self, cls, req, exc=None, **kwargs):
        if exc is not None and isinstance(exc, self.expected):
            return 1
        return 0


@objectify_predicate
def debug_mode(cls, req, rset=None, **kwargs):
    """Return 1 if running in debug mode."""
    return req.vreg.config.debugmode and 1 or 0
