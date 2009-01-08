"""classes to define schemas for CubicWeb

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import warnings
import re
from logging import getLogger

from logilab.common.decorators import cached, clear_cache
from logilab.common.compat import any

from yams import BadSchemaDefinition, buildobjs as ybo
from yams.schema import Schema, ERSchema, EntitySchema, RelationSchema
from yams.constraints import BaseConstraint, StaticVocabularyConstraint
from yams.reader import (CONSTRAINTS, RelationFileReader, PyFileReader,
                         SchemaLoader)

from rql import parse, nodes, RQLSyntaxError, TypeResolverException

from cubicweb import ETYPE_NAME_MAP, ValidationError, Unauthorized

_ = unicode

BASEGROUPS = ('managers', 'users', 'guests', 'owners')

LOGGER = getLogger('cubicweb.schemaloader')

# schema entities created from serialized schema have an eid rproperty
ybo.ETYPE_PROPERTIES += ('eid',)
ybo.RTYPE_PROPERTIES += ('eid',)
ybo.RDEF_PROPERTIES += ('eid',)

def bw_normalize_etype(etype):
    if etype in ETYPE_NAME_MAP:
        from warnings import warn
        msg = '%s has been renamed to %s, please update your code' % (
            etype, ETYPE_NAME_MAP[etype])            
        warn(msg, DeprecationWarning, stacklevel=4)
        etype = ETYPE_NAME_MAP[etype]
    return etype

# monkey path yams.builder.RelationDefinition to support a new wildcard type '@'
# corresponding to system entity (ie meta but not schema)
def _actual_types(self, schema, etype):
    # two bits of error checking & reporting :
    if type(etype) not in (str, list, tuple):
        raise RuntimeError, ('Entity types must not be instances but strings or'
                             ' list/tuples thereof. Ex. (bad, good) : '
                             'SubjectRelation(Foo), SubjectRelation("Foo"). '
                             'Hence, %r is not acceptable.' % etype)
    # real work :
    if etype == '**':
        return self._pow_etypes(schema)
    if isinstance(etype, (tuple, list)):
        return etype
    if '*' in etype or '@' in etype:
        assert len(etype) in (1, 2)
        etypes = ()
        if '*' in etype:
            etypes += tuple(self._wildcard_etypes(schema))
        if '@' in etype:
            etypes += tuple(system_etypes(schema))
        return etypes
    return (etype,)
ybo.RelationDefinition._actual_types = _actual_types

def display_name(req, key, form=''):
    """return a internationalized string for the key (schema entity or relation
    name) in a given form
    """
    assert form in ('', 'plural', 'subject', 'object')
    if form == 'subject':
        form = ''
    if form:
        key = key + '_' + form
    # ensure unicode
    # added .lower() in case no translation are available
    return unicode(req._(key)).lower()
__builtins__['display_name'] = display_name

def ERSchema_display_name(self, req, form=''):
    """return a internationalized string for the entity/relation type name in
    a given form
    """
    return display_name(req, self.type, form)
ERSchema.display_name = ERSchema_display_name

@cached
def ERSchema_get_groups(self, action):
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
        return frozenset(g for g in self._groups[action] if isinstance(g, basestring))
    except KeyError:
        return ()
ERSchema.get_groups = ERSchema_get_groups

def ERSchema_set_groups(self, action, groups):
    """set the groups allowed to perform <action> on entities of this type. Don't
    change rql expressions for the same action.

    :type action: str
    :param action: the name of a permission

    :type groups: list or tuple
    :param groups: names of the groups granted to do the given action
    """
    assert action in self.ACTIONS, action
    clear_cache(self, 'ERSchema_get_groups')
    self._groups[action] = tuple(groups) + self.get_rqlexprs(action)
ERSchema.set_groups = ERSchema_set_groups

@cached
def ERSchema_get_rqlexprs(self, action):
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
        return tuple(g for g in self._groups[action] if not isinstance(g, basestring))
    except KeyError:
        return ()
ERSchema.get_rqlexprs = ERSchema_get_rqlexprs

def ERSchema_set_rqlexprs(self, action, rqlexprs):
    """set the rql expression allowing to perform <action> on entities of this type. Don't
    change groups for the same action.

    :type action: str
    :param action: the name of a permission

    :type rqlexprs: list or tuple
    :param rqlexprs: the rql expressions allowing the given action
    """
    assert action in self.ACTIONS, action
    clear_cache(self, 'ERSchema_get_rqlexprs')
    self._groups[action] = tuple(self.get_groups(action)) + tuple(rqlexprs)
ERSchema.set_rqlexprs = ERSchema_set_rqlexprs

def ERSchema_set_permissions(self, action, permissions):
    """set the groups and rql expressions allowing to perform <action> on
    entities of this type

    :type action: str
    :param action: the name of a permission

    :type permissions: tuple
    :param permissions: the groups and rql expressions allowing the given action
    """
    assert action in self.ACTIONS, action
    clear_cache(self, 'ERSchema_get_rqlexprs')
    clear_cache(self, 'ERSchema_get_groups')
    self._groups[action] = tuple(permissions)
ERSchema.set_permissions = ERSchema_set_permissions

def ERSchema_has_perm(self, session, action, *args, **kwargs):
    """return true if the action is granted globaly or localy"""
    try:
        self.check_perm(session, action, *args, **kwargs)
        return True
    except Unauthorized:
        return False
ERSchema.has_perm = ERSchema_has_perm

def ERSchema_has_local_role(self, action):
    """return true if the action *may* be granted localy (eg either rql
    expressions or the owners group are used in security definition)

    XXX this method is only there since we don't know well how to deal with
    'add' action checking. Also find a better name would be nice.
    """
    assert action in self.ACTIONS, action
    if self.get_rqlexprs(action):
        return True
    if action in ('update', 'delete'):
        return self.has_group(action, 'owners')
    return False
ERSchema.has_local_role = ERSchema_has_local_role


def system_etypes(schema):
    """return system entity types only: skip final, schema and application entities
    """
    for eschema in schema.entities():
        if eschema.is_final() or eschema.schema_entity() or not eschema.meta:
            continue
        yield eschema.type

# Schema objects definition ###################################################

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
        # take care: no _groups attribute when deep-copying
        if getattr(self, '_groups', None): 
            for groups in self._groups.itervalues():
                for group_or_rqlexpr in groups:
                    if isinstance(group_or_rqlexpr, RRQLExpression):
                        msg = "can't use RRQLExpression on an entity type, use an ERQLExpression (%s)"
                        raise BadSchemaDefinition(msg % self.type)
            
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
            
    def add_subject_relation(self, rschema):
        """register the relation schema as possible subject relation"""
        super(CubicWebEntitySchema, self).add_subject_relation(rschema)
        self._update_has_text()

    def del_subject_relation(self, rtype):
        super(CubicWebEntitySchema, self).del_subject_relation(rtype)
        self._update_has_text(False)
        
    def _update_has_text(self, need_has_text=None):
        may_need_has_text, has_has_text = False, False
        for rschema in self.subject_relations():
            if rschema.is_final():
                if rschema == 'has_text':
                    has_has_text = True
                elif self.rproperty(rschema, 'fulltextindexed'):
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
                    break
        if need_has_text is None:
            need_has_text = may_need_has_text
        if need_has_text and not has_has_text:
            rdef = ybo.RelationDefinition(self.type, 'has_text', 'String')
            self.schema.add_relation_def(rdef)
        elif not need_has_text and has_has_text:
            self.schema.del_relation_def(self.type, 'has_text', 'String')
            
    def schema_entity(self):
        """return True if this entity type is used to build the schema"""
        return self.type in self.schema.schema_entity_types()

    def rich_text_fields(self):
        """return an iterator on (attribute, format attribute) of rich text field

        (the first tuple element containing the text and the second the text format)
        """
        for rschema, _ in self.attribute_definitions():
            if rschema.type.endswith('_format'):
                for constraint in self.constraints(rschema):
                    if isinstance(constraint, FormatConstraint):
                        yield self.subject_relation(rschema.type[:-7]), rschema
                        break
                    
    def check_perm(self, session, action, eid=None):
        # NB: session may be a server session or a request object
        user = session.user
        # check user is in an allowed group, if so that's enough
        # internal sessions should always stop there
        if user.matching_groups(self.get_groups(action)):
            return
        # if 'owners' in allowed groups, check if the user actually owns this
        # object, if so that's enough
        if eid is not None and 'owners' in self.get_groups(action) and \
               user.owns(eid):
            return
        # else if there is some rql expressions, check them
        if any(rqlexpr.check(session, eid)
               for rqlexpr in self.get_rqlexprs(action)):
            return        
        raise Unauthorized(action, str(self))

    def rql_expression(self, expression, mainvars=None, eid=None):
        """rql expression factory"""
        return ERQLExpression(expression, mainvars, eid)
    
class CubicWebRelationSchema(RelationSchema):
    RelationSchema._RPROPERTIES['eid'] = None
    _perms_checked = False
    
    def __init__(self, schema=None, rdef=None, eid=None, **kwargs):
        if rdef is not None:
            # if this relation is inlined
            self.inlined = rdef.inlined
        super(CubicWebRelationSchema, self).__init__(schema, rdef, **kwargs)
        if eid is None and rdef is not None:
            eid = getattr(rdef, 'eid', None)
        self.eid = eid
                    
        
    def update(self, subjschema, objschema, rdef):
        super(CubicWebRelationSchema, self).update(subjschema, objschema, rdef)
        if not self._perms_checked and self._groups:
            for action, groups in self._groups.iteritems():
                for group_or_rqlexpr in groups:
                    if action == 'read' and \
                           isinstance(group_or_rqlexpr, RQLExpression):
                        msg = "can't use rql expression for read permission of "\
                              "a relation type (%s)"
                        raise BadSchemaDefinition(msg % self.type)
                    elif self.final and isinstance(group_or_rqlexpr, RRQLExpression):
                        if self.schema.reading_from_database:
                            # we didn't have final relation earlier, so turn
                            # RRQLExpression into ERQLExpression now
                            rqlexpr = group_or_rqlexpr
                            newrqlexprs = [x for x in self.get_rqlexprs(action) if not x is rqlexpr]
                            newrqlexprs.append(ERQLExpression(rqlexpr.expression,
                                                              rqlexpr.mainvars,
                                                              rqlexpr.eid))
                            self.set_rqlexprs(action, newrqlexprs) 
                        else:
                            msg = "can't use RRQLExpression on a final relation "\
                                  "type (eg attribute relation), use an ERQLExpression (%s)"
                            raise BadSchemaDefinition(msg % self.type)
                    elif not self.final and \
                             isinstance(group_or_rqlexpr, ERQLExpression):
                        msg = "can't use ERQLExpression on a relation type, use "\
                              "a RRQLExpression (%s)"
                        raise BadSchemaDefinition(msg % self.type)
            self._perms_checked = True
            
    def cardinality(self, subjtype, objtype, target):
        card = self.rproperty(subjtype, objtype, 'cardinality')
        return (target == 'subject' and card[0]) or \
               (target == 'object' and card[1])
    
    def schema_relation(self):
        return self.type in ('relation_type', 'from_entity', 'to_entity',
                             'constrained_by', 'cstrtype')
    
    def physical_mode(self):
        """return an appropriate mode for physical storage of this relation type:
        * 'subjectinline' if every possible subject cardinalities are 1 or ?
        * 'objectinline' if 'subjectinline' mode is not possible but every
          possible object cardinalities are 1 or ?
        * None if neither 'subjectinline' and 'objectinline'
        """
        assert not self.final
        return self.inlined and 'subjectinline' or None

    def check_perm(self, session, action, *args, **kwargs):
        # NB: session may be a server session or a request object check user is
        # in an allowed group, if so that's enough internal sessions should
        # always stop there
        if session.user.matching_groups(self.get_groups(action)):
            return 
        # else if there is some rql expressions, check them
        if any(rqlexpr.check(session, *args, **kwargs)
               for rqlexpr in self.get_rqlexprs(action)):
            return
        raise Unauthorized(action, str(self))

    def rql_expression(self, expression, mainvars=None, eid=None):
        """rql expression factory"""
        if self.is_final():
            return ERQLExpression(expression, mainvars, eid)
        return RRQLExpression(expression, mainvars, eid)

    
class CubicWebSchema(Schema):
    """set of entities and relations schema defining the possible data sets
    used in an application


    :type name: str
    :ivar name: name of the schema, usually the application identifier
    
    :type base: str
    :ivar base: path of the directory where the schema is defined
    """
    reading_from_database = False    
    entity_class = CubicWebEntitySchema
    relation_class = CubicWebRelationSchema

    def __init__(self, *args, **kwargs):
        self._eid_index = {}
        super(CubicWebSchema, self).__init__(*args, **kwargs)
        ybo.register_base_types(self)
        rschema = self.add_relation_type(ybo.RelationType('eid', meta=True))
        rschema.final = True
        rschema.set_default_groups()
        rschema = self.add_relation_type(ybo.RelationType('has_text', meta=True))
        rschema.final = True
        rschema.set_default_groups()
        rschema = self.add_relation_type(ybo.RelationType('identity', meta=True))
        rschema.final = False
        rschema.set_default_groups()
        
    def schema_entity_types(self):
        """return the list of entity types used to build the schema"""
        return frozenset(('EEType', 'ERType', 'EFRDef', 'ENFRDef',
                          'EConstraint', 'EConstraintType', 'RQLExpression',
                          # XXX those are not really "schema" entity types
                          #     but we usually don't want them as @* targets
                          'EProperty', 'EPermission', 'State', 'Transition'))
        
    def add_entity_type(self, edef):
        edef.name = edef.name.encode()
        edef.name = bw_normalize_etype(edef.name)
        assert re.match(r'[A-Z][A-Za-z0-9]*[a-z]+[0-9]*$', edef.name), repr(edef.name)
        eschema = super(CubicWebSchema, self).add_entity_type(edef)
        if not eschema.is_final():
            # automatically add the eid relation to non final entity types
            rdef = ybo.RelationDefinition(eschema.type, 'eid', 'Int',
                                          cardinality='11', uid=True)
            self.add_relation_def(rdef)
            rdef = ybo.RelationDefinition(eschema.type, 'identity', eschema.type)
            self.add_relation_def(rdef)
        self._eid_index[eschema.eid] = eschema
        return eschema
        
    def add_relation_type(self, rdef):
        rdef.name = rdef.name.lower().encode()
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
        super(CubicWebSchema, self).add_relation_def(rdef)
        try:
            self._eid_index[rdef.eid] = (self.eschema(rdef.subject),
                                         self.rschema(rdef.name),
                                         self.eschema(rdef.object))
        except AttributeError:
            pass # not a serialized schema
    
    def del_relation_type(self, rtype):
        rschema = self.rschema(rtype)
        self._eid_index.pop(rschema.eid, None)
        super(CubicWebSchema, self).del_relation_type(rtype)
    
    def del_relation_def(self, subjtype, rtype, objtype):
        for k, v in self._eid_index.items():
            if v == (subjtype, rtype, objtype):
                del self._eid_index[k]
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


# Possible constraints ########################################################

class RQLVocabularyConstraint(BaseConstraint):
    """the rql vocabulary constraint :

    limit the proposed values to a set of entities returned by a rql query,
    but this is not enforced at the repository level
    
     restriction is additional rql restriction that will be added to
     a predefined query, where the S and O variables respectivly represent
     the subject and the object of the relation
    """
    
    def __init__(self, restriction):
        self.restriction = restriction

    def serialize(self):
        return self.restriction
    
    def deserialize(cls, value):
        return cls(value)
    deserialize = classmethod(deserialize)
    
    def check(self, entity, rtype, value):
        """return true if the value satisfy the constraint, else false"""
        # implemented as a hook in the repository
        return 1

    def repo_check(self, session, eidfrom, rtype, eidto):
        """raise ValidationError if the relation doesn't satisfy the constraint
        """
        pass # this is a vocabulary constraint, not enforce
    
    def __str__(self):
        return self.restriction

    def __repr__(self):
        return '<%s : %s>' % (self.__class__.__name__, repr(self.restriction))


class RQLConstraint(RQLVocabularyConstraint):
    """the rql constraint is similar to the RQLVocabularyConstraint but
    are also enforced at the repository level
    """
    def exec_query(self, session, eidfrom, eidto):
        rql = 'Any S,O WHERE S eid %(s)s, O eid %(o)s, ' + self.restriction
        return session.unsafe_execute(rql, {'s': eidfrom, 'o': eidto},
                                      ('s', 'o'), build_descr=False)
    def error(self, eid, rtype, msg):
        raise ValidationError(eid, {rtype: msg})
        
    def repo_check(self, session, eidfrom, rtype, eidto):
        """raise ValidationError if the relation doesn't satisfy the constraint
        """
        if not self.exec_query(session, eidfrom, eidto):
            # XXX at this point dunno if the validation error `occured` on
            #     eidfrom or eidto (from user interface point of view)
            self.error(eidfrom, rtype, 'constraint %s failed' % self)


class RQLUniqueConstraint(RQLConstraint):
    """the unique rql constraint check that the result of the query isn't
    greater than one
    """
    def repo_check(self, session, eidfrom, rtype, eidto):
        """raise ValidationError if the relation doesn't satisfy the constraint
        """
        if len(self.exec_query(session, eidfrom, eidto)) > 1:
            # XXX at this point dunno if the validation error `occured` on
            #     eidfrom or eidto (from user interface point of view)
            self.error(eidfrom, rtype, 'unique constraint %s failed' % self)

    
def split_expression(rqlstring):
    for expr in rqlstring.split(','):
        for word in expr.split():
            yield word
            
def normalize_expression(rqlstring):
    """normalize an rql expression to ease schema synchronization (avoid
    suppressing and reinserting an expression if only a space has been added/removed
    for instance)
    """
    return u', '.join(' '.join(expr.split()) for expr in rqlstring.split(','))


class RQLExpression(object):
    def __init__(self, expression, mainvars, eid):
        self.eid = eid # eid of the entity representing this rql expression
        if not isinstance(mainvars, unicode):
            mainvars = unicode(mainvars)
        self.mainvars = mainvars
        self.expression = normalize_expression(expression)
        try:
            self.rqlst = parse(self.full_rql, print_errors=False).children[0]
        except RQLSyntaxError:
            raise RQLSyntaxError(expression)
        for mainvar in mainvars.split(','):
            if len(self.rqlst.defined_vars[mainvar].references()) <= 2:
                LOGGER.warn('You did not use the %s variable in your RQL expression %s',
                            mainvar, self)
    
    def __str__(self):
        return self.full_rql
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.full_rql)
        
    def __deepcopy__(self, memo):
        return self.__class__(self.expression, self.mainvars)
    def __getstate__(self):
        return (self.expression, self.mainvars)
    def __setstate__(self, state):
        self.__init__(*state)
        
    @cached
    def transform_has_permission(self):
        found = None
        rqlst = self.rqlst
        for var in rqlst.defined_vars.itervalues():
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
                found.append((action, objvar, colindex))
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
        
    def _check(self, session, **kwargs):
        """return True if the rql expression is matching the given relation
        between fromeid and toeid

        session may actually be a request as well
        """
        if self.eid is not None:
            key = (self.eid, tuple(sorted(kwargs.iteritems())))
            try:
                return session.local_perm_cache[key]
            except KeyError:
                pass
        rql, has_perm_defs, keyarg = self.transform_has_permission()
        if keyarg is None:
            # on the server side, use unsafe_execute, but this is not available
            # on the client side (session is actually a request)
            execute = getattr(session, 'unsafe_execute', session.execute)
            # XXX what if 'u' in kwargs
            cachekey = kwargs.keys()
            kwargs['u'] = session.user.eid
            try:
                rset = execute(rql, kwargs, cachekey, build_descr=True)
            except NotImplementedError:
                self.critical('cant check rql expression, unsupported rql %s', rql)
                if self.eid is not None:
                    session.local_perm_cache[key] = False
                return False
            except TypeResolverException, ex:
                # some expression may not be resolvable with current kwargs
                # (type conflict)
                self.warning('%s: %s', rql, str(ex))
                if self.eid is not None:
                    session.local_perm_cache[key] = False
                return False
        else:
            rset = session.eid_rset(kwargs[keyarg])
        # if no special has_*_permission relation in the rql expression, just
        # check the result set contains something
        if has_perm_defs is None:
            if rset:
                if self.eid is not None:
                    session.local_perm_cache[key] = True
                return True
        elif rset:
            # check every special has_*_permission relation is satisfied
            get_eschema = session.vreg.schema.eschema
            try:
                for eaction, var, col in has_perm_defs:
                    for i in xrange(len(rset)):
                        eschema = get_eschema(rset.description[i][col])
                        eschema.check_perm(session, eaction, rset[i][col])
                if self.eid is not None:
                    session.local_perm_cache[key] = True
                return True
            except Unauthorized:
                pass
        if self.eid is not None:
            session.local_perm_cache[key] = False
        return False
    
    @property
    def minimal_rql(self):
        return 'Any %s WHERE %s' % (self.mainvars, self.expression)


class ERQLExpression(RQLExpression):
    def __init__(self, expression, mainvars=None, eid=None):
        RQLExpression.__init__(self, expression, mainvars or 'X', eid)
        # syntax tree used by read security (inserted in queries when necessary
        self.snippet_rqlst = parse(self.minimal_rql, print_errors=False).children[0]

    @property
    def full_rql(self):
        rql = self.minimal_rql
        rqlst = getattr(self, 'rqlst', None) # may be not set yet
        if rqlst is not None:
            defined = rqlst.defined_vars
        else:
            defined = set(split_expression(self.expression))
        if 'X' in defined:
            rql += ', X eid %(x)s'
        if 'U' in defined:
            rql += ', U eid %(u)s'
        return rql
    
    def check(self, session, eid=None):
        if 'X' in self.rqlst.defined_vars:
            if eid is None:
                return False
            return self._check(session, x=eid)
        return self._check(session)
    
PyFileReader.context['ERQLExpression'] = ERQLExpression
        
class RRQLExpression(RQLExpression):
    def __init__(self, expression, mainvars=None, eid=None):
        if mainvars is None:
            defined = set(split_expression(expression))
            mainvars = []
            if 'S' in defined:
                mainvars.append('S')
            if 'O' in defined:
                mainvars.append('O')
            if not mainvars:
                raise Exception('unable to guess selection variables')
            mainvars = ','.join(mainvars)
        RQLExpression.__init__(self, expression, mainvars, eid)

    @property
    def full_rql(self):
        rql = self.minimal_rql
        rqlst = getattr(self, 'rqlst', None) # may be not set yet
        if rqlst is not None:
            defined = rqlst.defined_vars
        else:
            defined = set(split_expression(self.expression))
        if 'S' in defined:
            rql += ', S eid %(s)s'
        if 'O' in defined:
            rql += ', O eid %(o)s'
        if 'U' in defined:
            rql += ', U eid %(u)s'
        return rql
    
    def check(self, session, fromeid=None, toeid=None):
        kwargs = {}
        if 'S' in self.rqlst.defined_vars:
            if fromeid is None:
                return False
            kwargs['s'] = fromeid
        if 'O' in self.rqlst.defined_vars:
            if toeid is None:
                return False
            kwargs['o'] = toeid
        return self._check(session, **kwargs)
        
PyFileReader.context['RRQLExpression'] = RRQLExpression

        
# schema loading ##############################################################

class CubicWebRelationFileReader(RelationFileReader):
    """cubicweb specific relation file reader, handling additional RQL
    constraints on a relation definition
    """
    
    def handle_constraint(self, rdef, constraint_text):
        """arbitrary constraint is an rql expression for cubicweb"""
        if not rdef.constraints:
            rdef.constraints = []
        rdef.constraints.append(RQLVocabularyConstraint(constraint_text))

    def process_properties(self, rdef, relation_def):
        if 'inline' in relation_def:
            rdef.inlined = True
        RelationFileReader.process_properties(self, rdef, relation_def)

        
CONSTRAINTS['RQLConstraint'] = RQLConstraint
CONSTRAINTS['RQLUniqueConstraint'] = RQLUniqueConstraint
CONSTRAINTS['RQLVocabularyConstraint'] = RQLVocabularyConstraint
PyFileReader.context.update(CONSTRAINTS)


class BootstrapSchemaLoader(SchemaLoader):
    """cubicweb specific schema loader, loading only schema necessary to read
    the persistent schema
    """
    schemacls = CubicWebSchema
    SchemaLoader.file_handlers.update({'.rel' : CubicWebRelationFileReader,
                                       })

    def load(self, config, path=()):
        """return a Schema instance from the schema definition read
        from <directory>
        """
        self.lib_directory = config.schemas_lib_dir()
        return super(BootstrapSchemaLoader, self).load(
            path, config.appid, register_base_types=False)
    
    def _load_definition_files(self, cubes=None):
        # bootstraping, ignore cubes
        for filepath in self.include_schema_files('bootstrap'):
            self.info('loading %s', filepath)
            self.handle_file(filepath)
        
    def unhandled_file(self, filepath):
        """called when a file without handler associated has been found"""
        self.warning('ignoring file %r', filepath)


class CubicWebSchemaLoader(BootstrapSchemaLoader):
    """cubicweb specific schema loader, automatically adding metadata to the
    application's schema
    """

    def load(self, config):
        """return a Schema instance from the schema definition read
        from <directory>
        """
        self.info('loading %s schemas', ', '.join(config.cubes()))
        if config.apphome:
            path = reversed([config.apphome] + config.cubes_path())
        else:
            path = reversed(config.cubes_path())
        return super(CubicWebSchemaLoader, self).load(config, path=path)

    def _load_definition_files(self, cubes):
        for filepath in (self.include_schema_files('bootstrap')
                         + self.include_schema_files('base')
                         + self.include_schema_files('Bookmark')
                         + self.include_schema_files('Card')):
            self.info('loading %s', filepath)
            self.handle_file(filepath)
        for cube in cubes:
            for filepath in self.get_schema_files(cube):
                self.info('loading %s', filepath)
                self.handle_file(filepath)


# _() is just there to add messages to the catalog, don't care about actual
# translation
PERM_USE_TEMPLATE_FORMAT = _('use_template_format')

class FormatConstraint(StaticVocabularyConstraint):
    need_perm_formats = (_('text/cubicweb-page-template'),
                         )
    regular_formats = (_('text/rest'),
                       _('text/html'),
                       _('text/plain'),
                       )
    def __init__(self):
        pass
    def serialize(self):
        """called to make persistent valuable data of a constraint"""
        return None

    @classmethod
    def deserialize(cls, value):
        """called to restore serialized data of a constraint. Should return
        a `cls` instance
        """
        return cls()
    
    def vocabulary(self, entity=None):
        if entity and entity.req.user.has_permission(PERM_USE_TEMPLATE_FORMAT):
            return self.regular_formats + self.need_perm_formats
        return self.regular_formats
    
    def __str__(self):
        return 'value in (%s)' % u', '.join(repr(unicode(word)) for word in self.vocabulary())
    
    
format_constraint = FormatConstraint()
CONSTRAINTS['FormatConstraint'] = FormatConstraint
PyFileReader.context['format_constraint'] = format_constraint

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(CubicWebSchemaLoader, getLogger('cubicweb.schemaloader'))
set_log_methods(BootstrapSchemaLoader, getLogger('cubicweb.bootstrapschemaloader'))
set_log_methods(RQLExpression, getLogger('cubicweb.schema'))

# XXX monkey patch PyFileReader.import_erschema until bw_normalize_etype is
# necessary
orig_import_erschema = PyFileReader.import_erschema
def bw_import_erschema(self, ertype, schemamod=None, instantiate=True):
    return orig_import_erschema(self, bw_normalize_etype(ertype), schemamod, instantiate)
PyFileReader.import_erschema = bw_import_erschema
    
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
