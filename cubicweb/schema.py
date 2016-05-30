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
"""classes to define schemas for CubicWeb"""
from __future__ import print_function

__docformat__ = "restructuredtext en"

import re
from os.path import join, basename
from logging import getLogger
from warnings import warn

from six import PY2, text_type, string_types, add_metaclass
from six.moves import range

from logilab.common import tempattr
from logilab.common.decorators import cached, clear_cache, monkeypatch, cachedproperty
from logilab.common.logging_ext import set_log_methods
from logilab.common.deprecation import deprecated, class_moved, moved
from logilab.common.textutils import splitstrip
from logilab.common.graph import get_cycles

import yams
from yams import BadSchemaDefinition, buildobjs as ybo
from yams.schema import Schema, ERSchema, EntitySchema, RelationSchema, \
     RelationDefinitionSchema, PermissionMixIn, role_name
from yams.constraints import (BaseConstraint, FormatConstraint, BoundaryConstraint,
                              IntervalBoundConstraint, StaticVocabularyConstraint,
                              cstr_json_dumps, cstr_json_loads)
from yams.reader import (CONSTRAINTS, PyFileReader, SchemaLoader,
                         cleanup_sys_modules, fill_schema_from_namespace)

from rql import parse, nodes, RQLSyntaxError, TypeResolverException
from rql.analyze import ETypeResolver

import cubicweb
from cubicweb import ETYPE_NAME_MAP, ValidationError, Unauthorized, _

try:
    from cubicweb import server
except ImportError:
    # We need to lookup DEBUG from there,
    # however a pure dbapi client may not have it.
    class server(object): pass
    server.DEBUG = False


PURE_VIRTUAL_RTYPES = set(('identity', 'has_text',))
VIRTUAL_RTYPES = set(('eid', 'identity', 'has_text',))

# set of meta-relations available for every entity types
META_RTYPES = set((
    'owned_by', 'created_by', 'is', 'is_instance_of', 'identity',
    'eid', 'creation_date', 'cw_source', 'modification_date', 'has_text', 'cwuri',
    ))
WORKFLOW_RTYPES = set(('custom_workflow', 'in_state', 'wf_info_for'))
WORKFLOW_DEF_RTYPES = set(('workflow_of', 'state_of', 'transition_of',
                           'initial_state', 'default_workflow',
                           'allowed_transition', 'destination_state',
                           'from_state', 'to_state', 'condition',
                           'subworkflow', 'subworkflow_state', 'subworkflow_exit',
                           'by_transition',
                           ))
SYSTEM_RTYPES = set(('in_group', 'require_group',
                     # cwproperty
                     'for_user',
                     'cw_schema', 'cw_import_of', 'cw_for_source',
                     'cw_host_config_of',
                     )) | WORKFLOW_RTYPES
NO_I18NCONTEXT = META_RTYPES | WORKFLOW_RTYPES

SKIP_COMPOSITE_RELS = [('cw_source', 'subject')]

# set of entity and relation types used to build the schema
SCHEMA_TYPES = set((
    'CWEType', 'CWRType', 'CWComputedRType', 'CWAttribute', 'CWRelation',
    'CWConstraint', 'CWConstraintType', 'CWUniqueTogetherConstraint',
    'RQLExpression',
    'specializes',
    'relation_type', 'from_entity', 'to_entity',
    'constrained_by', 'cstrtype',
    'constraint_of', 'relations',
    'read_permission', 'add_permission',
    'delete_permission', 'update_permission',
    ))

WORKFLOW_TYPES = set(('Transition', 'State', 'TrInfo', 'Workflow',
                      'WorkflowTransition', 'BaseTransition',
                      'SubWorkflowExitPoint'))

INTERNAL_TYPES = set(('CWProperty', 'CWCache', 'ExternalUri', 'CWDataImport',
                      'CWSource', 'CWSourceHostConfig', 'CWSourceSchemaConfig'))

UNIQUE_CONSTRAINTS = ('SizeConstraint', 'FormatConstraint',
                      'StaticVocabularyConstraint',
                      'RQLVocabularyConstraint')

_LOGGER = getLogger('cubicweb.schemaloader')

# entity and relation schema created from serialized schema have an eid
ybo.ETYPE_PROPERTIES += ('eid',)
ybo.RTYPE_PROPERTIES += ('eid',)

def build_schema_from_namespace(items):
    schema = CubicWebSchema('noname')
    fill_schema_from_namespace(schema, items, register_base_types=False)
    return schema

# Bases for manipulating RQL in schema #########################################

def guess_rrqlexpr_mainvars(expression):
    defined = set(split_expression(expression))
    mainvars = set()
    if 'S' in defined:
        mainvars.add('S')
    if 'O' in defined:
        mainvars.add('O')
    if 'U' in defined:
        mainvars.add('U')
    if not mainvars:
        raise BadSchemaDefinition('unable to guess selection variables in %r'
                                  % expression)
    return mainvars

def split_expression(rqlstring):
    for expr in rqlstring.split(','):
        for noparen1 in expr.split('('):
            for noparen2 in noparen1.split(')'):
                for word in noparen2.split():
                    yield word

def normalize_expression(rqlstring):
    """normalize an rql expression to ease schema synchronization (avoid
    suppressing and reinserting an expression if only a space has been
    added/removed for instance)
    """
    union = parse(u'Any 1 WHERE %s' % rqlstring).as_string()
    if PY2 and isinstance(union, str):
        union = union.decode('utf-8')
    return union.split(' WHERE ', 1)[1]


def _check_valid_formula(rdef, formula_rqlst):
    """Check the formula is a valid RQL query with some restriction (no union,
    single selected node, etc.), raise BadSchemaDefinition if not
    """
    if len(formula_rqlst.children) != 1:
        raise BadSchemaDefinition('computed attribute %(attr)s on %(etype)s: '
                                  'can not use UNION in formula %(form)r' %
                                  {'attr' : rdef.rtype,
                                   'etype' : rdef.subject.type,
                                   'form' : rdef.formula})
    select = formula_rqlst.children[0]
    if len(select.selection) != 1:
        raise BadSchemaDefinition('computed attribute %(attr)s on %(etype)s: '
                                  'can only select one term in formula %(form)r' %
                                  {'attr' : rdef.rtype,
                                   'etype' : rdef.subject.type,
                                   'form' : rdef.formula})
    term = select.selection[0]
    types = set(term.get_type(sol) for sol in select.solutions)
    if len(types) != 1:
        raise BadSchemaDefinition('computed attribute %(attr)s on %(etype)s: '
                                  'multiple possible types (%(types)s) for formula %(form)r' %
                                  {'attr' : rdef.rtype,
                                   'etype' : rdef.subject.type,
                                   'types' : list(types),
                                   'form' : rdef.formula})
    computed_type = types.pop()
    expected_type = rdef.object.type
    if computed_type != expected_type:
        raise BadSchemaDefinition('computed attribute %(attr)s on %(etype)s: '
                                  'computed attribute type (%(comp_type)s) mismatch with '
                                  'specified type (%(attr_type)s)' %
                                  {'attr' : rdef.rtype,
                                   'etype' : rdef.subject.type,
                                   'comp_type' : computed_type,
                                   'attr_type' : expected_type})


