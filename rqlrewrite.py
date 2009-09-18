"""RQL rewriting utilities : insert rql expression snippets into rql syntax
tree.

This is used for instance for read security checking in the repository.

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from rql import nodes as n, stmts, TypeResolverException

from logilab.common.compat import any

from cubicweb import Unauthorized, server, typed_eid
from cubicweb.server.ssplanner import add_types_restriction


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


class Unsupported(Exception): pass


class RQLRewriter(object):
    """insert some rql snippets into another rql syntax tree

    this class *isn't thread safe*
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

    def rewrite(self, select, snippets, solutions, kwargs):
        """
        snippets: (varmap, list of rql expression)
                  with varmap a *tuple* (select var, snippet var)
        """
        if server.DEBUG:
            print '---- rewrite', select, snippets, solutions
        self.select = self.insert_scope = select
        self.solutions = solutions
        self.kwargs = kwargs
        self.u_varname = None
        self.removing_ambiguity = False
        self.exists_snippet = {}
        self.pending_keys = []
        # we have to annotate the rqlst before inserting snippets, even though
        # we'll have to redo it latter
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
            'RQLExpression which insert a relation which doesn\'t exists in '
            'the schema)\nOrig solutions: %s\nnew solutions: %s' % (
            select, solutions, newsolutions))
        if len(newsolutions) > len(solutions):
            newsolutions = self.remove_ambiguities(snippets, newsolutions)
        select.solutions = newsolutions
        add_types_restriction(self.schema, select)
        if server.DEBUG:
            print '---- rewriten', select

    def insert_snippets(self, snippets, varexistsmap=None):
        self.rewritten = {}
        for varmap, rqlexprs in snippets:
            if varexistsmap is not None and not varmap in varexistsmap:
                continue
            self.varmap = varmap
            selectvar, snippetvar = varmap
            assert snippetvar in 'SOX'
            self.revvarmap = {snippetvar: selectvar}
            self.varinfo = vi = {}
            try:
                vi['const'] = typed_eid(selectvar) # XXX gae
                vi['rhs_rels'] = vi['lhs_rels'] = {}
            except ValueError:
                vi['stinfo'] = sti = self.select.defined_vars[selectvar].stinfo
                if varexistsmap is None:
                    vi['rhs_rels'] = dict( (r.r_type, r) for r in sti['rhsrelations'])
                    vi['lhs_rels'] = dict( (r.r_type, r) for r in sti['relations']
                                           if not r in sti['rhsrelations'])
                else:
                    vi['rhs_rels'] = vi['lhs_rels'] = {}
            parent = None
            inserted = False
            for rqlexpr in rqlexprs:
                self.current_expr = rqlexpr
                if varexistsmap is None:
                    try:
                        new = self.insert_snippet(varmap, rqlexpr.snippet_rqlst, parent)
                    except Unsupported:
                        import traceback
                        traceback.print_exc()
                        continue
                    inserted = True
                    if new is not None:
                        self.exists_snippet[rqlexpr] = new
                    parent = parent or new
                else:
                    # called to reintroduce snippet due to ambiguity creation,
                    # so skip snippets which are not introducing this ambiguity
                    exists = varexistsmap[varmap]
                    if self.exists_snippet[rqlexpr] is exists:
                        self.insert_snippet(varmap, rqlexpr.snippet_rqlst, exists)
            if varexistsmap is None and not inserted:
                # no rql expression found matching rql solutions. User has no access right
                raise Unauthorized()

    def insert_snippet(self, varmap, snippetrqlst, parent=None):
        new = snippetrqlst.where.accept(self)
        if new is not None:
            if self.varinfo.get('stinfo', {}).get('optrelations'):
                assert parent is None
                self.insert_scope = self.snippet_subquery(varmap, new)
                self.insert_pending()
                self.insert_scope = self.select
                return
            new = n.Exists(new)
            if parent is None:
                self.insert_scope.add_restriction(new)
            else:
                grandpa = parent.parent
                or_ = n.Or(parent, new)
                grandpa.replace(parent, or_)
            if not self.removing_ambiguity:
                try:
                    self.compute_solutions()
                except Unsupported:
                    # some solutions have been lost, can't apply this rql expr
                    if parent is None:
                        self.select.remove_node(new, undefine=True)
                    else:
                        parent.parent.replace(or_, or_.children[0])
                        self._cleanup_inserted(new)
                    raise
                else:
                    self.insert_scope = new
                    self.insert_pending()
                    self.insert_scope = self.select
            return new
        self.insert_pending()

    def insert_pending(self):
        """pending_keys hold variable referenced by U has_<action>_permission X
        relation.

        Once the snippet introducing this has been inserted and solutions
        recomputed, we have to insert snippet defined for <action> of entity
        types taken by X
        """
        while self.pending_keys:
            key, action = self.pending_keys.pop()
            try:
                varname = self.rewritten[key]
            except KeyError:
                try:
                    varname = self.revvarmap[key[-1]]
                except KeyError:
                    # variable isn't used anywhere else, we can't insert security
                    raise Unauthorized()
            ptypes = self.select.defined_vars[varname].stinfo['possibletypes']
            if len(ptypes) > 1:
                # XXX dunno how to handle this
                self.session.error(
                    'cant check security of %s, ambigous type for %s in %s',
                    self.select, varname, key[0]) # key[0] == the rql expression
                raise Unauthorized()
            etype = iter(ptypes).next()
            eschema = self.schema.eschema(etype)
            if not eschema.has_perm(self.session, action):
                rqlexprs = eschema.get_rqlexprs(action)
                if not rqlexprs:
                    raise Unauthorised()
                self.insert_snippets([((varname, 'X'), rqlexprs)])

    def snippet_subquery(self, varmap, transformedsnippet):
        """introduce the given snippet in a subquery"""
        subselect = stmts.Select()
        selectvar, snippetvar = varmap
        subselect.append_selected(n.VariableRef(
            subselect.get_variable(selectvar)))
        aliases = [selectvar]
        subselect.add_restriction(transformedsnippet.copy(subselect))
        stinfo = self.varinfo['stinfo']
        for rel in stinfo['relations']:
            rschema = self.schema.rschema(rel.r_type)
            if rschema.is_final() or (rschema.inlined and
                                      not rel in stinfo['rhsrelations']):
                self.select.remove_node(rel)
                rel.children[0].name = selectvar
                subselect.add_restriction(rel.copy(subselect))
                for vref in rel.children[1].iget_nodes(n.VariableRef):
                    subselect.append_selected(vref.copy(subselect))
                    aliases.append(vref.name)
        if self.u_varname:
            # generate an identifier for the substitution
            argname = subselect.allocate_varname()
            while argname in self.kwargs:
                argname = subselect.allocate_varname()
            subselect.add_constant_restriction(subselect.get_variable(self.u_varname),
                                               'eid', unicode(argname), 'Substitute')
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
            self.select.remove_subquery(new, undefine=True)
            raise
        return subselect

    def remove_ambiguities(self, snippets, newsolutions):
        # the snippet has introduced some ambiguities, we have to resolve them
        # "manually"
        variantes = self.build_variantes(newsolutions)
        # insert "is" where necessary
        varexistsmap = {}
        self.removing_ambiguity = True
        for (erqlexpr, varmap, oldvarname), etype in variantes[0].iteritems():
            varname = self.rewritten[(erqlexpr, varmap, oldvarname)]
            var = self.select.defined_vars[varname]
            exists = var.references()[0].scope
            exists.add_constant_restriction(var, 'is', etype, 'etype')
            varexistsmap[varmap] = exists
        # insert ORED exists where necessary
        for variante in variantes[1:]:
            self.insert_snippets(snippets, varexistsmap)
            for key, etype in variante.iteritems():
                varname = self.rewritten[key]
                try:
                    var = self.select.defined_vars[varname]
                except KeyError:
                    # not a newly inserted variable
                    continue
                exists = var.references()[0].scope
                exists.add_constant_restriction(var, 'is', etype, 'etype')
        # recompute solutions
        #select.annotated = False # avoid assertion error
        self.compute_solutions()
        # clean solutions according to initial solutions
        return remove_solutions(self.solutions, self.select.solutions,
                                self.select.defined_vars)

    def build_variantes(self, newsolutions):
        variantes = set()
        for sol in newsolutions:
            variante = []
            for key, newvar in self.rewritten.iteritems():
                variante.append( (key, sol[newvar]) )
            variantes.add(tuple(variante))
        # rebuild variantes as dict
        variantes = [dict(variante) for variante in variantes]
        # remove variable which have always the same type
        for key in self.rewritten:
            it = iter(variantes)
            etype = it.next()[key]
            for variante in it:
                if variante[key] != etype:
                    break
            else:
                for variante in variantes:
                    del variante[key]
        return variantes

    def _cleanup_inserted(self, node):
        # cleanup inserted variable references
        for vref in node.iget_nodes(n.VariableRef):
            vref.unregister_reference()
            if not vref.variable.stinfo['references']:
                # no more references, undefine the variable
                del self.select.defined_vars[vref.name]

    def _may_be_shared(self, relation, target, searchedvarname):
        """return True if the snippet relation can be skipped to use a relation
        from the original query
        """
        # if cardinality is in '?1', we can ignore the relation and use variable
        # from the original query
        rschema = self.schema.rschema(relation.r_type)
        if target == 'object':
            cardindex = 0
            ttypes_func = rschema.objects
            rprop = rschema.rproperty
        else: # target == 'subject':
            cardindex = 1
            ttypes_func = rschema.subjects
            rprop = lambda x, y, z: rschema.rproperty(y, x, z)
        for etype in self.varinfo['stinfo']['possibletypes']:
            for ttype in ttypes_func(etype):
                if rprop(etype, ttype, 'cardinality')[cardindex] in '+*':
                    return False
        return True

    def _use_outer_term(self, snippet_varname, term):
        key = (self.current_expr, self.varmap, snippet_varname)
        if key in self.rewritten:
            insertedvar = self.select.defined_vars.pop(self.rewritten[key])
            for inserted_vref in insertedvar.references():
                inserted_vref.parent.replace(inserted_vref, term.copy(self.select))
        self.rewritten[key] = term.name

    def _get_varname_or_term(self, vname):
        if vname == 'U':
            if self.u_varname is None:
                select = self.select
                self.u_varname = select.allocate_varname()
                # generate an identifier for the substitution
                argname = select.allocate_varname()
                while argname in self.kwargs:
                    argname = select.allocate_varname()
                # insert "U eid %(u)s"
                var = select.get_variable(self.u_varname)
                select.add_constant_restriction(select.get_variable(self.u_varname),
                                                'eid', unicode(argname), 'Substitute')
                self.kwargs[argname] = self.session.user.eid
            return self.u_varname
        key = (self.current_expr, self.varmap, vname)
        try:
            return self.rewritten[key]
        except KeyError:
            self.rewritten[key] = newvname = self.select.allocate_varname()
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

    def visit_relation(self, node):
        lhs, rhs = node.get_variable_parts()
        if node.r_type in ('has_add_permission', 'has_update_permission',
                           'has_delete_permission', 'has_read_permission'):
            assert lhs.name == 'U'
            action = node.r_type.split('_')[1]
            key = (self.current_expr, self.varmap, rhs.name)
            self.pending_keys.append( (key, action) )
            return
        if lhs.name in self.revvarmap:
            # on lhs
            # see if we can reuse this relation
            rels = self.varinfo['lhs_rels']
            if (node.r_type in rels and isinstance(rhs, n.VariableRef)
                and rhs.name != 'U' and not rels[node.r_type].neged(strict=True)
                and self._may_be_shared(node, 'object', lhs.name)):
                # ok, can share variable
                term = rels[node.r_type].children[1].children[0]
                self._use_outer_term(rhs.name, term)
                return
        elif isinstance(rhs, n.VariableRef) and rhs.name in self.revvarmap and lhs.name != 'U':
            # on rhs
            # see if we can reuse this relation
            rels = self.varinfo['rhs_rels']
            if (node.r_type in rels and not rels[node.r_type].neged(strict=True)
                and self._may_be_shared(node, 'subject', rhs.name)):
                # ok, can share variable
                term = rels[node.r_type].children[0]
                self._use_outer_term(lhs.name, term)
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
        for c in cmp.children:
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
        if node.name in self.revvarmap:
            if self.varinfo.get('const') is not None:
                return n.Constant(self.varinfo['const'], 'Int') # XXX gae
            return n.VariableRef(self.select.get_variable(
                self.revvarmap[node.name]))
        vname_or_term = self._get_varname_or_term(node.name)
        if isinstance(vname_or_term, basestring):
            return n.VariableRef(self.select.get_variable(vname_or_term))
        # shared term
        return vname_or_term.copy(self.select)
