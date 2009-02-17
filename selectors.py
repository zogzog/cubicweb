"""This file contains some basic selectors required by application objects.

A selector is responsible to score how well an object may be used with a
given result set (publishing time selection)

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
    from cubicweb.common.selectors import traced_selection
    with traced_selection():
        self.view('calendar', myrset)

    # in Python2.4
    from cubicweb.common import selectors
    selectors.TRACED_OIDS = ('calendar',)
    self.view('calendar', myrset)
    selectors.TRACED_OIDS = ()
 


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

import logging
from warnings import warn

from logilab.common.compat import all
from logilab.common.deprecation import deprecated_function
from logilab.common.interface import implements as implements_iface

from yams import BASE_TYPES

from cubicweb import Unauthorized, NoSelectableObject, role
from cubicweb.vregistry import NoSelectableObject, Selector, chainall, chainfirst
from cubicweb.cwvreg import DummyCursorError
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
        if isinstance(cls, Selector):
            selname = cls.__class__.__name__
            oid = args[0].id
        else:
            selname = selector.__name__
            oid = cls.id
        ret = selector(cls, *args, **kwargs)
        if TRACED_OIDS == 'all' or oid in TRACED_OIDS:
            #SELECTOR_LOGGER.warning('selector %s returned %s for %s', selname, ret, cls)
            print 'selector %s returned %s for %s' % (selname, ret, cls)
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


# abstract selectors ##########################################################

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
        return score and (score + 1)

    def score(self, cls, req, etype):
        if etype in BASE_TYPES:
            return 0
        return self.score_class(cls.vreg.etype_class(etype), req)
        
    def score_class(self, eclass, req):
        raise NotImplementedError()


class EntitySelector(EClassSelector):
    """abstract class for selectors working on the entity instances of the
    result set. Its __call__ method has the following behaviour:

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
        if not rset:
            return 0
        score = 0
        if row is None:
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
        return score and (score + 1)

    def score(self, req, rset, row, col):
        try:
            return self.score_entity(rset.get_entity(row, col))
        except NotAnEntity:
            return 0
                                 
    def score_entity(self, entity):
        raise NotImplementedError()


# very basic selectors ########################################################

def yes(cls, *args, **kwargs):
    """accept everything"""
    return 1

@lltrace
def none_rset(cls, req, rset, *args, **kwargs):
    """accept no result set (e.g. given rset is None)"""
    if rset is None:
        return 1
    return 0

@lltrace
def any_rset(cls, req, rset, *args, **kwargs):
    """accept result set, whatever the number of result it contains"""
    if rset is not None:
        return 1
    return 0

@lltrace
def nonempty_rset(cls, req, rset, *args, **kwargs):
    """accept any non empty result set"""
    if rset is not None and rset.rowcount:
        return 1
    return 0
    
@lltrace
def empty_rset(cls, req, rset, *args, **kwargs):
    """accept empty result set"""
    if rset is not None and rset.rowcount == 0:
        return 1
    return 0

@lltrace
def one_line_rset(cls, req, rset, row=None, *args, **kwargs):
    """if row is specified, accept result set with a single line of result,
    else accepts anyway
    """
    if rset is not None and (row is not None or rset.rowcount == 1):
        return 1
    return 0

@lltrace
def two_lines_rset(cls, req, rset, *args, **kwargs):
    """accept result set with *at least* two lines of result"""
    if rset is not None and rset.rowcount > 1:
        return 1
    return 0

@lltrace
def two_cols_rset(cls, req, rset, *args, **kwargs):
    """accept result set with at least one line and two columns of result"""
    if rset is not None and rset.rowcount and len(rset.rows[0]) > 1:
        return 1
    return 0

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

@lltrace
def sorted_rset(cls, req, rset, row=None, col=0, **kwargs):
    """accept sorted result set"""
    rqlst = rset.syntax_tree()
    if len(rqlst.children) > 1 or not rqlst.children[0].orderby:
        return 0
    return 2