class RQLExpression(object):
    """Base class for RQL expression used in schema (constraints and
    permissions)
    """
    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None
    # to be defined in concrete classes
    predefined_variables = None

    # Internal cache for parsed expressions
    _rql_cache = {}

    @classmethod
    def _cached_parse(cls, rql):
        try:
            return cls._rql_cache[rql]
        except KeyError:
            cls._rql_cache[rql] = parse(rql, print_errors=False).children[0]
            return cls._rql_cache[rql]

    def __init__(self, expression, mainvars, eid):
        """
        :type mainvars: sequence of RQL variables' names. Can be provided as a
                        comma separated string.
        :param mainvars: names of the variables being selected.

        """
        self.eid = eid # eid of the entity representing this rql expression
        assert mainvars, 'bad mainvars %s' % mainvars
        if isinstance(mainvars, string_types):
            mainvars = set(splitstrip(mainvars))
        elif not isinstance(mainvars, set):
            mainvars = set(mainvars)
        self.mainvars = mainvars
        self.expression = normalize_expression(expression)
        try:
            # syntax tree used by read security (inserted in queries when necessary)
            self.snippet_rqlst = self._cached_parse(self.minimal_rql)
        except RQLSyntaxError:
            raise RQLSyntaxError(expression)
        for mainvar in mainvars:
            if len(self.snippet_rqlst.defined_vars[mainvar].references()) < 2:
                _LOGGER.warn('You did not use the %s variable in your RQL '
                             'expression %s', mainvar, self)
        # graph of links between variables, used by rql rewriter
        self.vargraph = vargraph(self.snippet_rqlst)
        # useful for some instrumentation, e.g. localperms permcheck command
        self.package = ybo.PACKAGE

    def __str__(self):
        return self.rqlst.as_string()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.expression)

    def __lt__(self, other):
        if hasattr(other, 'expression'):
            return self.expression < other.expression
        return True

    def __eq__(self, other):
        if hasattr(other, 'expression'):
            return self.expression == other.expression
        return False

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.expression)

    def __deepcopy__(self, memo):
        return self.__class__(self.expression, self.mainvars)
    def __getstate__(self):
        return (self.expression, self.mainvars)
    def __setstate__(self, state):
        self.__init__(*state)

    @cachedproperty
    def rqlst(self):
        # Don't use _cached_parse here because the rqlst is modified
        select = parse(self.minimal_rql, print_errors=False).children[0]
        defined = set(split_expression(self.expression))
        for varname in self.predefined_variables:
            if varname in defined:
                select.add_eid_restriction(select.get_variable(varname), varname.lower(), 'Substitute')
        return select

    # permission rql expression specific stuff #################################

    @cached
    def transform_has_permission(self):
        found = None
        rqlst = self.rqlst
        for var in rqlst.defined_vars.values():
            for varref in var.references():
                rel = varref.relation()
                if rel is None:
                    continue
                try:
                    prefix, action, suffix = rel.r_type.split('_')
                except ValueError:
                    continue
                if prefix != 'has' or suffix != 'permission' or \
                       not action in ('add', 'delete', 'update', 'read'):
                    continue
                if found is None:
                    found = []
                    rqlst.save_state()
                assert rel.children[0].name == 'U'
                objvar = rel.children[1].children[0].variable
                rqlst.remove_node(rel)
                selected = [v.name for v in rqlst.get_selected_variables()]
                if objvar.name not in selected:
                    colindex = len(selected)
                    rqlst.add_selected(objvar)
                else:
                    colindex = selected.index(objvar.name)
                found.append((action, colindex))
                # remove U eid %(u)s if U is not used in any other relation
                uvrefs = rqlst.defined_vars['U'].references()
                if len(uvrefs) == 1:
                    rqlst.remove_node(uvrefs[0].relation())
        if found is not None:
            rql = rqlst.as_string()
            if len(rqlst.selection) == 1 and isinstance(rqlst.where, nodes.Relation):
                # only "Any X WHERE X eid %(x)s" remaining, no need to execute the rql
                keyarg = rqlst.selection[0].name.lower()
            else:
                keyarg = None
            rqlst.recover()
            return rql, found, keyarg
        return rqlst.as_string(), None, None

    def _check(self, _cw, **kwargs):
        """return True if the rql expression is matching the given relation
        between fromeid and toeid

        _cw may be a request or a server side transaction
        """
        creating = kwargs.get('creating')
        if not creating and self.eid is not None:
            key = (self.eid, tuple(sorted(kwargs.items())))
            try:
                return _cw.local_perm_cache[key]
            except KeyError:
                pass
        rql, has_perm_defs, keyarg = self.transform_has_permission()
        # when creating an entity, expression related to X satisfied
        if creating and 'X' in self.snippet_rqlst.defined_vars:
            return True
        if keyarg is None:
            kwargs.setdefault('u', _cw.user.eid)
            try:
                rset = _cw.execute(rql, kwargs, build_descr=True)
            except NotImplementedError:
                self.critical('cant check rql expression, unsupported rql %s', rql)
                if self.eid is not None:
                    _cw.local_perm_cache[key] = False
                return False
            except TypeResolverException as ex:
                # some expression may not be resolvable with current kwargs
                # (type conflict)
                self.warning('%s: %s', rql, str(ex))
                if self.eid is not None:
                    _cw.local_perm_cache[key] = False
                return False
            except Unauthorized as ex:
                self.debug('unauthorized %s: %s', rql, str(ex))
                if self.eid is not None:
                    _cw.local_perm_cache[key] = False
                return False
        else:
            rset = _cw.eid_rset(kwargs[keyarg])
        # if no special has_*_permission relation in the rql expression, just
        # check the result set contains something
        if has_perm_defs is None:
            if rset:
                if self.eid is not None:
                    _cw.local_perm_cache[key] = True
                return True
        elif rset:
            # check every special has_*_permission relation is satisfied
            get_eschema = _cw.vreg.schema.eschema
            try:
                for eaction, col in has_perm_defs:
                    for i in range(len(rset)):
                        eschema = get_eschema(rset.description[i][col])
                        eschema.check_perm(_cw, eaction, eid=rset[i][col])
                if self.eid is not None:
                    _cw.local_perm_cache[key] = True
                return True
            except Unauthorized:
                pass
        if self.eid is not None:
            _cw.local_perm_cache[key] = False
        return False

    @property
    def minimal_rql(self):
        return 'Any %s WHERE %s' % (','.join(sorted(self.mainvars)),
                                    self.expression)



