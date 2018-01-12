# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""plan execution of rql queries on a single source"""

from six import text_type

from rql.stmts import Union, Select
from rql.nodes import Constant, Relation

from cubicweb import QueryError
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.rqlrewrite import add_types_restriction, RQLRelationRewriter
from cubicweb.server.edition import EditedEntity

READ_ONLY_RTYPES = set(('eid', 'has_text', 'is', 'is_instance_of', 'identity'))

_CONSTANT = object()
_FROM_SUBSTEP = object()


def _extract_const_attributes(plan, rqlst, to_build):
    """add constant values to entity def, mark variables to be selected
    """
    to_select = {}
    for relation in rqlst.main_relations:
        lhs, rhs = relation.get_variable_parts()
        rtype = relation.r_type
        if rtype in READ_ONLY_RTYPES:
            raise QueryError("can't assign to %s" % rtype)
        try:
            edef = to_build[str(lhs)]
        except KeyError:
            # lhs var is not to build, should be selected and added as an
            # object relation
            edef = to_build[str(rhs)]
            to_select.setdefault(edef, []).append((rtype, lhs, 1))
        else:
            if isinstance(rhs, Constant) and not rhs.uid:
                # add constant values to entity def
                value = rhs.eval(plan.args)
                eschema = edef.entity.e_schema
                attrtype = eschema.subjrels[rtype].objects(eschema)[0]
                if attrtype == 'Password' and isinstance(value, text_type):
                    value = value.encode('UTF8')
                edef.edited_attribute(rtype, value)
            elif str(rhs) in to_build:
                # create a relation between two newly created variables
                plan.add_relation_def((edef, rtype, to_build[rhs.name]))
            else:
                to_select.setdefault(edef, []).append((rtype, rhs, 0))
    return to_select


def _extract_eid_consts(plan, rqlst):
    """return a dict mapping rqlst variable object to their eid if specified in
    the syntax tree
    """
    cnx = plan.cnx
    if rqlst.where is None:
        return {}
    eidconsts = {}
    neweids = cnx.transaction_data.get('neweids', ())
    checkread = cnx.read_security
    eschema = cnx.vreg.schema.eschema
    for rel in rqlst.where.get_nodes(Relation):
        # only care for 'eid' relations ...
        if (rel.r_type == 'eid'
                # ... that are not part of a NOT clause ...
                and not rel.neged(strict=True)
                # ... and where eid is specified by '=' operator.
                and rel.children[1].operator == '='):
            lhs, rhs = rel.get_variable_parts()
            if isinstance(rhs, Constant):
                eid = int(rhs.eval(plan.args))
                # check read permission here since it may not be done by
                # the generated select substep if not emited (eg nothing
                # to be selected)
                if checkread and eid not in neweids:
                    with cnx.security_enabled(read=False):
                        eschema(cnx.entity_type(eid)).check_perm(
                            cnx, 'read', eid=eid)
                eidconsts[lhs.variable] = eid
    return eidconsts


def _build_substep_query(select, origrqlst):
    """Finalize substep select query that should be executed to get proper
    selection of stuff to insert/update.

    Return None when no query actually needed, else the given select node that
    will be used as substep query.
    """
    if origrqlst.where is not None and not select.selection:
        # no selection, append one randomly by searching for a relation which is
        # not neged neither a type restriction (is/is_instance_of)
        for rel in origrqlst.where.iget_nodes(Relation):
            if not (rel.neged(traverse_scope=True) or rel.is_types_restriction()):
                select.append_selected(rel.children[0].copy(select))
                break
        else:
            return None
    if select.selection:
        if origrqlst.where is not None:
            select.set_where(origrqlst.where.copy(select))
        if getattr(origrqlst, 'having', None):
            select.set_having([sq.copy(select) for sq in origrqlst.having])
        return select
    return None