@lltrace
def one_etype_rset(cls, req, rset, row=None, col=0, *args, **kwargs):
    """accept result set where entities in the specified column (or 0) are all
    of the same type
    """
    if len(rset.column_types(col)) != 1:
        return 0
    return 1

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

@lltrace
def anonymous_user(cls, req, *args, **kwargs):
    """accept if user is anonymous"""
    if req.cnx.anonymous_connection:
        return 1
    return 0

@lltrace
def authenticated_user(cls, req, *args, **kwargs):
    """accept if user is authenticated"""
    return not anonymous_user(cls, req, *args, **kwargs)

@lltrace
def primary_view(cls, req, rset, row=None, col=0, view=None, **kwargs):
    """accept if view given as named argument is a primary view, or if no view
    is given
    """
    if view is not None and not view.is_primary():
        return 0
    return 1

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
        self.expected = expected
        
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


class match_user_groups(Selector):
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
    
    def __init__(self, *required_groups):
        self.required_groups = required_groups
    
    @lltrace
    def __call__(self, cls, req, rset=None, row=None, col=0, **kwargs):
        user = req.user
        if user is None:
            return int('guests' in self.required_groups)
        score = user.matching_groups(self.required_groups)
        if not score and 'owners' in self.required_groups and rset:
            nbowned = 0
            if row is not None:
                if not user.owns(rset[row][col]):
                    return 0
                score = 1
            else:
                score = all(user.owns(r[col or 0]) for r in rset)
        return 0


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