# rql expressions for use in permission definition #############################

class ERQLExpression(RQLExpression):
    predefined_variables = 'XU'

    def __init__(self, expression, mainvars=None, eid=None):
        RQLExpression.__init__(self, expression, mainvars or 'X', eid)

    def check(self, _cw, eid=None, creating=False, **kwargs):
        if 'X' in self.snippet_rqlst.defined_vars:
            if eid is None:
                if creating:
                    return self._check(_cw, creating=True, **kwargs)
                return False
            assert creating == False
            return self._check(_cw, x=eid, **kwargs)
        return self._check(_cw, **kwargs)


class CubicWebRelationDefinitionSchema(RelationDefinitionSchema):
    def constraint_by_eid(self, eid):
        for cstr in self.constraints:
            if cstr.eid == eid:
                return cstr
        raise ValueError('No constraint with eid %d' % eid)

    def rql_expression(self, expression, mainvars=None, eid=None):
        """rql expression factory"""
        if self.rtype.final:
            return ERQLExpression(expression, mainvars, eid)
        return RRQLExpression(expression, mainvars, eid)

    def check_permission_definitions(self):
        super(CubicWebRelationDefinitionSchema, self).check_permission_definitions()
        schema = self.subject.schema
        for action, groups in self.permissions.items():
            for group_or_rqlexpr in groups:
                if action == 'read' and \
                       isinstance(group_or_rqlexpr, RQLExpression):
                    msg = "can't use rql expression for read permission of %s"
                    raise BadSchemaDefinition(msg % self)
                if self.final and isinstance(group_or_rqlexpr, RRQLExpression):
                    msg = "can't use RRQLExpression on %s, use an ERQLExpression"
                    raise BadSchemaDefinition(msg % self)
                if not self.final and isinstance(group_or_rqlexpr, ERQLExpression):
                    msg = "can't use ERQLExpression on %s, use a RRQLExpression"
                    raise BadSchemaDefinition(msg % self)

def vargraph(rqlst):
    """ builds an adjacency graph of variables from the rql syntax tree, e.g:
    Any O,S WHERE T subworkflow_exit S, T subworkflow WF, O state_of WF
    => {'WF': ['O', 'T'], 'S': ['T'], 'T': ['WF', 'S'], 'O': ['WF']}
    """
    vargraph = {}
    for relation in rqlst.get_nodes(nodes.Relation):
        try:
            rhsvarname = relation.children[1].children[0].variable.name
            lhsvarname = relation.children[0].name
        except AttributeError:
            pass
        else:
            vargraph.setdefault(lhsvarname, []).append(rhsvarname)
            vargraph.setdefault(rhsvarname, []).append(lhsvarname)
            #vargraph[(lhsvarname, rhsvarname)] = relation.r_type
    return vargraph


class GeneratedConstraint(object):
    def __init__(self, rqlst, mainvars):
        self.snippet_rqlst = rqlst
        self.mainvars = mainvars
        self.vargraph = vargraph(rqlst)


class RRQLExpression(RQLExpression):
    predefined_variables = 'SOU'

    def __init__(self, expression, mainvars=None, eid=None):
        if mainvars is None:
            mainvars = guess_rrqlexpr_mainvars(expression)
        RQLExpression.__init__(self, expression, mainvars, eid)

    def check(self, _cw, fromeid=None, toeid=None):
        kwargs = {}
        if 'S' in self.snippet_rqlst.defined_vars:
            if fromeid is None:
                return False
            kwargs['s'] = fromeid
        if 'O' in self.snippet_rqlst.defined_vars:
            if toeid is None:
                return False
            kwargs['o'] = toeid
        return self._check(_cw, **kwargs)


# In yams, default 'update' perm for attributes granted to managers and owners.
# Within cw, we want to default to users who may edit the entity holding the
# attribute.
# These default permissions won't be checked by the security hooks:
# since they delegate checking to the entity, we can skip actual checks.
ybo.DEFAULT_ATTRPERMS['update'] = ('managers', ERQLExpression('U has_update_permission X'))
ybo.DEFAULT_ATTRPERMS['add'] = ('managers', ERQLExpression('U has_add_permission X'))

# we don't want 'add' or 'delete' permissions on computed relation types
# (they're hardcoded to '()' on computed relation definitions)
if 'add' in yams.DEFAULT_COMPUTED_RELPERMS:
    del yams.DEFAULT_COMPUTED_RELPERMS['add']
if 'delete' in yams.DEFAULT_COMPUTED_RELPERMS:
    del yams.DEFAULT_COMPUTED_RELPERMS['delete']


PUB_SYSTEM_ENTITY_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    ('managers',),
    'delete': ('managers',),
    'update': ('managers',),
    }
PUB_SYSTEM_REL_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    ('managers',),
    'delete': ('managers',),
    }
PUB_SYSTEM_ATTR_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add': ('managers',),
    'update': ('managers',),
    }
RO_REL_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    (),
    'delete': (),
    }
RO_ATTR_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add': ybo.DEFAULT_ATTRPERMS['add'],
    'update': (),
    }

# XXX same algorithm as in reorder_cubes and probably other place,
# may probably extract a generic function
def order_eschemas(eschemas):
    """return entity schemas ordered such that entity types which specializes an
    other one appears after that one
    """
    graph = {}
    for eschema in eschemas:
        if eschema.specializes():
            graph[eschema] = set((eschema.specializes(),))
        else:
            graph[eschema] = set()
    cycles = get_cycles(graph)
    if cycles:
        cycles = '\n'.join(' -> '.join(cycle) for cycle in cycles)
        raise Exception('cycles in entity schema specialization: %s'
                        % cycles)
    eschemas = []
    while graph:
        # sorted to get predictable results
        for eschema, deps in sorted(graph.items()):
            if not deps:
                eschemas.append(eschema)
                del graph[eschema]
                for deps in graph.values():
                    try:
                        deps.remove(eschema)
                    except KeyError:
                        continue
    return eschemas

