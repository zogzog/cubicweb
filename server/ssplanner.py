"""plan execution of rql queries on a single source

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from copy import copy

from rql.stmts import Union, Select
from rql.nodes import Constant, Relation

from cubicweb import QueryError, typed_eid
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.rqlrewrite import add_types_restriction

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
                eschema = edef.e_schema
                attrtype = eschema.subjrels[rtype].objects(eschema)[0]
                if attrtype == 'Password' and isinstance(value, unicode):
                    value = value.encode('UTF8')
                edef[rtype] = value
            elif to_build.has_key(str(rhs)):
                # create a relation between two newly created variables
                plan.add_relation_def((edef, rtype, to_build[rhs.name]))
            else:
                to_select.setdefault(edef, []).append( (rtype, rhs, 0) )
    return to_select

def _extract_eid_consts(plan, rqlst):
    """return a dict mapping rqlst variable object to their eid if specified in
    the syntax tree
    """
    session = plan.session
    eschema = session.vreg.schema.eschema
    if rqlst.where is None:
        return {}
    eidconsts = {}
    neweids = session.transaction_data.get('neweids', ())
    checkread = session.read_security
    for rel in rqlst.where.get_nodes(Relation):
        if rel.r_type == 'eid' and not rel.neged(strict=True):
            lhs, rhs = rel.get_variable_parts()
            if isinstance(rhs, Constant):
                eid = typed_eid(rhs.eval(plan.args))
                # check read permission here since it may not be done by
                # the generated select substep if not emited (eg nothing
                # to be selected)
                if checkread and eid not in neweids:
                    eschema(session.describe(eid)[0]).check_perm(session, 'read')
                eidconsts[lhs.variable] = eid
    return eidconsts

def _build_substep_query(select, origrqlst):
    """Finalize substep select query that should be executed to get proper
    selection of stuff to insert/update.

    Return None when no query actually needed, else the given select node that
    will be used as substep query.

    When select has nothing selected, search in origrqlst for restriction that
    should be considered.
    """
    if select.selection:
        if origrqlst.where is not None:
            select.set_where(origrqlst.where.copy(select))
        return select
    if origrqlst.where is None:
        return
    for rel in origrqlst.where.iget_nodes(Relation):
        # search for a relation which is neither a type restriction (is) nor an
        # eid specification (not neged eid with constant node
        if rel.neged(strict=True) or not (
            rel.is_types_restriction() or
            (rel.r_type == 'eid'
             and isinstance(rel.get_variable_parts()[1], Constant))):
            break
    else:
        return
    select.set_where(origrqlst.where.copy(select))
    if not select.selection:
        # no selection, append one randomly
        select.append_selected(rel.children[0].copy(select))
    return select


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
        etype_class = session.vreg['etypes'].etype_class
        for etype, var in rqlst.main_variables:
            # need to do this since entity class is shared w. web client code !
            to_build[var.name] = etype_class(etype)(session)
            plan.add_entity_def(to_build[var.name])
        # add constant values to entity def, mark variables to be selected
        to_select = _extract_const_attributes(plan, rqlst, to_build)
        # add necessary steps to add relations and update attributes
        step = InsertStep(plan) # insert each entity and its relations
        step.children += self._compute_relation_steps(plan, rqlst, to_select)
        return (step,)

    def _compute_relation_steps(self, plan, rqlst, to_select):
        """handle the selection of relations for an insert query"""
        eidconsts = _extract_eid_consts(plan, rqlst)
        for edef, rdefs in to_select.items():
            # create a select rql st to fetch needed data
            select = Select()
            eschema = edef.e_schema
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
        getrschema = self.schema.rschema
        select = Select()   # potential substep query
        selectedidx = {}    # local state
        attributes = set()  # edited attributes
        updatedefs = []     # definition of update attributes/relations
        selidx = residx = 0 # substep selection / resulting rset indexes
        # search for eid const in the WHERE clause
        eidconsts = _extract_eid_consts(plan, rqlst)
        # build `updatedefs` describing things to update and add necessary
        # variables to the substep selection
        for i, relation in enumerate(rqlst.main_relations):
            if relation.r_type in VIRTUAL_RTYPES:
                raise QueryError('can not assign to %r relation'
                                 % relation.r_type)
            lhs, rhs = relation.get_variable_parts()
            lhskey = lhs.as_string('utf-8')
            if not lhskey in selectedidx:
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
            rhskey = rhs.as_string('utf-8')
            if not rhskey in selectedidx:
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
            updatedefs.append( (lhsinfo, rhsinfo, rschema) )
            if rschema.final or rschema.inlined:
                attributes.add(relation.r_type)
        # the update step
        step = UpdateStep(plan, updatedefs, attributes)
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
            edef = copy(base_edef)
            # complete this entity def using row values
            index = 0
            for rtype, rorder, value in self.rdefs:
                if value is _FROM_SUBSTEP:
                    value = row[index]
                    index += 1
                if rorder == InsertRelationsStep.FINAL:
                    edef[rtype] = value
                elif rorder == InsertRelationsStep.RELATION:
                    self.plan.add_relation_def( (edef, rtype, value) )
                    edef.querier_pending_relations[(rtype, 'subject')] = value
                else:
                    self.plan.add_relation_def( (value, rtype, edef) )
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
        todelete = frozenset(typed_eid(eid) for eid, in self.execute_child())
        session = self.plan.session
        delete = session.repo.glob_delete_entity
        # register pending eids first to avoid multiple deletion
        pending = session.transaction_data.setdefault('pendingeids', set())
        actual = todelete - pending
        pending |= actual
        for eid in actual:
            delete(session, eid)
        return results

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

    def __init__(self, plan, updatedefs, attributes):
        Step.__init__(self, plan)
        self.updatedefs = updatedefs
        self.attributes = attributes

    def execute(self):
        """execute this step"""
        session = self.plan.session
        repo = session.repo
        edefs = {}
        # insert relations
        if self.children:
            result = self.execute_child()
        else:
            result = [[]]
        for i, row in enumerate(result):
            newrow = []
            for (lhsinfo, rhsinfo, rschema) in self.updatedefs:
                lhsval = _handle_relterm(lhsinfo, row, newrow)
                rhsval = _handle_relterm(rhsinfo, row, newrow)
                if rschema.final or rschema.inlined:
                    eid = typed_eid(lhsval)
                    try:
                        edef = edefs[eid]
                    except KeyError:
                        edefs[eid] = edef = session.entity_from_eid(eid)
                    edef[str(rschema)] = rhsval
                else:
                    repo.glob_add_relation(session, lhsval, str(rschema), rhsval)
            result[i] = newrow
        # update entities
        for eid, edef in edefs.iteritems():
            repo.glob_update_entity(session, edef, self.attributes)
        return result

def _handle_relterm(info, row, newrow):
    if info[0] is _CONSTANT:
        val = info[1]
    else: # _FROM_SUBSTEP
        val = row[info[1]]
    if info[-1] is not None:
        newrow.append(val)
    return val
