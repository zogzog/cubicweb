"""SPARQL -> RQL translator

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common import make_domains
from rql import TypeResolverException
from fyzz.yappsparser import parse
from fyzz import ast

from cubicweb.xy import xy


class UnsupportedQuery(Exception): pass

class QueryInfo(object):
    def __init__(self, sparqlst):
        self.sparqlst = sparqlst
        if sparqlst.selected == ['*']:
            self.selection = [var.upper() for var in sparqlst.variables]
        else:
            self.selection = [var.name.upper() for var in sparqlst.selected]
        self.possible_types = {}
        self.union_params = []
        self.restrictions = []

    def finalize(self):
        for varname, ptypes in self.possible_types.iteritems():
            if len(ptypes) == 1:
                self.restrictions.append('%s is %s' % (varname, iter(ptypes).next()))
        unions = []
        for releq, subjvar, objvar in self.union_params:
            thisunions = []
            for st, rt, ot in releq:
                thisunions.append(['%s %s %s' % (subjvar, rt, objvar)])
                if st != '*':
                    thisunions[-1].append('%s is %s' % (subjvar, st))
                if ot != '*':
                    thisunions[-1].append('%s is %s' % (objvar, ot))
            if not unions:
                unions = thisunions
            else:
                unions = zip(*make_domains([unions, thisunions]))
        baserql = 'Any %s WHERE %s' % (', '.join(self.selection),
                                       ', '.join(self.restrictions))
        if not unions:
            return baserql
        rqls = ['(%s, %s)' % (baserql, ', '.join(unionrestrs))
                for unionrestrs in unions]
        return ' UNION '.join(rqls)

    def set_possible_types(self, var, varpossibletypes):
        varpossibletypes = set(varpossibletypes)
        try:
            self.possible_types[var] &= varpossibletypes
            if not self.possible_types[var]:
                raise TypeResolverException()
        except KeyError:
            self.possible_types[var] = varpossibletypes


class Sparql2rqlTranslator(object):
    def __init__(self, yschema):
        self.yschema = yschema

    def translate(self, sparql):
        sparqlst = parse(sparql)
        if sparqlst.type != 'select':
            raise UnsupportedQuery()
        qi = QueryInfo(sparqlst)
        for subj, predicate, obj in sparqlst.where:
            if not isinstance(subj, ast.SparqlVar):
                raise UnsupportedQuery()
            subjvar = subj.name.upper()
            if predicate == ('', 'a'): # special 'is' relation
                if not isinstance(obj, tuple):
                    raise UnsupportedQuery()
                qi.set_possible_types(
                    subjvar, xy.yeq(':'.join(obj), isentity=True))
            else:
                if not isinstance(predicate, tuple):
                    raise UnsupportedQuery()
                releq = xy.yeq(':'.join(predicate))
                svptypes = set(s for s, r, o in releq)
                if not '*' in svptypes:
                    qi.set_possible_types(subjvar, svptypes)
                if subjvar in qi.possible_types:
                    releq = [(s, r, o) for s, r, o in releq
                             if s == '*' or s in qi.possible_types[subjvar]]
                if isinstance(obj, ast.SparqlVar):
                    objvar = obj.name.upper()
                    ovptypes = set(o for s, r, o in releq)
                    if not '*' in ovptypes:
                        qi.set_possible_types(objvar, ovptypes)
                    if objvar in qi.possible_types:
                        releq = [(s, r, o) for s, r, o in releq
                                 if o == '*' or o in qi.possible_types[objvar]]
                else:
                    raise UnsupportedQuery()
                rel = releq[0]
                for s, r, o in releq[1:]:
                    if r != rel[1]:
                        qi.union_params.append((releq, subjvar, objvar))
                        break
                else:
                    qi.restrictions.append('%s %s %s' % (subj.name.upper(),
                                                         rel[1],
                                                         obj.name.upper()))
        return qi