class SSPlanner(object):
    """SingleSourcePlanner: build execution plan for rql queries

    optimized for single source repositories
    """

    def __init__(self, schema, rqlhelper):
        self.schema = schema
        self.rqlhelper = rqlhelper

    def build_plan(self, plan):
        """build an execution plan from a RQL query

        do nothing here, dispatch according to the statement type
        """
        build_plan = getattr(self, 'build_%s_plan' % plan.rqlst.TYPE)
        for step in build_plan(plan, plan.rqlst):
            plan.add_step(step)

    def build_select_plan(self, plan, rqlst):
        """build execution plan for a SELECT RQL query. Suppose only one source
        is available and so avoid work need for query decomposition among sources

        the rqlst should not be tagged at this point.
        """
        plan.preprocess(rqlst)
        return (OneFetchStep(plan, rqlst),)

    def build_insert_plan(self, plan, rqlst):
        """get an execution plan from an INSERT RQL query"""
        # each variable in main variables is a new entity to insert
        to_build = {}
        cnx = plan.cnx
        etype_class = cnx.vreg['etypes'].etype_class
        for etype, var in rqlst.main_variables:
            # need to do this since entity class is shared w. web client code !
            to_build[var.name] = EditedEntity(etype_class(etype)(cnx))
            plan.add_entity_def(to_build[var.name])
        # add constant values to entity def, mark variables to be selected
        to_select = _extract_const_attributes(plan, rqlst, to_build)
        # add necessary steps to add relations and update attributes
        step = InsertStep(plan)  # insert each entity and its relations
        step.children += self._compute_relation_steps(plan, rqlst, to_select)
        return (step,)

    def _compute_relation_steps(self, plan, rqlst, to_select):
        """handle the selection of relations for an insert query"""
        eidconsts = _extract_eid_consts(plan, rqlst)
        for edef, rdefs in to_select.items():
            # create a select rql st to fetch needed data
            select = Select()
            eschema = edef.entity.e_schema
            for i, (rtype, term, reverse) in enumerate(rdefs):
                if getattr(term, 'variable', None) in eidconsts:
                    value = eidconsts[term.variable]
                else:
                    select.append_selected(term.copy(select))
                    value = _FROM_SUBSTEP
                if reverse:
                    rdefs[i] = (rtype, InsertRelationsStep.REVERSE_RELATION, value)
                else:
                    rschema = eschema.subjrels[rtype]
                    if rschema.final or rschema.inlined:
                        rdefs[i] = (rtype, InsertRelationsStep.FINAL, value)
                    else:
                        rdefs[i] = (rtype, InsertRelationsStep.RELATION, value)
            step = InsertRelationsStep(plan, edef, rdefs)
            select = _build_substep_query(select, rqlst)
            if select is not None:
                step.children += self._select_plan(plan, select, rqlst.solutions)
            yield step

    def build_delete_plan(self, plan, rqlst):
        """get an execution plan from a DELETE RQL query"""
        # build a select query to fetch entities to delete
        steps = []
        for etype, var in rqlst.main_variables:
            step = DeleteEntitiesStep(plan)
            step.children += self._sel_variable_step(plan, rqlst, etype, var)
            steps.append(step)
        for relation in rqlst.main_relations:
            rtype = relation.r_type
            if self.schema[rtype].rule:
                raise QueryError("'%s' is a computed relation" % rtype)
            step = DeleteRelationsStep(plan, rtype)
            step.children += self._sel_relation_steps(plan, rqlst, relation)
            steps.append(step)
        return steps

    def _sel_variable_step(self, plan, rqlst, etype, varref):
        """handle the selection of variables for a delete query"""
        select = Select()
        varref = varref.copy(select)
        select.defined_vars = {varref.name: varref.variable}
        select.append_selected(varref)
        if rqlst.where is not None:
            select.set_where(rqlst.where.copy(select))
        if getattr(rqlst, 'having', None):
            select.set_having([x.copy(select) for x in rqlst.having])
        if etype != 'Any':
            select.add_type_restriction(varref.variable, etype)
        return self._select_plan(plan, select, rqlst.solutions)

    def _sel_relation_steps(self, plan, rqlst, relation):
        """handle the selection of relations for a delete query"""
        select = Select()
        lhs, rhs = relation.get_variable_parts()
        select.append_selected(lhs.copy(select))
        select.append_selected(rhs.copy(select))
        select.set_where(relation.copy(select))
        if rqlst.where is not None:
            select.add_restriction(rqlst.where.copy(select))
        if getattr(rqlst, 'having', None):
            select.set_having([x.copy(select) for x in rqlst.having])
        return self._select_plan(plan, select, rqlst.solutions)

    def build_set_plan(self, plan, rqlst):
        """get an execution plan from an SET RQL query"""
        getrschema = self.schema.rschema
        select = Select()   # potential substep query
        selectedidx = {}    # local state
        updatedefs = []     # definition of update attributes/relations
        selidx = residx = 0  # substep selection / resulting rset indexes
        # search for eid const in the WHERE clause
        eidconsts = _extract_eid_consts(plan, rqlst)
        # build `updatedefs` describing things to update and add necessary
        # variables to the substep selection
        for i, relation in enumerate(rqlst.main_relations):
            if relation.r_type in VIRTUAL_RTYPES:
                raise QueryError('can not assign to %r relation'
                                 % relation.r_type)
            lhs, rhs = relation.get_variable_parts()
            lhskey = lhs.as_string()
            if lhskey not in selectedidx:
                if lhs.variable in eidconsts:
                    eid = eidconsts[lhs.variable]
                    lhsinfo = (_CONSTANT, eid, residx)
                else:
                    select.append_selected(lhs.copy(select))
                    lhsinfo = (_FROM_SUBSTEP, selidx, residx)
                    selidx += 1
                residx += 1
                selectedidx[lhskey] = lhsinfo
            else:
                lhsinfo = selectedidx[lhskey][:-1] + (None,)
            rhskey = rhs.as_string()
            if rhskey not in selectedidx:
                if isinstance(rhs, Constant):
                    rhsinfo = (_CONSTANT, rhs.eval(plan.args), residx)
                elif getattr(rhs, 'variable', None) in eidconsts:
                    eid = eidconsts[rhs.variable]
                    rhsinfo = (_CONSTANT, eid, residx)
                else:
                    select.append_selected(rhs.copy(select))
                    rhsinfo = (_FROM_SUBSTEP, selidx, residx)
                    selidx += 1
                residx += 1
                selectedidx[rhskey] = rhsinfo
            else:
                rhsinfo = selectedidx[rhskey][:-1] + (None,)
            rschema = getrschema(relation.r_type)
            updatedefs.append((lhsinfo, rhsinfo, rschema))
        # the update step
        step = UpdateStep(plan, updatedefs)
        # when necessary add substep to fetch yet unknown values
        select = _build_substep_query(select, rqlst)
        if select is not None:
            # set distinct to avoid potential duplicate key error
            select.distinct = True
            step.children += self._select_plan(plan, select, rqlst.solutions)
        return (step,)

    # internal methods ########################################################

    def _select_plan(self, plan, select, solutions):
        union = Union()
        union.append(select)
        select.clean_solutions(solutions)
        add_types_restriction(self.schema, select)
        # Rewrite computed relations
        rewriter = RQLRelationRewriter(plan.cnx)
        rewriter.rewrite(union, plan.args)
        self.rqlhelper.annotate(union)
        return self.build_select_plan(plan, union)


