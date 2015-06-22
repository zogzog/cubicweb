# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Hooks for synchronizing computed attributes"""

__docformat__ = "restructuredtext en"
_ = unicode

from collections import defaultdict

from rql import nodes

from cubicweb.server import hook


class RecomputeAttributeOperation(hook.DataOperationMixIn, hook.Operation):
    """Operation to recompute caches of computed attribute at commit time,
    depending on what's have been modified in the transaction and avoiding to
    recompute twice the same attribute
    """
    containercls = dict
    def add_data(self, computed_attribute, eid=None):
        try:
            self._container[computed_attribute].add(eid)
        except KeyError:
            self._container[computed_attribute] = set((eid,))

    def precommit_event(self):
        for computed_attribute_rdef, eids in self.get_data().iteritems():
            attr = computed_attribute_rdef.rtype
            formula  = computed_attribute_rdef.formula
            select = self.cnx.repo.vreg.rqlhelper.parse(formula).children[0]
            xvar = select.get_variable('X')
            select.add_selected(xvar, index=0)
            select.add_group_var(xvar, index=0)
            if None in eids:
                select.add_type_restriction(xvar, computed_attribute_rdef.subject)
            else:
                select.add_eid_restriction(xvar, eids)
            update_rql = 'SET X %s %%(value)s WHERE X eid %%(x)s' % attr
            for eid, value in self.cnx.execute(select.as_string()):
                self.cnx.execute(update_rql, {'value': value, 'x': eid})


class EntityWithCACreatedHook(hook.Hook):
    """When creating an entity that has some computed attribute, those
    attributes have to be computed.

    Concret class of this hook are generated at registration time by
    introspecting the schema.
    """
    __abstract__ = True
    events = ('after_add_entity',)
    # list of computed attribute rdefs that have to be recomputed
    computed_attributes = None

    def __call__(self):
        for rdef in self.computed_attributes:
            RecomputeAttributeOperation.get_instance(self._cw).add_data(
                rdef, self.entity.eid)


class RelationInvolvedInCAModifiedHook(hook.Hook):
    """When some relation used in a computed attribute is updated, those
    attributes have to be recomputed.

    Concret class of this hook are generated at registration time by
    introspecting the schema.
    """
    __abstract__ = True
    events = ('after_add_relation', 'before_delete_relation')
    # list of (computed attribute rdef, optimize_on) that have to be recomputed
    optimized_computed_attributes = None

    def __call__(self):
        for rdef, optimize_on in self.optimized_computed_attributes:
            if optimize_on is None:
                eid = None
            else:
                eid = getattr(self, optimize_on)
            RecomputeAttributeOperation.get_instance(self._cw).add_data(rdef, eid)


class AttributeInvolvedInCAModifiedHook(hook.Hook):
    """When some attribute used in a computed attribute is updated, those
    attributes have to be recomputed.

    Concret class of this hook are generated at registration time by
    introspecting the schema.
    """
    __abstract__ = True
    events = ('after_update_entity',)
    # list of (computed attribute rdef, attributes of this entity type involved)
    # that may have to be recomputed
    attributes_computed_attributes = None

    def __call__(self):
        edited_attributes = frozenset(self.entity.cw_edited)
        for rdef, used_attributes in self.attributes_computed_attributes.iteritems():
            if edited_attributes.intersection(used_attributes):
                # XXX optimize if the modified attributes belong to the same
                # entity as the computed attribute
                RecomputeAttributeOperation.get_instance(self._cw).add_data(rdef)


# code generation at registration time #########################################

def _optimize_on(formula_select, rtype):
    """Given a formula and some rtype, tells whether on update of the given
    relation, formula may be recomputed only for rhe relation's subject
    ('eidfrom' returned), object ('eidto' returned) or None.

    Optimizing is only possible when X is used as direct subject/object of this
    relation, else we may miss some necessary update.
    """
    for rel in formula_select.get_nodes(nodes.Relation):
        if rel.r_type == rtype:
            sub = rel.get_variable_parts()[0]
            obj = rel.get_variable_parts()[1]
            if sub.name == 'X':
                return 'eidfrom'
            elif obj.name == 'X':
                return 'eidto'
            else:
                return None


