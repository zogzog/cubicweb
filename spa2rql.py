# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""SPARQL -> RQL translator

"""
from logilab.common import make_domains
from rql import TypeResolverException
from fyzz.yappsparser import parse
from fyzz import ast

from cubicweb.xy import xy


class UnsupportedQuery(Exception): pass

def order_limit_offset(sparqlst):
    addons = ''
    if sparqlst.orderby:
        sortterms = ', '.join('%s %s' % (var.name.upper(), ascdesc.upper())
                              for var, ascdesc in sparqlst.orderby)
        addons += ' ORDERBY %s' % sortterms
    if sparqlst.limit:
        addons += ' LIMIT %s' % sparqlst.limit
    if sparqlst.offset:
        addons += ' OFFSET %s' % sparqlst.offset
    return addons


class QueryInfo(object):
    """wrapper class containing necessary information to generate a RQL query
    from a sparql syntax tree
    """
    def __init__(self, sparqlst):
        self.sparqlst = sparqlst
        if sparqlst.selected == ['*']:
            self.selection = [var.upper() for var in sparqlst.variables]
        else:
            self.selection = [var.name.upper() for var in sparqlst.selected]
        self.possible_types = {}
        self.infer_types_info = []
        self.union_params = []
        self.restrictions = []
        self.literals = {}
        self._litcount = 0

    def add_literal(self, value):
        key = chr(ord('a') + self._litcount)
        self._litcount += 1
        self.literals[key] = value
        return key

    def set_possible_types(self, var, varpossibletypes):
        """set/restrict possible types for the given variable.

        :return: True if something changed, else false.
        :raise: TypeResolverException if no more type allowed
        """
        varpossibletypes = set(varpossibletypes)
        try:
            ctypes = self.possible_types[var]
            nbctypes = len(ctypes)
            ctypes &= varpossibletypes
            if not ctypes:
                raise TypeResolverException()
            return len(ctypes) != nbctypes
        except KeyError:
            self.possible_types[var] = varpossibletypes
            return True

    def infer_types(self):
        # XXX should use something similar to rql.analyze for proper type inference
        modified = True
        # loop to infer types until nothing changed
        while modified:
            modified = False
            for yams_predicates, subjvar, obj in self.infer_types_info:
                nbchoices = len(yams_predicates)
                # get possible types for the subject variable, according to the
                # current predicate
                svptypes = set(s for s, r, o in yams_predicates)
                if not '*' in svptypes:
                    if self.set_possible_types(subjvar, svptypes):
                        modified = True
                # restrict predicates according to allowed subject var types
                if subjvar in self.possible_types:
                    yams_predicates = [(s, r, o) for s, r, o in yams_predicates
                                       if s == '*' or s in self.possible_types[subjvar]]
                if isinstance(obj, ast.SparqlVar):
                    # make a valid rql var name
                    objvar = obj.name.upper()
                    # get possible types for the object variable, according to
                    # the current predicate
                    ovptypes = set(o for s, r, o in yams_predicates)
                    if not '*' in ovptypes:
                        if self.set_possible_types(objvar, ovptypes):
                            modified = True
                    # restrict predicates according to allowed object var types
                    if objvar in self.possible_types:
                        yams_predicates = [(s, r, o) for s, r, o in yams_predicates
                                           if o == '*' or o in self.possible_types[objvar]]
                # ensure this still make sense
                if not yams_predicates:
                    raise TypeResolverException()
                if len(yams_predicates) != nbchoices:
                    modified = True

    def build_restrictions(self):
        # now, for each predicate
        for yams_predicates, subjvar, obj in self.infer_types_info:
            rel = yams_predicates[0]
            # if there are several yams relation type equivalences, we will have
            # to generate several unioned rql queries
            for s, r, o in yams_predicates[1:]:
                if r != rel[1]:
                    self.union_params.append((yams_predicates, subjvar, obj))
                    break
            # else we can simply add it to base rql restrictions
            else:
                restr = self.build_restriction(subjvar, rel[1], obj)
                self.restrictions.append(restr)

    def build_restriction(self, subjvar, rtype, obj):
        if isinstance(obj, ast.SparqlLiteral):
            key = self.add_literal(obj.value)
            objvar = '%%(%s)s' % key
        else:
            assert isinstance(obj, ast.SparqlVar)
            # make a valid rql var name
            objvar = obj.name.upper()
        # else we can simply add it to base rql restrictions
        return '%s %s %s' % (subjvar, rtype, objvar)

    def finalize(self):
        """return corresponding rql query (string) / args (dict)"""
        for varname, ptypes in self.possible_types.iteritems():
            if len(ptypes) == 1:
                self.restrictions.append('%s is %s' % (varname, iter(ptypes).next()))
        unions = []
        for releq, subjvar, obj in self.union_params:
            thisunions = []
            for st, rt, ot in releq:
                thisunions.append([self.build_restriction(subjvar, rt, obj)])
                if st != '*':
                    thisunions[-1].append('%s is %s' % (subjvar, st))
                if isinstance(obj, ast.SparqlVar) and ot != '*':
                    objvar = obj.name.upper()
                    thisunions[-1].append('%s is %s' % (objvar, objvar))
            if not unions:
                unions = thisunions
            else:
                unions = zip(*make_domains([unions, thisunions]))
        selection = 'Any ' + ', '.join(self.selection)
        sparqlst = self.sparqlst
        if sparqlst.distinct:
            selection = 'DISTINCT ' + selection
        if unions:
            baserql = '%s WHERE %s' % (selection, ', '.join(self.restrictions))
            rqls = ['(%s, %s)' % (baserql, ', '.join(unionrestrs))
                    for unionrestrs in unions]
            rql = ' UNION '.join(rqls)
            if sparqlst.orderby or sparqlst.limit or sparqlst.offset:
                rql = '%s%s WITH %s BEING (%s)' % (
                    selection, order_limit_offset(sparqlst),
                    ', '.join(self.selection), rql)
        else:
            rql = '%s%s WHERE %s' % (selection, order_limit_offset(sparqlst),
                                      ', '.join(self.restrictions))
        return rql, self.literals


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
            # make a valid rql var name
            subjvar = subj.name.upper()
            if predicate == ('', 'a'):
                # special 'is' relation
                if not isinstance(obj, tuple):
                    raise UnsupportedQuery()
                # restrict possible types for the subject variable
                qi.set_possible_types(
                    subjvar, xy.yeq(':'.join(obj), isentity=True))
            else:
                # 'regular' relation (eg not 'is')
                if not isinstance(predicate, tuple):
                    raise UnsupportedQuery()
                # list of 3-uple
                #   (yams etype (subject), yams rtype, yams etype (object))
                # where subject / object entity type may '*' if not specified
                yams_predicates = xy.yeq(':'.join(predicate))
                qi.infer_types_info.append((yams_predicates, subjvar, obj))
                if not isinstance(obj, (ast.SparqlLiteral, ast.SparqlVar)):
                    raise UnsupportedQuery()
        qi.infer_types()
        qi.build_restrictions()
        return qi
