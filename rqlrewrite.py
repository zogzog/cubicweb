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
"""RQL rewriting utilities : insert rql expression snippets into rql syntax
tree.

This is used for instance for read security checking in the repository.
"""
__docformat__ = "restructuredtext en"

from six import text_type, string_types

from rql import nodes as n, stmts, TypeResolverException
from rql.utils import common_parent

from yams import BadSchemaDefinition

from logilab.common import tempattr
from logilab.common.graph import has_path

from cubicweb import Unauthorized
from cubicweb.schema import RRQLExpression

def cleanup_solutions(rqlst, solutions):
    for sol in solutions:
        for vname in list(sol):
            if not (vname in rqlst.defined_vars or vname in rqlst.aliases):
                del sol[vname]


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
        for varname, etype in solution.items():
            # XXX not considering aliases by design, right ?
            if varname not in newroot.defined_vars or eschema(etype).final:
                continue
            allpossibletypes.setdefault(varname, set()).add(etype)
    # XXX could be factorized with add_etypes_restriction from rql 0.31
    for varname in sorted(allpossibletypes):
        var = newroot.defined_vars[varname]
        stinfo = var.stinfo
        if stinfo.get('uidrel') is not None:
            continue # eid specified, no need for additional type specification
        try:
            typerel = rqlst.defined_vars[varname].stinfo.get('typerel')
        except KeyError:
            assert varname in rqlst.aliases
            continue
        if newroot is rqlst and typerel is not None:
            mytyperel = typerel
        else:
            for vref in var.references():
                rel = vref.relation()
                if rel and rel.is_types_restriction():
                    mytyperel = rel
                    break
            else:
                mytyperel = None
        possibletypes = allpossibletypes[varname]
        if mytyperel is not None:
            if mytyperel.r_type == 'is_instance_of':
                # turn is_instance_of relation into a is relation since we've
                # all possible solutions and don't want to bother with
                # potential is_instance_of incompatibility
                mytyperel.r_type = 'is'
                if len(possibletypes) > 1:
                    node = n.Function('IN')
                    for etype in sorted(possibletypes):
                        node.append(n.Constant(etype, 'etype'))
                else:
                    etype = next(iter(possibletypes))
                    node = n.Constant(etype, 'etype')
                comp = mytyperel.children[1]
                comp.replace(comp.children[0], node)
            else:
                # variable has already some strict types restriction. new
                # possible types can only be a subset of existing ones, so only
                # remove no more possible types
                for cst in mytyperel.get_nodes(n.Constant):
                    if not cst.value in possibletypes:
                        cst.parent.remove(cst)
        else:
            # we have to add types restriction
            if stinfo.get('scope') is not None:
                rel = var.scope.add_type_restriction(var, possibletypes)
            else:
                # tree is not annotated yet, no scope set so add the restriction
                # to the root
                rel = newroot.add_type_restriction(var, possibletypes)
            stinfo['typerel'] = rel
        stinfo['possibletypes'] = possibletypes


def remove_solutions(origsolutions, solutions, defined):
    """when a rqlst has been generated from another by introducing security
    assertions, this method returns solutions which are contained in orig
    solutions
    """
    newsolutions = []
    for origsol in origsolutions:
        for newsol in solutions[:]:
            for var, etype in origsol.items():
                try:
                    if newsol[var] != etype:
                        try:
                            defined[var].stinfo['possibletypes'].remove(newsol[var])
                        except KeyError:
                            pass
                        break
                except KeyError:
                    # variable has been rewritten
                    continue
            else:
                newsolutions.append(newsol)
                solutions.remove(newsol)
    return newsolutions


def _add_noinvariant(noinvariant, restricted, select, nbtrees):
    # a variable can actually be invariant if it has not been restricted for
    # security reason or if security assertion hasn't modified the possible
    # solutions for the query
    for vname in restricted:
        try:
            var = select.defined_vars[vname]
        except KeyError:
            # this is an alias
            continue
        if nbtrees != 1 or len(var.stinfo['possibletypes']) != 1:
            noinvariant.add(var)


