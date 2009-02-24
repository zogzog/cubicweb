"""plan execution of rql queries on multiple sources

the best way to understand what are we trying to acheive here is to read
the unit-tests in unittest_querier_planner.py



Split and execution specifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For a system source and a ldap user source (only EUser and its attributes
is supported, no group or such):


:EUser X:
1. fetch EUser X from both sources and return concatenation of results


:EUser X WHERE X in_group G, G name 'users':
* catch 1
  1. fetch EUser X from both sources, store concatenation of results
     into a temporary table
  2. return the result of TMP X WHERE X in_group G, G name 'users' from
     the system source
     
* catch 2
  1. return the result of EUser X WHERE X in_group G, G name 'users'
     from system source, that's enough (optimization of the sql querier
     will avoid join on EUser, so we will directly get local eids)

    
:EUser X,L WHERE X in_group G, X login L, G name 'users':
1. fetch Any X,L WHERE X is EUser, X login L from both sources, store
   concatenation of results into a temporary table
2. return the result of Any X, L WHERE X is TMP, X login LX in_group G,
   G name 'users' from the system source


:Any X WHERE X owned_by Y:
* catch 1
  1. fetch EUser X from both sources, store concatenation of results
     into a temporary table
  2. return the result of Any X WHERE X owned_by Y, Y is TMP from
     the system source
     
* catch 2
  1. return the result of Any X WHERE X owned_by Y
     from system source, that's enough (optimization of the sql querier
     will avoid join on EUser, so we will directly get local eids)


:organization: Logilab
:copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from copy import deepcopy
from itertools import imap, ifilterfalse

from logilab.common.compat import any
from logilab.common.decorators import cached

from rql.stmts import Union, Select
from rql.nodes import VariableRef, Comparison, Relation, Constant, Exists, Variable

from cubicweb import server
from cubicweb.utils import make_uid
from cubicweb.server.utils import cleanup_solutions
from cubicweb.server.ssplanner import SSPlanner, OneFetchStep, add_types_restriction
from cubicweb.server.mssteps import *
from cubicweb.server.sources import AbstractSource

Variable._ms_table_key = lambda x: x.name
Relation._ms_table_key = lambda x: x.r_type
# str() Constant.value to ensure generated table name won't be unicode
Constant._ms_table_key = lambda x: str(x.value)

AbstractSource.dont_cross_relations = ()
AbstractSource.cross_relations = ()

def allequals(solutions):
    """return true if all solutions are identical"""
    sol = solutions.next()
    for sol_ in solutions:
        if sol_ != sol:
            return False
    return True
    
def need_aggr_step(select, sources, stepdefs=None):
    """return True if a temporary table is necessary to store some partial
    results to execute the given query
    """
    if len(sources) == 1:
        # can do everything at once with a single source
        return False
    if select.orderby or select.groupby or select.has_aggregat:
        # if more than one source, we need a temp table to deal with sort /
        # groups / aggregat if :
        # * the rqlst won't be splitted (in the other case the last query
        #   using partial temporary table can do sort/groups/aggregat without
        #   the need for a later AggrStep)
        # * the rqlst is splitted in multiple steps and there are more than one
        #   final step
        if stepdefs is None:
            return True
        has_one_final = False
        fstepsolindices = set()
        for stepdef in stepdefs:
            if stepdef[-1]:
                if has_one_final or frozenset(stepdef[2]) != fstepsolindices:
                    return True
                has_one_final = True
            else:
                fstepsolindices.update(stepdef[2])
    return False

def copy_node(newroot, node, subparts=()):
    newnode = node.__class__(*node.initargs(newroot))
    for part in subparts:
        newnode.append(part)
    return newnode
        
def same_scope(var):
    """return true if the variable is always used in the same scope"""
    try:
        return var.stinfo['samescope']
    except KeyError:
        for rel in var.stinfo['relations']:
            if not rel.scope is var.scope:
                var.stinfo['samescope'] = False
                return False
        var.stinfo['samescope'] = True
        return True

def select_group_sort(select): # XXX something similar done in rql2sql
    # add variables used in groups and sort terms to the selection
    # if necessary
    if select.groupby:
        for vref in select.groupby:
            if not vref in select.selection:
                select.append_selected(vref.copy(select))
    for sortterm in select.orderby:
        for vref in sortterm.iget_nodes(VariableRef):
            if not vref in select.get_selected_variables():
                # we can't directly insert sortterm.term because it references
                # a variable of the select before the copy.
                # XXX if constant term are used to define sort, their value
                # may necessite a decay
                select.append_selected(vref.copy(select))
                if select.groupby and not vref in select.groupby:
                    select.add_group_var(vref.copy(select))
            

class PartPlanInformation(object):
    """regroups necessary information to execute some part of a "global" rql
    query ("global" means as received by the querier, which may result in
    several internal queries, e.g. parts, due to security insertions)

    it exposes as well some methods helping in executing this part on a
    multi-sources repository, modifying its internal structure during the
    process

    :attr solutions: a list of mappings (varname -> vartype)
    :attr sourcesvars:
      a dictionnary telling for each source which variable/solution are
      supported, of the form {source : {varname: [solution index, ]}}
    """
    def __init__(self, plan, rqlst, rqlhelper=None):
        self.needsplit = False
        self.temptable = None
        self.finaltable = None
        self.plan = plan
        self.rqlst = rqlst
        self._session = plan.session
        self._solutions = rqlst.solutions
        self._solindices = range(len(self._solutions))
        # source : {var: [solution index, ]}
        self.sourcesvars = self._sourcesvars = {}
        # source : {relation: set(child variable and constant)}
        self._crossrelations = {}
        # dictionnary of variables which are linked to each other using a non
        # final relation which is supported by multiple sources
        self._linkedvars = {}
        self._crosslinkedvars = {}
        # processing
        self._compute_sourcesvars()
        self._remove_invalid_sources()
        self._compute_needsplit()
        self.sourcesvars = {}
        for k, v in self._sourcesvars.iteritems():
            self.sourcesvars[k] = {}
            for k2, v2 in v.iteritems():
                self.sourcesvars[k][k2] = v2.copy()
        self._inputmaps = {}
        if rqlhelper is not None: # else test
            self._insert_identity_variable = rqlhelper._annotator.rewrite_shared_optional

    def copy_solutions(self, solindices):
        return [self._solutions[solidx].copy() for solidx in solindices]
    
    @property
    @cached
    def part_sources(self):
        if self._sourcesvars:
            return tuple(sorted(self._sourcesvars))
        return (self._session.repo.system_source,)
    
    @property
    @cached
    def _sys_source_set(self):
        return frozenset((self._session.repo.system_source, solindex)
                         for solindex in self._solindices)        
       
    @cached
    def _norel_support_set(self, relation):
        """return a set of (source, solindex) where source doesn't support the
        relation
        """
        return frozenset((source, solidx) for source in self._session.repo.sources
                         for solidx in self._solindices
                         if not ((source.support_relation(relation.r_type) and
                                  not self.crossed_relation(source, relation))
                                 or relation.r_type in source.dont_cross_relations))


    def _compute_sourcesvars(self):
        """compute for each variable/solution in the rqlst which sources support
        them
        """
        repo = self._session.repo
        eschema = repo.schema.eschema
        sourcesvars = self._sourcesvars
        # find for each source which variable/solution are supported
        for varname, varobj in self.rqlst.defined_vars.items():
            # if variable has an eid specified, we can get its source directly
            # NOTE: use uidrels and not constnode to deal with "X eid IN(1,2,3,4)"
            if varobj.stinfo['uidrels']:
                vrels = varobj.stinfo['relations'] - varobj.stinfo['uidrels']
                for rel in varobj.stinfo['uidrels']:
                    if  rel.neged(strict=True) or rel.operator() != '=':
                        continue
                    for const in rel.children[1].get_nodes(Constant):
                        eid = const.eval(self.plan.args)
                        source = self._session.source_from_eid(eid)
                        if vrels and not any(source.support_relation(r.r_type)
                                             for r in vrels):
                            self._set_source_for_var(repo.system_source, varobj)
                        else:
                            self._set_source_for_var(source, varobj)
                continue
            rels = varobj.stinfo['relations']
            if not rels and not varobj.stinfo['typerels']:
                # (rare) case where the variable has no type specified nor
                # relation accessed ex. "Any MAX(X)"
                self._set_source_for_var(repo.system_source, varobj)
                continue
            for i, sol in enumerate(self._solutions):
                vartype = sol[varname]
                # skip final variable
                if eschema(vartype).is_final():
                    break
                for source in repo.sources:
                    if source.support_entity(vartype):
                        # the source support the entity type, though we will
                        # actually have to fetch from it only if
                        # * the variable isn't invariant
                        # * at least one supported relation specified
                        if not varobj._q_invariant or \
                               any(imap(source.support_relation,
                                        (r.r_type for r in rels if r.r_type != 'eid'))):
                            sourcesvars.setdefault(source, {}).setdefault(varobj, set()).add(i)
                        # if variable is not invariant and is used by a relation
                        # not supported by this source, we'll have to split the
                        # query
                        if not varobj._q_invariant and any(ifilterfalse(
                            source.support_relation, (r.r_type for r in rels))):
                            self.needsplit = True               

    def _handle_cross_relation(self, rel, relsources, vsources):
        crossvars = None
        for source in relsources:
            if rel.r_type in source.cross_relations:
                crossvars = set(x.variable for x in rel.get_nodes(VariableRef))
                crossvars.update(frozenset(x for x in rel.get_nodes(Constant)))
                assert len(crossvars) == 2
                ssource = self._session.repo.system_source
                needsplit = True
                flag = 0
                for v in crossvars:
                    if isinstance(v, Constant):
                        allsols = set(self._solindices)
                        try:
                            self._sourcesvars[ssource][v] = allsols
                        except KeyError:
                            self._sourcesvars[ssource] = {v: allsols}
                    if len(vsources[v]) == 1:
                        if iter(vsources[v]).next()[0].uri == 'system':
                            flag = 1
                            for ov in crossvars:
                                if ov is not v and (isinstance(ov, Constant) or ov._q_invariant):
                                    ssset = frozenset((ssource,))
                                    self._remove_sources(ov, vsources[ov] - ssset)
                        else:
                            for ov in crossvars:
                                if ov is not v and (isinstance(ov, Constant) or ov._q_invariant):
                                    needsplit = False
                                    break
                            else:
                                continue
                        if not rel.neged(strict=True):
                            break
                else:
                    self._crossrelations.setdefault(source, {})[rel] = crossvars
                    if not flag:
                        self._sourcesvars.setdefault(source, {})[rel] = set(self._solindices)
                    self._sourcesvars.setdefault(ssource, {})[rel] = set(self._solindices)
                    if needsplit:
                        self.needsplit = True
        return crossvars is None
        
    def _remove_invalid_sources(self):
        """removes invalid sources from `sourcesvars` member according to
        traversed relations and their properties (which sources support them,
        can they cross sources, etc...)
        """
        repo = self._session.repo
        rschema = repo.schema.rschema
        vsources = {}
        for rel in self.rqlst.iget_nodes(Relation):
            # process non final relations only
            # note: don't try to get schema for 'is' relation (not available
            # during bootstrap)
            if not rel.is_types_restriction() and not rschema(rel.r_type).is_final():
                # nothing to do if relation is not supported by multiple sources
                # or if some source has it listed in its cross_relations
                # attribute
                #
                # XXX code below don't deal if some source allow relation
                #     crossing but not another one
                relsources = repo.rel_type_sources(rel.r_type)
                crossvars = None
                if len(relsources) < 2:
                    # filter out sources being there because they have this
                    # relation in their dont_cross_relations attribute
                    relsources = [source for source in relsources
                                  if source.support_relation(rel.r_type)]
                    if relsources:
                        # this means the relation is using a variable inlined as
                        # a constant and another unsupported variable, in which
                        # case we put the relation in sourcesvars
                        self._sourcesvars.setdefault(relsources[0], {})[rel] = set(self._solindices)
                    continue
                lhs, rhs = rel.get_variable_parts()
                lhsv, rhsv = getattr(lhs, 'variable', lhs), getattr(rhs, 'variable', rhs)
                # update dictionnary of sources supporting lhs and rhs vars
                if not lhsv in vsources:
                    vsources[lhsv] = self._term_sources(lhs)
                if not rhsv in vsources:
                    vsources[rhsv] = self._term_sources(rhs)
                if self._handle_cross_relation(rel, relsources, vsources):
                    self._linkedvars.setdefault(lhsv, set()).add((rhsv, rel))
                    self._linkedvars.setdefault(rhsv, set()).add((lhsv, rel))
                else:
                    self._crosslinkedvars.setdefault(lhsv, set()).add((rhsv, rel))
                    self._crosslinkedvars.setdefault(rhsv, set()).add((lhsv, rel))
        for term in self._linkedvars:
            self._remove_sources_until_stable(term, vsources)
        if len(self._sourcesvars) > 1 and hasattr(self.plan.rqlst, 'main_relations'):
            # the querier doesn't annotate write queries, need to do it here
            self.plan.annotate_rqlst()
            # insert/update/delete queries, we may get extra information from
            # the main relation (eg relations to the left of the WHERE
            if self.plan.rqlst.TYPE == 'insert':
                inserted = dict((vref.variable, etype)
                                for etype, vref in self.plan.rqlst.main_variables)
            else:
                inserted = {}
            for rel in self.plan.rqlst.main_relations:
                if not rschema(rel.r_type).is_final():
                    # nothing to do if relation is not supported by multiple sources
                    if len(repo.rel_type_sources(rel.r_type)) < 2:
                        continue
                    lhs, rhs = rel.get_variable_parts()
                    try:
                        lhsv = self._extern_term(lhs, vsources, inserted)
                        rhsv = self._extern_term(rhs, vsources, inserted)
                    except KeyError, ex:
                        continue
                    norelsup = self._norel_support_set(rel)
                    self._remove_var_sources(lhsv, norelsup, rhsv, vsources)
                    self._remove_var_sources(rhsv, norelsup, lhsv, vsources)
        # cleanup linked var
        for var, linkedrelsinfo in self._linkedvars.iteritems():
            self._linkedvars[var] = frozenset(x[0] for x in linkedrelsinfo)
        # if there are other sources than the system source, consider simplified
        # variables'source
        if self._sourcesvars and self._sourcesvars.keys() != [self._session.repo.system_source]:
            # add source for rewritten constants to sourcesvars
            for vconsts in self.rqlst.stinfo['rewritten'].itervalues():
                const = vconsts[0]
                eid = const.eval(self.plan.args)
                source = self._session.source_from_eid(eid)
                if source is self._session.repo.system_source:
                    for const in vconsts:
                        self._set_source_for_var(source, const)
                elif source in self._sourcesvars:
                    source_scopes = frozenset(v.scope for v in self._sourcesvars[source])
                    for const in vconsts:
                        if const.scope in source_scopes:
                            self._set_source_for_var(source, const)
                            
    def _extern_term(self, term, vsources, inserted):
        var = term.variable
        if var.stinfo['constnode']:
            termv = var.stinfo['constnode']
            vsources[termv] = self._term_sources(termv)
        elif var in inserted:
            termv = var
            source = self._session.repo.locate_etype_source(inserted[var])
            vsources[termv] = set((source, solindex) for solindex in self._solindices)
        else:
            termv = self.rqlst.defined_vars[var.name]
            if not termv in vsources:
                vsources[termv] = self._term_sources(termv)
        return termv
        
    def _remove_sources_until_stable(self, var, vsources):
        sourcesvars = self._sourcesvars
        for ovar, rel in self._linkedvars.get(var, ()):
            if not var.scope is ovar.scope and rel.scope.neged(strict=True):
                # can't get information from relation inside a NOT exists
                # where variables don't belong to the same scope
                continue
            if not (var.scope is rel.scope and ovar.scope is rel.scope) and rel.ored():
                continue
            relsources = self._session.repo.rel_type_sources(rel.r_type)
            if rel.neged(strict=True) and (
                len(relsources) < 2
                or not isinstance(ovar, Variable)
                or ovar.valuable_references() != 1
                or any(sourcesvars[source][var] != sourcesvars[source][ovar]
                       for source in relsources
                       if var in sourcesvars.get(source, ())
                       and ovar in sourcesvars.get(source, ()))):
                # neged relation doesn't allow to infer variable sources unless we're
                # on a multisource relation for a variable only used by this relation
                # (eg "Any X WHERE NOT X multisource_rel Y" and over is Y), iif 
                continue
            norelsup = self._norel_support_set(rel)
            # compute invalid sources for variables and remove them
            self._remove_var_sources(var, norelsup, ovar, vsources)
            self._remove_var_sources(ovar, norelsup, var, vsources)
    
    def _remove_var_sources(self, var, norelsup, ovar, vsources):
        """remove invalid sources for var according to ovar's sources and the
        relation between those two variables. 
        """
        varsources = vsources[var]
        invalid_sources = varsources - (vsources[ovar] | norelsup)
        if invalid_sources:
            self._remove_sources(var, invalid_sources)
            varsources -= invalid_sources
            self._remove_sources_until_stable(var, vsources)
        
    def _compute_needsplit(self):
        """tell according to sourcesvars if the rqlst has to be splitted for
        execution among multiple sources
        
        the execution has to be split if
        * a source support an entity (non invariant) but doesn't support a
          relation on it
        * a source support an entity which is accessed by an optional relation
        * there is more than one source and either all sources'supported        
          variable/solutions are not equivalent or multiple variables have to
          be fetched from some source
        """
        # NOTE: < 2 since may be 0 on queries such as Any X WHERE X eid 2
        if len(self._sourcesvars) < 2: 
            self.needsplit = False
        elif not self.needsplit:
            if not allequals(self._sourcesvars.itervalues()):
                self.needsplit = True
            else:
                sample = self._sourcesvars.itervalues().next()
                if len(sample) > 1 and any(v for v in sample
                                           if not v in self._linkedvars
                                           and not v in self._crosslinkedvars):
                    self.needsplit = True
            
    def _set_source_for_var(self, source, var):
        self._sourcesvars.setdefault(source, {})[var] = set(self._solindices)

    def _term_sources(self, term):
        """returns possible sources for terms `term`"""
        if isinstance(term, Constant):
            source = self._session.source_from_eid(term.eval(self.plan.args))
            return set((source, solindex) for solindex in self._solindices)
        else:
            var = getattr(term, 'variable', term)
            sources = [source for source, varobjs in self.sourcesvars.iteritems()
                       if var in varobjs]
            return set((source, solindex) for source in sources
                       for solindex in self.sourcesvars[source][var])

    def _remove_sources(self, var, sources):
        """removes invalid sources (`sources`) from `sourcesvars`

        :param sources: the list of sources to remove
        :param var: the analyzed variable
        """
        sourcesvars = self._sourcesvars
        for source, solindex in sources:
            try:
                sourcesvars[source][var].remove(solindex)
            except KeyError:
                return # may occur with subquery column alias
            if not sourcesvars[source][var]:
                del sourcesvars[source][var]
                if not sourcesvars[source]:
                    del sourcesvars[source]

    def crossed_relation(self, source, relation):
        return relation in self._crossrelations.get(source, ())
    
    def part_steps(self):
        """precompute necessary part steps before generating actual rql for
        each step. This is necessary to know if an aggregate step will be
        necessary or not.
        """
        steps = []
        select = self.rqlst
        rschema = self.plan.schema.rschema
        for source in self.part_sources:
            sourcevars = self._sourcesvars[source]
            while sourcevars:
                # take a variable randomly, and all variables supporting the
                # same solutions
                var, solindices = self._choose_var(sourcevars)
                if source.uri == 'system':
                    # ensure all variables are available for the latest step
                    # (missing one will be available from temporary tables
                    # of previous steps)
                    scope = select
                    variables = scope.defined_vars.values() + scope.aliases.values()
                    sourcevars.clear()
                else:
                    scope = var.scope
                    variables = self._expand_vars(var, source, sourcevars, scope, solindices)
                    if not sourcevars:
                        del self._sourcesvars[source]
                # find which sources support the same variables/solutions
                sources = self._expand_sources(source, variables, solindices)
                # suppose this is a final step until the contrary is proven
                final = scope is select
                # set of variables which should be additionaly selected when
                # possible
                needsel = set()
                # add attribute variables and mark variables which should be
                # additionaly selected when possible
                for var in select.defined_vars.itervalues():
                    if not var in variables:
                        stinfo = var.stinfo
                        for ovar, rtype in stinfo['attrvars']:
                            if ovar in variables:
                                needsel.add(var.name)
                                variables.append(var)
                                break
                        else:
                            needsel.add(var.name)
                            final = False
                if final and source.uri != 'system':
                    # check rewritten constants
                    for vconsts in select.stinfo['rewritten'].itervalues():
                        const = vconsts[0]
                        eid = const.eval(self.plan.args)
                        _source = self._session.source_from_eid(eid)
                        if len(sources) > 1 or not _source in sources:
                            # if there is some rewriten constant used by a
                            # not neged relation while there are some source
                            # not supporting the associated entity, this step
                            # can't be final (unless the relation is explicitly
                            # in `variables`, eg cross relations)
                            for c in vconsts:
                                rel = c.relation()
                                if rel is None or not (rel in variables or rel.neged(strict=True)):
                                #if rel is not None and rel.r_type == 'identity' and not rel.neged(strict=True):
                                    final = False
                                    break
                            break
                # check where all relations are supported by the sources
                for rel in scope.iget_nodes(Relation):
                    if rel.is_types_restriction():
                        continue
                    # take care not overwriting the existing "source" identifier
                    for _source in sources:
                        if not _source.support_relation(rel.r_type):
                            for vref in rel.iget_nodes(VariableRef):
                                needsel.add(vref.name)
                            final = False
                            break
                        elif self.crossed_relation(_source, rel) and not rel in variables:
                            final = False
                            break
                    else:
                        if not scope is select:
                            self._exists_relation(rel, variables, needsel)
                        # if relation is supported by all sources and some of
                        # its lhs/rhs variable isn't in "variables", and the
                        # other end *is* in "variables", mark it have to be
                        # selected
                        if source.uri != 'system' and not rschema(rel.r_type).is_final():
                            lhs, rhs = rel.get_variable_parts()
                            try:
                                lhsvar = lhs.variable
                            except AttributeError:
                                lhsvar = lhs
                            try:
                                rhsvar = rhs.variable
                            except AttributeError:
                                rhsvar = rhs
                            if lhsvar in variables and not rhsvar in variables:
                                needsel.add(lhsvar.name)
                            elif rhsvar in variables and not lhsvar in variables:
                                needsel.add(rhsvar.name)
                if final:
                    self._cleanup_sourcesvars(sources, solindices)
                # XXX rename: variables may contain Relation and Constant nodes...
                steps.append( (sources, variables, solindices, scope, needsel,
                               final) )
        return steps

    def _exists_relation(self, rel, variables, needsel):
        rschema = self.plan.schema.rschema(rel.r_type)
        lhs, rhs = rel.get_variable_parts()
        try:
            lhsvar, rhsvar = lhs.variable, rhs.variable
        except AttributeError:
            pass
        else:
            # supported relation with at least one end supported, check the
            # other end is in as well. If not this usually means the
            # variable is refed by an outer scope and should be substituted
            # using an 'identity' relation (else we'll get a conflict of
            # temporary tables)
            if rhsvar in variables and not lhsvar in variables:
                self._identity_substitute(rel, lhsvar, variables, needsel)
            elif lhsvar in variables and not rhsvar in variables:
                self._identity_substitute(rel, rhsvar, variables, needsel)

    def _identity_substitute(self, relation, var, variables, needsel):
        newvar = self._insert_identity_variable(relation.scope, var)
        if newvar is not None:
            # ensure relation is using '=' operator, else we rely on a
            # sqlgenerator side effect (it won't insert an inequality operator
            # in this case)
            relation.children[1].operator = '=' 
            variables.append(newvar)
            needsel.add(newvar.name)
        
    def _choose_var(self, sourcevars):
        secondchoice = None
        if len(self._sourcesvars) > 1:
            # priority to variable from subscopes
            for var in sourcevars:
                if not var.scope is self.rqlst:
                    if isinstance(var, Variable):
                        return var, sourcevars.pop(var)
                    secondchoice = var
        else:
            # priority to variable outer scope
            for var in sourcevars:
                if var.scope is self.rqlst:
                    if isinstance(var, Variable):
                        return var, sourcevars.pop(var)
                    secondchoice = var
        if secondchoice is not None:
            return secondchoice, sourcevars.pop(secondchoice)
        # priority to variable
        for var in sourcevars:
            if isinstance(var, Variable):
                return var, sourcevars.pop(var)
        # whatever
        var = iter(sourcevars).next()
        return var, sourcevars.pop(var)
            
            
    def _expand_vars(self, var, source, sourcevars, scope, solindices):
        variables = [var]
        nbunlinked = 1
        linkedvars = self._linkedvars
        # variable has to belong to the same scope if there is more
        # than the system source remaining
        if len(self._sourcesvars) > 1 and not scope is self.rqlst:
            candidates = (v for v in sourcevars.keys() if scope is v.scope)
        else:
            candidates = sourcevars #.iterkeys()
        # we only want one unlinked variable in each generated query
        candidates = [v for v in candidates
                      if isinstance(v, Constant) or
                      (solindices.issubset(sourcevars[v]) and v in linkedvars)]
        accept_var = lambda x: (isinstance(x, Constant) or any(v for v in variables if v in linkedvars.get(x, ())))
        source_cross_rels = self._crossrelations.get(source, ())
        if isinstance(var, Relation) and var in source_cross_rels:
            cross_vars = source_cross_rels.pop(var)
            base_accept_var = accept_var
            accept_var = lambda x: (base_accept_var(x) or x in cross_vars)
            for refed in cross_vars:
                if not refed in candidates:
                    candidates.append(refed)
        else:
            cross_vars = ()
        # repeat until no variable can't be added, since addition of a new
        # variable may permit to another one to be added
        modified = True
        while modified and candidates:
            modified = False
            for var in candidates[:]:
                if accept_var(var):
                    variables.append(var)
                    try:
                        # constant nodes should be systematically deleted
                        if isinstance(var, Constant):
                            del sourcevars[var]
                        else:
                            # variable nodes should be deleted once all possible
                            # solutions indices have been consumed
                            sourcevars[var] -= solindices
                            if not sourcevars[var]:
                                del sourcevars[var]
                    except KeyError:
                        assert var in cross_vars
                    candidates.remove(var)
                    modified = True
        return variables
    
    def _expand_sources(self, selected_source, vars, solindices):
        sources = [selected_source]
        sourcesvars = self._sourcesvars
        for source in sourcesvars:
            if source is selected_source:
                continue
            for var in vars:
                if not (var in sourcesvars[source] and 
                        solindices.issubset(sourcesvars[source][var])):
                    break
            else:
                sources.append(source)
                if source.uri != 'system':
                    for var in vars:
                        varsolindices = sourcesvars[source][var]
                        varsolindices -= solindices
                        if not varsolindices:
                            del sourcesvars[source][var]                
        return sources
    
    def _cleanup_sourcesvars(self, sources, solindices):
        """on final parts, remove solutions so we know they are already processed"""
        for source in sources:
            try:
                sourcevars = self._sourcesvars[source]
            except KeyError:
                continue
            for var, varsolindices in sourcevars.items():
                if isinstance(var, Relation) and self.crossed_relation(source, var):
                    continue
                varsolindices -= solindices
                if not varsolindices:
                    del sourcevars[var]
                    
    def merge_input_maps(self, allsolindices):
        """inputmaps is a dictionary with tuple of solution indices as key with an
        associateed input map as value. This function compute for each solution 
        its necessary input map and return them grouped

        ex:
        inputmaps = {(0, 1, 2): {'A': 't1.login1', 'U': 't1.C0', 'U.login': 't1.login1'},
                     (1,): {'X': 't2.C0', 'T': 't2.C1'}}
        return : [([1],  {'A': 't1.login1', 'U': 't1.C0', 'U.login': 't1.login1',
                           'X': 't2.C0', 'T': 't2.C1'}),                   
                  ([0,2], {'A': 't1.login1', 'U': 't1.C0', 'U.login': 't1.login1'})]
        """
        if not self._inputmaps:
            return [(allsolindices, None)]
        mapbysol = {}
        # compute a single map for each solution
        for solindices, basemap in self._inputmaps.iteritems():
            for solindex in solindices:
                solmap = mapbysol.setdefault(solindex, {})
                solmap.update(basemap)
                try:
                    allsolindices.remove(solindex)
                except KeyError:
                    continue # already removed
        # group results by identical input map
        result = []
        for solindex, solmap in mapbysol.iteritems():
            for solindices, commonmap in result:
                if commonmap == solmap:
                    solindices.append(solindex)
                    break
            else:
                result.append( ([solindex], solmap) )
        if allsolindices:
            result.append( (list(allsolindices), None) )
        return result

    def build_final_part(self, select, solindices, inputmap,  sources,
                         insertedvars):
        plan = self.plan
        rqlst = plan.finalize(select, [self._solutions[i] for i in solindices],
                              insertedvars)
        if self.temptable is None and self.finaltable is None:
            return OneFetchStep(plan, rqlst, sources, inputmap=inputmap)
        table = self.temptable or self.finaltable
        return FetchStep(plan, rqlst, sources, table, True, inputmap)

    def build_non_final_part(self, select, solindices, sources, insertedvars,
                             table):
        """non final step, will have to store results in a temporary table"""
        plan = self.plan
        rqlst = plan.finalize(select, [self._solutions[i] for i in solindices],
                              insertedvars)
        step = FetchStep(plan, rqlst, sources, table, False)
        # update input map for following steps, according to processed solutions
        inputmapkey = tuple(sorted(solindices))
        inputmap = self._inputmaps.setdefault(inputmapkey, {})
        inputmap.update(step.outputmap)
        plan.add_step(step)


class MSPlanner(SSPlanner):
    """MultiSourcesPlanner: build execution plan for rql queries

    decompose the RQL query according to sources'schema
    """
        
    def build_select_plan(self, plan, rqlst):
        """build execution plan for a SELECT RQL query
               
        the rqlst should not be tagged at this point
        """
        if server.DEBUG:
            print '-'*80
            print 'PLANNING', rqlst
        for select in rqlst.children:
            if len(select.solutions) > 1:
                hasmultiplesols = True
                break
        else:
            hasmultiplesols = False
        # preprocess deals with security insertion and returns a new syntax tree
        # which have to be executed to fulfill the query: according
        # to permissions for variable's type, different rql queries may have to
        # be executed
        plan.preprocess(rqlst)
        ppis = [PartPlanInformation(plan, select, self.rqlhelper)
                for select in rqlst.children]
        steps = self._union_plan(plan, rqlst, ppis)
        if server.DEBUG:
            from pprint import pprint
            for step in plan.steps:
                pprint(step.test_repr())
            pprint(steps[0].test_repr())
        return steps

    def _ppi_subqueries(self, ppi):
        # part plan info for subqueries
        plan = ppi.plan
        inputmap = {}
        for subquery in ppi.rqlst.with_[:]:
            sppis = [PartPlanInformation(plan, select)
                     for select in subquery.query.children]
            for sppi in sppis:
                if sppi.needsplit or sppi.part_sources != ppi.part_sources:
                    temptable = 'T%s' % make_uid(id(subquery))
                    sstep = self._union_plan(plan, subquery.query, sppis, temptable)[0]
                    break
            else:
                sstep = None
            if sstep is not None:
                ppi.rqlst.with_.remove(subquery)
                for i, colalias in enumerate(subquery.aliases):
                    inputmap[colalias.name] = '%s.C%s' % (temptable, i)
                ppi.plan.add_step(sstep)
        return inputmap
    
    def _union_plan(self, plan, union, ppis, temptable=None):
        tosplit, cango, allsources = [], {}, set()
        for planinfo in ppis:
            if planinfo.needsplit:
                tosplit.append(planinfo)
            else:
                cango.setdefault(planinfo.part_sources, []).append(planinfo)
            for source in planinfo.part_sources:
                allsources.add(source)
        # first add steps for query parts which doesn't need to splitted
        steps = []
        for sources, cppis in cango.iteritems():
            byinputmap = {}
            for ppi in cppis:
                select = ppi.rqlst
                if sources != (plan.session.repo.system_source,):
                    add_types_restriction(self.schema, select)
                # part plan info for subqueries
                inputmap = self._ppi_subqueries(ppi)
                aggrstep = need_aggr_step(select, sources)
                if aggrstep:
                    atemptable = 'T%s' % make_uid(id(select))
                    sunion = Union()
                    sunion.append(select)
                    selected = select.selection[:]
                    select_group_sort(select)
                    step = AggrStep(plan, selected, select, atemptable, temptable)
                    step.set_limit_offset(select.limit, select.offset)
                    select.limit = None
                    select.offset = 0
                    fstep = FetchStep(plan, sunion, sources, atemptable, True, inputmap)
                    step.children.append(fstep)
                    steps.append(step)
                else:
                    byinputmap.setdefault(tuple(inputmap.iteritems()), []).append( (select) )
            for inputmap, queries in byinputmap.iteritems():
                inputmap = dict(inputmap)
                sunion = Union()
                for select in queries:
                    sunion.append(select)
                if temptable:
                    steps.append(FetchStep(plan, sunion, sources, temptable, True, inputmap))
                else:
                    steps.append(OneFetchStep(plan, sunion, sources, inputmap))
        # then add steps for splitted query parts
        for planinfo in tosplit:
            steps.append(self.split_part(planinfo, temptable))
        if len(steps) > 1:
            if temptable:
                step = UnionFetchStep(plan)
            else:
                step = UnionStep(plan)
            step.children = steps
            return (step,)
        return steps

    # internal methods for multisources decomposition #########################
    
    def split_part(self, ppi, temptable):
        ppi.finaltable = temptable
        plan = ppi.plan
        select = ppi.rqlst
        subinputmap = self._ppi_subqueries(ppi)
        stepdefs = ppi.part_steps()
        if need_aggr_step(select, ppi.part_sources, stepdefs):
            atemptable = 'T%s' % make_uid(id(select))
            selection = select.selection[:]
            select_group_sort(select)
        else:
            atemptable = None
            selection = select.selection
        ppi.temptable = atemptable
        vfilter = VariablesFiltererVisitor(self.schema, ppi)
        steps = []
        for sources, variables, solindices, scope, needsel, final in stepdefs:
            # extract an executable query using only the specified variables
            if sources[0].uri == 'system':
                # in this case we have to merge input maps before call to
                # filter so already processed restriction are correctly
                # removed
                solsinputmaps = ppi.merge_input_maps(solindices)
                for solindices, inputmap in solsinputmaps:
                    minrqlst, insertedvars = vfilter.filter(
                        sources, variables, scope, set(solindices), needsel, final)
                    if inputmap is None:
                        inputmap = subinputmap
                    else:
                        inputmap.update(subinputmap)
                    steps.append(ppi.build_final_part(minrqlst, solindices, inputmap,
                                                      sources, insertedvars))
            else:
                # this is a final part (i.e. retreiving results for the
                # original query part) if all variable / sources have been
                # treated or if this is the last shot for used solutions
                minrqlst, insertedvars = vfilter.filter(
                    sources, variables, scope, solindices, needsel, final)
                if final:
                    solsinputmaps = ppi.merge_input_maps(solindices)
                    for solindices, inputmap in solsinputmaps:
                        if inputmap is None:
                            inputmap = subinputmap
                        else:
                            inputmap.update(subinputmap)
                        steps.append(ppi.build_final_part(minrqlst, solindices, inputmap,
                                                  sources, insertedvars))
                else:
                    table = '_T%s%s' % (''.join(sorted(v._ms_table_key() for v in variables)),
                                        ''.join(sorted(str(i) for i in solindices)))
                    ppi.build_non_final_part(minrqlst, solindices, sources,
                                             insertedvars, table)
        # finally: join parts, deal with aggregat/group/sorts if necessary
        if atemptable is not None:
            step = AggrStep(plan, selection, select, atemptable, temptable)
            step.children = steps
        elif len(steps) > 1:
            if select.need_intersect or any(select.need_intersect
                                            for step in steps
                                            for select in step.union.children):
                if temptable:
                    step = IntersectFetchStep(plan)
                else:
                    step = IntersectStep(plan)
            else:
                if temptable:
                    step = UnionFetchStep(plan)
                else:
                    step = UnionStep(plan)
            step.children = steps
        else:
            step = steps[0]
        if select.limit is not None or select.offset:
            step.set_limit_offset(select.limit, select.offset)
        return step

    
class UnsupportedBranch(Exception):
    pass


class VariablesFiltererVisitor(object):
    def __init__(self, schema, ppi):
        self.schema = schema
        self.ppi = ppi
        self.skip = {}
        self.hasaggrstep = self.ppi.temptable
        self.extneedsel = frozenset(vref.name for sortterm in ppi.rqlst.orderby
                                    for vref in sortterm.iget_nodes(VariableRef))
        
    def _rqlst_accept(self, rqlst, node, newroot, variables, setfunc=None):
        try:
            newrestr, node_ = node.accept(self, newroot, variables[:])
        except UnsupportedBranch:
            return rqlst
        if setfunc is not None and newrestr is not None:
            setfunc(newrestr)
        if not node_ is node:
            rqlst = node.parent
        return rqlst

    def filter(self, sources, variables, rqlst, solindices, needsel, final):
        if server.DEBUG:
            print 'filter', final and 'final' or '', sources, variables, rqlst, solindices, needsel
        newroot = Select()
        self.sources = sorted(sources)
        self.variables = variables
        self.solindices = solindices
        self.final = final
        # variables which appear in unsupported branches
        needsel |= self.extneedsel
        self.needsel = needsel
        # variables which appear in supported branches
        self.mayneedsel = set()
        # new inserted variables
        self.insertedvars = []
        # other structures (XXX document)
        self.mayneedvar, self.hasvar = {}, {}
        self.use_only_defined = False
        self.scopes = {rqlst: newroot}
        if rqlst.where:
            rqlst = self._rqlst_accept(rqlst, rqlst.where, newroot, variables,
                                       newroot.set_where)
        if isinstance(rqlst, Select):
            self.use_only_defined = True
            if rqlst.groupby:
                groupby = []
                for node in rqlst.groupby:
                    rqlst = self._rqlst_accept(rqlst, node, newroot, variables,
                                               groupby.append)
                if groupby:
                    newroot.set_groupby(groupby)
            if rqlst.having:
                having = []
                for node in rqlst.having:
                    rqlst = self._rqlst_accept(rqlst, node, newroot, variables,
                                               having.append)
                if having:
                    newroot.set_having(having)
            if final and rqlst.orderby and not self.hasaggrstep:
                orderby = []
                for node in rqlst.orderby:
                    rqlst = self._rqlst_accept(rqlst, node, newroot, variables,
                                               orderby.append)
                if orderby:
                    newroot.set_orderby(orderby)
            self.process_selection(newroot, variables, rqlst)
        elif not newroot.where:
            # no restrictions have been copied, just select variables and add
            # type restriction (done later by add_types_restriction)
            for v in variables:
                if not isinstance(v, Variable):
                    continue
                newroot.append_selected(VariableRef(newroot.get_variable(v.name)))
        solutions = self.ppi.copy_solutions(solindices)
        cleanup_solutions(newroot, solutions)
        newroot.set_possible_types(solutions)
        if final:
            if self.hasaggrstep:
                self.add_necessary_selection(newroot, self.mayneedsel & self.extneedsel)
            newroot.distinct = rqlst.distinct
        else:
            self.add_necessary_selection(newroot, self.mayneedsel & self.needsel)
            # insert vars to fetch constant values when needed
            for (varname, rschema), reldefs in self.mayneedvar.iteritems():
                for rel, ored in reldefs:
                    if not (varname, rschema) in self.hasvar:
                        self.hasvar[(varname, rschema)] = None # just to avoid further insertion
                        cvar = newroot.make_variable()
                        for sol in newroot.solutions:
                            sol[cvar.name] = rschema.objects(sol[varname])[0]
                        # if the current restriction is not used in a OR branch,
                        # we can keep it, else we have to drop the constant
                        # restriction (or we may miss some results)
                        if not ored:
                            rel = rel.copy(newroot)
                            newroot.add_restriction(rel)
                        # add a relation to link the variable
                        newroot.remove_node(rel.children[1])
                        cmp = Comparison('=')
                        rel.append(cmp)
                        cmp.append(VariableRef(cvar))
                        self.insertedvars.append((varname, rschema, cvar.name))
                        newroot.append_selected(VariableRef(newroot.get_variable(cvar.name)))
                        # NOTE: even if the restriction is done by this query, we have
                        # to let it in the original rqlst so that it appears anyway in
                        # the "final" query, else we may change the meaning of the query
                        # if there are NOT somewhere :
                        # 'NOT X relation Y, Y name "toto"' means X WHERE X isn't related
                        # to Y whose name is toto while
                        # 'NOT X relation Y' means X WHERE X has no 'relation' (whatever Y)
                    elif ored:
                        newroot.remove_node(rel)
        add_types_restriction(self.schema, rqlst, newroot, solutions)
        if server.DEBUG:
            print '--->', newroot
        return newroot, self.insertedvars
        
    def visit_and(self, node, newroot, variables):
        subparts = []
        for i in xrange(len(node.children)):
            child = node.children[i]
            try:
                newchild, child_ = child.accept(self, newroot, variables)
                if not child_ is child:
                    node = child_.parent
                if newchild is None:
                    continue
                subparts.append(newchild)
            except UnsupportedBranch:
                continue
        if not subparts:
            return None, node
        if len(subparts) == 1:
            return subparts[0], node
        return copy_node(newroot, node, subparts), node

    visit_or = visit_and

    def _relation_supported(self, relation):
        rtype = relation.r_type
        for source in self.sources:
            if not source.support_relation(rtype) \
                   or (rtype in source.cross_relations and not relation in self.variables):#self.ppi.crossed_relation(source, relation):
                return False
        if not self.final:
            rschema = self.schema.rschema(relation.r_type)
            if not rschema.is_final():
                for term in relation.get_nodes((VariableRef, Constant)):
                    term = getattr(term, 'variable', term)
                    termsources = sorted(set(x[0] for x in self.ppi._term_sources(term)))
                    if termsources and termsources != self.sources:
                        return False
        return True
        
    def visit_relation(self, node, newroot, variables):
        if not node.is_types_restriction():
            if node in self.skip and self.solindices.issubset(self.skip[node]):
                if not self.schema.rschema(node.r_type).is_final():
                    # can't really skip the relation if one variable is selected and only
                    # referenced by this relation
                    for vref in node.iget_nodes(VariableRef):
                        stinfo = vref.variable.stinfo
                        if stinfo['selected'] and len(stinfo['relations']) == 1:
                            break
                    else:
                        return None, node
                else:
                    return None, node
            if not self._relation_supported(node):
                raise UnsupportedBranch()
        # don't copy type restriction unless this is the only relation for the
        # rhs variable, else they'll be reinserted later as needed (else we may
        # copy a type restriction while the variable is not actually used)
        elif not any(self._relation_supported(rel)
                     for rel in node.children[0].variable.stinfo['relations']):
            rel, node = self.visit_default(node, newroot, variables)
            return rel, node
        else:
            raise UnsupportedBranch()
        rschema = self.schema.rschema(node.r_type)
        res = self.visit_default(node, newroot, variables)[0]
        ored = node.ored()
        if rschema.is_final() or rschema.inlined:
            vrefs = node.children[1].get_nodes(VariableRef)
            if not vrefs:
                if not ored:
                    self.skip.setdefault(node, set()).update(self.solindices)
                else:
                    self.mayneedvar.setdefault((node.children[0].name, rschema), []).append( (res, ored) )                    
            else:
                assert len(vrefs) == 1
                vref = vrefs[0]
                # XXX check operator ?
                self.hasvar[(node.children[0].name, rschema)] = vref
                if self._may_skip_attr_rel(rschema, node, vref, ored, variables, res):
                    self.skip.setdefault(node, set()).update(self.solindices)
        elif not ored:
            self.skip.setdefault(node, set()).update(self.solindices)
        return res, node

    def _may_skip_attr_rel(self, rschema, rel, vref, ored, variables, res):
        var = vref.variable
        if ored:
            return False
        if var.name in self.extneedsel or var.stinfo['selected']:
            return False
        if not same_scope(var):
            return False
        if any(v for v,_ in var.stinfo['attrvars'] if not v.name in variables):
            return False
        return True
        
    def visit_exists(self, node, newroot, variables):
        newexists = node.__class__()
        self.scopes = {node: newexists}
        subparts, node = self._visit_children(node, newroot, variables)
        if not subparts:
            return None, node
        newexists.set_where(subparts[0])
        return newexists, node
    
    def visit_not(self, node, newroot, variables):
        subparts, node = self._visit_children(node, newroot, variables)
        if not subparts:
            return None, node
        return copy_node(newroot, node, subparts), node
    
    def visit_group(self, node, newroot, variables):
        if not self.final:
            return None, node
        return self.visit_default(node, newroot, variables)
            
    def visit_variableref(self, node, newroot, variables):
        if self.use_only_defined:
            if not node.variable.name in newroot.defined_vars:
                raise UnsupportedBranch(node.name)
        elif not node.variable in variables:
            raise UnsupportedBranch(node.name)
        self.mayneedsel.add(node.name)
        # set scope so we can insert types restriction properly
        newvar = newroot.get_variable(node.name)
        newvar.stinfo['scope'] = self.scopes.get(node.variable.scope, newroot)
        return VariableRef(newvar), node

    def visit_constant(self, node, newroot, variables):
        return copy_node(newroot, node), node
    
    def visit_default(self, node, newroot, variables):
        subparts, node = self._visit_children(node, newroot, variables)
        return copy_node(newroot, node, subparts), node
        
    visit_comparison = visit_mathexpression = visit_constant = visit_function = visit_default
    visit_sort = visit_sortterm = visit_default
    
    def _visit_children(self, node, newroot, variables):
        subparts = []
        for i in xrange(len(node.children)):
            child = node.children[i]
            newchild, child_ = child.accept(self, newroot, variables)
            if not child is child_:
                node = child_.parent
            if newchild is not None:
                subparts.append(newchild)
        return subparts, node
    
    def process_selection(self, newroot, variables, rqlst):
        if self.final:
            for term in rqlst.selection:
                newroot.append_selected(term.copy(newroot))
                for vref in term.get_nodes(VariableRef):
                    self.needsel.add(vref.name)
            return 
        for term in rqlst.selection:
            vrefs = term.get_nodes(VariableRef)
            if vrefs:
                supportedvars = []
                for vref in vrefs:
                    var = vref.variable
                    if var in variables:
                        supportedvars.append(vref)
                        continue
                    else:
                        self.needsel.add(vref.name)
                        break
                else:
                    for vref in vrefs:
                        newroot.append_selected(vref.copy(newroot))
                    supportedvars = []
                for vref in supportedvars:
                    if not vref in newroot.get_selected_variables():
                        newroot.append_selected(VariableRef(newroot.get_variable(vref.name)))
            
    def add_necessary_selection(self, newroot, variables):
        selected = tuple(newroot.get_selected_variables())
        for varname in variables:
            var = newroot.defined_vars[varname]
            for vref in var.references():
                rel = vref.relation()
                if rel is None and vref in selected:
                    # already selected
                    break
            else:
                selvref = VariableRef(var)
                newroot.append_selected(selvref)
                if newroot.groupby:
                    newroot.add_group_var(VariableRef(selvref.variable, noautoref=1))