def bw_normalize_etype(etype):
    if etype in ETYPE_NAME_MAP:
        msg = '%s has been renamed to %s, please update your code' % (
            etype, ETYPE_NAME_MAP[etype])
        warn(msg, DeprecationWarning, stacklevel=4)
        etype = ETYPE_NAME_MAP[etype]
    return etype

def display_name(req, key, form='', context=None):
    """return a internationalized string for the key (schema entity or relation
    name) in a given form
    """
    assert form in ('', 'plural', 'subject', 'object')
    if form == 'subject':
        form = ''
    if form:
        key = key + '_' + form
    # ensure unicode
    if context is not None:
        return text_type(req.pgettext(context, key))
    else:
        return text_type(req._(key))


# Schema objects definition ###################################################

def ERSchema_display_name(self, req, form='', context=None):
    """return a internationalized string for the entity/relation type name in
    a given form
    """
    return display_name(req, self.type, form, context)
ERSchema.display_name = ERSchema_display_name

@cached
def get_groups(self, action):
    """return the groups authorized to perform <action> on entities of
    this type

    :type action: str
    :param action: the name of a permission

    :rtype: tuple
    :return: names of the groups with the given permission
    """
    assert action in self.ACTIONS, action
    #assert action in self._groups, '%s %s' % (self, action)
    try:
        return frozenset(g for g in self.permissions[action] if isinstance(g, string_types))
    except KeyError:
        return ()
PermissionMixIn.get_groups = get_groups

@cached
def get_rqlexprs(self, action):
    """return the rql expressions representing queries to check the user is allowed
    to perform <action> on entities of this type

    :type action: str
    :param action: the name of a permission

    :rtype: tuple
    :return: the rql expressions with the given permission
    """
    assert action in self.ACTIONS, action
    #assert action in self._rqlexprs, '%s %s' % (self, action)
    try:
        return tuple(g for g in self.permissions[action] if not isinstance(g, string_types))
    except KeyError:
        return ()
PermissionMixIn.get_rqlexprs = get_rqlexprs

orig_set_action_permissions = PermissionMixIn.set_action_permissions
def set_action_permissions(self, action, permissions):
    """set the groups and rql expressions allowing to perform <action> on
    entities of this type

    :type action: str
    :param action: the name of a permission

    :type permissions: tuple
    :param permissions: the groups and rql expressions allowing the given action
    """
    orig_set_action_permissions(self, action, tuple(permissions))
    clear_cache(self, 'get_rqlexprs')
    clear_cache(self, 'get_groups')
PermissionMixIn.set_action_permissions = set_action_permissions

def has_local_role(self, action):
    """return true if the action *may* be granted locally (i.e. either rql
    expressions or the owners group are used in security definition)

    XXX this method is only there since we don't know well how to deal with
    'add' action checking. Also find a better name would be nice.
    """
    assert action in self.ACTIONS, action
    if self.get_rqlexprs(action):
        return True
    if action in ('update', 'delete'):
        return 'owners' in self.get_groups(action)
    return False
PermissionMixIn.has_local_role = has_local_role

def may_have_permission(self, action, req):
    if action != 'read' and not (self.has_local_role('read') or
                                 self.has_perm(req, 'read')):
        return False
    return self.has_local_role(action) or self.has_perm(req, action)
PermissionMixIn.may_have_permission = may_have_permission

def has_perm(self, _cw, action, **kwargs):
    """return true if the action is granted globally or locally"""
    try:
        self.check_perm(_cw, action, **kwargs)
        return True
    except Unauthorized:
        return False
PermissionMixIn.has_perm = has_perm


def check_perm(self, _cw, action, **kwargs):
    # NB: _cw may be a server transaction or a request object.
    #
    # check user is in an allowed group, if so that's enough internal
    # transactions should always stop there
    DBG = False
    if server.DEBUG & server.DBG_SEC:
        if action in server._SECURITY_CAPS:
            _self_str = str(self)
            if server._SECURITY_ITEMS:
                if any(item in _self_str for item in server._SECURITY_ITEMS):
                    DBG = True
            else:
                DBG = True
    groups = self.get_groups(action)
    if _cw.user.matching_groups(groups):
        if DBG:
            print('check_perm: %r %r: user matches %s' % (action, _self_str, groups))
        return
    # if 'owners' in allowed groups, check if the user actually owns this
    # object, if so that's enough
    #
    # NB: give _cw to user.owns since user is not be bound to a transaction on
    # the repository side
    if 'owners' in groups and (
          kwargs.get('creating')
          or ('eid' in kwargs and _cw.user.owns(kwargs['eid']))):
        if DBG:
            print('check_perm: %r %r: user is owner or creation time' %
                  (action, _self_str))
        return
    # else if there is some rql expressions, check them
    if DBG:
        print('check_perm: %r %r %s' %
              (action, _self_str, [(rqlexpr, kwargs, rqlexpr.check(_cw, **kwargs))
                                   for rqlexpr in self.get_rqlexprs(action)]))
    if any(rqlexpr.check(_cw, **kwargs)
           for rqlexpr in self.get_rqlexprs(action)):
        return
    raise Unauthorized(action, str(self))
PermissionMixIn.check_perm = check_perm


CubicWebRelationDefinitionSchema._RPROPERTIES['eid'] = None
# remember rproperties defined at this point. Others will have to be serialized in
# CWAttribute.extra_props
KNOWN_RPROPERTIES = CubicWebRelationDefinitionSchema.ALL_PROPERTIES()