def _expand_selection(terms, selected, aliases, select, newselect):
    for term in terms:
        for vref in term.iget_nodes(n.VariableRef):
            if not vref.name in selected:
                select.append_selected(vref)
                colalias = newselect.get_variable(vref.name, len(aliases))
                aliases.append(n.VariableRef(colalias))
                selected.add(vref.name)

def _has_multiple_cardinality(etypes, rdef, ttypes_func, cardindex):
    """return True if relation definitions from entity types (`etypes`) to
    target types returned by the `ttypes_func` function all have single (1 or ?)
    cardinality.
    """
    for etype in etypes:
        for ttype in ttypes_func(etype):
            if rdef(etype, ttype).cardinality[cardindex] in '+*':
                return True
    return False

def _compatible_relation(relations, stmt, sniprel):
    """Search among given rql relation nodes if there is one 'compatible' with the
    snippet relation, and return it if any, else None.

    A relation is compatible if it:
    * belongs to the currently processed statement,
    * isn't negged (i.e. direct parent is a NOT node)
    * isn't optional (outer join) or similarly as the snippet relation
    """
    for rel in relations:
        # don't share if relation's scope is not the current statement
        if rel.scope is not stmt:
            continue
        # don't share neged relation
        if rel.neged(strict=True):
            continue
        # don't share optional relation, unless the snippet relation is
        # similarly optional
        if rel.optional and rel.optional != sniprel.optional:
            continue
        return rel
    return None


def iter_relations(stinfo):
    # this is a function so that test may return relation in a predictable order
    return stinfo['relations'] - stinfo['rhsrelations']


class Unsupported(Exception):
    """raised when an rql expression can't be inserted in some rql query
    because it create an unresolvable query (eg no solutions found)
    """

class VariableFromSubQuery(Exception):
    """flow control exception to indicate that a variable is coming from a
    subquery, and let parent act accordingly
    """
    def __init__(self, variable):
        self.variable = variable


