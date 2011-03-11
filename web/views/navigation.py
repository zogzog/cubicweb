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
"""navigation components definition for CubicWeb web client"""

__docformat__ = "restructuredtext en"
_ = unicode

from rql.nodes import VariableRef, Constant

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

from cubicweb.selectors import (paginated_rset, sorted_rset,
                                adaptable, implements)
from cubicweb.uilib import cut
from cubicweb.view import EntityAdapter, implements_adapter_compat
from cubicweb.web.component import EmptyComponent, EntityCtxComponent, NavigationComponent


class PageNavigation(NavigationComponent):

    def call(self):
        """displays a resultset by page"""
        params = dict(self._cw.form)
        self.clean_params(params)
        basepath = self._cw.relative_path(includeparams=False)
        self.w(u'<div class="pagination">')
        self.w(u'%s&#160;' % self.previous_link(basepath, params))
        self.w(u'[&#160;%s&#160;]' %
               u'&#160;| '.join(self.iter_page_links(basepath, params)))
        self.w(u'&#160;%s' % self.next_link(basepath, params))
        self.w(u'</div>')

    def index_display(self, start, stop):
        return u'%s - %s' % (start+1, stop+1)

    def iter_page_links(self, basepath, params):
        rset = self.cw_rset
        page_size = self.page_size
        start = 0
        while start < rset.rowcount:
            stop = min(start + page_size - 1, rset.rowcount - 1)
            yield self.page_link(basepath, params, start, stop,
                                 self.index_display(start, stop))
            start = stop + 1


class PageNavigationSelect(PageNavigation):
    """displays a resultset by page as PageNavigationSelect but in a <select>,
    better when there are a lot of results.
    """
    __select__ = paginated_rset(4)

    page_link_templ = u'<option value="%s" title="%s">%s</option>'
    selected_page_link_templ = u'<option value="%s" selected="selected" title="%s">%s</option>'
    def call(self):
        params = dict(self._cw.form)
        self.clean_params(params)
        basepath = self._cw.relative_path(includeparams=False)
        w = self.w
        w(u'<div class="pagination">')
        w(u'%s&#160;' % self.previous_link(basepath, params))
        w(u'<select onchange="javascript: document.location=this.options[this.selectedIndex].value">')
        for option in self.iter_page_links(basepath, params):
            w(option)
        w(u'</select>')
        w(u'&#160;%s' % self.next_link(basepath, params))
        w(u'</div>')


class SortedNavigation(NavigationComponent):
    """sorted navigation apply if navigation is needed (according to page size)
    and if the result set is sorted
    """
    __select__ = paginated_rset() & sorted_rset()

    # number of considered chars to build page links
    nb_chars = 5

    def display_func(self, rset, col, attrname):
        if attrname is not None:
            def index_display(row):
                if not rset[row][col]: # outer join
                    return u''
                entity = rset.get_entity(row, col)
                return entity.printable_value(attrname, format='text/plain')
        elif self._cw.vreg.schema.eschema(rset.description[0][col]).final:
            def index_display(row):
                return unicode(rset[row][col])
        else:
            def index_display(row):
                return rset.get_entity(row, col).view('text')
        return index_display

    def call(self):
        """displays links to navigate accross pages of a result set

        Displayed result is done according to a variable on which the sort
        is done, and looks like:
        [ana - cro] | [cro - ghe] | ... | [tim - zou]
        """
        w = self.w
        rset = self.cw_rset
        page_size = self.page_size
        rschema = self._cw.vreg.schema.rschema
        # attrname = the name of attribute according to which the sort
        # is done if any
        for sorterm in rset.syntax_tree().children[0].orderby:
            if isinstance(sorterm.term, Constant):
                col = sorterm.term.value - 1
                index_display = self.display_func(rset, col, None)
                break
            var = sorterm.term.get_nodes(VariableRef)[0].variable
            col = None
            for ref in var.references():
                rel = ref.relation()
                if rel is None:
                    continue
                attrname = rel.r_type
                if attrname in ('is', 'has_text'):
                    continue
                if not rschema(attrname).final:
                    col = var.selected_index()
                    attrname = None
                if col is None:
                    # final relation or not selected non final relation
                    if var is rel.children[0]:
                        relvar = rel.children[1].children[0].get_nodes(VariableRef)[0]
                    else:
                        relvar = rel.children[0].variable
                    col = relvar.selected_index()
                if col is not None:
                    break
            else:
                # no relation but maybe usable anyway if selected
                col = var.selected_index()
                attrname = None
            if col is not None:
                index_display = self.display_func(rset, col, attrname)
                break
        else:
            # nothing usable found, use the first column
            index_display = self.display_func(rset, 0, None)
        blocklist = []
        params = dict(self._cw.form)
        self.clean_params(params)
        start = 0
        basepath = self._cw.relative_path(includeparams=False)
        while start < rset.rowcount:
            stop = min(start + page_size - 1, rset.rowcount - 1)
            cell = self.format_link_content(index_display(start), index_display(stop))
            blocklist.append(self.page_link(basepath, params, start, stop, cell))
            start = stop + 1
        self.write_links(basepath, params, blocklist)

    def format_link_content(self, startstr, stopstr):
        text = u'%s - %s' % (startstr.lower()[:self.nb_chars],
                             stopstr.lower()[:self.nb_chars])
        return xml_escape(text)

    def write_links(self, basepath, params, blocklist):
        self.w(u'<div class="pagination">')
        self.w(u'%s&#160;' % self.previous_link(basepath, params))
        self.w(u'[&#160;%s&#160;]' % u'&#160;| '.join(blocklist))
        self.w(u'&#160;%s' % self.next_link(basepath, params))
        self.w(u'</div>')