class implements(EClassSelector):
    """accept if entity class found in the result set implements at least one
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
    def __init__(self, *expected_ifaces):
        self.expected_ifaces = expected_ifaces

    def score_class(self, eclass, req):
        print '***********************************'
        score = 0
        for iface in self.expected_ifaces:
            print 'TESTING', iface, 'on', eclass
            if isinstance(iface, basestring):
                # entity type
                iface = eclass.vreg.etype_class(iface)
                print 'found iface ===', iface
            if implements_iface(eclass, iface):
                print 'and implementing !!!'
                score += 1
                if getattr(iface, '__registry__', None) == 'etypes':
                    score += 1
                    # adjust score if the interface is an entity class
                    if iface is eclass:
                        score += len(eclass.e_schema.ancestors())
#                        print 'is majoration', len(eclass.e_schema.ancestors()) 
                    else:
                        parents = [e.type for e in eclass.e_schema.ancestors()]
                        for index, etype in enumerate(reversed(parents)):
                            basecls = eclass.vreg.etype_class(etype)
                            if iface is basecls:
                                score += index
#                                print 'etype majoration', index
                                break
        print '***********************************', score
        return score


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
    def __call__(cls, req, *args, **kwargs):
        try:
            etype = req.form['etype']
        except KeyError:
            try:
                etype = kwargs['etype']
            except KeyError:
                return 0
        return self.score_class(cls.vreg.etype_class(etype), req)


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
        return super(relation_possible, self).__call__(cls, req, *args, **kwargs)
        
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
                if self.role == 'object':
                    return self.target_etype in rschema.objects(eschema)
                else:
                    return self.target_etype in rschema.subjects(eschema)
            except KeyError, ex:
                return 0
        return 1


class has_editable_relation(EntitySelector):
    """accept if some relations for an entity found in the result set is
    editable by the logged user.

    See `EntitySelector` documentation for behaviour when row is not specified.
    """
        
    def score_entity(self, entity):
        # if user has no update right but it can modify some relation,
        # display action anyway
        for dummy in entity.srelations_by_category(('generic', 'metadata'),
                                                   'add'):
            return 1
        for rschema, targetschemas, role in entity.relations_by_category(
            ('primary', 'secondary'), 'add'):
            if not rschema.is_final():
                return 1
        return 0


class may_add_relation(EntitySelector):
    """accept if the relation can be added to an entity found in the result set
    by the logged user.
    
    See `EntitySelector` documentation for behaviour when row is not specified.

    :param rtype: a relation type (`basestring`)
    :param role: the role of the result set entity in the relation. 'subject' or
                 'object', default to 'subject'.
    """
    
    def __init__(self, rtype, role='subject'):
        self.rtype = rtype
        self.role = role
        
    def score_entity(self, entity):
        rschema = entity.schema.rschema(self.rtype)
        if self.role == 'subject':
            if not rschema.has_perm(req, 'add', fromeid=entity.eid):
                return 0
        elif not rschema.has_perm(req, 'add', toeid=entity.eid):
            return 0
        return 1


class has_related_entities(EntitySelector):
    """accept if entity found in the result set has some linked entities using
    the specified relation (optionaly filtered according to the specified target
    type).
    
    See `EntitySelector` documentation for behaviour when row is not specified.

    :param rtype: a relation type (`basestring`)
    :param role: the role of the result set entity in the relation. 'subject' or
                 'object', default to 'subject'.
    :param target_type: if specified, check the relation's end may be of this
                        target type (`basestring`)
    """
    def __init__(self, rtype, role='subject', target_etype=None,
                 once_is_enough=False):
        self.rtype = rtype
        self.role = role
        self.target_etype = target_etype
        self.once_is_enough = once_is_enough
    
    def score_entity(self, entity):
        rset = entity.related(self.rtype, self.role)
        if self.target_etype:
            return any(x for x, in rset.description if x == self.target_etype)
        return bool(rset)

        
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
    def __init__(self, action):
        self.action = action
        
    @lltrace
    def __call__(self, cls, req, rset, row=None, col=0, **kwargs):
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
        return self.score(req, rset, i, col)
    
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
    def __init__(self, expression):
        if 'U' in frozenset(split_expression(expression)):
            rql = 'Any X WHERE X eid %%(x)s, U eid %%(u)s, %s' % expression
        else:
            rql = 'Any X WHERE X eid %%(x)s, %s' % expression
        self.rql = rql
        
    def score(self, req, rset, row, col):
        try:
            return len(req.execute(self.rql, {'x': eid, 'u': req.user.eid}, 'x'))
        except Unauthorized:
            return 0

        
class but_etype(EntitySelector):
    """accept if the given entity types are not found in the result set.

    See `EntitySelector` documentation for behaviour when row is not specified.
    
    :param *etypes: entity types (`basestring`) which should be refused
    """
    def __init__(self, *etypes):
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
    def __init__(self, scorefunc):
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
    """only check if the user has read access on the entity's type refered
    by the .etype attribute and on the relations's type refered by the
    .rtype attribute if set.
    """
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

searchstate_accept = chainall(nonempty_rset, match_search_state, accept,
                              name='searchstate_accept')
searchstate_accept_selector = deprecated_function(searchstate_accept)

searchstate_accept_one = chainall(one_line_rset, match_search_state,
                                  accept, _rql_condition,
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
            cls.__selectors__ += (match_user_groups(cls.require_groups),)
        return cls
    return plug_selector

@unbind_method
def accepts_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'accepts', None):
            warn('use "match_user_groups(group1, group2)" instead of using require_groups',
                 DeprecationWarning)
            cls.__selectors__ += (implements(*cls.accepts),)
        return cls
    return plug_selector

@unbind_method
def condition_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'condition', None):
            warn('use "use rql_condition(expression)" instead of using condition',
                 DeprecationWarning)
            cls.__selectors__ += (rql_condition(cls.condition),)
        return cls
    return plug_selector
     
@unbind_method
def has_relation_compat(registered):
    def plug_selector(cls, vreg):
        cls = registered(cls, vreg)
        if getattr(cls, 'type', None):
            warn('use relation_possible selector instead of using etype_rtype',
                 DeprecationWarning)
            cls.__selectors__ += (relation_possible(cls.rtype, role(cls),
                                                    getattr(cls, 'etype', None),
                                                    action=getattr(cls, 'require_permission', 'read')))
        return cls
    return plug_selector
