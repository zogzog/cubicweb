# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
_ = unicode

from logilab.mtconverter import xml_escape

from cubicweb.appobject import objectify_selector
from cubicweb.selectors import (non_final_entity, multi_lines_rset,
                                match_context_prop, yes, relation_possible)
from cubicweb.utils import json_dumps
from cubicweb.web import component, facet as facetbase
from cubicweb.rqlrewrite import add_types_restriction

def facets(req, rset, context, mainvar=None):
    """return the base rql and a list of widgets for facets applying to the
    given rset/context (cached version)
    """
    try:
        cache = req.__rset_facets
    except AttributeError:
        cache = req.__rset_facets = {}
    try:
        return cache[(rset, context, mainvar)]
    except KeyError:
        facets = _facets(req, rset, context, mainvar)
        cache[(rset, context, mainvar)] = facets
        return facets

def _facets(req, rset, context, mainvar):
    """return the base rql and a list of widgets for facets applying to the
    given rset/context
    """
    # XXX done by selectors, though maybe necessary when rset has been hijacked
    # (e.g. contextview_selector matched)
    origqlst = rset.syntax_tree()
    # union not yet supported
    if len(origqlst.children) != 1:
        return None, ()

    # Add type restriction to rql. This allow the get_type() method to return
    # useful value on variable extracted from a select statement.
    #
    # This is done on origqlst to ensure all rql related objects are properly
    # enriched when handled by a Facet:
    #    - the rset.syntax_tree() during selection
    #    - the select during selection
    #    - the select during filtering

    add_types_restriction(req.vreg.schema, origqlst.children[0])
    rqlst = origqlst.copy()
    select = rqlst.children[0]
    filtered_variable, baserql = facetbase.init_facets(rset, select, mainvar)
    wdgs = [(facet, facet.get_widget()) for facet in req.vreg['facets'].poss_visible_objects(
        req, rset=rset, rqlst=origqlst, select=select, context=context,
        filtered_variable=filtered_variable)]
    return baserql, [wdg for facet, wdg in wdgs if wdg is not None]


@objectify_selector
def contextview_selector(cls, req, rset=None, row=None, col=None, view=None,
                         **kwargs):
    if view:
        try:
            getcontext = getattr(view, 'filter_box_context_info')
        except AttributeError:
            return 0
        rset = getcontext()[0]
        if rset is None or rset.rowcount < 2:
            return 0
        wdgs = facets(req, rset, cls.__regid__)[1]
        return len(wdgs)
    return 0

@objectify_selector
def has_facets(cls, req, rset=None, mainvar=None, **kwargs):
    if rset is None or rset.rowcount < 2:
        return 0
    wdgs = facets(req, rset, cls.__regid__, mainvar)[1]
    return len(wdgs)


def filter_hiddens(w, baserql, wdgs, **kwargs):
    kwargs['facets'] = ','.join(wdg.facet.__regid__ for wdg in wdgs)
    kwargs['baserql'] = baserql
    for key, val in kwargs.items():
        w(u'<input type="hidden" name="%s" value="%s" />' % (
            key, xml_escape(val)))


