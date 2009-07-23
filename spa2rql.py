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

    def finalize(self):
        """return corresponding rql query"""
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
        if self.sparqlst.distinct:
            baserql = 'DISTINCT ' + baserql
        if not unions:
            return baserql
        rqls = ['(%s, %s)' % (baserql, ', '.join(unionrestrs))
                for unionrestrs in unions]
        return ' UNION '.join(rqls)

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
        # now, for each predicate
        for yams_predicates, subjvar, obj in self.infer_types_info:
            rel = yams_predicates[0]
            objvar = obj.name.upper()
            # if there are several yams relation type equivalences, we will have
            # to generate several unioned rql queries
            for s, r, o in yams_predicates[1:]:
                if r != rel[1]:
                    self.union_params.append((yams_predicates, subjvar, objvar))
                    break
            else:
                # else we can simply add it to base rql restrictions
                self.restrictions.append('%s %s %s' % (subjvar, rel[1], objvar))


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
                if isinstance(obj, ast.SparqlVar):
                    # make a valid rql var name
                    objvar = obj.name.upper()
                else:
                    raise UnsupportedQuery()
        qi.infer_types()
        return qi