class CubicWebEntitySchema(EntitySchema):
    """a entity has a type, a set of subject and or object relations
    the entity schema defines the possible relations for a given type and some
    constraints on those relations
    """
    def __init__(self, schema=None, edef=None, eid=None, **kwargs):
        super(CubicWebEntitySchema, self).__init__(schema, edef, **kwargs)
        if eid is None and edef is not None:
            eid = getattr(edef, 'eid', None)
        self.eid = eid

    def targets(self, role):
        assert role in ('subject', 'object')
        if role == 'subject':
            return self.subjrels.values()
        return self.objrels.values()

    @cachedproperty
    def composite_rdef_roles(self):
        """Return all relation definitions that define the current entity
        type as a composite.
        """
        rdef_roles = []
        for role in ('subject', 'object'):
            for rschema in self.targets(role):
                if rschema.final:
                    continue
                for rdef in rschema.rdefs.values():
                    if (role == 'subject' and rdef.subject == self) or \
                            (role == 'object' and rdef.object == self):
                        crole = rdef.composite
                        if crole == role:
                            rdef_roles.append((rdef, role))
        return rdef_roles

    @cachedproperty
    def is_composite(self):
        return bool(len(self.composite_rdef_roles))

    def check_permission_definitions(self):
        super(CubicWebEntitySchema, self).check_permission_definitions()
        for groups in self.permissions.values():
            for group_or_rqlexpr in groups:
                if isinstance(group_or_rqlexpr, RRQLExpression):
                    msg = "can't use RRQLExpression on %s, use an ERQLExpression"
                    raise BadSchemaDefinition(msg % self.type)

    def is_subobject(self, strict=False, skiprels=None):
        if skiprels is None:
            skiprels = SKIP_COMPOSITE_RELS
        else:
            skiprels += SKIP_COMPOSITE_RELS
        return super(CubicWebEntitySchema, self).is_subobject(strict,
                                                              skiprels=skiprels)

    def attribute_definitions(self):
        """return an iterator on attribute definitions

        attribute relations are a subset of subject relations where the
        object's type is a final entity

        an attribute definition is a 2-uple :
        * name of the relation
        * schema of the destination entity type
        """
        iter = super(CubicWebEntitySchema, self).attribute_definitions()
        for rschema, attrschema in iter:
            if rschema.type == 'has_text':
                continue
            yield rschema, attrschema

    def main_attribute(self):
        """convenience method that returns the *main* (i.e. the first non meta)
        attribute defined in the entity schema
        """
        for rschema, _ in self.attribute_definitions():
            if not (rschema in META_RTYPES
                    or self.is_metadata(rschema)):
                return rschema

    def add_subject_relation(self, rschema):
        """register the relation schema as possible subject relation"""
        super(CubicWebEntitySchema, self).add_subject_relation(rschema)
        if rschema.final:
            if self.rdef(rschema).get('fulltextindexed'):
                self._update_has_text()
        elif rschema.fulltext_container:
            self._update_has_text()

    def add_object_relation(self, rschema):
        """register the relation schema as possible object relation"""
        super(CubicWebEntitySchema, self).add_object_relation(rschema)
        if rschema.fulltext_container:
            self._update_has_text()

    def del_subject_relation(self, rtype):
        super(CubicWebEntitySchema, self).del_subject_relation(rtype)
        if 'has_text' in self.subjrels:
            self._update_has_text(deletion=True)

    def del_object_relation(self, rtype):
        super(CubicWebEntitySchema, self).del_object_relation(rtype)
        if 'has_text' in self.subjrels:
            self._update_has_text(deletion=True)

    def _update_has_text(self, deletion=False):
        may_need_has_text, has_has_text = False, False
        need_has_text = None
        for rschema in self.subject_relations():
            if rschema.final:
                if rschema == 'has_text':
                    has_has_text = True
                elif self.rdef(rschema).get('fulltextindexed'):
                    may_need_has_text = True
            elif rschema.fulltext_container:
                if rschema.fulltext_container == 'subject':
                    may_need_has_text = True
                else:
                    need_has_text = False
        for rschema in self.object_relations():
            if rschema.fulltext_container:
                if rschema.fulltext_container == 'object':
                    may_need_has_text = True
                else:
                    need_has_text = False
        if need_has_text is None:
            need_has_text = may_need_has_text
        if need_has_text and not has_has_text and not deletion:
            rdef = ybo.RelationDefinition(self.type, 'has_text', 'String',
                                          __permissions__=RO_ATTR_PERMS)
            self.schema.add_relation_def(rdef)
        elif not need_has_text and has_has_text:
            # use rschema.del_relation_def and not schema.del_relation_def to
            # avoid deleting the relation type accidentally...
            self.schema['has_text'].del_relation_def(self, self.schema['String'])

    def schema_entity(self): # XXX @property for consistency with meta
        """return True if this entity type is used to build the schema"""
        return self.type in SCHEMA_TYPES

    def rql_expression(self, expression, mainvars=None, eid=None):
        """rql expression factory"""
        return ERQLExpression(expression, mainvars, eid)


class CubicWebRelationSchema(PermissionMixIn, RelationSchema):
    permissions = {}
    ACTIONS = ()
    rdef_class = CubicWebRelationDefinitionSchema

    def __init__(self, schema=None, rdef=None, eid=None, **kwargs):
        if rdef is not None:
            # if this relation is inlined
            self.inlined = rdef.inlined
        super(CubicWebRelationSchema, self).__init__(schema, rdef, **kwargs)
        if eid is None and rdef is not None:
            eid = getattr(rdef, 'eid', None)
        self.eid = eid

    def init_computed_relation(self, rdef):
        self.ACTIONS = ('read',)
        super(CubicWebRelationSchema, self).init_computed_relation(rdef)

    def advertise_new_add_permission(self):
        pass

    def check_permission_definitions(self):
        RelationSchema.check_permission_definitions(self)
        PermissionMixIn.check_permission_definitions(self)

    @property
    def meta(self):
        return self.type in META_RTYPES

    def schema_relation(self): # XXX @property for consistency with meta
        """return True if this relation type is used to build the schema"""
        return self.type in SCHEMA_TYPES

    def may_have_permission(self, action, req, eschema=None, role=None):
        if eschema is not None:
            for tschema in self.targets(eschema, role):
                rdef = self.role_rdef(eschema, tschema, role)
                if rdef.may_have_permission(action, req):
                    return True
        else:
            for rdef in self.rdefs.values():
                if rdef.may_have_permission(action, req):
                    return True
        return False

    def has_perm(self, _cw, action, **kwargs):
        """return true if the action is granted globally or locally"""
        if self.final:
            assert not ('fromeid' in kwargs or 'toeid' in kwargs), kwargs
            assert action in ('read', 'update')
            if 'eid' in kwargs:
                subjtype = _cw.entity_metas(kwargs['eid'])['type']
            else:
                subjtype = objtype = None
        else:
            assert not 'eid' in kwargs, kwargs
            assert action in ('read', 'add', 'delete')
            if 'fromeid' in kwargs:
                subjtype = _cw.entity_metas(kwargs['fromeid'])['type']
            elif 'frometype' in kwargs:
                subjtype = kwargs.pop('frometype')
            else:
                subjtype = None
            if 'toeid' in kwargs:
                objtype = _cw.entity_metas(kwargs['toeid'])['type']
            elif 'toetype' in kwargs:
                objtype = kwargs.pop('toetype')
            else:
                objtype = None
        if objtype and subjtype:
            return self.rdef(subjtype, objtype).has_perm(_cw, action, **kwargs)
        elif subjtype:
            for tschema in self.targets(subjtype, 'subject'):
                rdef = self.rdef(subjtype, tschema)
                if not rdef.has_perm(_cw, action, **kwargs):
                    return False
        elif objtype:
            for tschema in self.targets(objtype, 'object'):
                rdef = self.rdef(tschema, objtype)
                if not rdef.has_perm(_cw, action, **kwargs):
                    return False
        else:
            for rdef in self.rdefs.values():
                if not rdef.has_perm(_cw, action, **kwargs):
                    return False
        return True

    @deprecated('use .rdef(subjtype, objtype).role_cardinality(role)')
    def cardinality(self, subjtype, objtype, target):
        return self.rdef(subjtype, objtype).role_cardinality(target)


