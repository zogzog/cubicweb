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
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import logging
from warnings import warn

from logilab.common.compat import all
from logilab.common.deprecation import deprecated_function
from logilab.common.interface import implements as implements_iface

from yams import BASE_TYPES

from cubicweb import (Unauthorized, NoSelectableObject, NotAnEntity,
                      role, typed_eid)
from cubicweb.vregistry import (NoSelectableObject, Selector,
                                chainall, objectify_selector)
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.schema import split_expression

# helpers for debugging selectors
SELECTOR_LOGGER = logging.getLogger('cubicweb.selectors')
TRACED_OIDS = ()

def lltrace(selector):
    # don't wrap selectors if not in development mode
    if CubicWebConfiguration.mode == 'installed':
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
        oid = vobj.id
        ret = selector(cls, *args, **kwargs)
        if TRACED_OIDS == 'all' or oid in TRACED_OIDS:
            #SELECTOR_LOGGER.warning('selector %s returned %s for %s', selname, ret, cls)
            print 'selector %s returned %s for %s' % (selname, ret, vobj)
        return ret
    traced.__name__ = selector.__name__
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


def score_interface(cls_or_inst, cls, iface):
    """Return XXX if the give object (maybe an instance or class) implements
    the interface.
    """
    if getattr(iface, '__registry__', None) == 'etypes':
        # adjust score if the interface is an entity class
        parents = cls_or_inst.parent_classes()
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


# abstract selectors ##########################################################

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
    def __init__(self, *expected_ifaces):
        super(ImplementsMixIn, self).__init__()
        self.expected_ifaces = expected_ifaces

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.expected_ifaces))

    def score_interfaces(self, cls_or_inst, cls):
        score = 0
        vreg, eschema = cls_or_inst.vreg, cls_or_inst.e_schema
        for iface in self.expected_ifaces:
            if isinstance(iface, basestring):
                # entity type
                try:
                    iface = vreg.etype_class(iface)
                except KeyError:
                    continue # entity type not in the schema
            score += score_interface(cls_or_inst, cls, iface)
        return score


class EClassSelector(Selector):
    """abstract class for selectors working on the entity classes of the result
    set. Its __call__ method has the following behaviour:

    * if row is specified, return the score returned by the score_class method
      called with the entity class found in the specified cell
    * else return the sum of score returned by the score_class method for each
      entity type found in the specified column, unless:
      - `once_is_enough` is True, in which case the first non-zero score is
        returned
      - `once_is_enough` is False, in which case if score_class return 0, 0 is
        returned
    """
    def __init__(self, once_is_enough=False):
        self.once_is_enough = once_is_enough

    @lltrace
    def __call__(self, cls, req, rset, row=None, col=0, **kwargs):
        if not rset:
            return 0
        score = 0
        if row is None:
            for etype in rset.column_types(col):
                if etype is None: # outer join
                    continue
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
        return self.score_class(cls.vreg.etype_class(etype), req)

    def score_class(self, eclass, req):
        raise NotImplementedError()


class EntitySelector(EClassSelector):
    """abstract class for selectors working on the entity instances of the
    result set. Its __call__ method has the following behaviour:

    * if 'entity' find in kwargs, return the score returned by the score_entity
      method for this entity
    * if row is specified, return the score returned by the score_entity method
      called with the entity instance found in the specified cell
    * else return the sum of score returned by the score_entity method for each
      entity found in the specified column, unless:
      - `once_is_enough` is True, in which case the first non-zero score is
        returned
      - `once_is_enough` is False, in which case if score_class return 0, 0 is
        returned

    note: None values (resulting from some outer join in the query) are not
          considered.
    """

    @lltrace
    def __call__(self, cls, req, rset, row=None, col=0, **kwargs):
        if not rset and not kwargs.get('entity'):
            return 0
        score = 0
        if kwargs.get('entity'):
            score = self.score_entity(kwargs['entity'])
        elif row is None:
            for row, rowvalue in enumerate(rset.rows):
                if rowvalue[col] is None: # outer join
                    continue
                escore = self.score(req, rset, row, col)
                if not escore and not self.once_is_enough:
                    return 0
                elif self.once_is_enough:
                    return escore
                score += escore
        else:
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


# very basic selectors ########################################################