from cubicweb.interfaces import IPrevNext

class IPrevNextAdapter(EntityAdapter):
    """interface for entities which can be linked to a previous and/or next
    entity
    """
    __needs_bw_compat__ = True
    __regid__ = 'IPrevNext'
    __select__ = implements(IPrevNext, warn=False) # XXX for bw compat, else should be abstract

    @implements_adapter_compat('IPrevNext')
    def next_entity(self):
        """return the 'next' entity"""
        raise NotImplementedError

    @implements_adapter_compat('IPrevNext')
    def previous_entity(self):
        """return the 'previous' entity"""
        raise NotImplementedError


class NextPrevNavigationComponent(EntityCtxComponent):
    __regid__ = 'prevnext'
    # register msg not generated since no entity implements IPrevNext in cubicweb
    # itself
    help = _('ctxcomponents_prevnext_description')
    __select__ = EntityCtxComponent.__select__ & adaptable('IPrevNext')
    context = 'navbottom'
    order = 10

    def init_rendering(self):
        adapter = self.entity.cw_adapt_to('IPrevNext')
        self.previous = adapter.previous_entity()
        self.next = adapter.next_entity()
        if not (self.previous or self.next):
            raise EmptyComponent()

    def render_body(self, w):
        w(u'<div class="prevnext">')
        self.prevnext(w)
        w(u'</div>')
        w(u'<div class="clear"></div>')

    def prevnext(self, w):
        if self.previous:
            self.prevnext_entity(w, self.previous, 'prev')
        if self.next:
            self.prevnext_entity(w, self.next, 'next')

    def prevnext_entity(self, w, entity, type):
        textsize = self._cw.property_value('navigation.short-line-size')
        if type == 'prev':
            title = self._cw._('i18nprevnext_previous')
            icon = u'&lt;&lt; '
            cssclass = u'previousEntity left'
        else:
            title = self._cw._('i18nprevnext_next')
            icon = u'&gt;&gt; '
            cssclass = u'nextEntity right'
        self.prevnext_div(w, type, cssclass, entity.absolute_url(),
                          title, icon + xml_escape(cut(entity.dc_title(), textsize)))

    def prevnext_div(self, w, type, cssclass, url, title, content):
        w(u'<div class="%s">' % cssclass)
        w(u'<a href="%s" title="%s">%s</a>' % (xml_escape(url),
                                               xml_escape(title),
                                               content))
        w(u'</div>')
        self._cw.html_headers.add_raw('<link rel="%s" href="%s" />' % (
              type, xml_escape(url)))


def do_paginate(view, rset=None, w=None, show_all_option=True, page_size=None):
    """write pages index in w stream (default to view.w) and then limit the result
    set (default to view.rset) to the currently displayed page
    """
    req = view._cw
    if rset is None:
        rset = view.cw_rset
    if w is None:
        w = view.w
    nav = req.vreg['components'].select_or_none(
        'navigation', req, rset=rset, page_size=page_size, view=view)
    if nav:
        if w is None:
            w = view.w
        # get boundaries before component rendering
        start, stop = nav.page_boundaries()
        nav.render(w=w)
        params = dict(req.form)
        nav.clean_params(params)
        # make a link to see them all
        if show_all_option:
            basepath = req.relative_path(includeparams=False)
            params['__force_display'] = 1
            url = nav.page_url(basepath, params)
            w(u'<div><a href="%s">%s</a></div>\n'
              % (xml_escape(url), req._('show %s results') % len(rset)))
        rset.limit(offset=start, limit=stop-start, inplace=True)


def paginate(view, show_all_option=True, w=None, page_size=None, rset=None):
    """paginate results if the view is paginable and we're not explictly told to
    display everything (by setting __force_display in req.form)
    """
    if view.paginable and not view._cw.form.get('__force_display'):
        do_paginate(view, rset, w, show_all_option, page_size)

# monkey patch base View class to add a .paginate([...])
# method to be called to write pages index in the view and then limit the result
# set to the current page
from cubicweb.view import View
View.do_paginate = do_paginate
View.paginate = paginate


#@deprecated (see below)
def limit_rset_using_paged_nav(self, req, rset, w, forcedisplay=False,
                               show_all_option=True, page_size=None):
    if not (forcedisplay or req.form.get('__force_display') is not None):
        do_paginate(self, rset, w, show_all_option, page_size)

View.pagination = deprecated('[3.2] .pagination is deprecated, use paginate')(
    limit_rset_using_paged_nav)
limit_rset_using_paged_nav = deprecated('[3.6] limit_rset_using_paged_nav is deprecated, use do_paginate')(
    limit_rset_using_paged_nav)
