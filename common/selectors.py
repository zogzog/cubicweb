"""This file contains some basic selectors required by application objects.

A selector is responsible to score how well an object may be used with a
given result set (publishing time selection)

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.common.compat import all
from logilab.common.deprecation import deprecated_function

from cubicweb import Unauthorized, NoSelectableObject, role
from cubicweb.cwvreg import DummyCursorError
from cubicweb.vregistry import chainall, chainfirst, NoSelectableObject
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.schema import split_expression


def lltrace(selector):
    # don't wrap selectors if not in development mode
    if CubicWebConfiguration.mode == 'installed':
        return selector
    def traced(cls, *args, **kwargs):
        ret = selector(cls, *args, **kwargs)
        cls.lldebug('selector %s returned %s for %s', selector.__name__, ret, cls)
        return ret
    return traced
    
# very basic selectors ########################################################

def yes(cls, *args, **kwargs):
    """accept everything"""
    return 1
yes_selector = deprecated_function(yes)

@lltrace
def none_rset(cls, req, rset, *args, **kwargs):
    """accept no result set"""
    if rset is None:
        return 1
    return 0
norset_selector = deprecated_function(none_rset)

@lltrace
def rset(cls, req, rset, *args, **kwargs):
    """accept result set, whatever the number of result"""
    if rset is not None:
        return 1
    return 0
rset_selector = deprecated_function(rset)

@lltrace
def nonempty_rset(cls, req, rset, *args, **kwargs):
    """accept any non empty result set"""
    if rset is not None and rset.rowcount:
        return 1
    return 0
anyrset_selector = deprecated_function(nonempty_rset)
    
@lltrace
def empty_rset(cls, req, rset, *args, **kwargs):
    """accept empty result set"""
    if rset is not None and rset.rowcount == 0:
        return 1
    return 0
emptyrset_selector = deprecated_function(empty_rset)

@lltrace
def one_line_rset(cls, req, rset, row=None, *args, **kwargs):
    """accept result set with a single line of result"""
    if rset is not None and (row is not None or rset.rowcount == 1):
        return 1
    return 0
onelinerset_selector = deprecated_function(one_line_rset)

@lltrace
def two_lines_rset(cls, req, rset, *args, **kwargs):
    """accept result set with *at least* two lines of result"""
    if rset is not None and rset.rowcount > 1:
        return 1
    return 0
twolinerset_selector = deprecated_function(two_lines_rset)

@lltrace
def two_cols_rset(cls, req, rset, *args, **kwargs):
    """accept result set with at least one line and two columns of result"""
    if rset is not None and rset.rowcount > 0 and len(rset.rows[0]) > 1:
        return 1
    return 0
twocolrset_selector = deprecated_function(two_cols_rset)

@lltrace
def paginated_rset(cls, req, rset, *args, **kwargs):
    """accept result sets with more rows than the page size
    """
    if rset is None or len(rset) <= req.property_value('navigation.page-size'):
        return 0
    return 1
largerset_selector = deprecated_function(paginated_rset)

@lltrace
def sorted_rset(cls, req, rset, row=None, col=None):
    """accept sorted result set"""
    rqlst = rset.syntax_tree()
    if len(rqlst.children) > 1 or not rqlst.children[0].orderby:
        return 0
    return 2
sortedrset_selector = deprecated_function(sorted_rset)

@lltrace
def one_etype_rset(cls, req, rset, *args, **kwargs):
    """accept result set where entities in the first columns are all of the
    same type
    """
    if len(rset.column_types(0)) != 1:
        return 0
    return 1
oneetyperset_selector = deprecated_function(one_etype_rset)

@lltrace
def two_etypes_rset(cls, req, rset, **kwargs):
    """accepts resultsets containing several entity types"""
    if rset:
        etypes = rset.column_types(0)
        if len(etypes) > 1:
            return 1
    return 0
multitype_selector = deprecated_function(two_etypes_rset)

@lltrace
def match_search_state(cls, req, rset, row=None, col=None, **kwargs):
    """checks if the current search state is in a .search_states attribute of
    the wrapped class

    search state should be either 'normal' or 'linksearch' (eg searching for an
    object to create a relation with another)
    """
    try:
        if not req.search_state[0] in cls.search_states:
            return 0
    except AttributeError:
        return 1 # class don't care about search state, accept it
    return 1
searchstate_selector = deprecated_function(match_search_state)

@lltrace
def anonymous_user(cls, req, *args, **kwargs):
    """accept if user is anonymous"""
    if req.cnx.anonymous_connection:
        return 1
    return 0
anonymous_selector = deprecated_function(anonymous_user)

@lltrace
def authenticated_user(cls, req, *args, **kwargs):
    """accept if user is authenticated"""
    return not anonymous_selector(cls, req, *args, **kwargs)
not_anonymous_selector = deprecated_function(authenticated_user)

@lltrace
def match_form_params(cls, req, *args, **kwargs):
    """check if parameters specified by the form_params attribute on
    the wrapped class are specified in request form parameters
    """
    score = 0
    for param in cls.form_params:
        val = req.form.get(param)
        if not val:
            return 0
        score += 1
    return score + 1
req_form_params_selector = deprecated_function(match_form_params)

@lltrace
def match_kwargs(cls, req, *args, **kwargs):
    """check if arguments specified by the expected_kwargs attribute on
    the wrapped class are specified in given named parameters
    """
    values = []
    for arg in cls.expected_kwargs:
        if not arg in kwargs:
            return 0
    return 1
kwargs_selector = deprecated_function(match_kwargs)


# not so basic selectors ######################################################

@lltrace
def etype_accepts(cls, req, *args, **kwargs):
    """check etype presence in request form *and* accepts conformance"""
    if 'etype' not in req.form and 'etype' not in kwargs:
        return 0
    try:
        etype = req.form['etype']
    except KeyError:
        etype = kwargs['etype']
    # value is a list or a tuple if web request form received several
    # values for etype parameter
    assert isinstance(etype, basestring), "got multiple etype parameters in req.form"
    if 'Any' in cls.accepts:
        return 1
    # no Any found, we *need* exact match
    if etype not in cls.accepts:
        return 0
    # exact match must return a greater value than 'Any'-match
    return 2
etype_form_selector = deprecated_function(etype_accepts)

@lltrace
def _nfentity_selector(cls, req, rset, row=None, col=None, **kwargs):
    """accept non final entities
    if row is not specified, use the first one
    if col is not specified, use the first one
    """
    etype = rset.description[row or 0][col or 0]
    if etype is None: # outer join
        return 0
    if cls.schema.eschema(etype).is_final():
        return 0
    return 1

@lltrace
def _rqlcondition_selector(cls, req, rset, row=None, col=None, **kwargs):
    """accept single entity result set if the entity match an rql condition
    """
    if cls.condition:
        eid = rset[row or 0][col or 0]
        if 'U' in frozenset(split_expression(cls.condition)):
            rql = 'Any X WHERE X eid %%(x)s, U eid %%(u)s, %s' % cls.condition
        else:
            rql = 'Any X WHERE X eid %%(x)s, %s' % cls.condition
        try:
            return len(req.execute(rql, {'x': eid, 'u': req.user.eid}, 'x'))
        except Unauthorized:
            return 0
        
    return 1

@lltrace
def _interface_selector(cls, req, rset, row=None, col=None, **kwargs):
    """accept uniform result sets, and apply the following rules:

    * wrapped class must have a accepts_interfaces attribute listing the
      accepted ORed interfaces
    * if row is None, return the sum of values returned by the method
      for each entity's class in the result set. If any score is 0,
      return 0.
    * if row is specified, return the value returned by the method with
      the entity's class of this row
    """
    # XXX this selector can be refactored : extract the code testing
    #     for entity schema / interface compliance
    score = 0
    # check 'accepts' to give priority to more specific classes
    if row is None:
        for etype in rset.column_types(col or 0):
            eclass = cls.vreg.etype_class(etype)
            escore = 0
            for iface in cls.accepts_interfaces:
                escore += iface.is_implemented_by(eclass)
            if not escore:
                return 0
            score += escore
            accepts = set(getattr(cls, 'accepts', ()))
            # if accepts is defined on the vobject, eclass must match
            if accepts:
                eschema = eclass.e_schema
                etypes = set([eschema] + eschema.ancestors())
                if accepts & etypes:
                    score += 2
                elif 'Any' not in accepts:
                    return 0
        return score + 1
    etype = rset.description[row][col or 0]
    if etype is None: # outer join
        return 0
    eclass = cls.vreg.etype_class(etype)
    for iface in cls.accepts_interfaces:
        score += iface.is_implemented_by(eclass)
    if score:
        accepts = set(getattr(cls, 'accepts', ()))
        # if accepts is defined on the vobject, eclass must match
        if accepts:
            eschema = eclass.e_schema
            etypes = set([eschema] + eschema.ancestors())
            if accepts & etypes:
                score += 1
            elif 'Any' not in accepts:
                return 0
        score += 1
    return score

@lltrace
def score_entity_selector(cls, req, rset, row=None, col=None, **kwargs):
    if row is None:
        rows = xrange(rset.rowcount)
    else:
        rows = (row,)
    for row in rows:
        try:
            score = cls.score_entity(rset.get_entity(row, col or 0))
        except DummyCursorError:
            # get a dummy cursor error, that means we are currently
            # using a dummy rset to list possible views for an entity
            # type, not for an actual result set. In that case, we
            # don't care of the value, consider the object as selectable
            return 1
        if not score:
            return 0
    return 1

@lltrace
def accept_rset_selector(cls, req, rset, row=None, col=None, **kwargs):
    """simply delegate to cls.accept_rset method"""
    return cls.accept_rset(req, rset, row=row, col=col)

@lltrace
def but_etype_selector(cls, req, rset, row=None, col=None, **kwargs):
    """restrict the searchstate_accept_one_selector to exclude entity's type
    refered by the .etype attribute
    """
    if rset.description[row or 0][col or 0] == cls.etype:
        return 0
    return 1

@lltrace
def etype_rtype_selector(cls, req, rset, row=None, col=None, **kwargs):
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
        if not schema.rschema(cls.rtype).has_perm(req, perm):
            return 0
    return 1

@lltrace
def accept_rtype_selector(cls, req, rset, row=None, col=None, **kwargs):
    if hasattr(cls, 'rtype'):
        if row is None:
            for etype in rset.column_types(col or 0):
                if not cls.relation_possible(etype):
                    return 0
        elif not cls.relation_possible(rset.description[row][col or 0]):
            return 0
    return 1

def has_related_entities(cls, req, rset, row=None, col=None, **kwargs):
    assert row is not None
    return bool(rset.get_entity(row, col).related(cls.rtype, role(cls)))
    
@lltrace
def one_has_relation_selector(cls, req, rset, row=None, col=None, **kwargs):
    """check if the user has read access on the relations's type refered by the
    .rtype attribute of the class, and if at least one entity type in the
    result set has this relation.
    """
    schema = cls.schema
    perm = getattr(cls, 'require_permission', 'read')
    if not schema.rschema(cls.rtype).has_perm(req, perm):
        return 0
    if row is None:
        for etype in rset.column_types(col or 0):
            if cls.relation_possible(etype):
                return 1
    elif cls.relation_possible(rset.description[row][col or 0]):
        return 1
    return 0

@lltrace
def match_user_group(cls, req, rset=None, row=None, col=None, **kwargs):
    """select according to user's groups"""
    if not cls.require_groups:
        return 1
    user = req.user
    if user is None:
        return int('guests' in cls.require_groups)
    score = 0
    if 'owners' in cls.require_groups and rset:
        if row is not None:
            eid = rset[row][col or 0]
            if user.owns(eid):
                score = 1
        else:
            score = all(user.owns(r[col or 0]) for r in rset)
    score += user.matching_groups(cls.require_groups)
    if score:
        # add 1 so that an object with one matching group take priority
        # on an object without require_groups
        return score + 1 
    return 0
