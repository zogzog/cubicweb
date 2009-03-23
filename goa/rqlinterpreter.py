"""provide a minimal RQL support for google appengine dbmodel

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from mx.DateTime import DateTimeType, DateTimeDeltaType
from datetime import datetime

from rql import RQLHelper, nodes
from logilab.common.compat import any

from cubicweb import Binary
from cubicweb.rset import ResultSet
from cubicweb.server import SQL_CONNECT_HOOKS

from google.appengine.api.datastore import Key, Get, Query, Entity
from google.appengine.api.datastore_types import Text, Blob
from google.appengine.api.datastore_errors import EntityNotFoundError, BadKeyError


def etype_from_key(key):
    return Key(key).kind()

def poss_var_types(myvar, ovar, kind, solutions):
    return frozenset(etypes[myvar] for etypes in solutions 
                     if etypes[ovar] == kind)

def expand_result(results, result, myvar, values, dsget=None):
    values = map(dsget, values)
    if values:
        result[myvar] = values.pop(0)
        for value in values:
            newresult = result.copy()
            newresult[myvar] = value
            results.append(newresult)
    else:
        results.remove(result)

def _resolve(restrictions, solutions, fixed):
    varname = restrictions[0].searched_var
    objs = []
    for etype in frozenset(etypes[varname] for etypes in solutions):
        gqlargs = {}
        query = Query(etype)
        for restriction in restrictions:
            restriction.fill_query(fixed, query)
        pobjs = query.Run()
        if varname in fixed:
            value = fixed[varname]
            objs += (x for x in pobjs if x == value)
        else:
            objs += pobjs
    if varname in fixed and not objs:
        raise EidMismatch(varname, value)
    return objs

def _resolve_not(restrictions, solutions, fixed):
    restr = restrictions[0]
    constrvarname = restr.constraint_var
    if len(restrictions) > 1 or not constrvarname in fixed:
        raise NotImplementedError()
    varname = restr.searched_var
    objs = []
    for etype in frozenset(etypes[varname] for etypes in solutions):
        gqlargs = {}
        for operator in ('<', '>'):
            query = Query(etype)
            restr.fill_query(fixed, query, operator)
            objs += query.Run()
    return objs

def _print_results(rlist):
    return '[%s]' % ', '.join(_print_result(r) for r in rlist)

def _print_result(rdict):
    string = []
    for k, v in rdict.iteritems():
        if isinstance(v, Entity):
            string.append('%s: %s' % (k, v.key()))#_print_result(v)))
        elif isinstance(v, list):
            string.append('%s: [%s]' % (k, ', '.join(str(i) for i in v)))
        else:
            string.append('%s: %s' % (k, v))
    return '{%s}' % ', '.join(string)

                         
class EidMismatch(Exception):
    def __init__(self, varname, value):
        self.varname = varname
        self.value = value


class Restriction(object):
    supported_operators = ('=',)
    def __init__(self, rel):
        operator = rel.children[1].operator
        if not operator in self.supported_operators:
            raise NotImplementedError('unsupported operator')
        self.rel = rel
        self.operator = operator
        self.rtype = rel.r_type
        self.var = rel.children[0]
        
    def __repr__(self):
        return '<%s for %s>' % (self.__class__.__name__, self.rel)
    
    @property
    def rhs(self):
        return self.rel.children[1].children[0]

        
class MultipleRestriction(object):
    def __init__(self, restrictions):
        self.restrictions = restrictions
        
    def resolve(self, solutions, fixed):
        return _resolve(self.restrictions, solutions, fixed)

    
class VariableSelection(Restriction):
    def __init__(self, rel, dsget, prefix='s'):
        Restriction.__init__(self, rel)
        self._dsget = dsget
        self._not = self.rel.neged(strict=True)
        self._prefix = prefix + '_'
        
    def __repr__(self):
        return '<%s%s for %s>' % (self._prefix[0], self.__class__.__name__, self.rel)
        
    @property
    def searched_var(self):
        if self._prefix == 's_':
            return self.var.name
        return self.rhs.name
        
    @property
    def constraint_var(self):
        if self._prefix == 's_':
            return self.rhs.name
        return self.var.name
        
    def _possible_values(self, myvar, ovar, entity, solutions, dsprefix):
        if self.rtype == 'identity':
            return (entity.key(),)
        value = entity.get(dsprefix + self.rtype)
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        vartypes = poss_var_types(myvar, ovar, entity.kind(), solutions)
        return (v for v in value if v.kind() in vartypes)
        
    def complete_and_filter(self, solutions, results):
        myvar = self.rhs.name
        ovar = self.var.name
        rtype = self.rtype
        if self.schema.rschema(rtype).is_final():
            # should be detected by rql.stcheck: "Any C WHERE NOT X attr C" doesn't make sense
            #if self._not:
            #    raise NotImplementedError()
            for result in results:
                result[myvar] = result[ovar].get('s_'+rtype)
        elif self.var.name in results[0]:
            if self.rhs.name in results[0]:
                self.filter(solutions, results)
            else:
                if self._not:
                    raise NotImplementedError()
                for result in results[:]:
                    values = self._possible_values(myvar, ovar, result[ovar],
                                                   solutions, 's_')
                    expand_result(results, result, myvar, values, self._dsget)
        else:
            assert self.rhs.name in results[0]
            self.object_complete_and_filter(solutions, results)           
            
    def filter(self, solutions, results):
        myvar = self.rhs.name
        ovar = self.var.name
        newsols = {}
        for result in results[:]:
            entity = result[ovar]
            key = entity.key()
            if not key in newsols:
                values = self._possible_values(myvar, ovar, entity, solutions, 's_')
                newsols[key] = frozenset(v for v in values)
            if self._not:
                if result[myvar].key() in newsols[key]:
                    results.remove(result)                
            elif not result[myvar].key() in newsols[key]:
                results.remove(result)
    
    def object_complete_and_filter(self, solutions, results):
        if self._not:
            raise NotImplementedError()
        myvar = self.var.name
        ovar = self.rhs.name
        for result in results[:]:
            values = self._possible_values(myvar, ovar, result[ovar],
                                           solutions, 'o_')
            expand_result(results, result, myvar, values, self._dsget)

    
class EidRestriction(Restriction):
    def __init__(self, rel, dsget):
        Restriction.__init__(self, rel)
        self._dsget = dsget

    def resolve(self, kwargs):
        value = self.rel.children[1].children[0].eval(kwargs)
        return self._dsget(value)


class RelationRestriction(VariableSelection):

    def _get_value(self, fixed):
        return fixed[self.constraint_var].key()
    
    def fill_query(self, fixed, query, operator=None):
        restr = '%s%s %s' % (self._prefix, self.rtype, operator or self.operator)
        query[restr] = self._get_value(fixed)

    def resolve(self, solutions, fixed):
        if self.rtype == 'identity':
            if self._not:
                raise NotImplementedError()
            return [fixed[self.constraint_var]]
        if self._not:
            return _resolve_not([self], solutions, fixed)
        return _resolve([self], solutions, fixed)


class NotRelationRestriction(RelationRestriction):

    def _get_value(self, fixed):
        return None
    
    def resolve(self, solutions, fixed):
        if self.rtype == 'identity':
            raise NotImplementedError()
        return _resolve([self], solutions, fixed)


class AttributeRestriction(RelationRestriction):
    supported_operators = ('=', '>', '>=', '<', '<=', 'ILIKE')
    def __init__(self, rel, kwargs):
        RelationRestriction.__init__(self, rel, None)
        value = self.rhs.eval(kwargs)
        self.value = value
        if self.operator == 'ILIKE':
            if value.startswith('%'):
                raise NotImplementedError('LIKE is only supported for prefix search')
            if not value.endswith('%'):
                raise NotImplementedError('LIKE is only supported for prefix search')
            self.operator = '>'
            self.value = value[:-1]
            
    def complete_and_filter(self, solutions, results):
        # check lhs var first in case this is a restriction
        assert self._not
        myvar, rtype, value = self.var.name, self.rtype, self.value
        for result in results[:]:
            if result[myvar].get('s_'+rtype) == value:
                results.remove(result)
            
    def _get_value(self, fixed):
        return self.value


class DateAttributeRestriction(AttributeRestriction):
    """just a thin layer on top af `AttributeRestriction` that
    tries to convert date strings such as in :
    Any X WHERE X creation_date >= '2008-03-04'
    """
    def __init__(self, rel, kwargs):
        super(DateAttributeRestriction, self).__init__(rel, kwargs)
        if isinstance(self.value, basestring):
#             try:
            self.value = datetime.strptime(self.value, '%Y-%m-%d')
#             except Exception, exc:
#                 from logging import error
#                 error('unable to parse date %s with format %%Y-%%m-%%d (exc=%s)', value, exc)


class AttributeInRestriction(AttributeRestriction):
    def __init__(self, rel, kwargs):
        RelationRestriction.__init__(self, rel, None)
        values = []
        for c in self.rel.children[1].iget_nodes(nodes.Constant):
            values.append(c.eval(kwargs))
        self.value = values

    @property
    def operator(self):
        return 'in'
            

class TypeRestriction(AttributeRestriction):
    def __init__(self, var):
        self.var = var

    def __repr__(self):
        return '<%s for %s>' % (self.__class__.__name__, self.var)
    
    def resolve(self, solutions, fixed):
        objs = []
        for etype in frozenset(etypes[self.var.name] for etypes in solutions):
            objs += Query(etype).Run()
        return objs


def append_result(res, descr, i, j, value, etype):
    if value is not None:
        if isinstance(value, Text):
            value = unicode(value)
        elif isinstance(value, Blob):
            value = Binary(str(value))
    if j == 0:
        res.append([value])
        descr.append([etype])
    else:
        res[i].append(value)
        descr[i].append(etype)


class ValueResolver(object):
    def __init__(self, functions, args, term):
        self.functions = functions
        self.args = args
        self.term = term
        self._solution = self.term.stmt.solutions[0]
        
    def compute(self, result):
        """return (entity type, value) to which self.term is evaluated according
        to the given result dictionnary and to query arguments (self.args)
        """
        return self.term.accept(self, result)

    def visit_function(self, node, result):
        args = tuple(n.accept(self, result)[1] for n in node.children)
        value = self.functions[node.name](*args)
        return node.get_type(self._solution, self.args), value
    
    def visit_variableref(self, node, result):
        value = result[node.name]
        try:
            etype = value.kind()
            value = str(value.key())
        except AttributeError:
            etype = self._solution[node.name]
        return etype, value
    
    def visit_constant(self, node, result):
        return node.get_type(kwargs=self.args), node.eval(self.args)
    
        
class RQLInterpreter(object):
    """algorithm:
    1. visit the restriction clauses and collect restriction for each subject
       of a relation. Different restriction types are:
       * EidRestriction
       * AttributeRestriction
       * RelationRestriction
       * VariableSelection (not really a restriction)
       -> dictionary {<variable>: [restriction...], ...}
    2. resolve eid restrictions
    3. for each select in union:
           for each solution in select'solutions:
               1. resolve variables which have attribute restriction
               2. resolve relation restriction
               3. resolve selection and add to global results 
    """
    def __init__(self, schema):
        self.schema = schema
        Restriction.schema = schema # yalta!
        self.rqlhelper = RQLHelper(schema, {'eid': etype_from_key})
        self._stored_proc = {'LOWER': lambda x: x.lower(),
                             'UPPER': lambda x: x.upper()}
        for cb in SQL_CONNECT_HOOKS.get('sqlite', []):
            cb(self)
            
    # emulate sqlite connection interface so we can reuse stored procedures
    def create_function(self, name, nbargs, func):
        self._stored_proc[name] = func
        
    def create_aggregate(self, name, nbargs, func):
        self._stored_proc[name] = func

        
    def execute(self, operation, parameters=None, eid_key=None, build_descr=True):
        rqlst = self.rqlhelper.parse(operation, annotate=True)
        try:
            self.rqlhelper.compute_solutions(rqlst, kwargs=parameters)
        except BadKeyError:
            results, description = [], []
        else:
            results, description = self.interpret(rqlst, parameters)
        return ResultSet(results, operation, parameters, description, rqlst=rqlst)
        
    def interpret(self, node, kwargs, dsget=None):
        if dsget is None:
            self._dsget = Get
        else:
            self._dsget = dsget
        try:
            return node.accept(self, kwargs)
        except NotImplementedError:
            self.critical('support for query not implemented: %s', node)
            raise

    def visit_union(self, node, kwargs):
        results, description = [], []
        extra = {'kwargs': kwargs}
        for child in node.children:
            pres, pdescr = self.visit_select(child, extra)
            results += pres
            description += pdescr
        return results, description
    
    def visit_select(self, node, extra):
        constraints = {}
        if node.where is not None:
            node.where.accept(self, constraints, extra)
        fixed, toresolve, postresolve, postfilters = {}, {}, {}, []
        # extract NOT filters
        for vname, restrictions in constraints.items():
            for restr in restrictions[:]:
                if isinstance(restr, AttributeRestriction) and restr._not:
                    postfilters.append(restr)
                    restrictions.remove(restr)
                    if not restrictions:
                        del constraints[vname]
        # add TypeRestriction for variable which have no restrictions at all
        for varname, var in node.defined_vars.iteritems():
            if not varname in constraints:
                constraints[varname] = [TypeRestriction(var)]
        #print node, constraints
        # compute eid restrictions
        kwargs = extra['kwargs']
        for varname, restrictions in constraints.iteritems():
            for restr in restrictions[:]:
                if isinstance(restr, EidRestriction):
                    assert not varname in fixed    
                    try:
                        value = restr.resolve(kwargs)
                        fixed[varname] = value
                    except EntityNotFoundError:
                        return [], []
                    restrictions.remove(restr)
        #print 'fixed', fixed.keys()
        # combine remaining restrictions
        for varname, restrictions in constraints.iteritems():
            for restr in restrictions:
                if isinstance(restr, AttributeRestriction):
                    toresolve.setdefault(varname, []).append(restr)
                elif isinstance(restr, NotRelationRestriction) or (
                    isinstance(restr, RelationRestriction) and 
                    not restr.searched_var in fixed and restr.constraint_var in fixed):
                    toresolve.setdefault(varname, []).append(restr)
                else:
                    postresolve.setdefault(varname, []).append(restr)
            try:
                if len(toresolve[varname]) > 1:
                    toresolve[varname] = MultipleRestriction(toresolve[varname])
                else:
                    toresolve[varname] = toresolve[varname][0]
            except KeyError:
                pass
        #print 'toresolve %s' % toresolve
        #print 'postresolve %s' % postresolve
        # resolve additional restrictions
        if fixed:
            partres = [fixed.copy()]
        else:
            partres = []
        for varname, restr in toresolve.iteritems():
            varpartres = partres[:]
            try:
                values = tuple(restr.resolve(node.solutions, fixed))
            except EidMismatch, ex:
                varname = ex.varname
                value = ex.value
                partres = [res for res in partres if res[varname] != value]
                if partres:
                    continue
                # some join failed, no possible results
                return [], []
            if not values:
                # some join failed, no possible results
                return [], []
            if not varpartres:
                # init results
                for value in values:
                    partres.append({varname: value})
            elif not varname in partres[0]:
                # cartesian product
                for res in partres:                    
                    res[varname] = values[0]
                for res in partres[:]:
                    for value in values[1:]:
                        res = res.copy()
                        res[varname] = value
                        partres.append(res)
            else:
                # union 
                for res in varpartres:
                    for value in values:
                        res = res.copy()
                        res[varname] = value
                        partres.append(res)
        #print 'partres', len(partres)
        #print partres                        
        # Note: don't check for empty partres since constant selection may still
        # produce result at this point
        # sort to get RelationRestriction before AttributeSelection
        restrictions = sorted((restr for restrictions in postresolve.itervalues()
                               for restr in restrictions),
                              key=lambda x: not isinstance(x, RelationRestriction))
        # compute stuff not doable in the previous step using datastore queries
        for restr in restrictions + postfilters:
            restr.complete_and_filter(node.solutions, partres)
            if not partres:
                # some join failed, no possible results
                return [], []
        if extra.pop('has_exists', False):
            # remove potential duplicates introduced by exists
            toremovevars = [v.name for v in node.defined_vars.itervalues()
                            if not v.scope is node]
            if toremovevars:
                newpartres = []
                for result in partres:
                    for var in toremovevars:
                        del result[var]
                    if not result in newpartres:
                        newpartres.append(result)
                if not newpartres:
                    # some join failed, no possible results
                    return [], []
                partres = newpartres
        if node.orderby:
            for sortterm in reversed(node.orderby):
                resolver = ValueResolver(self._stored_proc, kwargs, sortterm.term)
                partres.sort(reverse=not sortterm.asc,
                             key=lambda x: resolver.compute(x)[1])
        if partres:
            if node.offset:
                partres = partres[node.offset:]
            if node.limit:
                partres = partres[:node.limit]
            if not partres:
                return [], []
        #print 'completed partres', _print_results(partres)
        # compute results
        res, descr = [], []
        for j, term in enumerate(node.selection):
            resolver = ValueResolver(self._stored_proc, kwargs, term)
            if not partres:
                etype, value = resolver.compute({})
                # only constant selected
                if not res:
                    res.append([])
                    descr.append([])
                    res[0].append(value)
                    descr[0].append(etype)
            else:
                for i, sol in enumerate(partres):
                    etype, value = resolver.compute(sol)
                    append_result(res, descr, i, j, value, etype)
        #print '--------->', res
        return res, descr
    
    def visit_and(self, node, constraints, extra): 
        for child in node.children:
            child.accept(self, constraints, extra)
    def visit_exists(self, node, constraints, extra):
        extra['has_exists'] = True
        self.visit_and(node, constraints, extra)
    
    def visit_not(self, node, constraints, extra):
        for child in node.children:
            child.accept(self, constraints, extra)
        try:
            extra.pop(node)
        except KeyError:
            raise NotImplementedError()
        
    def visit_relation(self, node, constraints, extra):
        if node.is_types_restriction():
            return
        rschema = self.schema.rschema(node.r_type)
        neged = node.neged(strict=True)
        if neged:
            # ok, we *may* process this Not node (not implemented error will be
            # raised later if we can't)
            extra[node.parent] = True
        if rschema.is_final():
            self._visit_final_relation(rschema, node, constraints, extra)
        elif neged:
            self._visit_non_final_neged_relation(rschema, node, constraints)
        else:
            self._visit_non_final_relation(rschema, node, constraints)
                
    def _visit_non_final_relation(self, rschema, node, constraints, not_=False):
        lhs, rhs = node.get_variable_parts()
        for v1, v2, prefix in ((lhs, rhs, 's'), (rhs, lhs, 'o')):
            #if not_:
            nbrels = len(v2.variable.stinfo['relations'])
            #else:
            #    nbrels = len(v2.variable.stinfo['relations']) - len(v2.variable.stinfo['uidrels'])
            if nbrels > 1:
                constraints.setdefault(v1.name, []).append(
                    RelationRestriction(node, self._dsget, prefix))
                # just init an empty list for v2 variable to avoid a 
                # TypeRestriction being added for it
                constraints.setdefault(v2.name, [])
                break
        else:
            constraints.setdefault(rhs.name, []).append(
                VariableSelection(node, self._dsget, 's'))
                
    def _visit_non_final_neged_relation(self, rschema, node, constraints):
        lhs, rhs = node.get_variable_parts()
        for v1, v2, prefix in ((lhs, rhs, 's'), (rhs, lhs, 'o')):
            stinfo = v2.variable.stinfo
            if not stinfo['selected'] and len(stinfo['relations']) == 1:
                constraints.setdefault(v1.name, []).append(
                    NotRelationRestriction(node, self._dsget, prefix))
                constraints.setdefault(v2.name, [])
                break
        else:
            self._visit_non_final_relation(rschema, node, constraints, True)

    def _visit_final_relation(self, rschema, node, constraints, extra):
        varname = node.children[0].name
        if rschema.type == 'eid':
            constraints.setdefault(varname, []).append(
                EidRestriction(node, self._dsget))
        else:
            rhs = node.children[1].children[0]
            if isinstance(rhs, nodes.VariableRef):
                constraints.setdefault(rhs.name, []).append(
                    VariableSelection(node, self._dsget))
            elif isinstance(rhs, nodes.Constant):
                if rschema.objects()[0] in ('Datetime', 'Date'): # XXX
                    constraints.setdefault(varname, []).append(
                        DateAttributeRestriction(node, extra['kwargs']))
                else:
                    constraints.setdefault(varname, []).append(
                        AttributeRestriction(node, extra['kwargs']))
            elif isinstance(rhs, nodes.Function) and rhs.name == 'IN':
                constraints.setdefault(varname, []).append(
                    AttributeInRestriction(node, extra['kwargs']))
            else:
                raise NotImplementedError()
        
    def _not_implemented(self, *args, **kwargs):
        raise NotImplementedError()
    
    visit_or = _not_implemented
    # shouldn't occurs
    visit_set = _not_implemented
    visit_insert = _not_implemented
    visit_delete = _not_implemented
        

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(RQLInterpreter, getLogger('cubicweb.goa.rqlinterpreter'))
set_log_methods(Restriction, getLogger('cubicweb.goa.rqlinterpreter'))