# execution steps and helper functions ########################################

class Step(object):
    """base abstract class for execution step"""
    def __init__(self, plan):
        self.plan = plan
        self.children = []

    def execute_child(self):
        assert len(self.children) == 1
        return self.children[0].execute()

    def execute_children(self):
        for step in self.children:
            step.execute()

    def execute(self):
        """execute this step and store partial (eg this step) results"""
        raise NotImplementedError()

    def mytest_repr(self):
        """return a representation of this step suitable for test"""
        return (self.__class__.__name__,)

    def test_repr(self):
        """return a representation of this step suitable for test"""
        return self.mytest_repr() + (
            [step.test_repr() for step in self.children],)


class OneFetchStep(Step):
    """step consisting in fetching data from sources and directly returning
    results
    """
    def __init__(self, plan, union):
        Step.__init__(self, plan)
        self.union = union

    def execute(self):
        """call .syntax_tree_search with the given syntax tree on each
        source for each solution
        """
        self.execute_children()
        cnx = self.plan.cnx
        args = self.plan.args
        union = self.union
        if self.plan.cache_key is None:
            cachekey = None
        # union may have been splited into subqueries, in which case we can't
        # use plan.cache_key, rebuild a cache key
        elif isinstance(self.plan.cache_key, tuple):
            cachekey = list(self.plan.cache_key)
            cachekey[0] = union.as_string()
            cachekey = tuple(cachekey)
        else:
            cachekey = union.as_string()
        # get results for query
        source = cnx.repo.system_source
        result = source.syntax_tree_search(cnx, union, args, cachekey)
        return result

    def mytest_repr(self):
        """return a representation of this step suitable for test"""
        return (self.__class__.__name__,
                sorted((r.as_string(kwargs=self.plan.args), r.solutions)
                       for r in self.union.children))


# UPDATE/INSERT/DELETE steps ##################################################

