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
"""This module provides some generic components to navigate in the web
application.

Pagination
----------

Several implementations for large result set pagination are provided:

.. autoclass:: PageNavigation
.. autoclass:: PageNavigationSelect
.. autoclass:: SortedNavigation

Pagination will appear when needed according to the `page-size` ui property.

This module monkey-patch the :func:`paginate` function to the base :class:`View`
class, so that you can ask pagination explicitly on every result-set based views.

.. autofunction:: paginate


Previous / next navigation
--------------------------

An adapter and its related component for the somewhat usal "previous / next"
navigation are provided.

  .. autoclass:: IPrevNextAdapter
  .. autoclass:: NextPrevNavigationComponent
"""


from cubicweb import _

from datetime import datetime

from six import text_type

from rql.nodes import VariableRef, Constant

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

from cubicweb.predicates import paginated_rset, sorted_rset, adaptable
from cubicweb.uilib import cut
from cubicweb.view import EntityAdapter
from cubicweb.web.component import EmptyComponent, EntityCtxComponent, NavigationComponent


class PageNavigation(NavigationComponent):
    """The default pagination component: display link to pages where each pages
    is identified by the item number of its first and last elements.
    """
    def call(self):
        """displays a resultset by page"""
        params = dict(self._cw.form)
        self.clean_params(params)
        basepath = self._cw.relative_path(includeparams=False)
        self.w(u'<div class="pagination">')
        self.w(self.previous_link(basepath, params))
        self.w(u'[&#160;%s&#160;]' %
               u'&#160;| '.join(self.iter_page_links(basepath, params)))
        self.w(u'&#160;&#160;%s' % self.next_link(basepath, params))
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
    """This pagination component displays a result-set by page as
    :class:`PageNavigation` but in a <select>, which is better when there are a
    lot of results.

    By default it will be selected when there are more than 4 pages to be
    displayed.
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
        w(self.previous_link(basepath, params))
        w(u'<select onchange="javascript: document.location=this.options[this.selectedIndex].value">')
        for option in self.iter_page_links(basepath, params):
            w(option)
        w(u'</select>')
        w(u'&#160;&#160;%s' % self.next_link(basepath, params))
        w(u'</div>')


class SortedNavigation(NavigationComponent):
    """This pagination component will be selected by default if there are less
    than 4 pages and if the result set is sorted.

    Displayed links to navigate accross pages of a result set are done according
    to the first variable on which the sort is done, and looks like:

        [ana - cro] | [cro - ghe] | ... | [tim - zou]

    You may want to override this component to customize display in some cases.

    .. automethod:: sort_on
    .. automethod:: display_func
    .. automethod:: format_link_content
    .. automethod:: write_links

    Below an example from the tracker cube:

    .. sourcecode:: python

      class TicketsNavigation(navigation.SortedNavigation):
          __select__ = (navigation.SortedNavigation.__select__
                        & ~paginated_rset(4) & is_instance('Ticket'))
          def sort_on(self):
              col, attrname = super(TicketsNavigation, self).sort_on()
              if col == 6:
                  # sort on state, we don't want that
                  return None, None
              return col, attrname

    The idea is that in trackers'ticket tables, result set is first ordered on
    ticket's state while this doesn't make any sense in the navigation. So we
    override :meth:`sort_on` so that if we detect such sorting, we disable the
    feature to go back to item number in the pagination.

    Also notice the `~paginated_rset(4)` in the selector so that if there are
    more than 4 pages to display, :class:`PageNavigationSelect` will still be
    selected.
    """
    __select__ = paginated_rset() & sorted_rset()

    # number of considered chars to build page links
    nb_chars = 5

    def call(self):
        # attrname = the name of attribute according to which the sort
        # is done if any
        col, attrname = self.sort_on()
        index_display = self.display_func(self.cw_rset, col, attrname)
        basepath = self._cw.relative_path(includeparams=False)
        params = dict(self._cw.form)
        self.clean_params(params)
        blocklist = []
        start = 0
        total = self.cw_rset.rowcount
        while start < total:
            stop = min(start + self.page_size - 1, total - 1)
            cell = self.format_link_content(index_display(start), index_display(stop))
            blocklist.append(self.page_link(basepath, params, start, stop, cell))
            start = stop + 1
        self.write_links(basepath, params, blocklist)

    def display_func(self, rset, col, attrname):
        """Return a function that will be called with a row number as argument
        and should return a string to use as link for it.
        """
        if attrname is not None:
            def index_display(row):
                if not rset[row][col]: # outer join
                    return u''
                entity = rset.get_entity(row, col)
                return entity.printable_value(attrname, format='text/plain')
        elif col is None: # smart links disabled.
            def index_display(row):
                return text_type(row)
        elif self._cw.vreg.schema.eschema(rset.description[0][col]).final:
            def index_display(row):
                return text_type(rset[row][col])
        else:
            def index_display(row):
                return rset.get_entity(row, col).view('text')
        return index_display

    def sort_on(self):
        """Return entity column number / attr name to use for nice display by
        inspecting the rset'syntax tree.
        """
        rschema = self._cw.vreg.schema.rschema
        for sorterm in self.cw_rset.syntax_tree().children[0].orderby:
            if isinstance(sorterm.term, Constant):
                col = sorterm.term.value - 1
                return col, None
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
                # if column type is date[time], set proper 'nb_chars'
                if var.stinfo['possibletypes'] & frozenset(('TZDatetime', 'Datetime',
                                                            'Date')):
                    self.nb_chars = len(self._cw.format_date(datetime.today()))
                return col, attrname
        # nothing usable found, use the first column
        return 0, None

    def format_link_content(self, startstr, stopstr):
        """Return text for a page link, where `startstr` and `stopstr` are the
        text for the lower/upper boundaries of the page.

        By default text are stripped down to :attr:`nb_chars` characters.
        """
        text = u'%s - %s' % (startstr.lower()[:self.nb_chars],
                             stopstr.lower()[:self.nb_chars])
        return xml_escape(text)

    def write_links(self, basepath, params, blocklist):
        """Return HTML for the whole navigation: `blocklist` is a list of HTML
        snippets for each page, `basepath` and `params` will be necessary to
        build previous/next links.
        """
        self.w(u'<div class="pagination">')
        self.w(u'%s&#160;' % self.previous_link(basepath, params))
        self.w(u'[&#160;%s&#160;]' % u'&#160;| '.join(blocklist))
        self.w(u'&#160;%s' % self.next_link(basepath, params))
        self.w(u'</div>')


def do_paginate(view, rset=None, w=None, show_all_option=True, page_size=None):
    """write pages index in w stream (default to view.w) and then limit the
    result set (default to view.rset) to the currently displayed page if we're
    not explicitly told to display everything (by setting __force_display in
    req.form)
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
        if req.form.get('__force_display'):
            nav.render_link_back_to_pagination(w=w)
        else:
            # get boundaries before component rendering
            start, stop = nav.page_boundaries()
            nav.render(w=w)
            if show_all_option:
                nav.render_link_display_all(w=w)
            rset.limit(offset=start, limit=stop-start, inplace=True)