class _FormulaDependenciesMatrix(object):
    """This class computes and represents the dependencies of computed attributes
    towards relations and attributes
    """

    def __init__(self, schema):
        """Analyzes the schema to compute the dependencies"""
        # entity types holding some computed attribute {etype: [computed rdefs]}
        self.computed_attribute_by_etype = defaultdict(list)
        # depending entity types {dep. etype: {computed rdef: dep. etype attributes}}
        self.computed_attribute_by_etype_attrs = defaultdict(lambda: defaultdict(set))
        # depending relations def {dep. rdef: [computed rdefs]
        self.computed_attribute_by_relation = defaultdict(list) # by rdef
        # Walk through all attributes definitions
        for rdef in schema.iter_computed_attributes():
            self.computed_attribute_by_etype[rdef.subject.type].append(rdef)
            # extract the relations it depends upon - `rdef.formula_select` is
            # expected to have been set by finalize_computed_attributes
            select = rdef.formula_select
            for rel_node in select.get_nodes(nodes.Relation):
                if rel_node.is_types_restriction():
                    continue
                rschema = schema.rschema(rel_node.r_type)
                lhs, rhs = rel_node.get_variable_parts()
                for sol in select.solutions:
                    subject_etype = sol[lhs.name]
                    if isinstance(rhs, nodes.VariableRef):
                        object_etypes = set(sol[rhs.name] for sol in select.solutions)
                    else:
                        object_etypes = rschema.objects(subject_etype)
                    for object_etype in object_etypes:
                        if rschema.final:
                            attr_for_computations = self.computed_attribute_by_etype_attrs[subject_etype]
                            attr_for_computations[rdef].add(rschema.type)
                        else:
                            depend_on_rdef = rschema.rdefs[subject_etype, object_etype]
                            self.computed_attribute_by_relation[depend_on_rdef].append(rdef)

    def generate_entity_creation_hooks(self):
        for etype, computed_attributes in self.computed_attribute_by_etype.iteritems():
            regid = 'computed_attribute.%s_created' % etype
            selector = hook.is_instance(etype)
            yield type('%sCreatedHook' % etype,
                       (EntityWithCACreatedHook,),
                       {'__regid__': regid,
                        '__select__':  hook.Hook.__select__ & selector,
                        'computed_attributes': computed_attributes})

    def generate_relation_change_hooks(self):
        for rdef, computed_attributes in self.computed_attribute_by_relation.iteritems():
            regid = 'computed_attribute.%s_modified' % rdef.rtype
            selector = hook.match_rtype(rdef.rtype.type,
                                        frometypes=(rdef.subject.type,),
                                        toetypes=(rdef.object.type,))
            optimized_computed_attributes = []
            for computed_rdef in computed_attributes:
                optimized_computed_attributes.append(
                    (computed_rdef,
                     _optimize_on(computed_rdef.formula_select, rdef.rtype))
                     )
            yield type('%sModifiedHook' % rdef.rtype,
                       (RelationInvolvedInCAModifiedHook,),
                       {'__regid__': regid,
                        '__select__':  hook.Hook.__select__ & selector,
                        'optimized_computed_attributes': optimized_computed_attributes})

    def generate_entity_update_hooks(self):
        for etype, attributes_computed_attributes in self.computed_attribute_by_etype_attrs.iteritems():
            regid = 'computed_attribute.%s_updated' % etype
            selector = hook.is_instance(etype)
            yield type('%sModifiedHook' % etype,
                       (AttributeInvolvedInCAModifiedHook,),
                       {'__regid__': regid,
                        '__select__':  hook.Hook.__select__ & selector,
                        'attributes_computed_attributes': attributes_computed_attributes})


def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__)
    dependencies = _FormulaDependenciesMatrix(vreg.schema)
    for hook_class in dependencies.generate_entity_creation_hooks():
        vreg.register(hook_class)
    for hook_class in dependencies.generate_relation_change_hooks():
        vreg.register(hook_class)
    for hook_class in dependencies.generate_entity_update_hooks():
        vreg.register(hook_class)
