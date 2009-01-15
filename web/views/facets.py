"""the facets box and some basic facets

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps

from logilab.mtconverter import html_escape

from cubicweb.common.selectors import (chainfirst, chainall, non_final_entity,
                                    two_lines_rset, match_context_prop,
                                    yes, one_has_relation)
from cubicweb.web.box import BoxTemplate
from cubicweb.web.facet import (AbstractFacet, VocabularyFacet, FacetStringWidget,
                             RelationFacet, prepare_facets_rqlst, filter_hiddens)

def contextview_selector(cls, req, rset, row=None, col=None, view=None,
                         **kwargs):
    if view and getattr(view, 'filter_box_context_info', lambda: None)():
        return 1
    return 0    


class FilterBox(BoxTemplate):
    """filter results of a query"""
    id = 'filter_box'
    __selectors__ = (chainfirst(contextview_selector,
                                chainall(non_final_entity, two_lines_rset)),
                     match_context_prop)
    context = 'left'
    title = _('boxes_filter_box')
    visible = True # functionality provided by the search box by default
    order = 1
    roundcorners = True

    def facetargs(self):
        """this method returns the list of extra arguments that should
        be used by the facet
        """
        return {}
        
    def _get_context(self, view):
        context = getattr(view, 'filter_box_context_info', lambda: None)()
        if context:
            rset, vid, divid, paginate = context
        else:
            rset = self.rset
            vid, divid = None, 'pageContent'
            paginate = view and view.need_navigation
        return rset, vid, divid, paginate
        
    def call(self, view=None):
        req = self.req
        req.add_js( ('cubicweb.ajax.js', 'cubicweb.formfilter.js') )
        req.add_css('cubicweb.facets.css')
        if self.roundcorners:
            req.html_headers.add_onload('jQuery(".facet").corner("tl br 10px");')
        rset, vid, divid, paginate=self._get_context(view)
        if rset.rowcount < 2: # XXX done by selectors, though maybe necessary when rset has been hijacked
            return
        if vid is None:
            vid = req.form.get('vid')
        rqlst = rset.syntax_tree()
        rqlst.save_state()
        try:
            mainvar, baserql = prepare_facets_rqlst(rqlst, rset.args)
            widgets = []
            for facet in self.get_facets(rset, mainvar):
                if facet.propval('visible'):
                    wdg = facet.get_widget()
                    if wdg is not None:
                        widgets.append(wdg)
            if not widgets:
                return
            w = self.w
            eschema = self.schema.eschema('Bookmark')
            if eschema.has_perm(req, 'add'):
                bk_path = 'view?rql=%s' % rset.printable_rql()
                bk_title = req._('my custom search')
                linkto = 'bookmarked_by:%s:subject' % self.req.user.eid
                bk_add_url = self.build_url('add/Bookmark', path=bk_path, title=bk_title, __linkto=linkto)
                bk_base_url = self.build_url('add/Bookmark', title=bk_title, __linkto=linkto)
                w(u'<div class="facetTitle"><a cubicweb:target="%s" id="facetBkLink" href="%s">%s</a></div>' % (
                    html_escape(bk_base_url),
                    html_escape(bk_add_url),
                    req._('bookmark this search')))
            w(u'<form method="post" id="%sForm" cubicweb:facetargs="%s" action="">'  % (
                divid, html_escape(dumps([divid, vid, paginate, self.facetargs()]))))
            w(u'<fieldset>')
            hiddens = {'facets': ','.join(wdg.facet.id for wdg in widgets),
                       'baserql': baserql}
            for param in ('subvid', 'vtitle'):
                if param in req.form:
                    hiddens[param] = req.form[param]
            filter_hiddens(w, **hiddens)
            for wdg in widgets:
                wdg.render(w=self.w)
            w(u'</fieldset>\n</form>\n')
        finally:
            rqlst.recover()
            import cubicweb
            cubicweb.info('after facets with rql: %s' % repr(rqlst))

    def get_facets(self, rset, mainvar):
        return self.vreg.possible_vobjects('facets', self.req, rset,
                                           context='facetbox',
                                           filtered_variable=mainvar)
        
# facets ######################################################################

class CreatedByFacet(RelationFacet):
    id = 'created_by-facet'
    rtype = 'created_by'
    target_attr = 'login'

class InGroupFacet(RelationFacet):
    id = 'in_group-facet'
    rtype = 'in_group'
    target_attr = 'name'

class InStateFacet(RelationFacet):
    id = 'in_state-facet'
    rtype = 'in_state'
    target_attr = 'name'

# inherit from RelationFacet to benefit from its possible_values implementation
class ETypeFacet(RelationFacet):
    id = 'etype-facet'
    __selectors__ = (yes,)
    order = 1
    rtype = 'is'
    target_attr = 'name'

    @property
    def title(self):
        return self.req._('entity type')

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        etypes = self.rset.column_types(0)
        return sorted((self.req._(etype), etype) for etype in etypes)
    
    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self.req.form.get(self.id)
        if not value:
            return
        self.rqlst.add_type_restriction(self.filtered_variable, value)


class HasTextFacet(AbstractFacet):
    __selectors__ = (one_has_relation, match_context_prop)
    id = 'has_text-facet'
    rtype = 'has_text'
    role = 'subject'
    order = 0
    @property
    def title(self):
        return self.req._('has_text')
    
    def get_widget(self):
        """return the widget instance to use to display this facet

        default implentation expects a .vocabulary method on the facet and
        return a combobox displaying this vocabulary
        """
        return FacetStringWidget(self)

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self.req.form.get(self.id)
        if not value:
            return
        self.rqlst.add_constant_restriction(self.filtered_variable, 'has_text', value, 'String')
