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
"""the facets box and some basic facets"""

__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb.appobject import objectify_selector
from cubicweb.selectors import (non_final_entity, multi_lines_rset,
                                match_context_prop, yes, relation_possible)
from cubicweb.utils import json_dumps
from cubicweb.web.box import BoxTemplate
from cubicweb.web.facet import (AbstractFacet, FacetStringWidget, RelationFacet,
                                prepare_facets_rqlst, filter_hiddens, _cleanup_rqlst,
                                _prepare_vocabulary_rqlst)

@objectify_selector
def contextview_selector(cls, req, rset=None, row=None, col=None, view=None,
                         **kwargs):
    if view and getattr(view, 'filter_box_context_info', lambda: None)():
        return 1
    return 0


class FilterBox(BoxTemplate):
    """filter results of a query"""
    __regid__ = 'filter_box'
    __select__ = (((non_final_entity() & multi_lines_rset())
                   | contextview_selector()
                   ) & match_context_prop())
    context = 'left'
    title = _('boxes_filter_box')
    visible = True # functionality provided by the search box by default
    order = 1
    roundcorners = True

    needs_css = 'cubicweb.facets.css'
    needs_js = ('cubicweb.ajax.js', 'cubicweb.facets.js')

    bk_linkbox_template = u'<div class="facetTitle">%s</div>'

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
            rset = self.cw_rset
            vid, divid = None, 'pageContent'
            paginate = view and view.paginable
        return rset, vid, divid, paginate

    def call(self, view=None):
        req = self._cw
        req.add_js( self.needs_js )
        req.add_css( self.needs_css)
        if self.roundcorners:
            req.html_headers.add_onload('jQuery(".facet").corner("tl br 10px");')
        rset, vid, divid, paginate = self._get_context(view)
        if rset.rowcount < 2: # XXX done by selectors, though maybe necessary when rset has been hijacked
            return
        rqlst = rset.syntax_tree()
        # union not yet supported
        if len(rqlst.children) != 1:
            return ()
        rqlst = rqlst.copy()
        req.vreg.rqlhelper.annotate(rqlst)
        mainvar, baserql = prepare_facets_rqlst(rqlst, rset.args)
        widgets = []
        for facet in self.get_facets(rset, rqlst.children[0], mainvar):
            if facet.cw_propval('visible'):
                wdg = facet.get_widget()
                if wdg is not None:
                    widgets.append(wdg)
        if not widgets:
            return
        if vid is None:
            vid = req.form.get('vid')
        if self.bk_linkbox_template:
            self.display_bookmark_link(rset)
        w = self.w
        w(u'<form method="post" id="%sForm" cubicweb:facetargs="%s" action="">'  % (
            divid, xml_escape(json_dumps([divid, vid, paginate, self.facetargs()]))))
        w(u'<fieldset>')
        hiddens = {'facets': ','.join(wdg.facet.__regid__ for wdg in widgets),
                   'baserql': baserql}
        for param in ('subvid', 'vtitle'):
            if param in req.form:
                hiddens[param] = req.form[param]
        filter_hiddens(w, **hiddens)
        for wdg in widgets:
            wdg.render(w=self.w)
        w(u'</fieldset>\n</form>\n')

    def display_bookmark_link(self, rset):
        eschema = self._cw.vreg.schema.eschema('Bookmark')
        if eschema.has_perm(self._cw, 'add'):
            bk_path = 'rql=%s' % self._cw.url_quote(rset.printable_rql())
            if self._cw.form.get('vid'):
                bk_path += '&vid=%s' % self._cw.url_quote(self._cw.form['vid'])
            bk_path = 'view?' + bk_path
            bk_title = self._cw._('my custom search')
            linkto = 'bookmarked_by:%s:subject' % self._cw.user.eid
            bk_add_url = self._cw.build_url('add/Bookmark', path=bk_path, title=bk_title, __linkto=linkto)
            bk_base_url = self._cw.build_url('add/Bookmark', title=bk_title, __linkto=linkto)
            bk_link = u'<a cubicweb:target="%s" id="facetBkLink" href="%s">%s</a>' % (
                    xml_escape(bk_base_url),
                    xml_escape(bk_add_url),
                    self._cw._('bookmark this search'))
            self.w(self.bk_linkbox_template % bk_link)

    def get_facets(self, rset, rqlst, mainvar):
        return self._cw.vreg['facets'].poss_visible_objects(
            self._cw, rset=rset, rqlst=rqlst,
            context='facetbox', filtered_variable=mainvar)

# facets ######################################################################

class CreatedByFacet(RelationFacet):
    __regid__ = 'created_by-facet'
    rtype = 'created_by'
    target_attr = 'login'

class InGroupFacet(RelationFacet):
    __regid__ = 'in_group-facet'
    rtype = 'in_group'
    target_attr = 'name'

class InStateFacet(RelationFacet):
    __regid__ = 'in_state-facet'
    rtype = 'in_state'
    target_attr = 'name'

# inherit from RelationFacet to benefit from its possible_values implementation
class ETypeFacet(RelationFacet):
    __regid__ = 'etype-facet'
    __select__ = yes()
    order = 1
    rtype = 'is'
    target_attr = 'name'

    @property
    def title(self):
        return self._cw._('entity type')

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        etypes = self.cw_rset.column_types(0)
        return sorted((self._cw._(etype), etype) for etype in etypes)

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        self.rqlst.add_type_restriction(self.filtered_variable, value)

    def possible_values(self):
        """return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet
        """
        rqlst = self.rqlst
        rqlst.save_state()
        try:
            _cleanup_rqlst(rqlst, self.filtered_variable)
            etype_var = _prepare_vocabulary_rqlst(rqlst, self.filtered_variable, self.rtype, self.role)
            attrvar = rqlst.make_variable()
            rqlst.add_selected(attrvar)
            rqlst.add_relation(etype_var, 'name', attrvar)
            return [etype for _, etype in self.rqlexec(rqlst.as_string())]
        finally:
            rqlst.recover()

class HasTextFacet(AbstractFacet):
    __select__ = relation_possible('has_text', 'subject') & match_context_prop()
    __regid__ = 'has_text-facet'
    rtype = 'has_text'
    role = 'subject'
    order = 0
    @property
    def title(self):
        return self._cw._('has_text')

    def get_widget(self):
        """return the widget instance to use to display this facet

        default implentation expects a .vocabulary method on the facet and
        return a combobox displaying this vocabulary
        """
        return FacetStringWidget(self)

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        self.rqlst.add_constant_restriction(self.filtered_variable, 'has_text', value, 'String')