class yes(Selector):
    """return arbitrary score"""
    def __init__(self, score=1):
        self.score = score
    def __call__(self, *args, **kwargs):
        return self.score

@objectify_selector
@lltrace
def none_rset(cls, req, rset, *args, **kwargs):
    """accept no result set (e.g. given rset is None)"""
    if rset is None:
        return 1
    return 0

@objectify_selector
@lltrace
def any_rset(cls, req, rset, *args, **kwargs):
    """accept result set, whatever the number of result it contains"""
    if rset is not None:
        return 1
    return 0

@objectify_selector
@lltrace
def nonempty_rset(cls, req, rset, *args, **kwargs):
    """accept any non empty result set"""
    if rset is not None and rset.rowcount:
        return 1
    return 0

@objectify_selector
@lltrace
def empty_rset(cls, req, rset, *args, **kwargs):
    """accept empty result set"""
    if rset is not None and rset.rowcount == 0:
        return 1
    return 0

@objectify_selector
@lltrace
def one_line_rset(cls, req, rset, row=None, *args, **kwargs):
    """if row is specified, accept result set with a single line of result,
    else accepts anyway
    """
    if rset is not None and (row is not None or rset.rowcount == 1):
        return 1
    return 0

@objectify_selector
@lltrace
def two_lines_rset(cls, req, rset, *args, **kwargs):
    """accept result set with *at least* two lines of result"""
    if rset is not None and rset.rowcount > 1:
        return 1
    return 0

@objectify_selector
@lltrace
def two_cols_rset(cls, req, rset, *args, **kwargs):
    """accept result set with at least one line and two columns of result"""
    if rset is not None and rset.rowcount and len(rset.rows[0]) > 1:
        return 1
    return 0

@objectify_selector
@lltrace
def paginated_rset(cls, req, rset, *args, **kwargs):
    """accept result set with more lines than the page size.

    Page size is searched in (respecting order):
    * a page_size argument
    * a page_size form parameters
    * the navigation.page-size property
    """
    page_size = kwargs.get('page_size')
    if page_size is None:
        page_size = req.form.get('page_size')
        if page_size is None:
            page_size = req.property_value('navigation.page-size')
        else:
            page_size = int(page_size)
    if rset is None or rset.rowcount <= page_size:
        return 0
    return 1

@objectify_selector
@lltrace
def sorted_rset(cls, req, rset, row=None, col=0, **kwargs):
    """accept sorted result set"""
    rqlst = rset.syntax_tree()
    if len(rqlst.children) > 1 or not rqlst.children[0].orderby:
        return 0
    return 2

@objectify_selector
@lltrace
def one_etype_rset(cls, req, rset, row=None, col=0, *args, **kwargs):
    """accept result set where entities in the specified column (or 0) are all
    of the same type
    """
    if rset is None:
        return 0
    if len(rset.column_types(col)) != 1:
        return 0
    return 1

@objectify_selector
@lltrace
def two_etypes_rset(cls, req, rset, row=None, col=0, **kwargs):
    """accept result set where entities in the specified column (or 0) are not
    of the same type
    """
    if rset:
        etypes = rset.column_types(col)
        if len(etypes) > 1:
            return 1
    return 0

class non_final_entity(EClassSelector):
    """accept if entity type found in the result set is non final.

    See `EClassSelector` documentation for behaviour when row is not specified.
    """
    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return 1

@objectify_selector
@lltrace
def authenticated_user(cls, req, *args, **kwargs):
    """accept if user is authenticated"""
    if req.cnx.anonymous_connection:
        return 0
    return 1

def anonymous_user():
    return ~ authenticated_user()

@objectify_selector
@lltrace
def primary_view(cls, req, rset, row=None, col=0, view=None, **kwargs):
    """accept if view given as named argument is a primary view, or if no view
    is given
    """
    if view is not None and not view.is_primary():
        return 0
    return 1

@objectify_selector
@lltrace
def match_context_prop(cls, req, rset, row=None, col=0, context=None,
                       **kwargs):
    """accept if:
    * no context given
    * context (`basestring`) is matching the context property value for the
      given cls
    """
    propval = req.property_value('%s.%s.context' % (cls.__registry__, cls.id))
    if not propval:
        propval = cls.context
    if context is not None and propval and context != propval:
        return 0
    return 1