class InsertRelationsStep(Step):
    """step consisting in adding attributes/relations to entity defs from a
    previous FetchStep

    relations values comes from the latest result, with one columns for
    each relation defined in self.rdefs

    for one entity definition, we'll construct N entity, where N is the
    number of the latest result
    """

    FINAL = 0
    RELATION = 1
    REVERSE_RELATION = 2

    def __init__(self, plan, edef, rdefs):
        Step.__init__(self, plan)
        # partial entity definition to expand
        self.edef = edef
        # definition of relations to complete
        self.rdefs = rdefs

    def execute(self):
        """execute this step"""
        base_edef = self.edef
        edefs = []
        if self.children:
            result = self.execute_child()
        else:
            result = [[]]
        for row in result:
            # get a new entity definition for this row
            edef = base_edef.clone()
            # complete this entity def using row values
            index = 0
            for rtype, rorder, value in self.rdefs:
                if value is _FROM_SUBSTEP:
                    value = row[index]
                    index += 1
                if rorder == InsertRelationsStep.FINAL:
                    edef.edited_attribute(rtype, value)
                elif rorder == InsertRelationsStep.RELATION:
                    self.plan.add_relation_def((edef, rtype, value))
                    edef.querier_pending_relations[(rtype, 'subject')] = value
                else:
                    self.plan.add_relation_def((value, rtype, edef))
                    edef.querier_pending_relations[(rtype, 'object')] = value
            edefs.append(edef)
        self.plan.substitute_entity_def(base_edef, edefs)
        return result


class InsertStep(Step):
    """step consisting in inserting new entities / relations"""

    def execute(self):
        """execute this step"""
        for step in self.children:
            assert isinstance(step, InsertRelationsStep)
            step.plan = self.plan
            step.execute()
        # insert entities first
        result = self.plan.insert_entity_defs()
        # then relation
        self.plan.insert_relation_defs()
        # return eids of inserted entities
        return result


class DeleteEntitiesStep(Step):
    """step consisting in deleting entities"""

    def execute(self):
        """execute this step"""
        results = self.execute_child()
        if results:
            todelete = frozenset(int(eid) for eid, in results)
            cnx = self.plan.cnx
            cnx.repo.glob_delete_entities(cnx, todelete)
        return results


class DeleteRelationsStep(Step):
    """step consisting in deleting relations"""

    def __init__(self, plan, rtype):
        Step.__init__(self, plan)
        self.rtype = rtype

    def execute(self):
        """execute this step"""
        cnx = self.plan.cnx
        delete = cnx.repo.glob_delete_relation
        for subj, obj in self.execute_child():
            delete(cnx, subj, self.rtype, obj)


class UpdateStep(Step):
    """step consisting in updating entities / adding relations from relations
    definitions and from results fetched in previous step
    """

    def __init__(self, plan, updatedefs):
        Step.__init__(self, plan)
        self.updatedefs = updatedefs

    def execute(self):
        """execute this step"""
        cnx = self.plan.cnx
        repo = cnx.repo
        edefs = {}
        relations = {}
        # insert relations
        if self.children:
            result = self.execute_child()
        else:
            result = [[]]
        for i, row in enumerate(result):
            newrow = []
            for (lhsinfo, rhsinfo, rschema) in self.updatedefs:
                if rschema.rule:
                    raise QueryError("'%s' is a computed relation"
                                     % rschema.type)
                lhsval = _handle_relterm(lhsinfo, row, newrow)
                rhsval = _handle_relterm(rhsinfo, row, newrow)
                if rschema.final or rschema.inlined:
                    eid = int(lhsval)
                    try:
                        edited = edefs[eid]
                    except KeyError:
                        edef = cnx.entity_from_eid(eid)
                        edefs[eid] = edited = EditedEntity(edef)
                    edited.edited_attribute(str(rschema), rhsval)
                else:
                    str_rschema = str(rschema)
                    if str_rschema in relations:
                        relations[str_rschema].append((lhsval, rhsval))
                    else:
                        relations[str_rschema] = [(lhsval, rhsval)]
            result[i] = newrow
        # update entities
        repo.glob_add_relations(cnx, relations)
        for eid, edited in edefs.items():
            repo.glob_update_entity(cnx, edited)
        return result


def _handle_relterm(info, row, newrow):
    if info[0] is _CONSTANT:
        val = info[1]
    else:  # _FROM_SUBSTEP
        val = row[info[1]]
    if info[-1] is not None:
        newrow.append(val)
    return val
