"""RQL rewriting utilities, used for read security checking

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from rql import nodes, stmts, TypeResolverException
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
    """insert some rql snippets into another rql syntax tree"""
    def __init__(self, querier, session):
        self.session = session
        self.annotate = querier._rqlhelper.annotate
        self._compute_solutions = querier.solutions
        self.schema = querier.schema

    def compute_solutions(self):
        self.annotate(self.select)
        try:
            self._compute_solutions(self.session, self.select, self.kwargs)
        except TypeResolverException:
            raise Unsupported()
        if len(self.select.solutions) < len(self.solutions):
            raise Unsupported()
        
    def rewrite(self, select, snippets, solutions, kwargs):
        if server.DEBUG:
            print '---- rewrite', select, snippets, solutions
        self.select = select
        self.solutions = solutions
        self.kwargs = kwargs
        self.u_varname = None
        self.removing_ambiguity = False
        self.exists_snippet = {}
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
        assert len(newsolutions) >= len(solutions), \
               'rewritten rql %s has lost some solutions, there is probably something '\
               'wrong in your schema permission (for instance using a '\
              'RQLExpression which insert a relation which doesn\'t exists in '\
               'the schema)\nOrig solutions: %s\nnew solutions: %s' % (
            select, solutions, newsolutions)
        if len(newsolutions) > len(solutions):
            # the snippet has introduced some ambiguities, we have to resolve them
            # "manually"
            variantes = self.build_variantes(newsolutions)
            # insert "is" where necessary
            varexistsmap = {}
            self.removing_ambiguity = True
            for (erqlexpr, mainvar, oldvarname), etype in variantes[0].iteritems():
                varname = self.rewritten[(erqlexpr, mainvar, oldvarname)]
                var = select.defined_vars[varname]
                exists = var.references()[0].scope
                exists.add_constant_restriction(var, 'is', etype, 'etype')
                varexistsmap[mainvar] = exists
            # insert ORED exists where necessary
            for variante in variantes[1:]:
                self.insert_snippets(snippets, varexistsmap)
                for (erqlexpr, mainvar, oldvarname), etype in variante.iteritems():
                    varname = self.rewritten[(erqlexpr, mainvar, oldvarname)]
                    try:
                        var = select.defined_vars[varname]
                    except KeyError:
                        # not a newly inserted variable
                        continue
                    exists = var.references()[0].scope
                    exists.add_constant_restriction(var, 'is', etype, 'etype')
            # recompute solutions
            #select.annotated = False # avoid assertion error
            self.compute_solutions()
            # clean solutions according to initial solutions
            newsolutions = remove_solutions(solutions, select.solutions,
                                            select.defined_vars)
        select.solutions = newsolutions
        add_types_restriction(self.schema, select)
        if server.DEBUG:
            print '---- rewriten', select
            
    def build_variantes(self, newsolutions):
        variantes = set()
        for sol in newsolutions:
            variante = []
            for (erqlexpr, mainvar, oldvar), newvar in self.rewritten.iteritems():
                variante.append( ((erqlexpr, mainvar, oldvar), sol[newvar]) )
            variantes.add(tuple(variante))
        # rebuild variantes as dict
        variantes = [dict(variante) for variante in variantes]
        # remove variable which have always the same type
        for erqlexpr, mainvar, oldvar in self.rewritten:
            it = iter(variantes)
            etype = it.next()[(erqlexpr, mainvar, oldvar)]
            for variante in it:
                if variante[(erqlexpr, mainvar, oldvar)] != etype:
                    break
            else:
                for variante in variantes:
                    del variante[(erqlexpr, mainvar, oldvar)]
        return variantes
    
    def insert_snippets(self, snippets, varexistsmap=None):
        self.rewritten = {}
        for varname, erqlexprs in snippets:
            if varexistsmap is not None and not varname in varexistsmap:
                continue
            try:
                self.const = typed_eid(varname)
                self.varname = self.const
                self.rhs_rels = self.lhs_rels = {}
            except ValueError:
                self.varname = varname
                self.const = None
                self.varstinfo = stinfo = self.select.defined_vars[varname].stinfo
                if varexistsmap is None:
                    self.rhs_rels = dict( (rel.r_type, rel) for rel in stinfo['rhsrelations'])
                    self.lhs_rels = dict( (rel.r_type, rel) for rel in stinfo['relations']
                                                  if not rel in stinfo['rhsrelations'])
                else:
                    self.rhs_rels = self.lhs_rels = {}
            parent = None
            inserted = False
            for erqlexpr in erqlexprs:
                self.current_expr = erqlexpr
                if varexistsmap is None:
                    try:
                        new = self.insert_snippet(varname, erqlexpr.snippet_rqlst, parent)
                    except Unsupported:
                        continue
                    inserted = True
                    if new is not None:
                        self.exists_snippet[erqlexpr] = new
                    parent = parent or new
                else:
                    # called to reintroduce snippet due to ambiguity creation,
                    # so skip snippets which are not introducing this ambiguity
                    exists = varexistsmap[varname]
                    if self.exists_snippet[erqlexpr] is exists:
                        self.insert_snippet(varname, erqlexpr.snippet_rqlst, exists)
            if varexistsmap is None and not inserted:
                # no rql expression found matching rql solutions. User has no access right
                raise Unauthorized()
            
    def insert_snippet(self, varname, snippetrqlst, parent=None):
        new = snippetrqlst.where.accept(self)
        if new is not None:
            try:
                var = self.select.defined_vars[varname]
            except KeyError:
                # not a variable
                pass
            else:
                if var.stinfo['optrelations']:
                    # use a subquery
                    subselect = stmts.Select()
                    subselect.append_selected(nodes.VariableRef(subselect.get_variable(varname)))
                    subselect.add_restriction(new.copy(subselect))
                    aliases = [varname]
                    for rel in var.stinfo['relations']:
                        rschema = self.schema.rschema(rel.r_type)
                        if rschema.is_final() or (rschema.inlined and not rel in var.stinfo['rhsrelations']):
                            self.select.remove_node(rel)
                            rel.children[0].name = varname
                            subselect.add_restriction(rel.copy(subselect))
                            for vref in rel.children[1].iget_nodes(nodes.VariableRef):
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
                    add_types_restriction(self.schema, subselect, subselect, solutions=self.solutions)
                    assert parent is None
                    myunion = stmts.Union()
                    myunion.append(subselect)
                    aliases = [nodes.VariableRef(self.select.get_variable(name, i))
                               for i, name in enumerate(aliases)]
                    self.select.add_subquery(nodes.SubQuery(aliases, myunion), check=False)
                    self._cleanup_inserted(new)
                    try:
                        self.compute_solutions()
                    except Unsupported:
                        # some solutions have been lost, can't apply this rql expr
                        self.select.remove_subquery(new, undefine=True)
                        raise
                    return
            new = nodes.Exists(new)
            if parent is None:
                self.select.add_restriction(new)
            else:
                grandpa = parent.parent
                or_ = nodes.Or(parent, new)
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
            return new

    def _cleanup_inserted(self, node):
        # cleanup inserted variable references
        for vref in node.iget_nodes(nodes.VariableRef):
            vref.unregister_reference()
            if not vref.variable.stinfo['references']:
                # no more references, undefine the variable
                del self.select.defined_vars[vref.name]
        
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
        
    def visit_and(self, et):
        return self._visit_binary(et, nodes.And)

    def visit_or(self, ou):
        return self._visit_binary(ou, nodes.Or)
        
    def visit_not(self, node):
        return self._visit_unary(node, nodes.Not)

    def visit_exists(self, node):
        return self._visit_unary(node, nodes.Exists)
   
    def visit_relation(self, relation):
        lhs, rhs = relation.get_variable_parts()
        if lhs.name == 'X':
            # on lhs
            # see if we can reuse this relation
            if relation.r_type in self.lhs_rels and isinstance(rhs, nodes.VariableRef) and rhs.name != 'U':
                if self._may_be_shared(relation, 'object'):
                    # ok, can share variable
                    term = self.lhs_rels[relation.r_type].children[1].children[0]
                    self._use_outer_term(rhs.name, term)
                    return
        elif isinstance(rhs, nodes.VariableRef) and rhs.name == 'X' and lhs.name != 'U':
            # on rhs
            # see if we can reuse this relation
            if relation.r_type in self.rhs_rels and self._may_be_shared(relation, 'subject'):
                # ok, can share variable
                term = self.rhs_rels[relation.r_type].children[0]
                self._use_outer_term(lhs.name, term)            
                return
        rel = nodes.Relation(relation.r_type, relation.optional)
        for c in relation.children:
            rel.append(c.accept(self))
        return rel

    def visit_comparison(self, cmp):
        cmp_ = nodes.Comparison(cmp.operator)
        for c in cmp.children:
            cmp_.append(c.accept(self))
        return cmp_

    def visit_mathexpression(self, mexpr):
        cmp_ = nodes.MathExpression(mexpr.operator)
        for c in cmp.children:
            cmp_.append(c.accept(self))
        return cmp_
        
    def visit_function(self, function):
        """generate filter name for a function"""
        function_ = nodes.Function(function.name)
        for c in function.children:
            function_.append(c.accept(self))
        return function_

    def visit_constant(self, constant):
        """generate filter name for a constant"""
        return nodes.Constant(constant.value, constant.type)

    def visit_variableref(self, vref):
        """get the sql name for a variable reference"""
        if vref.name == 'X':
            if self.const is not None:
                return nodes.Constant(self.const, 'Int')
            return nodes.VariableRef(self.select.get_variable(self.varname))
        vname_or_term = self._get_varname_or_term(vref.name)
        if isinstance(vname_or_term, basestring):
            return nodes.VariableRef(self.select.get_variable(vname_or_term))
        # shared term
        return vname_or_term.copy(self.select)

    def _may_be_shared(self, relation, target):
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
        for etype in self.varstinfo['possibletypes']:
            for ttype in ttypes_func(etype):
                if rprop(etype, ttype, 'cardinality')[cardindex] in '+*':
                    return False
        return True

    def _use_outer_term(self, snippet_varname, term):
        key = (self.current_expr, self.varname, snippet_varname)
        if key in self.rewritten:
            insertedvar = self.select.defined_vars.pop(self.rewritten[key])
            for inserted_vref in insertedvar.references():
                inserted_vref.parent.replace(inserted_vref, term.copy(self.select))
        self.rewritten[key] = term
        
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
        key = (self.current_expr, self.varname, vname)
        try:
            return self.rewritten[key]
        except KeyError:
            self.rewritten[key] = newvname = self.select.allocate_varname()
            return newvname