class FacetFilterMixIn(object):
    needs_js = ['cubicweb.ajax.js', 'cubicweb.facets.js']
    needs_css = ['cubicweb.facets.css']
    roundcorners = True

    def generate_form(self, w, rset, divid, vid, vidargs,
                      paginate=False, cssclass='', **hiddens):
        """display a form to filter some view's content"""
        mainvar = self.cw_extra_kwargs.get('mainvar')
        baserql, wdgs = facets(self._cw, rset, self.__regid__, mainvar)
        assert wdgs
        self._cw.add_js(self.needs_js)
        self._cw.add_css(self.needs_css)
        self._cw.html_headers.define_var('facetLoadingMsg',
                                         self._cw._('facet-loading-msg'))
        if self.roundcorners:
            self._cw.html_headers.add_onload(
                'jQuery(".facet").corner("tl br 10px");')
        # drop False / None values from vidargs
        vidargs = dict((k, v) for k, v in vidargs.iteritems() if v)
        facetargs = xml_escape(json_dumps([divid, vid, paginate, vidargs]))
        w(u'<form id="%sForm" class="%s" method="post" action="" '
          'cubicweb:facetargs="%s" >' % (divid, cssclass, facetargs))
        w(u'<fieldset>')
        if mainvar:
            hiddens['mainvar'] = mainvar
        filter_hiddens(w, baserql, wdgs, **hiddens)
        self.layout_widgets(w, self.sorted_widgets(wdgs))

        # <Enter> is supposed to submit the form only if there is a single
        # input:text field. However most browsers will submit the form
        # on <Enter> anyway if there is an input:submit field.
        #
        # see: http://www.w3.org/MarkUp/html-spec/html-spec_8.html#SEC8.2
        #
        # Firefox 7.0.1 does not submit form on <Enter> if there is more than a
        # input:text field and not input:submit but does it if there is an
        # input:submit.
        #
        # IE 6 or Firefox 2 behave the same way.
        w(u'<input type="submit" class="hidden" />')
        #
        w(u'</fieldset>\n')
        w(u'</form>\n')

    def sorted_widgets(self, wdgs):
        """sort widgets: by default sort by widget height, then according to
        widget.order (the original widgets order)
        """
        return sorted(wdgs, key=lambda x: x.height())

    def layout_widgets(self, w, wdgs):
        """layout widgets: by default simply render each of them
        (i.e. succession of <div>)
        """
        for wdg in wdgs:
            wdg.render(w=w)


class FilterBox(FacetFilterMixIn, component.CtxComponent):
    """filter results of a query"""
    __regid__ = 'facet.filterbox'
    __select__ = ((non_final_entity() & has_facets())
                  | contextview_selector()) # can't use has_facets because of
                                            # contextview mecanism
    context = 'left' # XXX doesn't support 'incontext', only 'left' or 'right'
    title = _('facet.filters')
    visible = True # functionality provided by the search box by default
    order = 1

    bk_linkbox_template = u'<div class="facetTitle">%s</div>'

    def render_body(self, w, **kwargs):
        req = self._cw
        rset, vid, divid, paginate = self._get_context()
        assert len(rset) > 1
        if vid is None:
            vid = req.form.get('vid')
        if self.bk_linkbox_template and req.vreg.schema['Bookmark'].has_perm(req, 'add'):
            w(self.bookmark_link(rset))
        hiddens = {}
        for param in ('subvid', 'vtitle'):
            if param in req.form:
                hiddens[param] = req.form[param]
        self.generate_form(w, rset, divid, vid, self.vidargs(),
                           paginate=paginate, **hiddens)

    def _get_context(self):
        view = self.cw_extra_kwargs.get('view')
        context = getattr(view, 'filter_box_context_info', lambda: None)()
        if context:
            rset, vid, divid, paginate = context
        else:
            rset = self.cw_rset
            vid, divid = None, 'pageContent'
            paginate = view and view.paginable
        return rset, vid, divid, paginate

    def bookmark_link(self, rset):
        req = self._cw
        bk_path = u'rql=%s' % req.url_quote(rset.printable_rql())
        if req.form.get('vid'):
            bk_path += u'&vid=%s' % req.url_quote(req.form['vid'])
        bk_path = u'view?' + bk_path
        bk_title = req._('my custom search')
        linkto = u'bookmarked_by:%s:subject' % req.user.eid
        bkcls = req.vreg['etypes'].etype_class('Bookmark')
        bk_add_url = bkcls.cw_create_url(req, path=bk_path, title=bk_title,
                                         __linkto=linkto)
        bk_base_url = bkcls.cw_create_url(req, title=bk_title, __linkto=linkto)
        bk_link = u'<a cubicweb:target="%s" id="facetBkLink" href="%s">%s</a>' % (
                xml_escape(bk_base_url), xml_escape(bk_add_url),
                req._('bookmark this search'))
        return self.bk_linkbox_template % bk_link

    def vidargs(self):
        """this method returns the list of extra arguments that should be used
        by the filter or the view using it
        """
        return {}


