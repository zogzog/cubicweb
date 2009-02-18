"""navigation components definition for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from rql.nodes import VariableRef, Constant

from logilab.mtconverter import html_escape

from cubicweb.interfaces import IPrevNext
from cubicweb.selectors import (paginated_rset, sorted_rset,
                                primary_view, match_context_prop,
                                one_line_rset, implements)
from cubicweb.common.uilib import cut
from cubicweb.web.component import EntityVComponent, NavigationComponent

_ = unicode


class PageNavigation(NavigationComponent):

    def call(self):
        """displays a resultset by page"""
        w = self.w
        req = self.req
        rset = self.rset
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
        w(u'%s&nbsp;' % self.previous_link(params))
        w(u'[&nbsp;%s&nbsp;]' % u'&nbsp;| '.join(blocklist))
        w(u'&nbsp;%s' % self.next_link(params))
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
        req = self.req
        if attrname is not None:
            def index_display(row):
                entity = rset.get_entity(row, col)
                return entity.printable_value(attrname, format='text/plain')
        elif self.schema.eschema(rset.description[0][col]).is_final():
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
        rset = self.rset
        page_size = self.page_size
        rschema = self.schema.rschema
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
                if not rschema(attrname).is_final():
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
        params = dict(self.req.form)
        self.clean_params(params)
        start = 0
        basepath = self.req.relative_path(includeparams=False)
        while start < rset.rowcount:
            stop = min(start + page_size - 1, rset.rowcount - 1)
            cell = self.format_link_content(index_display(start), index_display(stop))
            blocklist.append(self.page_link(basepath, params, start, stop, cell))
            start = stop + 1
        self.write_links(params, blocklist)

    def format_link_content(self, startstr, stopstr):
        text = u'%s - %s' % (startstr.lower()[:self.nb_chars],
                             stopstr.lower()[:self.nb_chars])
        return html_escape(text)

    def write_links(self, params, blocklist):
        self.w(u'<div class="pagination">')
        self.w(u'%s&nbsp;' % self.previous_link(params))
        self.w(u'[&nbsp;%s&nbsp;]' % u'&nbsp;| '.join(blocklist))
        self.w(u'&nbsp;%s' % self.next_link(params))
        self.w(u'</div>')


def limit_rset_using_paged_nav(self, req, rset, w, forcedisplay=False,
                               show_all_option=True, page_size = None):
    showall = forcedisplay or req.form.get('__force_display') is not None
    nav = not showall and self.vreg.select_component('navigation', req, rset,
                                                     page_size=page_size)
    if nav:
        # get boundaries before component rendering
        start, stop = nav.page_boundaries()
        nav.dispatch(w=w)
        params = dict(req.form)
        nav.clean_params(params)
        # make a link to see them all
        if show_all_option:
            url = html_escape(self.build_url(__force_display=1, **params))
            w(u'<p><a href="%s">%s</a></p>\n'
              % (url, req._('show %s results') % len(rset)))
        rset.limit(offset=start, limit=stop-start, inplace=True)


# monkey patch base View class to add a .pagination(req, rset, w, forcedisplay)
# method to be called on view's result set and printing pages index in the view
from cubicweb.common.view import View
# XXX deprecated, use paginate
View.pagination = limit_rset_using_paged_nav

def paginate(view, show_all_option=True, w=None):
    limit_rset_using_paged_nav(view, view.req, view.rset, w or view.w,
                               not view.need_navigation, show_all_option)
View.paginate = paginate

class NextPrevNavigationComponent(EntityVComponent):
    id = 'prevnext'
    # register msg not generated since no entity implements IPrevNext in cubicweb
    # itself
    title = _('contentnavigation_prevnext')
    help = _('contentnavigation_prevnext_description')
    __select__ = (one_line_rset() & primary_view()
                  & match_context_prop() & implements(IPrevNext))
    context = 'navbottom'
    order = 10
    def call(self, view=None):
        entity = self.entity(0)
        previous = entity.previous_entity()
        next = entity.next_entity()
        if previous or next:
            textsize = self.req.property_value('navigation.short-line-size')
            self.w(u'<div class="prevnext">')
            if previous:
                self.w(u'<div class="previousEntity left">')
                self.w(self.previous_link(previous, textsize))
                self.w(u'</div>')
                self.req.html_headers.add_raw('<link rel="prev" href="%s" />'
                                              % html_escape(previous.absolute_url()))
            if next:
                self.w(u'<div class="nextEntity right">')
                self.w(self.next_link(next, textsize))
                self.w(u'</div>')
                self.req.html_headers.add_raw('<link rel="next" href="%s" />'
                                              % html_escape(next.absolute_url()))
            self.w(u'</div>')
            self.w(u'<div class="clear"></div>')

    def previous_link(self, previous, textsize):
        return u'<a href="%s" title="%s">&lt;&lt; %s</a>' % (
            html_escape(previous.absolute_url()),
            self.req._('i18nprevnext_previous'),
            html_escape(cut(previous.dc_title(), textsize)))
    
    def next_link(self, next, textsize):
        return u'<a href="%s" title="%s">%s &gt;&gt;</a>' % (
            html_escape(next.absolute_url()),
            self.req._('i18nprevnext_next'),
            html_escape(cut(next.dc_title(), textsize)))