class RQLRewriter(object):
    """Insert some rql snippets into another rql syntax tree, for security /
    relation vocabulary. This implies that it should only restrict results of
    the original query, not generate new ones. Hence, inserted snippets are
    inserted under an EXISTS node.

    This class *isn't thread safe*.
    """

    def __init__(self, session):
        self.session = session
        vreg = session.vreg
        self.schema = vreg.schema
        self.annotate = vreg.rqlhelper.annotate
        self._compute_solutions = vreg.solutions

    def compute_solutions(self):
        self.annotate(self.select)
        try:
            self._compute_solutions(self.session, self.select, self.kwargs)
        except TypeResolverException:
            raise Unsupported(str(self.select))
        if len(self.select.solutions) < len(self.solutions):
            raise Unsupported()

    def insert_local_checks(self, select, kwargs,
                            localchecks, restricted, noinvariant):
        """
        select: the rql syntax tree Select node
        kwargs: query arguments

        localchecks: {(('Var name', (rqlexpr1, rqlexpr2)),
                       ('Var name1', (rqlexpr1, rqlexpr23))): [solution]}

              (see querier._check_permissions docstring for more information)

        restricted: set of variable names to which an rql expression has to be
              applied

        noinvariant: set of variable names that can't be considered has
              invariant due to security reason (will be filed by this method)
        """
        nbtrees = len(localchecks)
        myunion = union = select.parent
        # transform in subquery when len(localchecks)>1 and groups
        if nbtrees > 1 and (select.orderby or select.groupby or
                            select.having or select.has_aggregat or
                            select.distinct or
                            select.limit or select.offset):
            newselect = stmts.Select()
            # only select variables in subqueries
            origselection = select.selection
            select.select_only_variables()
            select.has_aggregat = False
            # create subquery first so correct node are used on copy
            # (eg ColumnAlias instead of Variable)
            aliases = [n.VariableRef(newselect.get_variable(vref.name, i))
                       for i, vref in enumerate(select.selection)]
            selected = set(vref.name for vref in aliases)
            # now copy original selection and groups
            for term in origselection:
                newselect.append_selected(term.copy(newselect))
            if select.orderby:
                sortterms = []
                for sortterm in select.orderby:
                    sortterms.append(sortterm.copy(newselect))
                    for fnode in sortterm.get_nodes(n.Function):
                        if fnode.name == 'FTIRANK':
                            # we've to fetch the has_text relation as well
                            var = fnode.children[0].variable
                            rel = next(iter(var.stinfo['ftirels']))
                            assert not rel.ored(), 'unsupported'
                            newselect.add_restriction(rel.copy(newselect))
                            # remove relation from the orig select and
                            # cleanup variable stinfo
                            rel.parent.remove(rel)
                            var.stinfo['ftirels'].remove(rel)
                            var.stinfo['relations'].remove(rel)
                            # XXX not properly re-annotated after security insertion?
                            newvar = newselect.get_variable(var.name)
                            newvar.stinfo.setdefault('ftirels', set()).add(rel)
                            newvar.stinfo.setdefault('relations', set()).add(rel)
                newselect.set_orderby(sortterms)
                _expand_selection(select.orderby, selected, aliases, select, newselect)
                select.orderby = () # XXX dereference?
            if select.groupby:
                newselect.set_groupby([g.copy(newselect) for g in select.groupby])
                _expand_selection(select.groupby, selected, aliases, select, newselect)
                select.groupby = () # XXX dereference?
            if select.having:
                newselect.set_having([g.copy(newselect) for g in select.having])
                _expand_selection(select.having, selected, aliases, select, newselect)
                select.having = () # XXX dereference?
            if select.limit:
                newselect.limit = select.limit
                select.limit = None
            if select.offset:
                newselect.offset = select.offset
                select.offset = 0
            myunion = stmts.Union()
            newselect.set_with([n.SubQuery(aliases, myunion)], check=False)
            newselect.distinct = select.distinct
            solutions = [sol.copy() for sol in select.solutions]
            cleanup_solutions(newselect, solutions)
            newselect.set_possible_types(solutions)
            # if some solutions doesn't need rewriting, insert original
            # select as first union subquery
            if () in localchecks:
                myunion.append(select)
            # we're done, replace original select by the new select with
            # subqueries (more added in the loop below)
            union.replace(select, newselect)
        elif not () in localchecks:
            union.remove(select)
        for lcheckdef, lchecksolutions in localchecks.items():
            if not lcheckdef:
                continue
            myrqlst = select.copy(solutions=lchecksolutions)
            myunion.append(myrqlst)
            # in-place rewrite + annotation / simplification
            lcheckdef = [({var: 'X'}, rqlexprs) for var, rqlexprs in lcheckdef]
            self.rewrite(myrqlst, lcheckdef, kwargs)
            _add_noinvariant(noinvariant, restricted, myrqlst, nbtrees)
        if () in localchecks:
            select.set_possible_types(localchecks[()])
            add_types_restriction(self.schema, select)
            _add_noinvariant(noinvariant, restricted, select, nbtrees)
        self.annotate(union)

    def rewrite(self, select, snippets, kwargs, existingvars=None):
        """
        snippets: (varmap, list of rql expression)
                  with varmap a *dict* {select var: snippet var}
        """
        self.select = select
        # remove_solutions used below require a copy
        self.solutions = solutions = select.solutions[:]
        self.kwargs = kwargs
        self.u_varname = None
        self.removing_ambiguity = False
        self.exists_snippet = {}
        self.pending_keys = []
        self.existingvars = existingvars
        # we have to annotate the rqlst before inserting snippets, even though
        # we'll have to redo it later
        self.annotate(select)
        self.insert_snippets(snippets)
        if not self.exists_snippet and self.u_varname:
            # U has been inserted than cancelled, cleanup
            select.undefine_variable(select.defined_vars[self.u_varname])
        # clean solutions according to initial solutions
        newsolutions = remove_solutions(solutions, select.solutions,
                                        select.defined_vars)
        assert len(newsolutions) >= len(solutions), (
            'rewritten rql %s has lost some solutions, there is probably '
            'something wrong in your schema permission (for instance using a '
            'RQLExpression which inserts a relation which doesn\'t exist in '
            'the schema)\nOrig solutions: %s\nnew solutions: %s' % (
            select, solutions, newsolutions))
        if len(newsolutions) > len(solutions):
            newsolutions = self.remove_ambiguities(snippets, newsolutions)
            assert newsolutions
        select.solutions = newsolutions
        add_types_restriction(self.schema, select)

    def insert_snippets(self, snippets, varexistsmap=None):
        self.rewritten = {}
        for varmap, rqlexprs in snippets:
            if isinstance(varmap, dict):
                varmap = tuple(sorted(varmap.items()))
            else:
                assert isinstance(varmap, tuple), varmap
            if varexistsmap is not None and not varmap in varexistsmap:
                continue
            self.insert_varmap_snippets(varmap, rqlexprs, varexistsmap)

    def init_from_varmap(self, varmap, varexistsmap=None):
        self.varmap = varmap
        self.revvarmap = {}
        self.varinfos = []
        for i, (selectvar, snippetvar) in enumerate(varmap):
            assert snippetvar in 'SOX'
            self.revvarmap[snippetvar] = (selectvar, i)
            vi = {}
            self.varinfos.append(vi)
            try:
                vi['const'] = int(selectvar)
                vi['rhs_rels'] = vi['lhs_rels'] = {}
            except ValueError:
                try:
                    vi['stinfo'] = sti = self.select.defined_vars[selectvar].stinfo
                except KeyError:
                    vi['stinfo'] = sti = self._subquery_variable(selectvar)
                if varexistsmap is None:
                    # build an index for quick access to relations
                    vi['rhs_rels'] = {}
                    for rel in sti.get('rhsrelations', []):
                        vi['rhs_rels'].setdefault(rel.r_type, []).append(rel)
                    vi['lhs_rels'] = {}
                    for rel in sti.get('relations', []):
                        if not rel in sti.get('rhsrelations', []):
                            vi['lhs_rels'].setdefault(rel.r_type, []).append(rel)
                else:
                    vi['rhs_rels'] = vi['lhs_rels'] = {}

    def _subquery_variable(self, selectvar):
        raise VariableFromSubQuery(selectvar)

    def insert_varmap_snippets(self, varmap, rqlexprs, varexistsmap):
        try:
            self.init_from_varmap(varmap, varexistsmap)
        except VariableFromSubQuery as ex:
            # variable may have been moved to a newly inserted subquery
            # we should insert snippet in that subquery
            subquery = self.select.aliases[ex.variable].query
            assert len(subquery.children) == 1, subquery
            subselect = subquery.children[0]
            RQLRewriter(self.session).rewrite(subselect, [(varmap, rqlexprs)],
                                              self.kwargs)
            return
        self._insert_scope = None
        previous = None
        inserted = False
        for rqlexpr in rqlexprs:
            self.current_expr = rqlexpr
            if varexistsmap is None:
                try:
                    new = self.insert_snippet(varmap, rqlexpr.snippet_rqlst, previous)
                except Unsupported:
                    continue
                inserted = True
                if new is not None and self._insert_scope is None:
                    self.exists_snippet[rqlexpr] = new
                previous = previous or new
            else:
                # called to reintroduce snippet due to ambiguity creation,
                # so skip snippets which are not introducing this ambiguity
                exists = varexistsmap[varmap]
                if self.exists_snippet.get(rqlexpr) is exists:
                    self.insert_snippet(varmap, rqlexpr.snippet_rqlst, exists)
        if varexistsmap is None and not inserted:
            # no rql expression found matching rql solutions. User has no access right
            raise Unauthorized() # XXX may also be because of bad constraints in schema definition

    def insert_snippet(self, varmap, snippetrqlst, previous=None):
        new = snippetrqlst.where.accept(self)
        existing = self.existingvars
        self.existingvars = None
        try:
            return self._insert_snippet(varmap, previous, new)
        finally:
            self.existingvars = existing

    def _inserted_root(self, new):
        if not isinstance(new, (n.Exists, n.Not)):
            new = n.Exists(new)
        return new

    def _insert_snippet(self, varmap, previous, new):
        """insert `new` snippet into the syntax tree, which have been rewritten
        using `varmap`. In cases where an action is protected by several rql
        expresssion, `previous` will be the first rql expression which has been
        inserted, and so should be ORed with the following expressions.
        """
        if new is not None:
            if self._insert_scope is None:
                insert_scope = None
                for vi in self.varinfos:
                    scope = vi.get('stinfo', {}).get('scope', self.select)
                    if insert_scope is None:
                        insert_scope = scope
                    else:
                        insert_scope = common_parent(scope, insert_scope)
            else:
                insert_scope = self._insert_scope
            if self._insert_scope is None and any(vi.get('stinfo', {}).get('optrelations')
                                                  for vi in self.varinfos):
                assert previous is None
                self._insert_scope, new = self.snippet_subquery(varmap, new)
                self.insert_pending()
                #self._insert_scope = None
                return new
            new = self._inserted_root(new)
            if previous is None:
                insert_scope.add_restriction(new)
            else:
                grandpa = previous.parent
                or_ = n.Or(previous, new)
                grandpa.replace(previous, or_)
            if not self.removing_ambiguity:
                try:
                    self.compute_solutions()
                except Unsupported:
                    # some solutions have been lost, can't apply this rql expr
                    if previous is None:
                        self.current_statement().remove_node(new, undefine=True)
                    else:
                        grandpa.replace(or_, previous)
                        self._cleanup_inserted(new)
                    raise
                else:
                    with tempattr(self, '_insert_scope', new):
                        self.insert_pending()
            return new
        self.insert_pending()

    def insert_pending(self):
        """pending_keys hold variable referenced by U has_<action>_permission X
        relation.

        Once the snippet introducing this has been inserted and solutions
        recomputed, we have to insert snippet defined for <action> of entity
        types taken by X
        """
        stmt = self.current_statement()
        while self.pending_keys:
            key, action = self.pending_keys.pop()
            try:
                varname = self.rewritten[key]
            except KeyError:
                try:
                    varname = self.revvarmap[key[-1]][0]
                except KeyError:
                    # variable isn't used anywhere else, we can't insert security
                    raise Unauthorized()
            ptypes = stmt.defined_vars[varname].stinfo['possibletypes']
            if len(ptypes) > 1:
                # XXX dunno how to handle this
                self.session.error(
                    'cant check security of %s, ambigous type for %s in %s',
                    stmt, varname, key[0]) # key[0] == the rql expression
                raise Unauthorized()
            etype = next(iter(ptypes))
            eschema = self.schema.eschema(etype)
            if not eschema.has_perm(self.session, action):
                rqlexprs = eschema.get_rqlexprs(action)
                if not rqlexprs:
                    raise Unauthorized()
                self.insert_snippets([({varname: 'X'}, rqlexprs)])

    def snippet_subquery(self, varmap, transformedsnippet):
        """introduce the given snippet in a subquery"""
        subselect = stmts.Select()
        snippetrqlst = n.Exists(transformedsnippet.copy(subselect))
        get_rschema = self.schema.rschema
        aliases = []
        done = set()
        for i, (selectvar, _) in enumerate(varmap):
            need_null_test = False
            subselectvar = subselect.get_variable(selectvar)
            subselect.append_selected(n.VariableRef(subselectvar))
            aliases.append(selectvar)
            todo = [(selectvar, self.varinfos[i]['stinfo'])]
            while todo:
                varname, stinfo = todo.pop()
                done.add(varname)
                for rel in iter_relations(stinfo):
                    if rel in done:
                        continue
                    done.add(rel)
                    rschema = get_rschema(rel.r_type)
                    if rschema.final or rschema.inlined:
                        rel.children[0].name = varname # XXX explain why
                        subselect.add_restriction(rel.copy(subselect))
                        for vref in rel.children[1].iget_nodes(n.VariableRef):
                            if isinstance(vref.variable, n.ColumnAlias):
                                # XXX could probably be handled by generating the
                                # subquery into the detected subquery
                                raise BadSchemaDefinition(
                                    "cant insert security because of usage two inlined "
                                    "relations in this query. You should probably at "
                                    "least uninline %s" % rel.r_type)
                            subselect.append_selected(vref.copy(subselect))
                            aliases.append(vref.name)
                        self.select.remove_node(rel)
                        # when some inlined relation has to be copied in the
                        # subquery and that relation is optional, we need to
                        # test that either value is NULL or that the snippet
                        # condition is satisfied
                        if varname == selectvar and rel.optional and rschema.inlined:
                            need_null_test = True
                        # also, if some attributes or inlined relation of the
                        # object variable are accessed, we need to get all those
                        # from the subquery as well
                        if vref.name not in done and rschema.inlined:
                            # we can use vref here define in above for loop
                            ostinfo = vref.variable.stinfo
                            for orel in iter_relations(ostinfo):
                                orschema = get_rschema(orel.r_type)
                                if orschema.final or orschema.inlined:
                                    todo.append( (vref.name, ostinfo) )
                                    break
            if need_null_test:
                snippetrqlst = n.Or(
                    n.make_relation(subselect.get_variable(selectvar), 'is',
                                    (None, None), n.Constant,
                                    operator='='),
                    snippetrqlst)
        subselect.add_restriction(snippetrqlst)
        if self.u_varname:
            # generate an identifier for the substitution
            argname = subselect.allocate_varname()
            while argname in self.kwargs:
                argname = subselect.allocate_varname()
            subselect.add_constant_restriction(subselect.get_variable(self.u_varname),
                                               'eid', text_type(argname), 'Substitute')
            self.kwargs[argname] = self.session.user.eid
        add_types_restriction(self.schema, subselect, subselect,
                              solutions=self.solutions)
        myunion = stmts.Union()
        myunion.append(subselect)
        aliases = [n.VariableRef(self.select.get_variable(name, i))
                   for i, name in enumerate(aliases)]
        self.select.add_subquery(n.SubQuery(aliases, myunion), check=False)
        self._cleanup_inserted(transformedsnippet)
        try:
            self.compute_solutions()
        except Unsupported:
            # some solutions have been lost, can't apply this rql expr
            self.select.remove_subquery(self.select.with_[-1])
            raise
        return subselect, snippetrqlst

    def remove_ambiguities(self, snippets, newsolutions):
        # the snippet has introduced some ambiguities, we have to resolve them
        # "manually"
        variantes = self.build_variantes(newsolutions)
        # insert "is" where necessary
        varexistsmap = {}
        self.removing_ambiguity = True
        for (erqlexpr, varmap, oldvarname), etype in variantes[0].items():
            varname = self.rewritten[(erqlexpr, varmap, oldvarname)]
            var = self.select.defined_vars[varname]
            exists = var.references()[0].scope
            exists.add_constant_restriction(var, 'is', etype, 'etype')
            varexistsmap[varmap] = exists
        # insert ORED exists where necessary
        for variante in variantes[1:]:
            self.insert_snippets(snippets, varexistsmap)
            for key, etype in variante.items():
                varname = self.rewritten[key]
                try:
                    var = self.select.defined_vars[varname]
                except KeyError:
                    # not a newly inserted variable
                    continue
                exists = var.references()[0].scope
                exists.add_constant_restriction(var, 'is', etype, 'etype')
        # recompute solutions
        self.compute_solutions()
        # clean solutions according to initial solutions
        return remove_solutions(self.solutions, self.select.solutions,
                                self.select.defined_vars)

    def build_variantes(self, newsolutions):
        variantes = set()
        for sol in newsolutions:
            variante = []
            for key, newvar in self.rewritten.items():
                variante.append( (key, sol[newvar]) )
            variantes.add(tuple(variante))
        # rebuild variantes as dict
        variantes = [dict(variante) for variante in variantes]
        # remove variable which have always the same type
        for key in self.rewritten:
            it = iter(variantes)
            etype = next(it)[key]
            for variante in it:
                if variante[key] != etype:
                    break
            else:
                for variante in variantes:
                    del variante[key]
        return variantes

    def _cleanup_inserted(self, node):
        # cleanup inserted variable references
        removed = set()
        for vref in node.iget_nodes(n.VariableRef):
            vref.unregister_reference()
            if not vref.variable.stinfo['references']:
                # no more references, undefine the variable
                del self.select.defined_vars[vref.name]
                removed.add(vref.name)
        for key, newvar in list(self.rewritten.items()):
            if newvar in removed:
                del self.rewritten[key]


    def _may_be_shared_with(self, sniprel, target):
        """if the snippet relation can be skipped to use a relation from the
        original query, return that relation node
        """
        if sniprel.neged(strict=True):
            return None # no way
        rschema = self.schema.rschema(sniprel.r_type)
        stmt = self.current_statement()
        for vi in self.varinfos:
            try:
                if target == 'object':
                    orels = vi['lhs_rels'][sniprel.r_type]
                    cardindex = 0
                    ttypes_func = rschema.objects
                    rdef = rschema.rdef
                else: # target == 'subject':
                    orels = vi['rhs_rels'][sniprel.r_type]
                    cardindex = 1
                    ttypes_func = rschema.subjects
                    rdef = lambda x, y: rschema.rdef(y, x)
            except KeyError:
                # may be raised by vi['xhs_rels'][sniprel.r_type]
                continue
            # if cardinality isn't in '?1', we can't ignore the snippet relation
            # and use variable from the original query
            if _has_multiple_cardinality(vi['stinfo']['possibletypes'], rdef,
                                         ttypes_func, cardindex):
                continue
            orel = _compatible_relation(orels, stmt, sniprel)
            if orel is not None:
                return orel
        return None

    def _use_orig_term(self, snippet_varname, term):
        key = (self.current_expr, self.varmap, snippet_varname)
        if key in self.rewritten:
            stmt = self.current_statement()
            insertedvar = stmt.defined_vars.pop(self.rewritten[key])
            for inserted_vref in insertedvar.references():
                inserted_vref.parent.replace(inserted_vref, term.copy(stmt))
        self.rewritten[key] = term.name

    def _get_varname_or_term(self, vname):
        stmt = self.current_statement()
        if vname == 'U':
            stmt = self.select
            if self.u_varname is None:
                self.u_varname = stmt.allocate_varname()
                # generate an identifier for the substitution
                argname = stmt.allocate_varname()
                while argname in self.kwargs:
                    argname = stmt.allocate_varname()
                # insert "U eid %(u)s"
                stmt.add_constant_restriction(
                    stmt.get_variable(self.u_varname),
                    'eid', text_type(argname), 'Substitute')
                self.kwargs[argname] = self.session.user.eid
            return self.u_varname
        key = (self.current_expr, self.varmap, vname)
        try:
            return self.rewritten[key]
        except KeyError:
            self.rewritten[key] = newvname = stmt.allocate_varname()
            return newvname

    # visitor methods ##########################################################

    def _visit_binary(self, node, cls):
        newnode = cls()
        for c in node.children:
            new = c.accept(self)
            if new is None:
                continue
            newnode.append(new)
        if len(newnode.children) == 0:
            return None
        if len(newnode.children) == 1:
            return newnode.children[0]
        return newnode

    def _visit_unary(self, node, cls):
        newc = node.children[0].accept(self)
        if newc is None:
            return None
        newnode = cls()
        newnode.append(newc)
        return newnode

    def visit_and(self, node):
        return self._visit_binary(node, n.And)

    def visit_or(self, node):
        return self._visit_binary(node, n.Or)

    def visit_not(self, node):
        return self._visit_unary(node, n.Not)

    def visit_exists(self, node):
        return self._visit_unary(node, n.Exists)

    def keep_var(self, varname):
        if varname in 'SO':
            return varname in self.existingvars
        if varname == 'U':
            return True
        vargraph = self.current_expr.vargraph
        for existingvar in self.existingvars:
            #path = has_path(vargraph, varname, existingvar)
            if not varname in vargraph or has_path(vargraph, varname, existingvar):
                return True
        # no path from this variable to an existing variable
        return False

    def visit_relation(self, node):
        lhs, rhs = node.get_variable_parts()
        # remove relations where an unexistant variable and or a variable linked
        # to an unexistant variable is used.
        if self.existingvars:
            if not self.keep_var(lhs.name):
                return
        if node.r_type in ('has_add_permission', 'has_update_permission',
                           'has_delete_permission', 'has_read_permission'):
            assert lhs.name == 'U'
            action = node.r_type.split('_')[1]
            key = (self.current_expr, self.varmap, rhs.name)
            self.pending_keys.append( (key, action) )
            return
        if isinstance(rhs, n.VariableRef):
            if self.existingvars and not self.keep_var(rhs.name):
                return
            if lhs.name in self.revvarmap and rhs.name != 'U':
                orel = self._may_be_shared_with(node, 'object')
                if orel is not None:
                    self._use_orig_term(rhs.name, orel.children[1].children[0])
                    return
            elif rhs.name in self.revvarmap and lhs.name != 'U':
                orel = self._may_be_shared_with(node, 'subject')
                if orel is not None:
                    self._use_orig_term(lhs.name, orel.children[0])
                    return
        rel = n.Relation(node.r_type, node.optional)
        for c in node.children:
            rel.append(c.accept(self))
        return rel

    def visit_comparison(self, node):
        cmp_ = n.Comparison(node.operator)
        for c in node.children:
            cmp_.append(c.accept(self))
        return cmp_

    def visit_mathexpression(self, node):
        cmp_ = n.MathExpression(node.operator)
        for c in node.children:
            cmp_.append(c.accept(self))
        return cmp_

    def visit_function(self, node):
        """generate filter name for a function"""
        function_ = n.Function(node.name)
        for c in node.children:
            function_.append(c.accept(self))
        return function_

    def visit_constant(self, node):
        """generate filter name for a constant"""
        return n.Constant(node.value, node.type)

    def visit_variableref(self, node):
        """get the sql name for a variable reference"""
        stmt = self.current_statement()
        if node.name in self.revvarmap:
            selectvar, index = self.revvarmap[node.name]
            vi = self.varinfos[index]
            if vi.get('const') is not None:
                return n.Constant(vi['const'], 'Int')
            return n.VariableRef(stmt.get_variable(selectvar))
        vname_or_term = self._get_varname_or_term(node.name)
        if isinstance(vname_or_term, string_types):
            return n.VariableRef(stmt.get_variable(vname_or_term))
        # shared term
        return vname_or_term.copy(stmt)

    def current_statement(self):
        if self._insert_scope is None:
            return self.select
        return self._insert_scope.stmt