class match_search_state(Selector):
    """accept if the current request search state is in one of the expected
    states given to the initializer

    :param expected: either 'normal' or 'linksearch' (eg searching for an
                     object to create a relation with another)
    """
    def __init__(self, *expected):
        assert expected, self
        self.expected = frozenset(expected)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(sorted(str(s) for s in self.expected)))

    @lltrace
    def __call__(self, cls, req, rset, row=None, col=0, **kwargs):
        try:
            if not req.search_state[0] in self.expected:
                return 0
        except AttributeError:
            return 1 # class doesn't care about search state, accept it
        return 1


class match_form_params(match_search_state):
    """accept if parameters specified as initializer arguments are specified
    in request's form parameters

    :param *expected: parameters (eg `basestring`) which are expected to be
                      found in request's form parameters
    """

    @lltrace
    def __call__(self, cls, req, *args, **kwargs):
        score = 0
        for param in self.expected:
            val = req.form.get(param)
            if not val:
                return 0
            score += 1
        return len(self.expected)


class match_kwargs(match_search_state):
    """accept if parameters specified as initializer arguments are specified
    in named arguments given to the selector

    :param *expected: parameters (eg `basestring`) which are expected to be
                      found in named arguments (kwargs)
    """

    @lltrace
    def __call__(self, cls, req, *args, **kwargs):
        for arg in self.expected:
            if not arg in kwargs:
                return 0
        return len(self.expected)


