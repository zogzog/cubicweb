"""contains utility functions and some visual component to restrict results of
a search

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from itertools import chain
from copy import deepcopy

from logilab.mtconverter import html_escape

from logilab.common.graph import has_path
from logilab.common.decorators import cached
from logilab.common.compat import all

from rql import parse, nodes

from cubicweb import Unauthorized, typed_eid
from cubicweb.common.selectors import match_context_prop, one_has_relation
from cubicweb.common.registerers import priority_registerer
from cubicweb.common.appobject import AppRsetObject
from cubicweb.common.utils import AcceptMixIn
from cubicweb.web.htmlwidgets import HTMLWidget

## rqlst manipulation functions used by facets ################################

def prepare_facets_rqlst(rqlst, args=None):
    """prepare a syntax tree to generate facet filters
    
    * remove ORDERBY clause
    * cleanup selection (remove everything)
    * undefine unnecessary variables
    * set DISTINCT
    * unset LIMIT/OFFSET
    """
    if len(rqlst.children) > 1:
        raise NotImplementedError('FIXME: union not yet supported')
    select = rqlst.children[0]
    mainvar = filtered_variable(select)
    select.set_limit(None)
    select.set_offset(None)
    baserql = select.as_string(kwargs=args)
    # cleanup sort terms
    select.remove_sort_terms()
    # selection: only vocabulary entity
    for term in select.selection[:]:
        select.remove_selected(term)
    # remove unbound variables which only have some type restriction
    for dvar in select.defined_vars.values():
        if not (dvar is mainvar or dvar.stinfo['relations']):
            select.undefine_variable(dvar)
    # global tree config: DISTINCT, LIMIT, OFFSET
    select.set_distinct(True)
    return mainvar, baserql

def filtered_variable(rqlst):
    vref = rqlst.selection[0].iget_nodes(nodes.VariableRef).next()
    return vref.variable


def get_facet(req, facetid, rqlst, mainvar):
    return req.vreg.object_by_id('facets', facetid, req, rqlst=rqlst,
                                 filtered_variable=mainvar)
    

def filter_hiddens(w, **kwargs):
    for key, val in kwargs.items():
        w(u'<input type="hidden" name="%s" value="%s" />' % (
            key, html_escape(val)))


def _may_be_removed(rel, schema, mainvar):
    """if the given relation may be removed from the tree, return the variable
    on the other side of `mainvar`, else return None
    Conditions:
    * the relation is an attribute selection of the main variable
    * the relation is optional relation linked to the main variable
    * the relation is a mandatory relation linked to the main variable
      without any restriction on the other variable
    """
    lhs, rhs = rel.get_variable_parts()
    rschema = schema.rschema(rel.r_type)
    if lhs.variable is mainvar:
        try:
            ovar = rhs.variable
        except AttributeError:
            # constant restriction
            # XXX: X title LOWER(T) if it makes sense?
            return None
        if rschema.is_final():
            if len(ovar.stinfo['relations']) == 1:
                # attribute selection
                return ovar
            return None
        opt = 'right'
        cardidx = 0
    elif getattr(rhs, 'variable', None) is mainvar:
        ovar = lhs.variable
        opt = 'left'
        cardidx = 1
    else:
        # not directly linked to the main variable
        return None
    if rel.optional in (opt, 'both'):
        # optional relation
        return ovar
    if all(rschema.rproperty(s, o, 'cardinality')[cardidx] in '1+'
           for s,o in rschema.iter_rdefs()):
        # mandatory relation without any restriction on the other variable
        for orel in ovar.stinfo['relations']:
            if rel is orel:
                continue
            if _may_be_removed(orel, schema, ovar) is None:
                return None
        return ovar
    return None

def _add_rtype_relation(rqlst, mainvar, rtype, role):
    newvar = rqlst.make_variable()
    if role == 'object':
        rel = rqlst.add_relation(newvar, rtype, mainvar)
    else:
        rel = rqlst.add_relation(mainvar, rtype, newvar)
    return newvar, rel

def _prepare_vocabulary_rqlst(rqlst, mainvar, rtype, role):
    """prepare a syntax tree to generate a filter vocabulary rql using the given
    relation:
    * create a variable to filter on this relation
    * add the relation
    * add the new variable to GROUPBY clause if necessary
    * add the new variable to the selection
    """
    newvar, rel = _add_rtype_relation(rqlst, mainvar, rtype, role)
    if rqlst.groupby:
        rqlst.add_group_var(newvar)
    rqlst.add_selected(newvar)
    return newvar, rel
        
def _remove_relation(rqlst, rel, var):
    """remove a constraint relation from the syntax tree"""
    # remove the relation
    rqlst.remove_node(rel)
    # remove relations where the filtered variable appears on the
    # lhs and rhs is a constant restriction
    extra = []
    for vrel in var.stinfo['relations']:
        if vrel is rel:
            continue
        if vrel.children[0].variable is var:
            if not vrel.children[1].get_nodes(nodes.Constant):
                extra.append(vrel)
            rqlst.remove_node(vrel)
    return extra

def _set_orderby(rqlst, newvar, sortasc, sortfuncname):
    if sortfuncname is None:
        rqlst.add_sort_var(newvar, sortasc)
    else:
        vref = nodes.variable_ref(newvar)
        vref.register_reference()
        sortfunc = nodes.Function(sortfuncname)
        sortfunc.append(vref)
        term = nodes.SortTerm(sortfunc, sortasc)
        rqlst.add_sort_term(term)

def insert_attr_select_relation(rqlst, mainvar, rtype, role, attrname,
                                sortfuncname=None, sortasc=True):
    """modify a syntax tree to retrieve only relevant attribute `attr` of `var`"""
    _cleanup_rqlst(rqlst, mainvar)
    var, mainrel = _prepare_vocabulary_rqlst(rqlst, mainvar, rtype, role)
    # not found, create one
    attrvar = rqlst.make_variable()
    attrrel = rqlst.add_relation(var, attrname, attrvar)
    # if query is grouped, we have to add the attribute variable
    if rqlst.groupby:
        if not attrvar in rqlst.groupby:
            rqlst.add_group_var(attrvar)
    _set_orderby(rqlst, attrvar, sortasc, sortfuncname)
    # add attribute variable to selection
    rqlst.add_selected(attrvar)
    # add is restriction if necessary
    if not mainvar.stinfo['typerels']:
        etypes = frozenset(sol[mainvar.name] for sol in rqlst.solutions)
        rqlst.add_type_restriction(mainvar, etypes)
    return var

def _cleanup_rqlst(rqlst, mainvar):
    """cleanup tree from unnecessary restriction:
    * attribute selection
    * optional relations linked to the main variable
    * mandatory relations linked to the main variable
    """
    if rqlst.where is None:
        return
    schema = rqlst.root.schema
    toremove = set()
    vargraph = deepcopy(rqlst.vargraph) # graph representing links between variable
    for rel in rqlst.where.get_nodes(nodes.Relation):
        ovar = _may_be_removed(rel, schema, mainvar)
        if ovar is not None:
            toremove.add(ovar)
    removed = set()
    while toremove:
        trvar = toremove.pop()
        trvarname = trvar.name
        # remove paths using this variable from the graph
        linkedvars = vargraph.pop(trvarname)
        for ovarname in linkedvars:
            vargraph[ovarname].remove(trvarname)
        # remove relation using this variable
        for rel in chain(trvar.stinfo['relations'], trvar.stinfo['typerels']):
            if rel in removed:
                # already removed
                continue
            rqlst.remove_node(rel)
            removed.add(rel)
        # cleanup groupby clause
        if rqlst.groupby:
            for vref in rqlst.groupby[:]:
                if vref.name == trvarname:
                    rqlst.remove_group_var(vref)
        # we can also remove all variables which are linked to this variable
        # and have no path to the main variable
        for ovarname in linkedvars:
            if ovarname == mainvar.name:
                continue
            if not has_path(vargraph, ovarname, mainvar.name):
                toremove.add(rqlst.defined_vars[ovarname])            

        
        
## base facet classes #########################################################
class AbstractFacet(AcceptMixIn, AppRsetObject):
    __registerer__ = priority_registerer
    __abstract__ = True
    __registry__ = 'facets'
    property_defs = {
        _('visible'): dict(type='Boolean', default=True,
                           help=_('display the box or not')),
        _('order'):   dict(type='Int', default=99,
                           help=_('display order of the box')),
        _('context'): dict(type='String', default=None,
                           # None <-> both
                           vocabulary=(_('tablefilter'), _('facetbox'), None),
                           help=_('context where this box should be displayed')),
        }
    visible = True
    context = None
    needs_update = False
    start_unfolded = True
    
    @classmethod
    def selected(cls, req, rset=None, rqlst=None, context=None,
                 filtered_variable=None):
        assert rset is not None or rqlst is not None
        assert filtered_variable
        instance = super(AbstractFacet, cls).selected(req, rset)
        #instance = AppRsetObject.selected(req, rset)
        #instance.__class__ = cls
        # facet retreived using `object_by_id` from an ajax call
        if rset is None:
            instance.init_from_form(rqlst=rqlst)
        # facet retreived from `select` using the result set to filter
        else:
            instance.init_from_rset()
        instance.filtered_variable = filtered_variable
        return instance

    def init_from_rset(self):
        self.rqlst = self.rset.syntax_tree().children[0]

    def init_from_form(self, rqlst):
        self.rqlst = rqlst

    @property
    def operator(self):
        # OR between selected values by default
        return self.req.form.get(self.id + '_andor', 'OR')
    
    def get_widget(self):
        """return the widget instance to use to display this facet
        """
        raise NotImplementedError
    
    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        raise NotImplementedError
    

class VocabularyFacet(AbstractFacet):
    needs_update = True
    
    def get_widget(self):
        """return the widget instance to use to display this facet

        default implentation expects a .vocabulary method on the facet and
        return a combobox displaying this vocabulary
        """
        vocab = self.vocabulary()
        if len(vocab) <= 1:
            return None
        wdg = FacetVocabularyWidget(self)
        selected = frozenset(typed_eid(eid) for eid in self.req.list_form_param(self.id))
        for label, value in vocab:
            if value is None:
                wdg.append(FacetSeparator(label))
            else:
                wdg.append(FacetItem(self.req, label, value, value in selected))
        return wdg
    
    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        raise NotImplementedError
    
    def possible_values(self):
        """return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet
        """
        raise NotImplementedError

    def support_and(self):
        return False
    
    def rqlexec(self, rql, args=None, cachekey=None):
        try:
            return self.req.execute(rql, args, cachekey)
        except Unauthorized:
            return []
        

class RelationFacet(VocabularyFacet):
    __selectors__ = (one_has_relation, match_context_prop)
    # class attributes to configure the relation facet
    rtype = None
    role = 'subject'
    target_attr = 'eid'
    # set this to a stored procedure name if you want to sort on the result of
    # this function's result instead of direct value
    sortfunc = None
    # ascendant/descendant sorting
    sortasc = True
    
    @property
    def title(self):
        return display_name(self.req, self.rtype, form=self.role)        

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        rqlst = self.rqlst
        rqlst.save_state()
        try:
            mainvar = self.filtered_variable
            insert_attr_select_relation(rqlst, mainvar, self.rtype, self.role,
                                        self.target_attr, self.sortfunc, self.sortasc)
            try:
                rset = self.rqlexec(rqlst.as_string(), self.rset.args, self.rset.cachekey)
            except:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, rqlst.as_string())
                return ()
        finally:
            rqlst.recover()
        return self.rset_vocabulary(rset)
    
    def possible_values(self):
        """return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet
        """
        rqlst = self.rqlst
        rqlst.save_state()
        try:
            _cleanup_rqlst(rqlst, self.filtered_variable)
            _prepare_vocabulary_rqlst(rqlst, self.filtered_variable, self.rtype, self.role)
            return [str(x) for x, in self.rqlexec(rqlst.as_string())]
        finally:
            rqlst.recover()
    
    def rset_vocabulary(self, rset):
        _ = self.req._
        return [(_(label), eid) for eid, label in rset]

    @cached
    def support_and(self):
        rschema = self.schema.rschema(self.rtype)
        if self.role == 'subject':
            cardidx = 0
        else:
            cardidx = 1
        # XXX when called via ajax, no rset to compute possible types
        possibletypes = self.rset and self.rset.column_types(0)
        for subjtype, objtype in rschema.iter_rdefs():
            if possibletypes is not None:
                if self.role == 'subject':
                    if not subjtype in possibletypes:
                        continue
                elif not objtype in possibletypes:
                    continue
            if rschema.rproperty(subjtype, objtype, 'cardinality')[cardidx] in '+*':
                return True
        return False

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self.req.form.get(self.id)
        if not value:
            return
        mainvar = self.filtered_variable
        restrvar = _add_rtype_relation(self.rqlst, mainvar, self.rtype, self.role)[0]
        if isinstance(value, basestring):
            # only one value selected
            self.rqlst.add_eid_restriction(restrvar, value)
        elif self.operator == 'OR':
            #  multiple values with OR operator
            # set_distinct only if rtype cardinality is > 1
            if self.support_and():
                self.rqlst.set_distinct(True)
            self.rqlst.add_eid_restriction(restrvar, value)
        else:
            # multiple values with AND operator
            self.rqlst.add_eid_restriction(restrvar, value.pop())
            while value:
                restrvar = _add_rtype_relation(self.rqlst, mainvar, self.rtype, self.role)[0]
                self.rqlst.add_eid_restriction(restrvar, value.pop())


class AttributeFacet(RelationFacet):
    # attribute type
    attrtype = 'String'
    
    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        rqlst = self.rqlst
        rqlst.save_state()
        try:
            mainvar = self.filtered_variable
            _cleanup_rqlst(rqlst, mainvar)
            newvar, rel = _prepare_vocabulary_rqlst(rqlst, mainvar, self.rtype, self.role)
            _set_orderby(rqlst, newvar, self.sortasc, self.sortfunc)
            try:
                rset = self.rqlexec(rqlst.as_string(), self.rset.args, self.rset.cachekey)
            except:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, rqlst.as_string())
                return ()
        finally:
            rqlst.recover()
        return self.rset_vocabulary(rset)
    
    def rset_vocabulary(self, rset):
        _ = self.req._
        return [(_(value), value) for value, in rset]

    def support_and(self):
        return False
            
    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self.req.form.get(self.id)
        if not value:
            return
        mainvar = self.filtered_variable
        self.rqlst.add_constant_restriction(mainvar, self.rtype, value,
                                            self.attrtype)


        
class FilterRQLBuilder(object):
    """called by javascript to get a rql string from filter form"""

    def __init__(self, req):
        self.req = req
                
    def build_rql(self):#, tablefilter=False):
        form = self.req.form
        facetids = form['facets'].split(',')
        select = parse(form['baserql']).children[0] # XXX Union unsupported yet
        mainvar = filtered_variable(select)
        toupdate = []
        for facetid in facetids:
            facet = get_facet(self.req, facetid, select, mainvar)
            facet.add_rql_restrictions()
            if facet.needs_update:
                toupdate.append(facetid)
        return select.as_string(), toupdate

        
## html widets ################################################################

class FacetVocabularyWidget(HTMLWidget):
    
    def __init__(self, facet):
        self.facet = facet
        self.items = []

    def append(self, item):
        self.items.append(item)
            
    def _render(self):
        title = html_escape(self.facet.title)
        facetid = html_escape(self.facet.id)
        if len(self.items) > 6:
            self.w(u'<div id="%s" class="facet overflowed">\n' % facetid)
        else:
            self.w(u'<div id="%s" class="facet">\n' % facetid)
        self.w(u'<div class="facetTitle" cubicweb:facetName="%s">%s</div>\n' %
               (html_escape(facetid), title))
        if self.facet.support_and():
            _ = self.facet.req._
            self.w(u'''<select name="%s" class="radio facetOperator" title="%s">
  <option value="OR">%s</option>
  <option value="AND">%s</option>
</select>''' % (facetid + '_andor', _('and/or between different values'),
                _('OR'), _('AND')))
        cssclass = ''
        if not self.facet.start_unfolded:
            cssclass += ' hidden'
        self.w(u'<div class="facetBody%s">\n' % cssclass)
        for item in self.items:
            item.render(self.w)
        self.w(u'</div>\n')
        self.w(u'</div>\n')

        
class FacetStringWidget(HTMLWidget):
    def __init__(self, facet):
        self.facet = facet
        self.value = None

    def _render(self):
        title = html_escape(self.facet.title)
        facetid = html_escape(self.facet.id)
        self.w(u'<div id="%s" class="facet">\n' % facetid)
        self.w(u'<div class="facetTitle" cubicweb:facetName="%s">%s</div>\n' %
               (facetid, title))
        self.w(u'<input name="%s" type="text" value="%s" />\n' % (facetid, self.value or u''))
        self.w(u'</div>\n')


class FacetItem(HTMLWidget):

    selected_img = "black-check.png"
    unselected_img = "no-check-no-border.png"

    def __init__(self, req, label, value, selected=False):
        self.req = req
        self.label = label
        self.value = value
        self.selected = selected

    def _render(self):
        if self.selected:
            cssclass = ' facetValueSelected'
            imgsrc = self.req.datadir_url + self.selected_img
        else:
            cssclass = ''
            imgsrc = self.req.datadir_url + self.unselected_img            
        self.w(u'<div class="facetValue facetCheckBox%s" cubicweb:value="%s">\n'
               % (cssclass, html_escape(unicode(self.value))))
        self.w(u'<img src="%s" />&nbsp;' % imgsrc)
        self.w(u'<a href="javascript: {}">%s</a>' % html_escape(self.label))
        self.w(u'</div>')


class FacetSeparator(HTMLWidget):
    def __init__(self, label=None):
        self.label = label or u'&nbsp;'
        
    def _render(self):
        pass