class CubicWebSchema(Schema):
    """set of entities and relations schema defining the possible data sets
    used in an application

    :type name: str
    :ivar name: name of the schema, usually the instance identifier

    :type base: str
    :ivar base: path of the directory where the schema is defined
    """
    reading_from_database = False
    entity_class = CubicWebEntitySchema
    relation_class = CubicWebRelationSchema
    no_specialization_inference = ('identity',)

    def __init__(self, *args, **kwargs):
        self._eid_index = {}
        super(CubicWebSchema, self).__init__(*args, **kwargs)
        ybo.register_base_types(self)
        rschema = self.add_relation_type(ybo.RelationType('eid'))
        rschema.final = True
        rschema = self.add_relation_type(ybo.RelationType('has_text'))
        rschema.final = True
        rschema = self.add_relation_type(ybo.RelationType('identity'))
        rschema.final = False

    etype_name_re = r'[A-Z][A-Za-z0-9]*[a-z]+[A-Za-z0-9]*$'
    def add_entity_type(self, edef):
        edef.name = str(edef.name)
        edef.name = bw_normalize_etype(edef.name)
        if not re.match(self.etype_name_re, edef.name):
            raise BadSchemaDefinition(
                '%r is not a valid name for an entity type. It should start '
                'with an upper cased letter and be followed by at least a '
                'lower cased letter' % edef.name)
        eschema = super(CubicWebSchema, self).add_entity_type(edef)
        if not eschema.final:
            # automatically add the eid relation to non final entity types
            rdef = ybo.RelationDefinition(eschema.type, 'eid', 'Int',
                                          cardinality='11', uid=True,
                                          __permissions__=RO_ATTR_PERMS)
            self.add_relation_def(rdef)
            rdef = ybo.RelationDefinition(eschema.type, 'identity', eschema.type,
                                          __permissions__=RO_REL_PERMS)
            self.add_relation_def(rdef)
        self._eid_index[eschema.eid] = eschema
        return eschema

    def add_relation_type(self, rdef):
        if not rdef.name.islower():
            raise BadSchemaDefinition(
                '%r is not a valid name for a relation type. It should be '
                'lower cased' % rdef.name)
        rdef.name = str(rdef.name)
        rschema = super(CubicWebSchema, self).add_relation_type(rdef)
        self._eid_index[rschema.eid] = rschema
        return rschema

    def add_relation_def(self, rdef):
        """build a part of a relation schema
        (i.e. add a relation between two specific entity's types)

        :type subject: str
        :param subject: entity's type that is subject of the relation

        :type rtype: str
        :param rtype: the relation's type (i.e. the name of the relation)

        :type obj: str
        :param obj: entity's type that is object of the relation

        :rtype: RelationSchema
        :param: the newly created or just completed relation schema
        """
        rdef.name = rdef.name.lower()
        rdef.subject = bw_normalize_etype(rdef.subject)
        rdef.object = bw_normalize_etype(rdef.object)
        rdefs = super(CubicWebSchema, self).add_relation_def(rdef)
        if rdefs:
            try:
                self._eid_index[rdef.eid] = rdefs
            except AttributeError:
                pass # not a serialized schema
        return rdefs

    def del_relation_type(self, rtype):
        rschema = self.rschema(rtype)
        self._eid_index.pop(rschema.eid, None)
        super(CubicWebSchema, self).del_relation_type(rtype)

    def del_relation_def(self, subjtype, rtype, objtype):
        for k, v in self._eid_index.items():
            if not isinstance(v, RelationDefinitionSchema):
                continue
            if v.subject == subjtype and v.rtype == rtype and v.object == objtype:
                del self._eid_index[k]
                break
        super(CubicWebSchema, self).del_relation_def(subjtype, rtype, objtype)

    def del_entity_type(self, etype):
        eschema = self.eschema(etype)
        self._eid_index.pop(eschema.eid, None)
        # deal with has_text first, else its automatic deletion (see above)
        # may trigger an error in ancestor's del_entity_type method
        if 'has_text' in eschema.subject_relations():
            self.del_relation_def(etype, 'has_text', 'String')
        super(CubicWebSchema, self).del_entity_type(etype)

    def schema_by_eid(self, eid):
        return self._eid_index[eid]

    def iter_computed_attributes(self):
        for relation in self.relations():
            for rdef in relation.rdefs.values():
                if rdef.final and rdef.formula is not None:
                    yield rdef

    def iter_computed_relations(self):
        for relation in self.relations():
            if relation.rule:
                yield relation

    def finalize(self):
        super(CubicWebSchema, self).finalize()
        self.finalize_computed_attributes()
        self.finalize_computed_relations()

    def finalize_computed_attributes(self):
        """Check computed attributes validity (if any), else raise
        `BadSchemaDefinition`
        """
        analyzer = ETypeResolver(self)
        for rdef in self.iter_computed_attributes():
            rqlst = parse(rdef.formula)
            select = rqlst.children[0]
            select.add_type_restriction(select.defined_vars['X'], str(rdef.subject))
            analyzer.visit(select)
            _check_valid_formula(rdef, rqlst)
            rdef.formula_select = select # avoid later recomputation


    def finalize_computed_relations(self):
        """Build relation definitions for computed relations

        The subject and object types are infered using rql analyzer.
        """
        analyzer = ETypeResolver(self)
        for rschema in self.iter_computed_relations():
            # XXX rule is valid if both S and O are defined and not in an exists
            rqlexpr = RRQLExpression(rschema.rule)
            rqlst = rqlexpr.snippet_rqlst
            analyzer.visit(rqlst)
            couples = set((sol['S'], sol['O']) for sol in rqlst.solutions)
            for subjtype, objtype in couples:
                if self[objtype].final:
                    raise BadSchemaDefinition('computed relations cannot be final')
                rdef = ybo.RelationDefinition(
                    subjtype, rschema.type, objtype,
                    __permissions__={'add': (),
                                     'delete': (),
                                     'read': rschema.permissions['read']})
                rdef.infered = True
                self.add_relation_def(rdef)

    def rebuild_infered_relations(self):
        super(CubicWebSchema, self).rebuild_infered_relations()
        self.finalize_computed_attributes()
        self.finalize_computed_relations()