class RQLRelationRewriter(RQLRewriter):
    """Insert some rql snippets into another rql syntax tree, replacing computed
    relations by their associated rule.

    This class *isn't thread safe*.
    """
    def __init__(self, session):
        super(RQLRelationRewriter, self).__init__(session)
        self.rules = {}
        for rschema in self.schema.iter_computed_relations():
            self.rules[rschema.type] = RRQLExpression(rschema.rule)

    def rewrite(self, union, kwargs=None):
        self.kwargs = kwargs
        self.removing_ambiguity = False
        self.existingvars = None
        self.pending_keys = None
        for relation in union.iget_nodes(n.Relation):
            if relation.r_type in self.rules:
                self.select = relation.stmt
                self.solutions = solutions = self.select.solutions[:]
                self.current_expr = self.rules[relation.r_type]
                self._insert_scope = relation.scope
                self.rewritten = {}
                lhs, rhs = relation.get_variable_parts()
                varmap = {lhs.name: 'S', rhs.name: 'O'}
                self.init_from_varmap(tuple(sorted(varmap.items())))
                self.insert_snippet(varmap, self.current_expr.snippet_rqlst)
                self.select.remove_node(relation)

    def _subquery_variable(self, selectvar):
        return self.select.aliases[selectvar].stinfo

    def _inserted_root(self, new):
        return new
