# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Functions to add additional annotations on a rql syntax tree to ease later
code generation.
"""
from __future__ import print_function

__docformat__ = "restructuredtext en"

from rql import BadRQLQuery
from rql.nodes import Relation, VariableRef, Constant, Variable, Or, Exists
from rql.utils import common_parent

def _annotate_select(annotator, rqlst):
    has_text_query = False
    for subquery in rqlst.with_:
        if annotator._annotate_union(subquery.query):
            has_text_query = True
    #if server.DEBUG:
    #    print '-------- sql annotate', repr(rqlst)
    getrschema = annotator.schema.rschema
    for var in rqlst.defined_vars.values():
        stinfo = var.stinfo
        if stinfo.get('ftirels'):
            has_text_query = True
        if stinfo['attrvar']:
            stinfo['invariant'] = False
            stinfo['principal'] = _select_main_var(stinfo['rhsrelations'])
            continue
        if not stinfo['relations'] and stinfo['typerel'] is None:
            # Any X, Any MAX(X)...
            # those particular queries should be executed using the system
            # entities table unless there is some type restriction
            stinfo['invariant'] = True
            stinfo['principal'] = None
            continue
        if any(rel for rel in stinfo['relations'] if rel.r_type == 'eid' and rel.operator() != '=') and \
               not any(r for r in var.stinfo['relations'] - var.stinfo['rhsrelations']
                       if r.r_type != 'eid' and (getrschema(r.r_type).inlined or getrschema(r.r_type).final)):
            # Any X WHERE X eid > 2
            # those particular queries should be executed using the system entities table
            stinfo['invariant'] = True
            stinfo['principal'] = None
            continue
        if stinfo['selected'] and var.valuable_references() == 1+bool(stinfo['constnode']):
            # "Any X", "Any X, Y WHERE X attr Y"
            stinfo['invariant'] = False
            continue
        joins = set()
        invariant = False
        for ref in var.references():
            rel = ref.relation()
            if rel is None or rel.is_types_restriction():
                continue
            lhs, rhs = rel.get_parts()
            onlhs = ref is lhs
            role = 'subject' if onlhs else 'object'
            if rel.r_type == 'eid':
                if not (onlhs and len(stinfo['relations']) > 1):
                    break
                if not stinfo['constnode']:
                    joins.add( (rel, role) )
                continue
            elif rel.r_type == 'identity':
                # identity can't be used as principal, so check other relation are used
                # XXX explain rhs.operator == '='
                if rhs.operator != '=' or len(stinfo['relations']) <= 1: #(stinfo['constnode'] and rhs.operator == '='):
                    break
                joins.add( (rel, role) )
                continue
            rschema = getrschema(rel.r_type)
            if rel.optional:
                if rel in stinfo.get('optrelations', ()):
                    # optional variable can't be invariant if this is the lhs
                    # variable of an inlined relation
                    if not rel in stinfo['rhsrelations'] and rschema.inlined:
                        break
                # variable used as main variable of an optional relation can't
                # be invariant, unless we can use some other relation as
                # reference for the outer join
                elif not stinfo['constnode']:
                    break
                elif len(stinfo['relations']) == 2:
                    if onlhs:
                        ostinfo = rhs.children[0].variable.stinfo
                    else:
                        ostinfo = lhs.variable.stinfo
                    if not (ostinfo.get('optcomparisons') or
                            any(orel for orel in ostinfo['relations']
                                if orel.optional and orel is not rel)):
                        break
            if rschema.final or (onlhs and rschema.inlined):
                if rschema.type != 'has_text':
                    # need join anyway if the variable appears in a final or
                    # inlined relation
                    break
                joins.add( (rel, role) )
                continue
            if not stinfo['constnode']:
                if rschema.inlined and rel.neged(strict=True):
                    # if relation is inlined, can't be invariant if that
                    # variable is used anywhere else.
                    # see 'Any P WHERE NOT N ecrit_par P, N eid 512':
                    # sql for 'NOT N ecrit_par P' is 'N.ecrit_par is NULL' so P
                    # can use N.ecrit_par as principal
                    if (stinfo['selected'] or len(stinfo['relations']) > 1):
                        break
            joins.add( (rel, role) )
        else:
            # if there is at least one ambigous relation and no other to
            # restrict types, can't be invariant since we need to filter out
            # other types
            if not annotator.is_ambiguous(var):
                invariant = True
        stinfo['invariant'] = invariant
        if invariant and joins:
            # remember rqlst/solutions analyze information
            # we have to select a kindof "main" relation which will "extrajoins"
            # the other
            # priority should be given to relation which are not in inner queries
            # (eg exists)
            try:
                stinfo['principal'] = principal = _select_principal(var.scope, joins)
                if getrschema(principal.r_type).inlined:
                    # the scope of the lhs variable must be equal or outer to the
                    # rhs variable's scope (since it's retrieved from lhs's table)
                    sstinfo = principal.children[0].variable.stinfo
                    sstinfo['scope'] = common_parent(sstinfo['scope'], stinfo['scope']).scope
            except CantSelectPrincipal:
                stinfo['invariant'] = False
    # see unittest_rqlannotation. test_has_text_security_cache_bug
    # XXX probably more to do, but yet that work without more...
    for col_alias in rqlst.aliases.values():
        if col_alias.stinfo.get('ftirels'):
            has_text_query = True
    return has_text_query



class CantSelectPrincipal(Exception):
    """raised when no 'principal' variable can be found"""

def _select_principal(scope, relations, _sort=lambda x:x):
    """given a list of rqlst relations, select one which will be used to
    represent an invariant variable (e.g. using on extremity of the relation
    instead of the variable's type table
    """
    # _sort argument is there for test
    diffscope_rels = {}
    ored_rels = set()
    diffscope_rels = set()
    for rel, role in _sort(relations):
        # note: only eid and has_text among all final relations may be there
        if rel.r_type in ('eid', 'identity'):
            continue
        if rel.optional is not None and len(relations) > 1:
            if role == 'subject' and rel.optional == 'right':
                continue
            if role == 'object' and rel.optional == 'left':
                continue
        if rel.ored(traverse_scope=True):
            ored_rels.add(rel)
        elif rel.scope is scope:
            return rel
        elif not rel.neged(traverse_scope=True):
            diffscope_rels.add(rel)
    if len(ored_rels) > 1:
        ored_rels_copy = tuple(ored_rels)
        for rel1 in ored_rels_copy:
            for rel2 in ored_rels_copy:
                if rel1 is rel2:
                    continue
                if isinstance(common_parent(rel1, rel2), Or):
                    ored_rels.discard(rel1)
                    ored_rels.discard(rel2)
    for rel in _sort(ored_rels):
        if rel.scope is scope:
            return rel
        diffscope_rels.add(rel)
    # if DISTINCT query, can use variable from a different scope as principal
    # since introduced duplicates will be removed
    if scope.stmt.distinct and diffscope_rels:
        return next(iter(_sort(diffscope_rels)))
    # XXX could use a relation from a different scope if it can't generate
    # duplicates, so we should have to check cardinality
    raise CantSelectPrincipal()

def _select_main_var(relations):
    """given a list of rqlst relations, select one which will be used as main
    relation for the rhs variable
    """
    principal = None
    others = []
    # sort for test predictability
    for rel in sorted(relations, key=lambda x: (x.children[0].name, x.r_type)):
        # only equality relation with a variable as rhs may be principal
        if rel.operator() not in ('=', 'IS') \
               or not isinstance(rel.children[1].children[0], VariableRef) or rel.neged(strict=True):
            continue
        if rel.optional:
            others.append(rel)
            continue
        if rel.scope is rel.stmt:
            return rel
        principal = rel
    if principal is None:
        if others:
            return others[0]
        raise BadRQLQuery('unable to find principal in %s' % ', '.join(
            r.as_string() for r in relations))
    return principal


def set_qdata(getrschema, union, noinvariant):
    """recursive function to set querier data on variables in the syntax tree
    """
    for select in union.children:
        for subquery in select.with_:
            set_qdata(getrschema, subquery.query, noinvariant)
        for var in select.defined_vars.values():
            if var.stinfo['invariant']:
                if var in noinvariant and not var.stinfo['principal'].r_type == 'has_text':
                    var._q_invariant = False
                else:
                    var._q_invariant = True
            else:
                var._q_invariant = False


class SQLGenAnnotator(object):
    def __init__(self, schema):
        self.schema = schema
        self.nfdomain = frozenset(eschema.type for eschema in schema.entities()
                                  if not eschema.final)

    def annotate(self, rqlst):
        """add information to the rql syntax tree to help sources to do their
        job (read sql generation)

        a variable is tagged as invariant if:
        * it's a non final variable
        * it's not used as lhs in any final or inlined relation
        * there is no type restriction on this variable (either explicit in the
          syntax tree or because a solution for this variable has been removed
          due to security filtering)
        """
        #assert rqlst.TYPE == 'select', rqlst
        rqlst.has_text_query = self._annotate_union(rqlst)

    def _annotate_union(self, union):
        has_text_query = False
        for select in union.children:
            if _annotate_select(self, select):
                has_text_query = True
        return has_text_query

    def is_ambiguous(self, var):
        # ignore has_text relation when we know it will be used as principal.
        # This is expected by the rql2sql generator which will use the `entities`
        # table to filter out by type if necessary, This optimisation is very
        # interesting in multi-sources cases, as it may avoid a costly query
        # on sources to get all entities of a given type to achieve this, while
        # we have all the necessary information.
        root = var.stmt.root # Union node
        # rel.scope -> Select or Exists node, so add .parent to get Union from
        # Select node
        rels = [rel for rel in var.stinfo['relations'] if rel.scope.parent is root]
        if len(rels) == 1 and rels[0].r_type == 'has_text':
            return False
        try:
            data = var.stmt._deamb_data
        except AttributeError:
            data = var.stmt._deamb_data = IsAmbData(self.schema, self.nfdomain)
            data.compute(var.stmt)
        return data.is_ambiguous(var)


class IsAmbData(object):
    def __init__(self, schema, nfdomain):
        self.schema = schema
        # shortcuts
        self.rschema = schema.rschema
        self.eschema = schema.eschema
        # domain for non final variables
        self.nfdomain = nfdomain
        # {var: possible solutions set}
        self.varsols = {}
        # set of ambiguous variables
        self.ambiguousvars = set()
        # remember if a variable has been deambiguified by another to avoid
        # doing the opposite
        self.deambification_map = {}
        # not invariant variables (access to final.inlined relation)
        self.not_invariants = set()

    def is_ambiguous(self, var):
        return var in self.ambiguousvars

    def restrict(self, var, restricted_domain):
        self.varsols[var] &= restricted_domain
        if var in self.ambiguousvars and self.varsols[var] == var.stinfo['possibletypes']:
            self.ambiguousvars.remove(var)

    def compute(self, rqlst):
        # set domains for each variable
        for varname, var in rqlst.defined_vars.items():
            if var.stinfo['uidrel'] is not None or \
                   self.eschema(rqlst.solutions[0][varname]).final:
                ptypes = var.stinfo['possibletypes']
            else:
                ptypes = set(self.nfdomain)
                self.ambiguousvars.add(var)
            self.varsols[var] = ptypes
        if not self.ambiguousvars:
            return
        # apply relation restriction
        self.maydeambrels = maydeambrels = {}
        for rel in rqlst.iget_nodes(Relation):
            if rel.r_type == 'eid' or rel.is_types_restriction():
                continue
            lhs, rhs = rel.get_variable_parts()
            if isinstance(lhs, VariableRef) or isinstance(rhs, VariableRef):
                rschema = self.rschema(rel.r_type)
                if rschema.inlined or rschema.final:
                    self.not_invariants.add(lhs.variable)
                self.set_rel_constraint(lhs, rel, rschema.subjects)
                self.set_rel_constraint(rhs, rel, rschema.objects)
        # try to deambiguify more variables by considering other variables'type
        modified = True
        while modified and self.ambiguousvars:
            modified = False
            for var in self.ambiguousvars.copy():
                try:
                    for rel in (var.stinfo['relations'] & maydeambrels[var]):
                        if self.deambiguifying_relation(var, rel):
                            modified = True
                            break
                except KeyError:
                    # no relation to deambiguify
                    continue

    def _debug_print(self):
        print('varsols', dict((x, sorted(str(v) for v in values))
                               for x, values in self.varsols.items()))
        print('ambiguous vars', sorted(self.ambiguousvars))

    def set_rel_constraint(self, term, rel, etypes_func):
        if isinstance(term, VariableRef) and self.is_ambiguous(term.variable):
            var = term.variable
            if len(var.stinfo['relations']) == 1 \
                   or rel.scope is var.scope or rel.r_type == 'identity':
                self.restrict(var, frozenset(etypes_func()))
                try:
                    self.maydeambrels[var].add(rel)
                except KeyError:
                    self.maydeambrels[var] = set((rel,))

    def deambiguifying_relation(self, var, rel):
        lhs, rhs = rel.get_variable_parts()
        onlhs = var is getattr(lhs, 'variable', None)
        other = onlhs and rhs or lhs
        otheretypes = None
        # XXX isinstance(other.variable, Variable) to skip column alias
        if isinstance(other, VariableRef) and isinstance(other.variable, Variable):
            deambiguifier = other.variable
            if not var is self.deambification_map.get(deambiguifier):
                if var.stinfo['typerel'] is None:
                    otheretypes = deambiguifier.stinfo['possibletypes']
                elif not self.is_ambiguous(deambiguifier):
                    otheretypes = self.varsols[deambiguifier]
                elif deambiguifier in self.not_invariants:
                    # we know variable won't be invariant, try to use
                    # it to deambguify the current variable
                    otheretypes = self.varsols[deambiguifier]
            if deambiguifier.stinfo['typerel'] is None:
                # if deambiguifier has no type restriction using 'is',
                # don't record it
                deambiguifier = None
        elif isinstance(other, Constant) and other.uidtype:
            otheretypes = (other.uidtype,)
            deambiguifier = None
        if otheretypes is not None:
            # to restrict, we must check that for all type in othertypes,
            # possible types on the other end of the relation are matching
            # variable's possible types
            rschema = self.rschema(rel.r_type)
            if onlhs:
                rtypefunc = rschema.subjects
            else:
                rtypefunc = rschema.objects
            for otheretype in otheretypes:
                reltypes = frozenset(rtypefunc(otheretype))
                if var.stinfo['possibletypes'] != reltypes:
                    return False
            self.restrict(var, var.stinfo['possibletypes'])
            self.deambification_map[var] = deambiguifier
            return True
        return False