def paginate(view, show_all_option=True, w=None, page_size=None, rset=None):
    """paginate results if the view is paginable
    """
    if view.paginable:
        do_paginate(view, rset, w, show_all_option, page_size)

# monkey patch base View class to add a .paginate([...])
# method to be called to write pages index in the view and then limit the result
# set to the current page
from cubicweb.view import View
View.do_paginate = do_paginate
View.paginate = paginate
View.handle_pagination = False



class IPrevNextAdapter(EntityAdapter):
    """Interface for entities which can be linked to a previous and/or next
    entity

    .. automethod:: next_entity
    .. automethod:: previous_entity
    """
    __needs_bw_compat__ = True
    __regid__ = 'IPrevNext'
    __abstract__ = True

    def next_entity(self):
        """return the 'next' entity"""
        raise NotImplementedError

    def previous_entity(self):
        """return the 'previous' entity"""
        raise NotImplementedError


class NextPrevNavigationComponent(EntityCtxComponent):
    """Entities adaptable to the 'IPrevNext' should have this component
    automatically displayed. You may want to override this component to have a
    different look and feel.
    """

    __regid__ = 'prevnext'
    # register msg not generated since no entity implements IPrevNext in cubicweb
    # itself
    help = _('ctxcomponents_prevnext_description')
    __select__ = EntityCtxComponent.__select__ & adaptable('IPrevNext')
    context = 'navbottom'
    order = 10

    @property
    def prev_icon(self):
        return '<img src="%s" alt="%s" />' % (
            xml_escape(self._cw.data_url('go_prev.png')), self._cw._('previous page'))

    @property
    def next_icon(self):
        return '<img src="%s" alt="%s" />' % (
            xml_escape(self._cw.data_url('go_next.png')), self._cw._('next page'))

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
        content = xml_escape(cut(entity.dc_title(), textsize))
        if type == 'prev':
            title = self._cw._('i18nprevnext_previous')
            icon = self.prev_icon
            cssclass = u'previousEntity left'
            content = icon + '&#160;&#160;' + content
        else:
            title = self._cw._('i18nprevnext_next')
            icon = self.next_icon
            cssclass = u'nextEntity right'
            content = content + '&#160;&#160;' + icon
        self.prevnext_div(w, type, cssclass, entity.absolute_url(),
                          title, content)

    def prevnext_div(self, w, type, cssclass, url, title, content):
        w(u'<div class="%s">' % cssclass)
        w(u'<a href="%s" title="%s">%s</a>' % (xml_escape(url),
                                               xml_escape(title),
                                               content))
        w(u'</div>')
        self._cw.html_headers.add_raw('<link rel="%s" href="%s" />' % (
              type, xml_escape(url)))