# additional cw specific constraints ###########################################

class BaseRQLConstraint(RRQLExpression, BaseConstraint):
    """base class for rql constraints"""
    distinct_query = None

    def serialize(self):
        return cstr_json_dumps({u'mainvars': sorted(self.mainvars),
                                u'expression': self.expression})

    @classmethod
    def deserialize(cls, value):
        try:
            d = cstr_json_loads(value)
            return cls(d['expression'], d['mainvars'])
        except ValueError:
            _, mainvars, expression = value.split(';', 2)
            return cls(expression, mainvars)

    def check(self, entity, rtype, value):
        """return true if the value satisfy the constraint, else false"""
        # implemented as a hook in the repository
        return 1

    def __str__(self):
        if self.distinct_query:
            selop = 'Any'
        else:
            selop = 'DISTINCT Any'
        return '%s(%s %s WHERE %s)' % (self.__class__.__name__, selop,
                                       ','.join(sorted(self.mainvars)),
                                       self.expression)

    def __repr__(self):
        return '<%s @%#x>' % (self.__str__(), id(self))


class RQLVocabularyConstraint(BaseRQLConstraint):
    """the rql vocabulary constraint:

    limits the proposed values to a set of entities returned by an rql query,
    but this is not enforced at the repository level

    `expression` is an additional rql restriction that will be added to
    a predefined query, where the S and O variables respectively represent
    the subject and the object of the relation

    `mainvars` is a set of variables that should be used as selection variables
    (i.e. `'Any %s WHERE ...' % mainvars`). If not specified, an attempt will be
    made to guess it based on the variables used in the expression.
    """

    def repo_check(self, session, eidfrom, rtype, eidto):
        """raise ValidationError if the relation doesn't satisfy the constraint
        """
        pass # this is a vocabulary constraint, not enforced


class RepoEnforcedRQLConstraintMixIn(object):

    def __init__(self, expression, mainvars=None, msg=None):
        super(RepoEnforcedRQLConstraintMixIn, self).__init__(expression, mainvars)
        self.msg = msg

    def serialize(self):
        return cstr_json_dumps({
            u'mainvars': sorted(self.mainvars),
            u'expression': self.expression,
            u'msg': self.msg})

    @classmethod
    def deserialize(cls, value):
        try:
            d = cstr_json_loads(value)
            return cls(d['expression'], d['mainvars'], d['msg'])
        except ValueError:
            value, msg = value.split('\n', 1)
            _, mainvars, expression = value.split(';', 2)
            return cls(expression, mainvars, msg)

    def repo_check(self, session, eidfrom, rtype, eidto=None):
        """raise ValidationError if the relation doesn't satisfy the constraint
        """
        if not self.match_condition(session, eidfrom, eidto):
            # XXX at this point if both or neither of S and O are in mainvar we
            # dunno if the validation error `occurred` on eidfrom or eidto (from
            # user interface point of view)
            #
            # possible enhancement: check entity being created, it's probably
            # the main eid unless this is a composite relation
            if eidto is None or 'S' in self.mainvars or not 'O' in self.mainvars:
                maineid = eidfrom
                qname = role_name(rtype, 'subject')
            else:
                maineid = eidto
                qname = role_name(rtype, 'object')
            if self.msg:
                msg = session._(self.msg)
            else:
                msg = '%(constraint)s %(expression)s failed' % {
                    'constraint':  session._(self.type()),
                    'expression': self.expression}
            raise ValidationError(maineid, {qname: msg})

    def exec_query(self, _cw, eidfrom, eidto):
        if eidto is None:
            # checking constraint for an attribute relation
            expression = 'S eid %(s)s, ' + self.expression
            args = {'s': eidfrom}
        else:
            expression = 'S eid %(s)s, O eid %(o)s, ' + self.expression
            args = {'s': eidfrom, 'o': eidto}
        if 'U' in self.snippet_rqlst.defined_vars:
            expression = 'U eid %(u)s, ' + expression
            args['u'] = _cw.user.eid
        rql = 'Any %s WHERE %s' % (','.join(sorted(self.mainvars)), expression)
        if self.distinct_query:
            rql = 'DISTINCT ' + rql
        return _cw.execute(rql, args, build_descr=False)


class RQLConstraint(RepoEnforcedRQLConstraintMixIn, BaseRQLConstraint):
    """the rql constraint is similar to the RQLVocabularyConstraint but
    are also enforced at the repository level
    """
    distinct_query = False

    def match_condition(self, session, eidfrom, eidto):
        return self.exec_query(session, eidfrom, eidto)


class RQLUniqueConstraint(RepoEnforcedRQLConstraintMixIn, BaseRQLConstraint):
    """the unique rql constraint check that the result of the query isn't
    greater than one.

    You *must* specify `mainvars` when instantiating the constraint since there
    is no way to guess it correctly (e.g. if using S,O or U the constraint will
    always be satisfied because we've to use a DISTINCT query).
    """
    # XXX turns mainvars into a required argument in __init__
    distinct_query = True

    def match_condition(self, session, eidfrom, eidto):
        return len(self.exec_query(session, eidfrom, eidto)) <= 1


# workflow extensions #########################################################

from yams.buildobjs import _add_relation as yams_add_relation

class workflowable_definition(ybo.metadefinition):
    """extends default EntityType's metaclass to add workflow relations
    (i.e. in_state, wf_info_for and custom_workflow). This is the default
    metaclass for WorkflowableEntityType.
    """
    def __new__(mcs, name, bases, classdict):
        abstract = classdict.pop('__abstract__', False)
        cls = super(workflowable_definition, mcs).__new__(mcs, name, bases,
                                                          classdict)
        if not abstract:
            make_workflowable(cls)
        return cls


@add_metaclass(workflowable_definition)
class WorkflowableEntityType(ybo.EntityType):
    """Use this base class instead of :class:`EntityType` to have workflow
    relations (i.e. `in_state`, `wf_info_for` and `custom_workflow`) on your
    entity type.
    """
    __abstract__ = True


