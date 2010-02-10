"""This file contains some basic selectors required by application objects.

A selector is responsible to score how well an object may be used with a
given context by returning a score.

In CubicWeb Usually the context consists for a request object, a result set
or None, a specific row/col in the result set, etc...


If you have trouble with selectors, especially if the objet (typically
a view or a component) you want to use is not selected and you want to
know which one(s) of its selectors fail (e.g. returns 0), you can use
`traced_selection` or even direclty `TRACED_OIDS`.

`TRACED_OIDS` is a tuple of traced object ids. The special value
'all' may be used to log selectors for all objects.

For instance, say that the following code yields a `NoSelectableObject`
exception::

    self.view('calendar', myrset)

You can log the selectors involved for *calendar* by replacing the line
above by::

    # in Python2.5
    from cubicweb.selectors import traced_selection
    with traced_selection():
        self.view('calendar', myrset)

    # in Python2.4
    from cubicweb import selectors
    selectors.TRACED_OIDS = ('calendar',)
    self.view('calendar', myrset)
    selectors.TRACED_OIDS = ()


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import logging
from warnings import warn, filterwarnings

from logilab.common.deprecation import class_renamed
from logilab.common.compat import all, any
from logilab.common.interface import implements as implements_iface

from yams import BASE_TYPES

from cubicweb import (Unauthorized, NoSelectableObject, NotAnEntity,
                      role, typed_eid)
# even if not used, let yes here so it's importable through this module
from cubicweb.appobject import Selector, objectify_selector, yes
from cubicweb.vregistry import class_regid
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.schema import split_expression

# helpers for debugging selectors
SELECTOR_LOGGER = logging.getLogger('cubicweb.selectors')
TRACED_OIDS = ()

def lltrace(selector):
    # don't wrap selectors if not in development mode
    if CubicWebConfiguration.mode == 'system': # XXX config.debug
        return selector
    def traced(cls, *args, **kwargs):
        # /!\ lltrace decorates pure function or __call__ method, this
        #     means argument order may be different
        if isinstance(cls, Selector):
            selname = str(cls)
            vobj = args[0]
        else:
            selname = selector.__name__
            vobj = cls
        oid = class_regid(vobj)
        ret = selector(cls, *args, **kwargs)
        if TRACED_OIDS == 'all' or oid in TRACED_OIDS:
            #SELECTOR_LOGGER.warning('selector %s returned %s for %s', selname, ret, cls)
            print '%s -> %s for %s(%s)' % (selname, ret, vobj, vobj.__regid__)
        return ret
    traced.__name__ = selector.__name__
    traced.__doc__ = selector.__doc__
    return traced

class traced_selection(object):
    """selector debugging helper.

    Typical usage is :

    >>> with traced_selection():
    ...     # some code in which you want to debug selectors
    ...     # for all objects

    or

    >>> with traced_selection( ('oid1', 'oid2') ):
    ...     # some code in which you want to debug selectors
    ...     # for objects with id 'oid1' and 'oid2'

    """
    def __init__(self, traced='all'):
        self.traced = traced

    def __enter__(self):
        global TRACED_OIDS
        TRACED_OIDS = self.traced

    def __exit__(self, exctype, exc, traceback):
        global TRACED_OIDS
        TRACED_OIDS = ()
        return traceback is None


def score_interface(etypesreg, cls_or_inst, cls, iface):
    """Return XXX if the give object (maybe an instance or class) implements
    the interface.
    """
    if getattr(iface, '__registry__', None) == 'etypes':
        # adjust score if the interface is an entity class
        parents = etypesreg.parent_classes(cls_or_inst.__regid__)
        if iface is cls:
            return len(parents) + 4
        if iface is parents[-1]: # Any
            return 1
        for index, basecls in enumerate(reversed(parents[:-1])):
            if iface is basecls:
                return index + 3
        return 0
    if implements_iface(cls_or_inst, iface):
        # implenting an interface takes precedence other special Any interface
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


class ImplementsMixIn(object):
    """mix-in class for selectors checking implemented interfaces of something
    """
    def __init__(self, *expected_ifaces, **kwargs):
        super(ImplementsMixIn, self).__init__(**kwargs)
        self.expected_ifaces = expected_ifaces

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.expected_ifaces))

    def score_interfaces(self, req, cls_or_inst, cls):
        score = 0
        etypesreg = req.vreg['etypes']
        eschema = cls_or_inst.e_schema
        for iface in self.expected_ifaces:
            if isinstance(iface, basestring):
                # entity type
                try:
                    iface = etypesreg.etype_class(iface)
                except KeyError:
                    continue # entity type not in the schema
            score += score_interface(etypesreg, cls_or_inst, cls, iface)
        return score


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
    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        if kwargs.get('entity'):
            return self.score_class(kwargs['entity'].__class__, req)
        if not rset:
            return 0
        score = 0
        if row is None:
            if not self.accept_none:
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

    .. note::
       using EntitySelector or EClassSelector as base selector class impacts
       performance, since when no entity or row is specified the later works on
       every different *entity class* found in the result set, while the former
       works on each *entity* (eg each row of the result set), which may be much
       more costly.
    """

    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        if not rset and not kwargs.get('entity'):
            return 0
        score = 0
        if kwargs.get('entity'):
            score = self.score_entity(kwargs['entity'])
        elif row is None:
            col = col or 0
            for row, rowvalue in enumerate(rset.rows):
                if rowvalue[col] is None: # outer join
                    if not self.accept_none:
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
    """Take a list of expected values as initializer argument, check
    _get_value method return one of these expected values.
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
    """return 1 if another appobject is selectable using the same input context.

    Initializer arguments:
    * `registry`, a registry name
    * `regid`, an object identifier in this registry
    """
    def __init__(self, registry, regid):
        self.registry = registry
        self.regid = regid

    def __call__(self, cls, req, **kwargs):
        try:
            req.vreg[self.registry].select(self.regid, req, **kwargs)
            return 1
        except NoSelectableObject:
            return 0


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
    """Return 1 if the result set is of size 1 or if a specific row in the
    result set is specified ('row' argument).
    """
    if rset is not None and (row is not None or rset.rowcount == 1):
        return 1
    return 0


class multi_lines_rset(Selector):
    """If `nb`is specified, return 1 if the result set has exactly `nb` row of
    result. Else (`nb` is None), return 1 if the result set contains *at least*
    two rows.
    """
    def __init__(self, nb=None):
        self.expected = nb

    def match_expected(self, num):
        if self.expected is None:
            return num > 1
        return num == self.expected

    @lltrace
    def __call__(self, cls, req, rset=None, **kwargs):
        return rset is not None and self.match_expected(rset.rowcount)


class multi_columns_rset(multi_lines_rset):
    """If `nb`is specified, return 1 if the result set has exactly `nb` column
    per row. Else (`nb` is None), return 1 if the result set contains *at least*
    two columns per row. Return 0 for empty result set.
    """

    @lltrace
    def __call__(self, cls, req, rset=None, **kwargs):
        # 'or 0' since we *must not* return None
        return rset and self.match_expected(len(rset.rows[0])) or 0


@objectify_selector
@lltrace
def paginated_rset(cls, req, rset=None, **kwargs):
    """Return 1 for result set with more rows than a page size.

    Page size is searched in (respecting order):
    * a `page_size` argument
    * a `page_size` form parameters
    * the :ref:`navigation.page-size` property
    """
    if rset is None:
        return 0
    page_size = kwargs.get('page_size')
    if page_size is None:
        page_size = req.form.get('page_size')
        if page_size is None:
            page_size = req.property_value('navigation.page-size')
        else:
            page_size = int(page_size)
    if rset.rowcount <= page_size:
        return 0
    return 1


@objectify_selector
@lltrace
def sorted_rset(cls, req, rset=None, **kwargs):
    """Return 1 for sorted result set (e.g. from an RQL query containing an
    :ref:ORDERBY clause.
    """
    if rset is None:
        return 0
    rqlst = rset.syntax_tree()
    if len(rqlst.children) > 1 or not rqlst.children[0].orderby:
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


# entity selectors #############################################################

class non_final_entity(EClassSelector):
    """Return 1 for entity of a non final entity type(s). Remember, "final"
    entity types are String, Int, etc... This is equivalent to
    `implements('Any')` but more optimized.

    See :class:`~cubicweb.selectors.EClassSelector` documentation for entity
    class lookup / score rules according to the input context.
    """
    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return 1


class implements(ImplementsMixIn, EClassSelector):
    """Return non-zero score for entity that are of the given type(s) or
    implements at least one of the given interface(s). If multiple arguments are
    given, matching one of them is enough.

    Entity types should be given as string, the corresponding class will be
    fetched from the entity types registry at selection time.

    See :class:`~cubicweb.selectors.EClassSelector` documentation for entity
    class lookup / score rules according to the input context.

    .. note:: when interface is an entity class, the score will reflect class
              proximity so the most specific object will be selected.
    """
    def score_class(self, eclass, req):
        return self.score_interfaces(req, eclass, eclass)


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
      be returned

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
                if not rdef.may_have_permission(self.action, req):
                    return 0
            except KeyError:
                return 0
        else:
            return rschema.may_have_permission(self.action, req, eschema, self.role)
        return 1

    def score_entity(self, entity):
        rschema = self._get_rschema(entity)
        if rschema is None:
            return 0 # relation not supported
        if self.target_etype is not None:
            rschema = rschema.role_rdef(entity.e_schema, self.target_etype, self.role)
        if self.role == 'subject':
            if not rschema.has_perm(entity._cw, 'add', fromeid=entity.eid):
                return 0
        elif not rschema.has_perm(entity._cw, 'add', toeid=entity.eid):
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
        user = req.user
        action = self.action
        if row is None:
            score = 0
            need_local_check = []
            geteschema = req.vreg.schema.eschema
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
                    if not rset.description[i][0] in need_local_check:
                        continue
                    if not self.score(req, rset, i, col):
                        return 0
                score += 1
            return score
        return self.score(req, rset, row, col)

    def score_entity(self, entity):
        if entity.has_perm(self.action):
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
            rql = 'Any X WHERE X eid %%(x)s, U eid %%(u)s, %s' % expression
        else:
            rql = 'Any X WHERE X eid %%(x)s, %s' % expression
        self.rql = rql

    def __repr__(self):
        return u'<rql_condition "%s" at %x>' % (self.rql, id(self))

    def score(self, req, rset, row, col):
        try:
            return len(req.execute(self.rql, {'x': rset[row][col],
                                              'u': req.user.eid}, 'x'))
        except Unauthorized:
            return 0

# logged user selectors ########################################################

@objectify_selector
@lltrace
def authenticated_user(cls, req, **kwargs):
    """Return 1 if the user is authenticated (e.g. not the anonymous user).

    May only be used on the web side, not on the data repository side.
    """
    if req.cnx.anonymous_connection:
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


class match_view(ExpectedValueSelector):
    """Return 1 if a view is specified an as its registry id is in one of the
    expected view id given to the initializer.
    """
    @lltrace
    def __call__(self, cls, req, view=None, **kwargs):
        if view is None or not view.__regid__ in self.expected:
            return 0
        return 1


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
    if not propval:
        propval = cls.context
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


class specified_etype_implements(implements):
    """Return non-zero score if the entity type specified by an 'etype' key
    searched in (by priority) input context kwargs and request form parameters
    match a known entity type (case insensitivly), and it's associated entity
    class is of one of the type(s) given to the initializer or implements at
    least one of the given interfaces. If multiple arguments are given, matching
    one of them is enough.

    Entity types should be given as string, the corresponding class will be
    fetched from the entity types registry at selection time.

    .. note:: when interface is an entity class, the score will reflect class
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


# Other selectors ##############################################################


class match_transition(ExpectedValueSelector):
    """Return 1 if:

    * a `transition` argument is found in the input context which
      has a `.name` attribute matching one of the expected names given to the
      initializer

    * no transition specified.
    """
    @lltrace
    def __call__(self, cls, req, transition=None, **kwargs):
        # XXX check this is a transition that apply to the object?
        if transition is None:
            return 1
        if transition is not None and getattr(transition, 'name', None) in self.expected:
            return 1
        return 0


## deprecated stuff ############################################################

entity_implements = class_renamed('entity_implements', implements)

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

but_etype = class_renamed('but_etype', _but_etype, 'use ~implements(*etypes) instead')


# XXX deprecated the one_* variants of selectors below w/ multi_xxx(nb=1)?
#     take care at the implementation though (looking for the 'row' argument's
#     value)
two_lines_rset = class_renamed('two_lines_rset', multi_lines_rset)
two_cols_rset = class_renamed('two_cols_rset', multi_columns_rset)
two_etypes_rset = class_renamed('two_etypes_rset', multi_etypes_rset)
