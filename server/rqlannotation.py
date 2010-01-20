"""Functions to add additional annotations on a rql syntax tree to ease later
code generation.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.compat import any

from rql import BadRQLQuery
from rql.nodes import Relation, VariableRef, Constant, Variable, Or
from rql.utils import common_parent

def _annotate_select(annotator, rqlst):
    for subquery in rqlst.with_:
        annotator._annotate_union(subquery.query)
    #if server.DEBUG:
    #    print '-------- sql annotate', repr(rqlst)
    getrschema = annotator.schema.rschema
    has_text_query = False
    need_distinct = rqlst.distinct
    for rel in rqlst.iget_nodes(Relation):
        if getrschema(rel.r_type).symetric and not rel.neged(strict=True):
            for vref in rel.iget_nodes(VariableRef):
                stinfo = vref.variable.stinfo
                if not stinfo['constnode'] and stinfo['selected']:
                    need_distinct = True
                    # XXX could mark as not invariant
                    break
    for name, var in rqlst.defined_vars.items():
        stinfo = var.stinfo
        if stinfo.get('ftirels'):
            has_text_query = True
        if stinfo['attrvar']:
            stinfo['invariant'] = False
            stinfo['principal'] = _select_main_var(stinfo['rhsrelations'])
            continue
        if not stinfo['relations'] and not stinfo['typerels']:
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
            if rel.r_type == 'eid':
                if not (onlhs and len(stinfo['relations']) > 1):
                    break
                if not stinfo['constnode']:
                    joins.add(rel)
                continue
            elif rel.r_type == 'identity':
                # identity can't be used as principal, so check other relation are used
                # XXX explain rhs.operator == '='
                if rhs.operator != '=' or len(stinfo['relations']) <= 1: #(stinfo['constnode'] and rhs.operator == '='):
                    break
                joins.add(rel)
                continue
            rschema = getrschema(rel.r_type)
            if rel.optional:
                if rel in stinfo['optrelations']:
                    # optional variable can't be invariant if this is the lhs
                    # variable of an inlined relation
                    if not rel in stinfo['rhsrelations'] and rschema.inlined:
                        break
                else:
                    # variable used as main variable of an optional relation
                    # can't be invariant
                    break
            if rschema.final or (onlhs and rschema.inlined):
                if rschema.type != 'has_text':
                    # need join anyway if the variable appears in a final or
                    # inlined relation
                    break
                joins.add(rel)
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
                elif rschema.symetric and stinfo['selected']:
                    break
            joins.add(rel)
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
                stinfo['principal'] = _select_principal(var.sqlscope, joins)
            except CantSelectPrincipal:
                stinfo['invariant'] = False
    rqlst.need_distinct = need_distinct
    return has_text_query



class CantSelectPrincipal(Exception): pass

def _select_principal(sqlscope, relations, _sort=lambda x:x):
    """given a list of rqlst relations, select one which will be used to
    represent an invariant variable (e.g. using on extremity of the relation
    instead of the variable's type table
    """
    # _sort argument is there for test
    diffscope_rels = {}
    has_same_scope_rel = False
    ored_rels = set()
    diffscope_rels = set()
    for rel in _sort(relations):
        # note: only eid and has_text among all final relations may be there
        if rel.r_type in ('eid', 'identity'):
            has_same_scope_rel = rel.sqlscope is sqlscope
            continue
        if rel.ored(traverse_scope=True):
            ored_rels.add(rel)
        elif rel.sqlscope is sqlscope:
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
        if rel.sqlscope is sqlscope:
            return rel
        diffscope_rels.add(rel)
    # if DISTINCT query, can use variable from a different scope as principal
    # since introduced duplicates will be removed
    if sqlscope.stmt.distinct and diffscope_rels:
        return iter(_sort(diffscope_rels)).next()
    # XXX  could use a relation for a different scope if it can't generate
    # duplicates, so we would have to check cardinality
    raise CantSelectPrincipal()

def _select_main_var(relations):
    """given a list of rqlst relations, select one which will be used as main
    relation for the rhs variable
    """
    principal = None
    # sort for test predictability
    for rel in sorted(relations, key=lambda x: (x.children[0].name, x.r_type)):
        # only equality relation with a variable as rhs may be principal
        if rel.operator() not in ('=', 'IS') \
               or not isinstance(rel.children[1].children[0], VariableRef):
            continue
        if rel.sqlscope is rel.stmt:
            return rel
        principal = rel
    if principal is None:
        print iter(relations).next().root
        raise BadRQLQuery('unable to find principal in %s' % ', '.join(
            r.as_string() for r in relations))
    return principal


def set_qdata(getrschema, union, noinvariant):
    """recursive function to set querier data on variables in the syntax tree
    """
    for select in union.children:
        for subquery in select.with_:
            set_qdata(getrschema, subquery.query, noinvariant)
        for var in select.defined_vars.itervalues():
            if var.stinfo['invariant']:
                if var in noinvariant and not var.stinfo['principal'].r_type == 'has_text':
                    var._q_invariant = False
                else:
                    var._q_invariant = True
            else:
                var._q_invariant = False
        for rel in select.iget_nodes(Relation):
            if rel.neged(strict=True) and not rel.is_types_restriction():
                rschema = getrschema(rel.r_type)
                if not rschema.final:
                    # if one of the relation's variable is ambiguous but not
                    # invariant, an intersection will be necessary
                    for vref in rel.get_nodes(VariableRef):
                        var = vref.variable
                        if (not var._q_invariant and var.valuable_references() == 1
                            and len(var.stinfo['possibletypes']) > 1):
                            select.need_intersect = True
                            break
                    else:
                        continue
                    break
        else:
            select.need_intersect = False


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
            htq = _annotate_select(self, select)
            if htq:
                has_text_query = True
        return has_text_query

    def is_ambiguous(self, var):
        # ignore has_text relation
        if len([rel for rel in var.stinfo['relations']
                if rel.sqlscope is var.sqlscope and rel.r_type == 'has_text']) == 1:
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
        for varname, var in rqlst.defined_vars.iteritems():
            if var.stinfo['uidrels'] or \
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
            if rel.is_types_restriction() or rel.r_type == 'eid':
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
        print 'varsols', dict((x, sorted(str(v) for v in values))
                               for x, values in self.varsols.iteritems())
        print 'ambiguous vars', sorted(self.ambiguousvars)

    def set_rel_constraint(self, term, rel, etypes_func):
        if isinstance(term, VariableRef) and self.is_ambiguous(term.variable):
            var = term.variable
            if len(var.stinfo['relations'] - var.stinfo['typerels']) == 1 \
                   or rel.sqlscope is var.sqlscope or rel.r_type == 'identity':
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
                if not var.stinfo['typerels']:
                    otheretypes = deambiguifier.stinfo['possibletypes']
                elif not self.is_ambiguous(deambiguifier):
                    otheretypes = self.varsols[deambiguifier]
                elif deambiguifier in self.not_invariants:
                    # we know variable won't be invariant, try to use
                    # it to deambguify the current variable
                    otheretypes = self.varsols[deambiguifier]
            if not deambiguifier.stinfo['typerels']:
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
                    break
            else:
                self.restrict(var, var.stinfo['possibletypes'])
                self.deambification_map[var] = deambiguifier
                return True
        return False