from cubicweb.view import AnyRsetView

class FilterTable(FacetFilterMixIn, AnyRsetView):
    __regid__ = 'facet.filtertable'
    __select__ = has_facets()
    compact_layout_threshold = 5

    def call(self, vid, divid, vidargs, cssclass=''):
        self.generate_form(self.w, self.cw_rset, divid, vid, vidargs,
                           cssclass=cssclass, fromformfilter='1',
                           # divid=divid XXX
                           )

    def _simple_horizontal_layout(self, w, wdgs):
        w(u'<table class="filter">\n')
        w(u'<tr>\n')
        for wdg in wdgs:
            w(u'<td>')
            wdg.render(w=w)
            w(u'</td>')
        w(u'</tr>\n')
        w(u'</table>\n')

    def layout_widgets(self, w, wdgs):
        """layout widgets: put them in a table where each column should have
        sum(wdg.height()) < wdg_stack_size.
        """
        if len(wdgs) < self.compact_layout_threshold:
            self._simple_horizontal_layout(w, wdgs)
            return
        w(u'<table class="filter">\n')
        widget_queue = []
        queue_height = 0
        wdg_stack_size = max(wdgs, key=lambda wdg:wdg.height()).height()
        w(u'<tr>\n')
        for wdg in wdgs:
            height = wdg.height()
            if queue_height + height <= wdg_stack_size:
                widget_queue.append(wdg)
                queue_height += height
                continue
            w(u'<td>')
            for queued in widget_queue:
                queued.render(w=w)
            w(u'</td>')
            widget_queue = [wdg]
            queue_height = height
        if widget_queue:
            w(u'<td>')
            for queued in widget_queue:
                queued.render(w=w)
            w(u'</td>')
        w(u'</tr>\n')
        w(u'</table>\n')


# facets ######################################################################

class CWSourceFacet(facetbase.RelationFacet):
    __regid__ = 'cw_source-facet'
    rtype = 'cw_source'
    target_attr = 'name'

class CreatedByFacet(facetbase.RelationFacet):
    __regid__ = 'created_by-facet'
    rtype = 'created_by'
    target_attr = 'login'

class InGroupFacet(facetbase.RelationFacet):
    __regid__ = 'in_group-facet'
    rtype = 'in_group'
    target_attr = 'name'

class InStateFacet(facetbase.RelationAttributeFacet):
    __regid__ = 'in_state-facet'
    rtype = 'in_state'
    target_attr = 'name'


# inherit from RelationFacet to benefit from its possible_values implementation
class ETypeFacet(facetbase.RelationFacet):
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
        self.select.add_type_restriction(self.filtered_variable, value)

    def possible_values(self):
        """return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet
        """
        select = self.select
        select.save_state()
        try:
            facetbase.cleanup_select(select, self.filtered_variable)
            etype_var = facetbase.prepare_vocabulary_select(
                select, self.filtered_variable, self.rtype, self.role)
            attrvar = select.make_variable()
            select.add_selected(attrvar)
            select.add_relation(etype_var, 'name', attrvar)
            return [etype for _, etype in self.rqlexec(select.as_string())]
        finally:
            select.recover()


class HasTextFacet(facetbase.AbstractFacet):
    __select__ = relation_possible('has_text', 'subject') & match_context_prop()
    __regid__ = 'has_text-facet'
    rtype = 'has_text'
    role = 'subject'
    order = 0

    @property
    def wdgclass(self):
        return facetbase.FacetStringWidget

    @property
    def title(self):
        return self._cw._('has_text')

    def get_widget(self):
        """return the widget instance to use to display this facet

        default implentation expects a .vocabulary method on the facet and
        return a combobox displaying this vocabulary
        """
        return self.wdgclass(self)

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        self.select.add_constant_restriction(self.filtered_variable, 'has_text', value, 'String')
