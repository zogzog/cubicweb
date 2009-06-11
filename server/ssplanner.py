"""plan execution of rql queries on a single source

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from copy import copy

from rql.stmts import Union, Select
from rql.nodes import Constant

from cubicweb import QueryError, typed_eid

def add_types_restriction(schema, rqlst, newroot=None, solutions=None):
    if newroot is None:
        assert solutions is None
        if hasattr(rqlst, '_types_restr_added'):
            return
        solutions = rqlst.solutions
        newroot = rqlst
        rqlst._types_restr_added = True
    else:
        assert solutions is not None
        rqlst = rqlst.stmt
    eschema = schema.eschema
    allpossibletypes = {}
    for solution in solutions:
        for varname, etype in solution.iteritems():
            if not varname in newroot.defined_vars or eschema(etype).is_final():
                continue
            allpossibletypes.setdefault(varname, set()).add(etype)
    for varname in sorted(allpossibletypes):
        try:
            var = newroot.defined_vars[varname]
        except KeyError:
            continue
        stinfo = var.stinfo
        if stinfo.get('uidrels'):
            continue # eid specified, no need for additional type specification
        try:
            typerels = rqlst.defined_vars[varname].stinfo.get('typerels')
        except KeyError:
            assert varname in rqlst.aliases
            continue
        if newroot is rqlst and typerels:
            mytyperel = iter(typerels).next()
        else:
            for vref in newroot.defined_vars[varname].references():
                rel = vref.relation()
                if rel and rel.is_types_restriction():
                    mytyperel = rel
                    break
            else:
                mytyperel = None
        possibletypes = allpossibletypes[varname]
        if mytyperel is not None:
            # variable as already some types restriction. new possible types
            # can only be a subset of existing ones, so only remove no more
            # possible types
            for cst in mytyperel.get_nodes(Constant):
                if not cst.value in possibletypes:
                    cst.parent.remove(cst)
                    try:
                        stinfo['possibletypes'].remove(cst.value)
                    except KeyError:
                        # restriction on a type not used by this query, may
                        # occurs with X is IN(...)
                        pass
        else:
            # we have to add types restriction
            if stinfo.get('scope') is not None:
                rel = var.scope.add_type_restriction(var, possibletypes)
            else:
                # tree is not annotated yet, no scope set so add the restriction
                # to the root
                rel = newroot.add_type_restriction(var, possibletypes)
            stinfo['typerels'] = frozenset((rel,))
            stinfo['possibletypes'] = possibletypes

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
        return (OneFetchStep(plan, rqlst, plan.session.repo.sources),)

    def build_insert_plan(self, plan, rqlst):
        """get an execution plan from an INSERT RQL query"""
        # each variable in main variables is a new entity to insert
        to_build = {}
        session = plan.session
        for etype, var in rqlst.main_variables:
            # need to do this since entity class is shared w. web client code !
            to_build[var.name] = session.etype_class(etype)(session, None, None)
            plan.add_entity_def(to_build[var.name])
        # add constant values to entity def, mark variables to be selected
        to_select = plan.relation_definitions(rqlst, to_build)
        # add necessary steps to add relations and update attributes
        step = InsertStep(plan) # insert each entity and its relations
        step.children += self._compute_relation_steps(plan, rqlst.solutions,
                                                      rqlst.where, to_select)
        return (step,)

    def _compute_relation_steps(self, plan, solutions, restriction, to_select):
        """handle the selection of relations for an insert query"""
        for edef, rdefs in to_select.items():
            # create a select rql st to fetch needed data
            select = Select()
            eschema = edef.e_schema
            for i in range(len(rdefs)):
                rtype, term, reverse = rdefs[i]
                select.append_selected(term.copy(select))
                if reverse:
                    rdefs[i] = rtype, RelationsStep.REVERSE_RELATION
                else:
                    rschema = eschema.subject_relation(rtype)
                    if rschema.is_final() or rschema.inlined:
                        rdefs[i] = rtype, RelationsStep.FINAL
                    else:
                        rdefs[i] = rtype, RelationsStep.RELATION
            if restriction is not None:
                select.set_where(restriction.copy(select))
            step = RelationsStep(plan, edef, rdefs)
            step.children += self._select_plan(plan, select, solutions)
            yield step

    def build_delete_plan(self, plan, rqlst):
        """get an execution plan from a DELETE RQL query"""
        # build a select query to fetch entities to delete
        steps = []
        for etype, var in rqlst.main_variables:
            step = DeleteEntitiesStep(plan)
            step.children += self._sel_variable_step(plan, rqlst.solutions,
                                                     rqlst.where, etype, var)
            steps.append(step)
        for relation in rqlst.main_relations:
            step = DeleteRelationsStep(plan, relation.r_type)
            step.children += self._sel_relation_steps(plan, rqlst.solutions,
                                                      rqlst.where, relation)
            steps.append(step)
        return steps

    def _sel_variable_step(self, plan, solutions, restriction, etype, varref):
        """handle the selection of variables for a delete query"""
        select = Select()
        varref = varref.copy(select)
        select.defined_vars = {varref.name: varref.variable}
        select.append_selected(varref)
        if restriction is not None:
            select.set_where(restriction.copy(select))
        if etype != 'Any':
            select.add_type_restriction(varref.variable, etype)
        return self._select_plan(plan, select, solutions)

    def _sel_relation_steps(self, plan, solutions, restriction, relation):
        """handle the selection of relations for a delete query"""
        select = Select()
        lhs, rhs = relation.get_variable_parts()
        select.append_selected(lhs.copy(select))
        select.append_selected(rhs.copy(select))
        select.set_where(relation.copy(select))
        if restriction is not None:
            select.add_restriction(restriction.copy(select))
        return self._select_plan(plan, select, solutions)

    def build_set_plan(self, plan, rqlst):
        """get an execution plan from an SET RQL query"""
        select = Select()
        # extract variables to add to the selection
        selected_index = {}
        index = 0
        relations, attrrelations = [], []
        getrschema = self.schema.rschema
        for relation in rqlst.main_relations:
            if relation.r_type in ('eid', 'has_text', 'identity'):
                raise QueryError('can not assign to %r relation'
                                 % relation.r_type)
            lhs, rhs = relation.get_variable_parts()
            if not lhs.as_string('utf-8') in selected_index:
                select.append_selected(lhs.copy(select))
                selected_index[lhs.as_string('utf-8')] = index
                index += 1
            if not rhs.as_string('utf-8') in selected_index:
                select.append_selected(rhs.copy(select))
                selected_index[rhs.as_string('utf-8')] = index
                index += 1
            rschema = getrschema(relation.r_type)
            if rschema.is_final() or rschema.inlined:
                attrrelations.append(relation)
            else:
                relations.append(relation)
        # add step necessary to fetch all selected variables values
        if rqlst.where is not None:
            select.set_where(rqlst.where.copy(select))
        # set distinct to avoid potential duplicate key error
        select.distinct = True
        step = UpdateStep(plan, attrrelations, relations, selected_index)
        step.children += self._select_plan(plan, select, rqlst.solutions)
        return (step,)

    # internal methods ########################################################

    def _select_plan(self, plan, select, solutions):
        union = Union()
        union.append(select)
        select.clean_solutions(solutions)
        add_types_restriction(self.schema, select)
        self.rqlhelper.annotate(union)
        return self.build_select_plan(plan, union)


# execution steps and helper functions ########################################

def varmap_test_repr(varmap, tablesinorder):
    if varmap is None:
        return varmap
    maprepr = {}
    for var, sql in varmap.iteritems():
        table, col = sql.split('.')
        maprepr[var] = '%s.%s' % (tablesinorder[table], col)
    return maprepr

def offset_result(offset, result):
    offset -= len(result)
    if offset < 0:
        result = result[offset:]
        offset = None
    elif offset == 0:
        offset = None
        result = ()
    return offset, result


class LimitOffsetMixIn(object):
    limit = offset = None
    def set_limit_offset(self, limit, offset):
        self.limit = limit
        self.offset = offset or None


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


class OneFetchStep(LimitOffsetMixIn, Step):
    """step consisting in fetching data from sources and directly returning
    results
    """
    def __init__(self, plan, union, sources, inputmap=None):
        Step.__init__(self, plan)
        self.union = union
        self.sources = sources
        self.inputmap = inputmap
        self.set_limit_offset(union.children[-1].limit, union.children[-1].offset)

    def set_limit_offset(self, limit, offset):
        LimitOffsetMixIn.set_limit_offset(self, limit, offset)
        for select in self.union.children:
            select.limit = limit
            select.offset = offset

    def execute(self):
        """call .syntax_tree_search with the given syntax tree on each
        source for each solution
        """
        self.execute_children()
        session = self.plan.session
        args = self.plan.args
        inputmap = self.inputmap
        union = self.union
        # do we have to use a inputmap from a previous step ? If so disable
        # cachekey
        if inputmap or self.plan.cache_key is None:
            cachekey = None
        # union may have been splited into subqueries, rebuild a cache key
        elif isinstance(self.plan.cache_key, tuple):
            cachekey = list(self.plan.cache_key)
            cachekey[0] = union.as_string()
            cachekey = tuple(cachekey)
        else:
            cachekey = union.as_string()
        result = []
        # limit / offset processing
        limit = self.limit
        offset = self.offset
        if offset is not None:
            if len(self.sources) > 1:
                # we'll have to deal with limit/offset by ourself
                if union.children[-1].limit:
                    union.children[-1].limit = limit + offset
                union.children[-1].offset = None
            else:
                offset, limit = None, None
        for source in self.sources:
            if offset is None and limit is not None:
                # modifying the sample rqlst is enough since sql generation
                # will pick it here as well
                union.children[-1].limit = limit - len(result)
            result_ = source.syntax_tree_search(session, union, args, cachekey,
                                                inputmap)
            if offset is not None:
                offset, result_ = offset_result(offset, result_)
            result += result_
            if limit is not None:
                if len(result) >= limit:
                    return result[:limit]
        #print 'ONEFETCH RESULT %s' % (result)
        return result

    def mytest_repr(self):
        """return a representation of this step suitable for test"""
        try:
            inputmap = varmap_test_repr(self.inputmap, self.plan.tablesinorder)
        except AttributeError:
            inputmap = self.inputmap
        return (self.__class__.__name__,
                sorted((r.as_string(kwargs=self.plan.args), r.solutions)
                       for r in self.union.children),
                self.limit, self.offset,
                sorted(self.sources), inputmap)


# UPDATE/INSERT/DELETE steps ##################################################

class RelationsStep(Step):
    """step consisting in adding attributes/relations to entity defs from a
    previous FetchStep

    relations values comes from the latest result, with one columns for
    each relation defined in self.r_defs

    for one entity definition, we'll construct N entity, where N is the
    number of the latest result
    """

    FINAL = 0
    RELATION = 1
    REVERSE_RELATION = 2

    def __init__(self, plan, e_def, r_defs):
        Step.__init__(self, plan)
        # partial entity definition to expand
        self.e_def = e_def
        # definition of relations to complete
        self.r_defs = r_defs

    def execute(self):
        """execute this step"""
        base_e_def = self.e_def
        result = []
        for row in self.execute_child():
            # get a new entity definition for this row
            e_def = copy(base_e_def)
            # complete this entity def using row values
            for i in range(len(self.r_defs)):
                rtype, rorder = self.r_defs[i]
                if rorder == RelationsStep.FINAL:
                    e_def[rtype] = row[i]
                elif rorder == RelationsStep.RELATION:
                    self.plan.add_relation_def( (e_def, rtype, row[i]) )
                    e_def.querier_pending_relations[(rtype, 'subject')] = row[i]
                else:
                    self.plan.add_relation_def( (row[i], rtype, e_def) )
                    e_def.querier_pending_relations[(rtype, 'object')] = row[i]
            result.append(e_def)
        self.plan.substitute_entity_def(base_e_def, result)


class InsertStep(Step):
    """step consisting in inserting new entities / relations"""

    def execute(self):
        """execute this step"""
        for step in self.children:
            assert isinstance(step, RelationsStep)
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
        todelete = frozenset(typed_eid(eid) for eid, in self.execute_child())
        session = self.plan.session
        delete = session.repo.glob_delete_entity
        # register pending eids first to avoid multiple deletion
        pending = session.transaction_data.setdefault('pendingeids', set())
        actual = todelete - pending
        pending |= actual
        for eid in actual:
            delete(session, eid)


class DeleteRelationsStep(Step):
    """step consisting in deleting relations"""

    def __init__(self, plan, rtype):
        Step.__init__(self, plan)
        self.rtype = rtype

    def execute(self):
        """execute this step"""
        session = self.plan.session
        delete = session.repo.glob_delete_relation
        for subj, obj in self.execute_child():
            delete(session, subj, self.rtype, obj)


class UpdateStep(Step):
    """step consisting in updating entities / adding relations from relations
    definitions and from results fetched in previous step
    """

    def __init__(self, plan, attribute_relations, relations, selected_index):
        Step.__init__(self, plan)
        self.attribute_relations = attribute_relations
        self.relations = relations
        self.selected_index = selected_index

    def execute(self):
        """execute this step"""
        plan = self.plan
        session = self.plan.session
        repo = session.repo
        edefs = {}
        # insert relations
        for row in self.execute_child():
            for relation in self.attribute_relations:
                lhs, rhs = relation.get_variable_parts()
                eid = typed_eid(row[self.selected_index[str(lhs)]])
                try:
                    edef = edefs[eid]
                except KeyError:
                    edefs[eid] = edef = session.eid_rset(eid).get_entity(0, 0)
                if isinstance(rhs, Constant):
                    # add constant values to entity def
                    value = rhs.eval(plan.args)
                    edef[relation.r_type] = value
                else:
                    edef[relation.r_type] = row[self.selected_index[str(rhs)]]
            for relation in self.relations:
                subj = row[self.selected_index[str(relation.children[0])]]
                obj = row[self.selected_index[str(relation.children[1])]]
                repo.glob_add_relation(session, subj, relation.r_type, obj)
        # update entities
        result = []
        for eid, edef in edefs.iteritems():
            repo.glob_update_entity(session, edef)
            result.append( (eid,) )
        return result