in_group_selector = deprecated_function(match_user_group)

@lltrace
def user_can_add_etype(cls, req, rset, row=None, col=None, **kwargs):
    """only check if the user has add access on the entity's type refered
    by the .etype attribute.
    """
    if not cls.schema.eschema(cls.etype).has_perm(req, 'add'):
        return 0
    return 1
add_etype_selector = deprecated_function(user_can_add_etype)

@lltrace
def match_context_prop(cls, req, rset, row=None, col=None, context=None,
                       **kwargs):
    propval = req.property_value('%s.%s.context' % (cls.__registry__, cls.id))
    if not propval:
        propval = cls.context
    if context is not None and propval is not None and context != propval:
        return 0
    return 1
contextprop_selector = deprecated_function(match_context_prop)

@lltrace
def primary_view(cls, req, rset, row=None, col=None, view=None,
                          **kwargs):
    if view is not None and not view.is_primary():
        return 0
    return 1
primaryview_selector = deprecated_function(primary_view)

def appobject_selectable(registry, oid):
    """return a selector that will have a positive score if an object for the
    given registry and object id is selectable for the input context
    """
    @lltrace
    def selector(cls, req, rset, *args, **kwargs):
        try:
            cls.vreg.select_object(registry, oid, req, rset, *args, **kwargs)
            return 1
        except NoSelectableObject:
            return 0
    return selector


# compound selectors ##########################################################

nfentity_selector = chainall(anyrset_selector, _nfentity_selector)
interface_selector = chainall(nfentity_selector, _interface_selector)

accept_selector = chainall(nfentity_selector, accept_rset_selector)
accept_one_selector = chainall(onelinerset_selector, accept_selector)

rqlcondition_selector = chainall(nfentity_selector,
                                 onelinerset_selector,
                                 _rqlcondition_selector)

searchstate_accept_selector = chainall(anyrset_selector, searchstate_selector,
                                       accept_selector)
searchstate_accept_one_selector = chainall(anyrset_selector, searchstate_selector,
                                           accept_selector, rqlcondition_selector)
searchstate_accept_one_but_etype_selector = chainall(searchstate_accept_one_selector,
                                                     but_etype_selector)

__all__ = [name for name in globals().keys() if name.endswith('selector')]
__all__ += ['chainall', 'chainfirst']
