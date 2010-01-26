"""navigation components definition for CubicWeb web client

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from rql.nodes import VariableRef, Constant

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

from cubicweb.interfaces import IPrevNext
from cubicweb.selectors import (paginated_rset, sorted_rset,
                                primary_view, match_context_prop,
                                one_line_rset, implements)
from cubicweb.uilib import cut
from cubicweb.web.component import EntityVComponent, NavigationComponent


class PageNavigation(NavigationComponent):

    def call(self):
        """displays a resultset by page"""
        w = self.w
        req = self._cw
        rset = self.cw_rset
        page_size = self.page_size
        start = 0
        blocklist = []
        params = dict(req.form)
        self.clean_params(params)
        basepath = req.relative_path(includeparams=False)
        while start < rset.rowcount:
            stop = min(start + page_size - 1, rset.rowcount - 1)
            blocklist.append(self.page_link(basepath, params, start, stop,
                                            self.index_display(start, stop)))
            start = stop + 1
        w(u'<div class="pagination">')
        w(u'%s&#160;' % self.previous_link(basepath, params))
        w(u'[&#160;%s&#160;]' % u'&#160;| '.join(blocklist))
        w(u'&#160;%s' % self.next_link(basepath, params))
        w(u'</div>')

    def index_display(self, start, stop):
        return u'%s - %s' % (start+1, stop+1)


class SortedNavigation(NavigationComponent):
    """sorted navigation apply if navigation is needed (according to page size)
    and if the result set is sorted
    """
    __select__ = paginated_rset() & sorted_rset()

    # number of considered chars to build page links
    nb_chars = 5

    def display_func(self, rset, col, attrname):
        req = self._cw
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
                if attrname == 'is':
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


class NextPrevNavigationComponent(EntityVComponent):
    __regid__ = 'prevnext'
    # register msg not generated since no entity implements IPrevNext in cubicweb
    # itself
    title = _('contentnavigation_prevnext')
    help = _('contentnavigation_prevnext_description')
    __select__ = (one_line_rset() & primary_view()
                  & match_context_prop() & implements(IPrevNext))
    context = 'navbottom'
    order = 10
    def call(self, view=None):
        entity = self.cw_rset.get_entity(0,0)
        previous = entity.previous_entity()
        next = entity.next_entity()
        if previous or next:
            textsize = self._cw.property_value('navigation.short-line-size')
            self.w(u'<div class="prevnext">')
            if previous:
                self.w(u'<div class="previousEntity left">')
                self.w(self.previous_link(previous, textsize))
                self.w(u'</div>')
                self._cw.html_headers.add_raw('<link rel="prev" href="%s" />'
                                              % xml_escape(previous.absolute_url()))
            if next:
                self.w(u'<div class="nextEntity right">')
                self.w(self.next_link(next, textsize))
                self.w(u'</div>')
                self._cw.html_headers.add_raw('<link rel="next" href="%s" />'
                                              % xml_escape(next.absolute_url()))
            self.w(u'</div>')
            self.w(u'<div class="clear"></div>')

    def previous_link(self, previous, textsize):
        return u'<a href="%s" title="%s">&lt;&lt; %s</a>' % (
            xml_escape(previous.absolute_url()),
            self._cw._('i18nprevnext_previous'),
            xml_escape(cut(previous.dc_title(), textsize)))

    def next_link(self, next, textsize):
        return u'<a href="%s" title="%s">%s &gt;&gt;</a>' % (
            xml_escape(next.absolute_url()),
            self._cw._('i18nprevnext_next'),
            xml_escape(cut(next.dc_title(), textsize)))


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
        'navigation', req, rset=rset, page_size=page_size)
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
            url = xml_escape(req.build_url(__force_display=1, **params))
            w(u'<span><a href="%s">%s</a></span>\n'
              % (url, req._('show %s results') % len(rset)))
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