class match_user_groups(match_search_state):
    """accept if logged users is in at least one of the given groups. Returned
    score is the number of groups in which the user is.

    If the special 'owners' group is given:
    * if row is specified check the entity at the given row/col is owned by the
      logged user
    * if row is not specified check all entities in col are owned by the logged
      user

    :param *required_groups: name of groups (`basestring`) in which the logged
                             user should be
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


class match_transition(match_search_state):
    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        try:
            trname = req.execute('Any XN WHERE X is Transition, X eid %(x)s, X name XN',
                                 {'x': typed_eid(req.form['treid'])})[0][0]
        except (KeyError, IndexError):
            return 0
        # XXX check this is a transition that apply to the object?
        if not trname in self.expected:
            return 0
        return 1


class match_view(match_search_state):
    """accept if the current view is in one of the expected vid given to the
    initializer
    """
    @lltrace
    def __call__(self, cls, req, rset, row=None, col=0, view=None, **kwargs):
        if view is None or not view.id in self.expected:
            return 0
        return 1


class appobject_selectable(Selector):
    """accept with another appobject is selectable using selector's input
    context.

    :param registry: a registry name (`basestring`)
    :param oid: an object identifier (`basestring`)
    """
    def __init__(self, registry, oid):
        self.registry = registry
        self.oid = oid

    def __call__(self, cls, req, rset, *args, **kwargs):
        try:
            cls.vreg.select_object(self.registry, self.oid, req, rset, *args, **kwargs)
            return 1
        except NoSelectableObject:
            return 0


# not so basic selectors ######################################################

class implements(ImplementsMixIn, EClassSelector):
    """accept if entity classes found in the result set implements at least one
    of the interfaces given as argument. Returned score is the number of
    implemented interfaces.

    See `EClassSelector` documentation for behaviour when row is not specified.

    :param *expected_ifaces: expected interfaces. An interface may be a class
                             or an entity type (e.g. `basestring`) in which case
                             the associated class will be searched in the
                             registry (at selection time)

    note: when interface is an entity class, the score will reflect class
          proximity so the most specific object'll be selected
    """
    def score_class(self, eclass, req):
        return self.score_interfaces(eclass, eclass)


class specified_etype_implements(implements):
    """accept if entity class specified using an 'etype' parameters in name
    argument or request form implements at least one of the interfaces given as
    argument. Returned score is the number of implemented interfaces.

    :param *expected_ifaces: expected interfaces. An interface may be a class
                             or an entity type (e.g. `basestring`) in which case
                             the associated class will be searched in the
                             registry (at selection time)

    note: when interface is an entity class, the score will reflect class
          proximity so the most specific object'll be selected
    """

    @lltrace
    def __call__(self, cls, req, *args, **kwargs):
        try:
            etype = req.form['etype']
        except KeyError:
            try:
                etype = kwargs['etype']
            except KeyError:
                return 0
        return self.score_class(cls.vreg.etype_class(etype), req)


class entity_implements(ImplementsMixIn, EntitySelector):
    """accept if entity instances found in the result set implements at least one
    of the interfaces given as argument. Returned score is the number of
    implemented interfaces.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param *expected_ifaces: expected interfaces. An interface may be a class
                             or an entity type (e.g. `basestring`) in which case
                             the associated class will be searched in the
                             registry (at selection time)

    note: when interface is an entity class, the score will reflect class
          proximity so the most specific object'll be selected
    """
    def score_entity(self, entity):
        return self.score_interfaces(entity, entity.__class__)


class relation_possible(EClassSelector):
    """accept if entity class found in the result set support the relation.

    See `EClassSelector` documentation for behaviour when row is not specified.

    :param rtype: a relation type (`basestring`)
    :param role: the role of the result set entity in the relation. 'subject' or
                 'object', default to 'subject'.
    :param target_type: if specified, check the relation's end may be of this
                        target type (`basestring`)
    :param action: a relation schema action (one of 'read', 'add', 'delete')
                   which must be granted to the logged user, else a 0 score will
                   be returned
    """
    def __init__(self, rtype, role='subject', target_etype=None,
                 action='read', once_is_enough=False):
        super(relation_possible, self).__init__(once_is_enough)
        self.rtype = rtype
        self.role = role
        self.target_etype = target_etype
        self.action = action

    @lltrace
    def __call__(self, cls, req, *args, **kwargs):
        rschema = cls.schema.rschema(self.rtype)
        if not (rschema.has_perm(req, self.action)
                or rschema.has_local_role(self.action)):
            return 0
        score = super(relation_possible, self).__call__(cls, req, *args, **kwargs)
        return score

    def score_class(self, eclass, req):
        eschema = eclass.e_schema
        try:
            if self.role == 'object':
                rschema = eschema.object_relation(self.rtype)
            else:
                rschema = eschema.subject_relation(self.rtype)
        except KeyError:
            return 0
        if self.target_etype is not None:
            try:
                if self.role == 'subject':
                    return int(self.target_etype in rschema.objects(eschema))
                else:
                    return int(self.target_etype in rschema.subjects(eschema))
            except KeyError:
                return 0
        return 1


class partial_relation_possible(PartialSelectorMixIn, relation_possible):
    """partial version of the relation_possible selector

    The selector will look for class attributes to find its missing
    information. The list of attributes required on the class
    for this selector are:

    - `rtype`: same as `rtype` parameter of the `relation_possible` selector

    - `role`: this attribute will be passed to the `cubicweb.role` function
      to determine the role of class in the relation

    - `etype` (optional): the entity type on the other side of the relation

    :param action: a relation schema action (one of 'read', 'add', 'delete')
                   which must be granted to the logged user, else a 0 score will
                   be returned
    """
    def __init__(self, action='read', once_is_enough=False):
        super(partial_relation_possible, self).__init__(None, None, None,
                                                        action, once_is_enough)

    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)
        self.target_etype = getattr(cls, 'etype', None)


class may_add_relation(EntitySelector):
    """accept if the relation can be added to an entity found in the result set
    by the logged user.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param rtype: a relation type (`basestring`)
    :param role: the role of the result set entity in the relation. 'subject' or
                 'object', default to 'subject'.
    """

    def __init__(self, rtype, role='subject', once_is_enough=False):
        super(may_add_relation, self).__init__(once_is_enough)
        self.rtype = rtype
        self.role = role

    def score_entity(self, entity):
        rschema = entity.schema.rschema(self.rtype)
        if self.role == 'subject':
            if not rschema.has_perm(entity.req, 'add', fromeid=entity.eid):
                return 0
        elif not rschema.has_perm(entity.req, 'add', toeid=entity.eid):
            return 0
        return 1


class partial_may_add_relation(PartialSelectorMixIn, may_add_relation):
    """partial version of the may_add_relation selector

    The selector will look for class attributes to find its missing
    information. The list of attributes required on the class
    for this selector are:

    - `rtype`: same as `rtype` parameter of the `relation_possible` selector

    - `role`: this attribute will be passed to the `cubicweb.role` function
      to determine the role of class in the relation.

    :param action: a relation schema action (one of 'read', 'add', 'delete')
                   which must be granted to the logged user, else a 0 score will
                   be returned
    """
    def __init__(self, once_is_enough=False):
        super(partial_may_add_relation, self).__init__(None, None, once_is_enough)

    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)


class has_related_entities(EntitySelector):
    """accept if entity found in the result set has some linked entities using
    the specified relation (optionaly filtered according to the specified target
    type). Checks first if the relation is possible.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param rtype: a relation type (`basestring`)
    :param role: the role of the result set entity in the relation. 'subject' or
                 'object', default to 'subject'.
    :param target_type: if specified, check the relation's end may be of this
                        target type (`basestring`)
    """
    def __init__(self, rtype, role='subject', target_etype=None,
                 once_is_enough=False):
        super(has_related_entities, self).__init__(once_is_enough)
        self.rtype = rtype
        self.role = role
        self.target_etype = target_etype

    def score_entity(self, entity):
        relpossel = relation_possible(self.rtype, self.role, self.target_etype)
        if not relpossel.score_class(entity.__class__, entity.req):
            return 0
        rset = entity.related(self.rtype, self.role)
        if self.target_etype:
            return any(r for r in rset.description if r[0] == self.target_etype)
        return rset and 1 or 0


class partial_has_related_entities(PartialSelectorMixIn, has_related_entities):
    """partial version of the has_related_entities selector

    The selector will look for class attributes to find its missing
    information. The list of attributes required on the class
    for this selector are:

    - `rtype`: same as `rtype` parameter of the `relation_possible` selector

    - `role`: this attribute will be passed to the `cubicweb.role` function
      to determine the role of class in the relation.

    - `etype` (optional): the entity type on the other side of the relation

    :param action: a relation schema action (one of 'read', 'add', 'delete')
                   which must be granted to the logged user, else a 0 score will
                   be returned
    """
    def __init__(self, once_is_enough=False):
        super(partial_has_related_entities, self).__init__(None, None,
                                                           None, once_is_enough)
    def complete(self, cls):
        self.rtype = cls.rtype
        self.role = role(cls)
        self.target_etype = getattr(cls, 'etype', None)


class has_permission(EntitySelector):
    """accept if user has the permission to do the requested action on a result
    set entity.

    * if row is specified, return 1 if user has the permission on the entity
      instance found in the specified cell
    * else return a positive score if user has the permission for every entity
      in the found in the specified column

    note: None values (resulting from some outer join in the query) are not
          considered.

    :param action: an entity schema action (eg 'read'/'add'/'delete'/'update')
    """
    def __init__(self, action, once_is_enough=False):
        super(has_permission, self).__init__(once_is_enough)
        self.action = action

    @lltrace
    def __call__(self, cls, req, rset, row=None, col=0, **kwargs):
        if rset is None:
            return 0
        user = req.user
        action = self.action
        if row is None:
            score = 0
            need_local_check = []
            geteschema = cls.schema.eschema
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
    """accept if logged user has the add permission on entity class found in the
    result set, and class is not a strict subobject.

    See `EClassSelector` documentation for behaviour when row is not specified.
    """
    def score(self, cls, req, etype):
        eschema = cls.schema.eschema(etype)
        if not (eschema.is_final() or eschema.is_subobject(strict=True)) \
               and eschema.has_perm(req, 'add'):
            return 1
        return 0


class rql_condition(EntitySelector):
    """accept if an arbitrary rql return some results for an eid found in the
    result set. Returned score is the number of items returned by the rql
    condition.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param expression: basestring containing an rql expression, which should use
                       X variable to represent the context entity and may use U
                       to represent the logged user

    return the sum of the number of items returned by the rql condition as score
    or 0 at the first entity scoring to zero.
    """
    def __init__(self, expression, once_is_enough=False):
        super(rql_condition, self).__init__(once_is_enough)
        if 'U' in frozenset(split_expression(expression)):
            rql = 'Any X WHERE X eid %%(x)s, U eid %%(u)s, %s' % expression
        else:
            rql = 'Any X WHERE X eid %%(x)s, %s' % expression
        self.rql = rql

    def score(self, req, rset, row, col):
        try:
            return len(req.execute(self.rql, {'x': rset[row][col],
                                              'u': req.user.eid}, 'x'))
        except Unauthorized:
            return 0

    def __repr__(self):
        return u'<rql_condition "%s" at %x>' % (self.rql, id(self))

class but_etype(EntitySelector):
    """accept if the given entity types are not found in the result set.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param *etypes: entity types (`basestring`) which should be refused
    """
    def __init__(self, *etypes):
        super(but_etype, self).__init__()
        self.but_etypes = etypes

    def score(self, req, rset, row, col):
        if rset.description[row][col] in self.but_etypes:
            return 0
        return 1


class score_entity(EntitySelector):
    """accept if some arbitrary function return a positive score for an entity
    found in the result set.

    See `EntitySelector` documentation for behaviour when row is not specified.

    :param scorefunc: callable expected to take an entity as argument and to
                      return a score >= 0
    """
    def __init__(self, scorefunc, once_is_enough=False):
        super(score_entity, self).__init__(once_is_enough)
        self.score_entity = scorefunc


# XXX DEPRECATED ##############################################################

yes_selector = deprecated_function(yes)
norset_selector = deprecated_function(none_rset)
rset_selector = deprecated_function(any_rset)
anyrset_selector = deprecated_function(nonempty_rset)
emptyrset_selector = deprecated_function(empty_rset)
onelinerset_selector = deprecated_function(one_line_rset)
twolinerset_selector = deprecated_function(two_lines_rset)
twocolrset_selector = deprecated_function(two_cols_rset)
largerset_selector = deprecated_function(paginated_rset)
sortedrset_selector = deprecated_function(sorted_rset)
oneetyperset_selector = deprecated_function(one_etype_rset)
multitype_selector = deprecated_function(two_etypes_rset)
anonymous_selector = deprecated_function(anonymous_user)
not_anonymous_selector = deprecated_function(authenticated_user)
primaryview_selector = deprecated_function(primary_view)
contextprop_selector = deprecated_function(match_context_prop)

def nfentity_selector(cls, req, rset, row=None, col=0, **kwargs):
    return non_final_entity()(cls, req, rset, row, col)
nfentity_selector = deprecated_function(nfentity_selector)

def implement_interface(cls, req, rset, row=None, col=0, **kwargs):
    return implements(*cls.accepts_interfaces)(cls, req, rset, row, col)
_interface_selector = deprecated_function(implement_interface)
interface_selector = deprecated_function(implement_interface)
implement_interface = deprecated_function(implement_interface, 'use implements')

def accept_etype(cls, req, *args, **kwargs):
    """check etype presence in request form *and* accepts conformance"""
    return specified_etype_implements(*cls.accepts)(cls, req, *args)
etype_form_selector = deprecated_function(accept_etype)
accept_etype = deprecated_function(accept_etype, 'use specified_etype_implements')

def searchstate_selector(cls, req, rset, row=None, col=0, **kwargs):
    return match_search_state(cls.search_states)(cls, req, rset, row, col)
searchstate_selector = deprecated_function(searchstate_selector)

def match_user_group(cls, req, rset=None, row=None, col=0, **kwargs):
    return match_user_groups(*cls.require_groups)(cls, req, rset, row, col, **kwargs)
in_group_selector = deprecated_function(match_user_group)
match_user_group = deprecated_function(match_user_group)

def has_relation(cls, req, rset, row=None, col=0, **kwargs):
    return relation_possible(cls.rtype, role(cls), cls.etype,
                             getattr(cls, 'require_permission', 'read'))(cls, req, rset, row, col, **kwargs)
has_relation = deprecated_function(has_relation)

def one_has_relation(cls, req, rset, row=None, col=0, **kwargs):
    return relation_possible(cls.rtype, role(cls), cls.etype,
                             getattr(cls, 'require_permission', 'read',
                                     once_is_enough=True))(cls, req, rset, row, col, **kwargs)
one_has_relation = deprecated_function(one_has_relation, 'use relation_possible selector')

def accept_rset(cls, req, rset, row=None, col=0, **kwargs):
    """simply delegate to cls.accept_rset method"""
    return implements(*cls.accepts)(cls, req, rset, row=row, col=col)
accept_rset_selector = deprecated_function(accept_rset)
accept_rset = deprecated_function(accept_rset, 'use implements selector')

accept = chainall(non_final_entity(), accept_rset, name='accept')
accept_selector = deprecated_function(accept)
accept = deprecated_function(accept, 'use implements selector')

accept_one = deprecated_function(chainall(one_line_rset, accept,
                                          name='accept_one'))
accept_one_selector = deprecated_function(accept_one)


def _rql_condition(cls, req, rset, row=None, col=0, **kwargs):
    if cls.condition:
        return rql_condition(cls.condition)(cls, req, rset, row, col)
    return 1
_rqlcondition_selector = deprecated_function(_rql_condition)

rqlcondition_selector = deprecated_function(chainall(non_final_entity(), one_line_rset, _rql_condition,
                         name='rql_condition'))

def but_etype_selector(cls, req, rset, row=None, col=0, **kwargs):
    return but_etype(cls.etype)(cls, req, rset, row, col)
but_etype_selector = deprecated_function(but_etype_selector)

@lltrace
def etype_rtype_selector(cls, req, rset, row=None, col=0, **kwargs):
    schema = cls.schema
    perm = getattr(cls, 'require_permission', 'read')
    if hasattr(cls, 'etype'):
        eschema = schema.eschema(cls.etype)
        if not (eschema.has_perm(req, perm) or eschema.has_local_role(perm)):
            return 0
    if hasattr(cls, 'rtype'):
        rschema = schema.rschema(cls.rtype)
        if not (rschema.has_perm(req, perm) or rschema.has_local_role(perm)):
            return 0
    return 1
etype_rtype_selector = deprecated_function(etype_rtype_selector)

#req_form_params_selector = deprecated_function(match_form_params) # form_params
#kwargs_selector = deprecated_function(match_kwargs) # expected_kwargs

# compound selectors ##########################################################

searchstate_accept = chainall(nonempty_rset(), accept,
                              name='searchstate_accept')
searchstate_accept_selector = deprecated_function(searchstate_accept)

searchstate_accept_one = chainall(one_line_rset, accept, _rql_condition,
                                  name='searchstate_accept_one')
searchstate_accept_one_selector = deprecated_function(searchstate_accept_one)

searchstate_accept = deprecated_function(searchstate_accept)
searchstate_accept_one = deprecated_function(searchstate_accept_one)


def unbind_method(selector):
    def new_selector(registered):
        # get the unbound method
        if hasattr(registered, 'im_func'):
            registered = registered.im_func
        # don't rebind since it will be done automatically during
        # the assignment, inside the destination class body
        return selector(registered)
    new_selector.__name__ = selector.__name__
    return new_selector


def deprecate(registered, msg):
    # get the unbound method
    if hasattr(registered, 'im_func'):
        registered = registered.im_func
    def _deprecate(cls, vreg):
        warn(msg, DeprecationWarning)
        return registered(cls, vreg)
    return _deprecate

@unbind_method
def require_group_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'require_groups', None):
            warn('use "match_user_groups(group1, group2)" instead of using require_groups',
                 DeprecationWarning)
            cls.__select__ &= match_user_groups(cls.require_groups)
        return cls
    return plug_selector

@unbind_method
def accepts_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'accepts', None):
            warn('use "implements("EntityType", IFace)" instead of using accepts on %s'
                 % cls,
                 DeprecationWarning)
            cls.__select__ &= implements(*cls.accepts)
        return cls
    return plug_selector

@unbind_method
def accepts_etype_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'accepts', None):
            warn('use "specified_etype_implements("EntityType", IFace)" instead of using accepts',
                 DeprecationWarning)
            cls.__select__ &= specified_etype_implements(*cls.accepts)
        return cls
    return plug_selector

@unbind_method
def condition_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'condition', None):
            warn('use "use rql_condition(expression)" instead of using condition',
                 DeprecationWarning)
            cls.__select__ &= rql_condition(cls.condition)
        return cls
    return plug_selector

@unbind_method
def has_relation_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'etype', None):
            warn('use relation_possible selector instead of using etype_rtype',
                 DeprecationWarning)
            cls.__select__ &= relation_possible(cls.rtype, role(cls),
                                                getattr(cls, 'etype', None),
                                                action=getattr(cls, 'require_permission', 'read'))
        return cls
    return plug_selector