def make_workflowable(cls, in_state_descr=None):
    """Adds workflow relations as :class:`WorkflowableEntityType`, but usable on
    existing classes which are not using that base class.
    """
    existing_rels = set(rdef.name for rdef in cls.__relations__)
    # let relation types defined in cw.schemas.workflow carrying
    # cardinality, constraints and other relation definition properties
    etype = getattr(cls, 'name', cls.__name__)
    if 'custom_workflow' not in existing_rels:
        rdef = ybo.RelationDefinition(etype, 'custom_workflow', 'Workflow')
        yams_add_relation(cls.__relations__, rdef)
    if 'in_state' not in existing_rels:
        rdef = ybo.RelationDefinition(etype, 'in_state', 'State',
                                      description=in_state_descr)
        yams_add_relation(cls.__relations__, rdef)
    if 'wf_info_for' not in existing_rels:
        rdef = ybo.RelationDefinition('TrInfo', 'wf_info_for', etype)
        yams_add_relation(cls.__relations__, rdef)


# schema loading ##############################################################

CONSTRAINTS['RQLConstraint'] = RQLConstraint
CONSTRAINTS['RQLUniqueConstraint'] = RQLUniqueConstraint
CONSTRAINTS['RQLVocabularyConstraint'] = RQLVocabularyConstraint
CONSTRAINTS.pop('MultipleStaticVocabularyConstraint', None) # don't want this in cw yams schema
PyFileReader.context.update(CONSTRAINTS)


class BootstrapSchemaLoader(SchemaLoader):
    """cubicweb specific schema loader, loading only schema necessary to read
    the persistent schema
    """
    schemacls = CubicWebSchema

    def load(self, config, path=(), **kwargs):
        """return a Schema instance from the schema definition read
        from <directory>
        """
        return super(BootstrapSchemaLoader, self).load(
            path, config.appid, register_base_types=False, **kwargs)

    def _load_definition_files(self, cubes=None):
        # bootstraping, ignore cubes
        filepath = join(cubicweb.CW_SOFTWARE_ROOT, 'schemas', 'bootstrap.py')
        self.info('loading %s', filepath)
        with tempattr(ybo, 'PACKAGE', 'cubicweb'): # though we don't care here
            self.handle_file(filepath)

    def unhandled_file(self, filepath):
        """called when a file without handler associated has been found"""
        self.warning('ignoring file %r', filepath)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

class CubicWebSchemaLoader(BootstrapSchemaLoader):
    """cubicweb specific schema loader, automatically adding metadata to the
    instance's schema
    """

    def load(self, config, **kwargs):
        """return a Schema instance from the schema definition read
        from <directory>
        """
        self.info('loading %s schemas', ', '.join(config.cubes()))
        self.extrapath = {}
        for cubesdir in config.cubes_search_path():
            if cubesdir != config.CUBES_DIR:
                self.extrapath[cubesdir] = 'cubes'
        if config.apphome:
            path = tuple(reversed([config.apphome] + config.cubes_path()))
        else:
            path = tuple(reversed(config.cubes_path()))
        try:
            return super(CubicWebSchemaLoader, self).load(config, path=path, **kwargs)
        finally:
            # we've to cleanup modules imported from cubicweb.schemas as well
            cleanup_sys_modules([join(cubicweb.CW_SOFTWARE_ROOT, 'schemas')])

    def _load_definition_files(self, cubes):
        for filepath in (join(cubicweb.CW_SOFTWARE_ROOT, 'schemas', 'bootstrap.py'),
                         join(cubicweb.CW_SOFTWARE_ROOT, 'schemas', 'base.py'),
                         join(cubicweb.CW_SOFTWARE_ROOT, 'schemas', 'workflow.py'),
                         join(cubicweb.CW_SOFTWARE_ROOT, 'schemas', 'Bookmark.py')):
            self.info('loading %s', filepath)
            with tempattr(ybo, 'PACKAGE', 'cubicweb'):
                self.handle_file(filepath)
        for cube in cubes:
            for filepath in self.get_schema_files(cube):
                with tempattr(ybo, 'PACKAGE', basename(cube)):
                    self.handle_file(filepath)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None


set_log_methods(CubicWebSchemaLoader, getLogger('cubicweb.schemaloader'))
set_log_methods(BootstrapSchemaLoader, getLogger('cubicweb.bootstrapschemaloader'))
set_log_methods(RQLExpression, getLogger('cubicweb.schema'))

# _() is just there to add messages to the catalog, don't care about actual
# translation
MAY_USE_TEMPLATE_FORMAT = set(('managers',))
NEED_PERM_FORMATS = [_('text/cubicweb-page-template')]

@monkeypatch(FormatConstraint)
def vocabulary(self, entity=None, form=None):
    cw = None
    if form is None and entity is not None:
        cw = entity._cw
    elif form is not None:
        cw = form._cw
    if cw is not None:
        if hasattr(cw, 'write_security'): # test it's a session and not a request
            # cw is a server session
            hasperm = not cw.write_security or \
                      not cw.is_hook_category_activated('integrity') or \
                      cw.user.matching_groups(MAY_USE_TEMPLATE_FORMAT)
        else:
            hasperm = cw.user.matching_groups(MAY_USE_TEMPLATE_FORMAT)
        if hasperm:
            return self.regular_formats + tuple(NEED_PERM_FORMATS)
    return self.regular_formats

# XXX itou for some Statement methods
from rql import stmts
orig_get_etype = stmts.ScopeNode.get_etype
def bw_get_etype(self, name):
    return orig_get_etype(self, bw_normalize_etype(name))
stmts.ScopeNode.get_etype = bw_get_etype

orig_add_main_variable_delete = stmts.Delete.add_main_variable
def bw_add_main_variable_delete(self, etype, vref):
    return orig_add_main_variable_delete(self, bw_normalize_etype(etype), vref)
stmts.Delete.add_main_variable = bw_add_main_variable_delete

orig_add_main_variable_insert = stmts.Insert.add_main_variable
def bw_add_main_variable_insert(self, etype, vref):
    return orig_add_main_variable_insert(self, bw_normalize_etype(etype), vref)
stmts.Insert.add_main_variable = bw_add_main_variable_insert

orig_set_statement_type = stmts.Select.set_statement_type
def bw_set_statement_type(self, etype):
    return orig_set_statement_type(self, bw_normalize_etype(etype))
stmts.Select.set_statement_type = bw_set_statement_type
