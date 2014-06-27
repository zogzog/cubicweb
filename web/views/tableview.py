# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""This module contains table views, with the following features that may be
provided (depending on the used implementation):

* facets filtering
* pagination
* actions menu
* properly sortable content
* odd/row/hover line styles

The three main implementation are described below. Each implementation is
suitable for a particular case, but they each attempt to display tables that
looks similar.

.. autoclass:: cubicweb.web.views.tableview.RsetTableView
   :members:

.. autoclass:: cubicweb.web.views.tableview.EntityTableView
   :members:

.. autoclass:: cubicweb.web.views.pyviews.PyValTableView
   :members:

All those classes are rendered using a *layout*:

.. autoclass:: cubicweb.web.views.tableview.TableLayout
   :members:

There is by default only on table layout, using the 'table_layout' identifier,
that is referenced by table views
:attr:`cubicweb.web.views.tableview.TableMixIn.layout_id`.  If you want to
customize the look and feel of your table, you can either replace the default
one by yours, having multiple variants with proper selectors, or change the
`layout_id` identifier of your table to use your table specific implementation.

Notice you can gives options to the layout using a `layout_args` dictionary on
your class.

If you can still find a view that suit your needs, you should take a look at the
class below that is the common abstract base class for the three views defined
above and implements you own class.

.. autoclass:: cubicweb.web.views.tableview.TableMixIn
   :members:
"""

__docformat__ = "restructuredtext en"
_ = unicode

from warnings import warn
from copy import copy
from types import MethodType

from logilab.mtconverter import xml_escape
from logilab.common.decorators import cachedproperty
from logilab.common.deprecation import class_deprecated
from logilab.common.registry import yes

from cubicweb import NoSelectableObject, tags
from cubicweb.predicates import nonempty_rset, match_kwargs, objectify_predicate
from cubicweb.schema import display_name
from cubicweb.utils import make_uid, js_dumps, JSString, UStringIO
from cubicweb.uilib import toggle_action, limitsize, htmlescape, sgml_attributes, domid
from cubicweb.view import EntityView, AnyRsetView
from cubicweb.web import jsonize, component
from cubicweb.web.htmlwidgets import (TableWidget, TableColumn, MenuWidget,
                                      PopupBoxMenu)


@objectify_predicate
def unreloadable_table(cls, req, rset=None,
                       displaycols=None, headers=None, cellvids=None,
                       paginate=False, displayactions=False, displayfilter=False,
                       **kwargs):
    # one may wish to specify one of headers/displaycols/cellvids as long as he
    # doesn't want pagination nor actions nor facets
    if not kwargs and (displaycols or headers or cellvids) and not (
        displayfilter or displayactions or paginate):
        return 1
    return 0


class TableLayout(component.Component):
    """The default layout for table. When `render` is called, this will use
    the API described on :class:`TableMixIn` to feed the generated table.

    This layout behaviour may be customized using the following attributes /
    selection arguments:

    * `cssclass`, a string that should be used as HTML class attribute. Default
      to "listing".

    * `needs_css`, the CSS files that should be used together with this
      table. Default to ('cubicweb.tablesorter.css', 'cubicweb.tableview.css').

    * `needs_js`, the Javascript files that should be used together with this
      table. Default to ('jquery.tablesorter.js',)

    * `display_filter`, tells if the facets filter should be displayed when
      possible. Allowed values are:
      - `None`, don't display it
      - 'top', display it above the table
      - 'bottom', display it below the table

    * `display_actions`, tells if a menu for available actions should be
      displayed when possible (see two following options). Allowed values are:
      - `None`, don't display it
      - 'top', display it above the table
      - 'bottom', display it below the table

    * `hide_filter`, when true (the default), facets filter will be hidden by
      default, with an action in the actions menu allowing to show / hide it.

    * `show_all_option`, when true, a *show all results* link will be displayed
      below the navigation component.

    * `add_view_actions`, when true, actions returned by view.table_actions()
      will be included in the actions menu.

    * `header_column_idx`, if not `None`, should be a colum index or a set of
      column index where <th> tags should be generated instead of <td>
    """ #'# make emacs happier
    __regid__ = 'table_layout'
    cssclass = "listing"
    needs_css = ('cubicweb.tableview.css',)
    needs_js = ()
    display_filter = None    # None / 'top' / 'bottom'
    display_actions = 'top'  # None / 'top' / 'bottom'
    hide_filter = True
    show_all_option = True   # make navcomp generate a 'show all' results link
    add_view_actions = False
    header_column_idx = None
    enable_sorting = True
    sortvalue_limit = 10
    tablesorter_settings = {
        'textExtraction': JSString('cw.sortValueExtraction'),
        'selectorHeaders': "thead tr:first th[class='sortable']", # only plug on the first row
        }

    def _setup_tablesorter(self, divid):
        self._cw.add_css('cubicweb.tablesorter.css')
        self._cw.add_js('jquery.tablesorter.js')
        self._cw.add_onload('''$(document).ready(function() {
    $("#%s table").tablesorter(%s);
});''' % (divid, js_dumps(self.tablesorter_settings)))

    def __init__(self, req, view, **kwargs):
        super(TableLayout, self).__init__(req, **kwargs)
        for key, val in self.cw_extra_kwargs.items():
            if hasattr(self.__class__, key) and not key[0] == '_':
                setattr(self, key, val)
                self.cw_extra_kwargs.pop(key)
        self.view = view
        if self.header_column_idx is None:
            self.header_column_idx = frozenset()
        elif isinstance(self.header_column_idx, int):
            self.header_column_idx = frozenset( (self.header_column_idx,) )

    @cachedproperty
    def initial_load(self):
        """We detect a bit heuristically if we are built for the first time or
        from subsequent calls by the form filter or by the pagination hooks.
        """
        form = self._cw.form
        return 'fromformfilter' not in form and '__fromnavigation' not in form

    def render(self, w, **kwargs):
        assert self.display_filter in (None, 'top', 'bottom'), self.display_filter
        if self.needs_css:
            self._cw.add_css(self.needs_css)
        if self.needs_js:
            self._cw.add_js(self.needs_js)
        if self.enable_sorting:
            self._setup_tablesorter(self.view.domid)
        # Notice facets form must be rendered **outside** the main div as it
        # shouldn't be rendered on ajax call subsequent to facet restriction
        # (hence the 'fromformfilter' parameter added by the form
        generate_form = self.initial_load
        if self.display_filter and generate_form:
            facetsform = self.view.facets_form()
        else:
            facetsform = None
        if facetsform and self.display_filter == 'top':
            cssclass = u'hidden' if self.hide_filter else u''
            facetsform.render(w, vid=self.view.__regid__, cssclass=cssclass,
                              divid=self.view.domid)
        actions = []
        if self.display_actions:
            if self.add_view_actions:
                actions = self.view.table_actions()
            if self.display_filter and self.hide_filter and (facetsform or not generate_form):
                actions += self.show_hide_filter_actions(not generate_form)
        self.render_table(w, actions, self.view.paginable)
        if facetsform and self.display_filter == 'bottom':
            cssclass = u'hidden' if self.hide_filter else u''
            facetsform.render(w, vid=self.view.__regid__, cssclass=cssclass,
                              divid=self.view.domid)

    def render_table_headers(self, w, colrenderers):
        w(u'<thead><tr>')
        for colrenderer in colrenderers:
            if colrenderer.sortable:
                w(u'<th class="sortable">')
            else:
                w(u'<th>')
            colrenderer.render_header(w)
            w(u'</th>')
        w(u'</tr></thead>\n')

    def render_table_body(self, w, colrenderers):
        w(u'<tbody>')
        for rownum in xrange(self.view.table_size):
            self.render_row(w, rownum, colrenderers)
        w(u'</tbody>')

    def render_table(self, w, actions, paginate):
        view = self.view
        divid = view.domid
        if divid is not None:
            w(u'<div id="%s">' % divid)
        else:
            assert not (actions or paginate)
        nav_html = UStringIO()
        if paginate:
            view.paginate(w=nav_html.write, show_all_option=self.show_all_option)
        w(nav_html.getvalue())
        if actions and self.display_actions == 'top':
            self.render_actions(w, actions)
        colrenderers = view.build_column_renderers()
        attrs = self.table_attributes()
        w(u'<table %s>' % sgml_attributes(attrs))
        if self.view.has_headers:
            self.render_table_headers(w, colrenderers)
        self.render_table_body(w, colrenderers)
        w(u'</table>')
        if actions and self.display_actions == 'bottom':
            self.render_actions(w, actions)
        w(nav_html.getvalue())
        if divid is not None:
            w(u'</div>')

    def table_attributes(self):
        return {'class': self.cssclass}

    def render_row(self, w, rownum, renderers):
        attrs = self.row_attributes(rownum)
        w(u'<tr %s>' % sgml_attributes(attrs))
        for colnum, renderer in enumerate(renderers):
            self.render_cell(w, rownum, colnum, renderer)
        w(u'</tr>\n')

    def row_attributes(self, rownum):
        return {'class': 'odd' if (rownum%2==1) else 'even',
                'onmouseover': '$(this).addClass("highlighted");',
                'onmouseout': '$(this).removeClass("highlighted")'}

    def render_cell(self, w, rownum, colnum, renderer):
        attrs = self.cell_attributes(rownum, colnum, renderer)
        if colnum in self.header_column_idx:
            tag = u'th'
        else:
            tag = u'td'
        w(u'<%s %s>' % (tag, sgml_attributes(attrs)))
        renderer.render_cell(w, rownum)
        w(u'</%s>' % tag)

    def cell_attributes(self, rownum, _colnum, renderer):
        attrs = renderer.attributes.copy()
        if renderer.sortable:
            sortvalue = renderer.sortvalue(rownum)
            if isinstance(sortvalue, basestring):
                sortvalue = sortvalue[:self.sortvalue_limit]
            if sortvalue is not None:
                attrs[u'cubicweb:sortvalue'] = js_dumps(sortvalue)
        return attrs

    def render_actions(self, w, actions):
        box = MenuWidget('', '', _class='tableActionsBox', islist=False)
        label = tags.span(self._cw._('action menu'))
        menu = PopupBoxMenu(label, isitem=False, link_class='actionsBox',
                            ident='%sActions' % self.view.domid)
        box.append(menu)
        for action in actions:
            menu.append(action)
        box.render(w=w)
        w(u'<div class="clear"></div>')

    def show_hide_filter_actions(self, currentlydisplayed=False):
        divid = self.view.domid
        showhide = u';'.join(toggle_action('%s%s' % (divid, what))[11:]
                             for what in ('Form', 'Show', 'Hide', 'Actions'))
        showhide = 'javascript:' + showhide
        self._cw.add_onload(u'''\
$(document).ready(function() {
  if ($('#%(id)sForm[class=\"hidden\"]').length) {
    $('#%(id)sHide').attr('class', 'hidden');
  } else {
    $('#%(id)sShow').attr('class', 'hidden');
  }
});''' % {'id': divid})
        showlabel = self._cw._('show filter form')
        hidelabel = self._cw._('hide filter form')
        return [component.Link(showhide, showlabel, id='%sShow' % divid),
                component.Link(showhide, hidelabel, id='%sHide' % divid)]


class AbstractColumnRenderer(object):
    """Abstract base class for column renderer. Interface of a column renderer follows:

    .. automethod:: cubicweb.web.views.tableview.AbstractColumnRenderer.bind
    .. automethod:: cubicweb.web.views.tableview.AbstractColumnRenderer.render_header
    .. automethod:: cubicweb.web.views.tableview.AbstractColumnRenderer.render_cell
    .. automethod:: cubicweb.web.views.tableview.AbstractColumnRenderer.sortvalue

    Attributes on this base class are:

    :attr: `header`, the column header. If None, default to `_(colid)`
    :attr: `addcount`, if True, add the table size in parenthezis beside the header
    :attr: `trheader`, should the header be translated
    :attr: `escapeheader`, should the header be xml_escaped
    :attr: `sortable`, tell if the column is sortable
    :attr: `view`, the table view
    :attr: `_cw`, the request object
    :attr: `colid`, the column identifier
    :attr: `attributes`, dictionary of attributes to put on the HTML tag when
            the cell is rendered
    """ #'# make emacs
    attributes = {}
    empty_cell_content = u'&#160;'

    def __init__(self, header=None, addcount=False, trheader=True,
                 escapeheader=True, sortable=True):
        self.header = header
        self.trheader = trheader
        self.escapeheader = escapeheader
        self.addcount = addcount
        self.sortable = sortable
        self.view = None
        self._cw = None
        self.colid = None

    def __str__(self):
        return '<%s.%s (column %s) at 0x%x>' % (self.view.__class__.__name__,
                                        self.__class__.__name__,
                                        self.colid, id(self))

    def bind(self, view, colid):
        """Bind the column renderer to its view. This is where `_cw`, `view`,
        `colid` are set and the method to override if you want to add more
        view/request depending attributes on your column render.
        """
        self.view = view
        self._cw = view._cw
        self.colid = colid

    def copy(self):
        assert self.view is None
        return copy(self)

    def default_header(self):
        """Return header for this column if one has not been specified."""
        return self._cw._(self.colid)

    def render_header(self, w):
        """Write label for the specified column by calling w()."""
        header = self.header
        if header is None:
            header = self.default_header()
        elif self.trheader and header:
           header = self._cw._(header)
        if self.addcount:
            header = '%s (%s)' % (header, self.view.table_size)
        if header:
            if self.escapeheader:
                header = xml_escape(header)
        else:
            header = self.empty_cell_content
        if self.sortable:
            header = tags.span(
                header, escapecontent=False,
                title=self._cw._('Click to sort on this column'))
        w(header)

    def render_cell(self, w, rownum):
        """Write value for the specified cell by calling w().

         :param `rownum`: the row number in the table
         """
        raise NotImplementedError()

    def sortvalue(self, _rownum):
        """Return typed value to be used for sorting on the specified column.

        :param `rownum`: the row number in the table
        """
        return None


class TableMixIn(component.LayoutableMixIn):
    """Abstract mix-in class for layout based tables.

    This default implementation's call method simply delegate to
    meth:`layout_render` that will select the renderer whose identifier is given
    by the :attr:`layout_id` attribute.

    Then it provides some default implementation for various parts of the API
    used by that layout.

    Abstract method you will have to override is:

    .. automethod:: build_column_renderers

    You may also want to overridde:

    .. autoattribute:: cubicweb.web.views.tableview.TableMixIn.table_size

    The :attr:`has_headers` boolean attribute tells if the table has some
    headers to be displayed. Default to `True`.
    """
    __abstract__ = True
    # table layout to use
    layout_id = 'table_layout'
    # true if the table has some headers
    has_headers = True
    # dictionary {colid : column renderer}
    column_renderers = {}
    # default renderer class to use when no renderer specified for the column
    default_column_renderer_class = None
    # default layout handles inner pagination
    handle_pagination = True

    def call(self, **kwargs):
        self._cw.add_js('cubicweb.ajax.js') # for pagination
        self.layout_render(self.w)

    def column_renderer(self, colid, *args, **kwargs):
        """Return a column renderer for column of the given id."""
        try:
            crenderer = self.column_renderers[colid].copy()
        except KeyError:
            crenderer = self.default_column_renderer_class(*args, **kwargs)
        crenderer.bind(self, colid)
        return crenderer

    # layout callbacks #########################################################

    def facets_form(self, **kwargs):# XXX extracted from jqplot cube
        return self._cw.vreg['views'].select_or_none(
            'facet.filtertable', self._cw, rset=self.cw_rset, view=self,
            **kwargs)

    @cachedproperty
    def domid(self):
        return self._cw.form.get('divid') or domid('%s-%s' % (self.__regid__, make_uid()))

    @property
    def table_size(self):
        """Return the number of rows (header excluded) to be displayed.

        By default return the number of rows in the view's result set. If your
        table isn't reult set based, override this method.
        """
        return self.cw_rset.rowcount

    def build_column_renderers(self):
        """Return a list of column renderers, one for each column to be
        rendered. Prototype of a column renderer is described below:

        .. autoclass:: cubicweb.web.views.tableview.AbstractColumnRenderer
        """
        raise NotImplementedError()

    def table_actions(self):
        """Return a list of actions (:class:`~cubicweb.web.component.Link`) that
        match the view's result set, and return those in the 'mainactions'
        category.
        """
        req = self._cw
        actions = []
        actionsbycat = req.vreg['actions'].possible_actions(req, self.cw_rset)
        for action in actionsbycat.get('mainactions', ()):
            for action in action.actual_actions():
                actions.append(component.Link(action.url(), req._(action.title),
                                              klass=action.html_class()) )
        return actions

    # interaction with navigation component ####################################

    def page_navigation_url(self, navcomp, _path, params):
        params['divid'] = self.domid
        params['vid'] = self.__regid__
        return navcomp.ajax_page_url(**params)


class RsetTableColRenderer(AbstractColumnRenderer):
    """Default renderer for :class:`RsetTableView`."""

    def __init__(self, cellvid, **kwargs):
        super(RsetTableColRenderer, self).__init__(**kwargs)
        self.cellvid = cellvid

    def bind(self, view, colid):
        super(RsetTableColRenderer, self).bind(view, colid)
        self.cw_rset = view.cw_rset
    def render_cell(self, w, rownum):
        self._cw.view(self.cellvid, self.cw_rset, 'empty-cell',
                      row=rownum, col=self.colid, w=w)

    # limit value's length as much as possible (e.g. by returning the 10 first
    # characters of a string)
    def sortvalue(self, rownum):
        colid = self.colid
        val = self.cw_rset[rownum][colid]
        if val is None:
            return u''
        etype = self.cw_rset.description[rownum][colid]
        if etype is None:
            return u''
        if self._cw.vreg.schema.eschema(etype).final:
            entity, rtype = self.cw_rset.related_entity(rownum, colid)
            if entity is None:
                return val # remove_html_tags() ?
            return entity.sortvalue(rtype)
        entity = self.cw_rset.get_entity(rownum, colid)
        return entity.sortvalue()


class RsetTableView(TableMixIn, AnyRsetView):
    """This table view accepts any non-empty rset. It uses introspection on the
    result set to compute column names and the proper way to display the cells.

    It is highly configurable and accepts a wealth of options, but take care to
    check what you're trying to achieve wouldn't be a job for the
    :class:`EntityTableView`. Basically the question is: does this view should
    be tied to the result set query's shape or no? If yes, than you're fine. If
    no, you should take a look at the other table implementation.

    The following class attributes may be used to control the table:

    * `finalvid`, a view identifier that should be called on final entities
      (e.g. attribute values). Default to 'final'.

    * `nonfinalvid`, a view identifier that should be called on
      entities. Default to 'incontext'.

    * `displaycols`, if not `None`, should be a list of rset's columns to be
      displayed.

    * `headers`, if not `None`, should be a list of headers for the table's
      columns.  `None` values in the list will be replaced by computed column
      names.

    * `cellvids`, if not `None`, should be a dictionary with table column index
      as key and a view identifier as value, telling the view that should be
      used in the given column.

    Notice `displaycols`, `headers` and `cellvids` may be specified at selection
    time but then the table won't have pagination and shouldn't be configured to
    display the facets filter nor actions (as they wouldn't behave as expected).

    This table class use the :class:`RsetTableColRenderer` as default column
    renderer.

    .. autoclass:: RsetTableColRenderer
    """    #'# make emacs happier
    __regid__ = 'table'
    # selector trick for bw compath with the former :class:TableView
    __select__ = AnyRsetView.__select__ & (~match_kwargs(
        'title', 'subvid', 'displayfilter', 'headers', 'displaycols',
        'displayactions', 'actions', 'divid', 'cellvids', 'cellattrs',
        'mainindex', 'paginate', 'page_size', mode='any')
                                            | unreloadable_table())
    title = _('table')
    # additional configuration parameters
    finalvid = 'final'
    nonfinalvid = 'incontext'
    displaycols = None
    headers = None
    cellvids = None
    default_column_renderer_class = RsetTableColRenderer

    def linkable(self):
        # specific subclasses of this view usually don't want to be linkable
        # since they depends on a particular shape (being linkable meaning view
        # may be listed in possible views
        return self.__regid__ == 'table'

    def call(self, headers=None, displaycols=None, cellvids=None,
             paginate=None, **kwargs):
        if self.headers:
            self.headers = [h and self._cw._(h) for h in self.headers]
        if (headers or displaycols or cellvids or paginate):
            if headers is not None:
                self.headers = headers
            if displaycols is not None:
                self.displaycols = displaycols
            if cellvids is not None:
                self.cellvids = cellvids
            if paginate is not None:
                self.paginable = paginate
        if kwargs:
            # old table view arguments that we can safely ignore thanks to
            # selectors
            if len(kwargs) > 1:
                msg = '[3.14] %s arguments are deprecated' % ', '.join(kwargs)
            else:
                msg = '[3.14] %s argument is deprecated' % ', '.join(kwargs)
            warn(msg, DeprecationWarning, stacklevel=2)
        super(RsetTableView, self).call(**kwargs)

    def main_var_index(self):
        """returns the index of the first non-attribute variable among the RQL
        selected variables
        """
        eschema = self._cw.vreg.schema.eschema
        for i, etype in enumerate(self.cw_rset.description[0]):
            if not eschema(etype).final:
                return i
        return None

    # layout callbacks #########################################################

    @property
    def table_size(self):
        """return the number of rows (header excluded) to be displayed"""
        return self.cw_rset.rowcount

    def build_column_renderers(self):
        headers = self.headers
        # compute displayed columns
        if self.displaycols is None:
            if headers is not None:
                displaycols = range(len(headers))
            else:
                rqlst = self.cw_rset.syntax_tree()
                displaycols = range(len(rqlst.children[0].selection))
        else:
            displaycols = self.displaycols
        # compute table headers
        main_var_index = self.main_var_index()
        computed_titles = self.columns_labels(main_var_index)
        # compute build renderers
        cellvids = self.cellvids
        renderers = []
        for colnum, colid in enumerate(displaycols):
            addcount = False
            # compute column header
            title = None
            if headers is not None:
                title = headers[colnum]
            if title is None:
                title = computed_titles[colid]
            if colid == main_var_index:
                addcount = True
            # compute cell vid for the column
            if cellvids is not None and colnum in cellvids:
                cellvid = cellvids[colnum]
            else:
                coltype = self.cw_rset.description[0][colid]
                if coltype is not None and self._cw.vreg.schema.eschema(coltype).final:
                    cellvid = self.finalvid
                else:
                    cellvid = self.nonfinalvid
            # get renderer
            renderer = self.column_renderer(colid, header=title, trheader=False,
                                            addcount=addcount, cellvid=cellvid)
            renderers.append(renderer)
        return renderers


class EntityTableColRenderer(AbstractColumnRenderer):
    """Default column renderer for :class:`EntityTableView`.

    You may use the :meth:`entity` method to retrieve the main entity for a
    given row number.

    .. automethod:: cubicweb.web.views.tableview.EntityTableColRenderer.entity
    .. automethod:: cubicweb.web.views.tableview.EntityTableColRenderer.render_entity
    .. automethod:: cubicweb.web.views.tableview.EntityTableColRenderer.entity_sortvalue
    """
    def __init__(self, renderfunc=None, sortfunc=None, sortable=None, **kwargs):
        if renderfunc is None:
            renderfunc = self.render_entity
            # if renderfunc nor sortfunc nor sortable specified, column will be
            # sortable using the default implementation.
            if sortable is None:
                sortable = True
        # no sortfunc given but asked to be sortable: use the default sort
        # method. Sub-class may set `entity_sortvalue` to None if they don't
        # support sorting.
        if sortfunc is None and sortable:
            sortfunc = self.entity_sortvalue
        # at this point `sortable` may still be unspecified while `sortfunc` is
        # sure to be set to someting else than None if the column is sortable.
        sortable = sortfunc is not None
        super(EntityTableColRenderer, self).__init__(sortable=sortable, **kwargs)
        self.renderfunc = renderfunc
        self.sortfunc = sortfunc

    def copy(self):
        assert self.view is None
        # copy of attribute referencing a method doesn't work with python < 2.7
        renderfunc = self.__dict__.pop('renderfunc')
        sortfunc = self.__dict__.pop('sortfunc')
        try:
            acopy =  copy(self)
            for aname, member in[('renderfunc', renderfunc),
                                 ('sortfunc', sortfunc)]:
                if isinstance(member, MethodType):
                    member = MethodType(member.im_func, acopy, acopy.__class__)
                setattr(acopy, aname, member)
            return acopy
        finally:
            self.renderfunc = renderfunc
            self.sortfunc = sortfunc

    def render_cell(self, w, rownum):
        entity = self.entity(rownum)
        if entity is None:
            w(self.empty_cell_content)
        else:
            self.renderfunc(w, entity)

    def sortvalue(self, rownum):
        entity = self.entity(rownum)
        if entity is None:
            return None
        else:
            return self.sortfunc(entity)

    def entity(self, rownum):
        """Convenience method returning the table's main entity."""
        return self.view.entity(rownum)

    def render_entity(self, w, entity):
        """Sort value if `renderfunc` nor `sortfunc` specified at
        initialization.

        This default implementation consider column id is an entity attribute
        and print its value.
        """
        w(entity.printable_value(self.colid))

    def entity_sortvalue(self, entity):
        """Cell rendering implementation if `renderfunc` nor `sortfunc`
        specified at initialization.

        This default implementation consider column id is an entity attribute
        and return its sort value by calling `entity.sortvalue(colid)`.
        """
        return entity.sortvalue(self.colid)


class MainEntityColRenderer(EntityTableColRenderer):
    """Renderer to be used for the column displaying the 'main entity' of a
    :class:`EntityTableView`.

    By default display it using the 'incontext' view. You may specify another
    view identifier using the `vid` argument.

    If header not specified, it would be built using entity types in the main
    column.
    """
    def __init__(self, vid='incontext', addcount=True, **kwargs):
        super(MainEntityColRenderer, self).__init__(addcount=addcount, **kwargs)
        self.vid = vid

    def default_header(self):
        view = self.view
        if len(view.cw_rset) > 1:
            suffix = '_plural'
        else:
            suffix = ''
        return u', '.join(self._cw.__(et + suffix)
                          for et in view.cw_rset.column_types(view.cw_col or 0))

    def render_entity(self, w, entity):
        entity.view(self.vid, w=w)

    def entity_sortvalue(self, entity):
        return entity.sortvalue()


class RelatedEntityColRenderer(MainEntityColRenderer):
    """Renderer to be used for column displaying an entity related the 'main
    entity' of a :class:`EntityTableView`.

    By default display it using the 'incontext' view. You may specify another
    view identifier using the `vid` argument.

    If header not specified, it would be built by translating the column id.
    """
    def __init__(self, getrelated, addcount=False, **kwargs):
        super(RelatedEntityColRenderer, self).__init__(addcount=addcount, **kwargs)
        self.getrelated = getrelated

    def entity(self, rownum):
        entity = super(RelatedEntityColRenderer, self).entity(rownum)
        return self.getrelated(entity)

    def default_header(self):
        return self._cw._(self.colid)


class RelationColRenderer(EntityTableColRenderer):
    """Renderer to be used for column displaying a list of entities related the
    'main entity' of a :class:`EntityTableView`. By default, the main entity is
    considered as the subject of the relation but you may specify otherwise
    using the `role` argument.

    By default display the related rset using the 'csv' view, using
    'outofcontext' sub-view for each entity. You may specify another view
    identifier using respectivly the `vid` and `subvid` arguments.

    If you specify a 'rtype view', such as 'reledit', you should add a
    is_rtype_view=True parameter.

    If header not specified, it would be built by translating the column id,
    properly considering role.
    """
    def __init__(self, role='subject', vid='csv', subvid=None,
                 fallbackvid='empty-cell', is_rtype_view=False, **kwargs):
        super(RelationColRenderer, self).__init__(**kwargs)
        self.role = role
        self.vid = vid
        if subvid is None and vid in ('csv', 'list'):
            subvid = 'outofcontext'
        self.subvid = subvid
        self.fallbackvid = fallbackvid
        self.is_rtype_view = is_rtype_view

    def render_entity(self, w, entity):
        kwargs = {'w': w}
        if self.is_rtype_view:
            rset = None
            kwargs['entity'] = entity
            kwargs['rtype'] = self.colid
            kwargs['role'] = self.role
        else:
            rset = entity.related(self.colid, self.role)
        if self.subvid is not None:
            kwargs['subvid'] = self.subvid
        self._cw.view(self.vid, rset, self.fallbackvid, **kwargs)

    def default_header(self):
        return display_name(self._cw, self.colid, self.role)

    entity_sortvalue = None # column not sortable by default


class EntityTableView(TableMixIn, EntityView):
    """This abstract table view is designed to be used with an
    :class:`is_instance()` or :class:`adaptable` predicate, hence doesn't depend
    the result set shape as the :class:`RsetTableView` does.

    It will display columns that should be defined using the `columns` class
    attribute containing a list of column ids. By default, each column is
    renderered by :class:`EntityTableColRenderer` which consider that the column
    id is an attribute of the table's main entity (ie the one for which the view
    is selected).

    You may wish to specify :class:`MainEntityColRenderer` or
    :class:`RelatedEntityColRenderer` renderer for a column in the
    :attr:`column_renderers` dictionary.

    .. autoclass:: cubicweb.web.views.tableview.EntityTableColRenderer
    .. autoclass:: cubicweb.web.views.tableview.MainEntityColRenderer
    .. autoclass:: cubicweb.web.views.tableview.RelatedEntityColRenderer
    .. autoclass:: cubicweb.web.views.tableview.RelationColRenderer
    """
    __abstract__ = True
    default_column_renderer_class = EntityTableColRenderer
    columns = None # to be defined in concret class

    def call(self, columns=None, **kwargs):
        if columns is not None:
            self.columns = columns
        self.layout_render(self.w)

    @property
    def table_size(self):
        return self.cw_rset.rowcount

    def build_column_renderers(self):
        return [self.column_renderer(colid) for colid in self.columns]

    def entity(self, rownum):
        """Return the table's main entity"""
        return self.cw_rset.get_entity(rownum, self.cw_col or 0)


class EmptyCellView(AnyRsetView):
    __regid__ = 'empty-cell'
    __select__ = yes()
    def call(self, **kwargs):
        self.w(u'&#160;')
    cell_call = call


################################################################################
# DEPRECATED tables ############################################################
################################################################################


class TableView(AnyRsetView):
    """The table view accepts any non-empty rset. It uses introspection on the
    result set to compute column names and the proper way to display the cells.

    It is however highly configurable and accepts a wealth of options.
    """
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.14] %(cls)s is deprecated'
    __regid__ = 'table'
    title = _('table')
    finalview = 'final'

    table_widget_class = TableWidget
    table_column_class = TableColumn

    tablesorter_settings = {
        'textExtraction': JSString('cw.sortValueExtraction'),
        'selectorHeaders': 'thead tr:first th', # only plug on the first row
        }
    handle_pagination = True

    def form_filter(self, divid, displaycols, displayactions, displayfilter,
                    paginate, hidden=True):
        try:
            filterform = self._cw.vreg['views'].select(
                'facet.filtertable', self._cw, rset=self.cw_rset)
        except NoSelectableObject:
            return ()
        vidargs = {'paginate': paginate,
                   'displaycols': displaycols,
                   'displayactions': displayactions,
                   'displayfilter': displayfilter}
        cssclass = hidden and 'hidden' or ''
        filterform.render(self.w, vid=self.__regid__, divid=divid,
                          vidargs=vidargs, cssclass=cssclass)
        return self.show_hide_actions(divid, not hidden)

    def main_var_index(self):
        """Returns the index of the first non final variable of the rset.

        Used to select the main etype to help generate accurate column headers.
        XXX explain the concept

        May return None if none is found.
        """
        eschema = self._cw.vreg.schema.eschema
        for i, etype in enumerate(self.cw_rset.description[0]):
            try:
                if not eschema(etype).final:
                    return i
            except KeyError: # XXX possible?
                continue
        return None

    def displaycols(self, displaycols, headers):
        if displaycols is None:
            if 'displaycols' in self._cw.form:
                displaycols = [int(idx) for idx in self._cw.form['displaycols']]
            elif headers is not None:
                displaycols = range(len(headers))
            else:
                displaycols = range(len(self.cw_rset.syntax_tree().children[0].selection))
        return displaycols

    def _setup_tablesorter(self, divid):
        req = self._cw
        req.add_js('jquery.tablesorter.js')
        req.add_onload('''$(document).ready(function() {
    $("#%s table.listing").tablesorter(%s);
});''' % (divid, js_dumps(self.tablesorter_settings)))
        req.add_css(('cubicweb.tablesorter.css', 'cubicweb.tableview.css'))

    @cachedproperty
    def initial_load(self):
        """We detect a bit heuristically if we are built for the first time of
        from subsequent calls by the form filter or by the pagination hooks
        """
        form = self._cw.form
        return 'fromformfilter' not in form and '__start' not in form

    def call(self, title=None, subvid=None, displayfilter=None, headers=None,
             displaycols=None, displayactions=None, actions=(), divid=None,
             cellvids=None, cellattrs=None, mainindex=None,
             paginate=False, page_size=None):
        """Produces a table displaying a composite query

        :param title: title added before table
        :param subvid: cell view
        :param displayfilter: filter that selects rows to display
        :param headers: columns' titles
        :param displaycols: indexes of columns to display (first column is 0)
        :param displayactions: if True, display action menu
        """
        req = self._cw
        divid = divid or req.form.get('divid') or 'rs%s' % make_uid(id(self.cw_rset))
        self._setup_tablesorter(divid)
        # compute label first  since the filter form may remove some necessary
        # information from the rql syntax tree
        if mainindex is None:
            mainindex = self.main_var_index()
        computed_labels = self.columns_labels(mainindex)
        if not subvid and 'subvid' in req.form:
            subvid = req.form.pop('subvid')
        actions = list(actions)
        if mainindex is None:
            displayfilter, displayactions = False, False
        else:
            if displayfilter is None and req.form.get('displayfilter'):
                displayfilter = True
            if displayactions is None and req.form.get('displayactions'):
                displayactions = True
        displaycols = self.displaycols(displaycols, headers)
        if self.initial_load:
            self.w(u'<div class="section">')
            if not title and 'title' in req.form:
                title = req.form['title']
            if title:
                self.w(u'<h2 class="tableTitle">%s</h2>\n' % title)
            if displayfilter:
                actions += self.form_filter(divid, displaycols, displayfilter,
                                            displayactions, paginate)
        elif displayfilter:
            actions += self.show_hide_actions(divid, True)
        self.w(u'<div id="%s">' % divid)
        if displayactions:
            actionsbycat = self._cw.vreg['actions'].possible_actions(req, self.cw_rset)
            for action in actionsbycat.get('mainactions', ()):
                for action in action.actual_actions():
                    actions.append( (action.url(), req._(action.title),
                                     action.html_class(), None) )
        # render actions menu
        if actions:
            self.render_actions(divid, actions)
        # render table
        if paginate:
            self.divid = divid # XXX iirk (see usage in page_navigation_url)
            self.paginate(page_size=page_size, show_all_option=False)
        table = self.table_widget_class(self)
        for column in self.get_columns(computed_labels, displaycols, headers,
                                       subvid, cellvids, cellattrs, mainindex):
            table.append_column(column)
        table.render(self.w)
        self.w(u'</div>\n')
        if self.initial_load:
            self.w(u'</div>\n')

    def page_navigation_url(self, navcomp, path, params):
        """Build a URL to the current view using the <navcomp> attributes

        :param navcomp: a NavigationComponent to call a URL method on.
        :param path:    expected to be json here?
        :param params: params to give to build_url method

        this is called by :class:`cubiweb.web.component.NavigationComponent`
        """
        if hasattr(self, 'divid'):
            # XXX this assert a single call
            params['divid'] = self.divid
        params['vid'] = self.__regid__
        return navcomp.ajax_page_url(**params)

    def show_hide_actions(self, divid, currentlydisplayed=False):
        showhide = u';'.join(toggle_action('%s%s' % (divid, what))[11:]
                             for what in ('Form', 'Show', 'Hide', 'Actions'))
        showhide = 'javascript:' + showhide
        showlabel = self._cw._('show filter form')
        hidelabel = self._cw._('hide filter form')
        if currentlydisplayed:
            return [(showhide, showlabel, 'hidden', '%sShow' % divid),
                    (showhide, hidelabel, None, '%sHide' % divid)]
        return [(showhide, showlabel, None, '%sShow' % divid),
                (showhide, hidelabel, 'hidden', '%sHide' % divid)]

    def render_actions(self, divid, actions):
        box = MenuWidget('', 'tableActionsBox', _class='', islist=False)
        label = tags.img(src=self._cw.uiprops['PUCE_DOWN'],
                         alt=xml_escape(self._cw._('action(s) on this selection')))
        menu = PopupBoxMenu(label, isitem=False, link_class='actionsBox',
                            ident='%sActions' % divid)
        box.append(menu)
        for url, label, klass, ident in actions:
            menu.append(component.Link(url, label, klass=klass, id=ident))
        box.render(w=self.w)
        self.w(u'<div class="clear"></div>')

    def get_columns(self, computed_labels, displaycols, headers, subvid,
                    cellvids, cellattrs, mainindex):
        """build columns description from various parameters

        : computed_labels: columns headers computed from rset to be used if there is no headers entry
        : displaycols: see :meth:`call`
        : headers: explicitly define columns headers
        : subvid: see :meth:`call`
        : cellvids: see :meth:`call`
        : cellattrs: see :meth:`call`
        : mainindex: see :meth:`call`

        return a list of columns description to be used by
               :class:`~cubicweb.web.htmlwidgets.TableWidget`
        """
        columns = []
        eschema = self._cw.vreg.schema.eschema
        for colindex, label in enumerate(computed_labels):
            if colindex not in displaycols:
                continue
            # compute column header
            if headers is not None:
                _label = headers[displaycols.index(colindex)]
                if _label is not None:
                    label = _label
            if colindex == mainindex and label is not None:
                label += ' (%s)' % self.cw_rset.rowcount
            column = self.table_column_class(label, colindex)
            coltype = self.cw_rset.description[0][colindex]
            # compute column cell view (if coltype is None, it's a left outer
            # join, use the default non final subvid)
            if cellvids and colindex in cellvids:
                column.append_renderer(cellvids[colindex], colindex)
            elif coltype is not None and eschema(coltype).final:
                column.append_renderer(self.finalview, colindex)
            else:
                column.append_renderer(subvid or 'incontext', colindex)
            if cellattrs and colindex in cellattrs:
                for name, value in cellattrs[colindex].iteritems():
                    column.add_attr(name, value)
            # add column
            columns.append(column)
        return columns


    def render_cell(self, cellvid, row, col, w):
        self._cw.view('cell', self.cw_rset, row=row, col=col, cellvid=cellvid, w=w)

    def get_rows(self):
        return self.cw_rset

    @htmlescape
    @jsonize
    @limitsize(10)
    def sortvalue(self, row, col):
        # XXX it might be interesting to try to limit value's
        #     length as much as possible (e.g. by returning the 10
        #     first characters of a string)
        val = self.cw_rset[row][col]
        if val is None:
            return u''
        etype = self.cw_rset.description[row][col]
        if etype is None:
            return u''
        if self._cw.vreg.schema.eschema(etype).final:
            entity, rtype = self.cw_rset.related_entity(row, col)
            if entity is None:
                return val # remove_html_tags() ?
            return entity.sortvalue(rtype)
        entity = self.cw_rset.get_entity(row, col)
        return entity.sortvalue()


class EditableTableView(TableView):
    __regid__ = 'editable-table'
    finalview = 'editable-final'
    title = _('editable-table')


class CellView(EntityView):
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.14] %(cls)s is deprecated'
    __regid__ = 'cell'
    __select__ = nonempty_rset()

    def cell_call(self, row, col, cellvid=None):
        """
        :param row, col: indexes locating the cell value in view's result set
        :param cellvid: cell view (defaults to 'outofcontext')
        """
        etype, val = self.cw_rset.description[row][col], self.cw_rset[row][col]
        if etype is None or not self._cw.vreg.schema.eschema(etype).final:
            if val is None:
                # This is usually caused by a left outer join and in that case,
                # regular views will most certainly fail if they don't have
                # a real eid
                # XXX if cellvid is e.g. reledit, we may wanna call it anyway
                self.w(u'&#160;')
            else:
                self.wview(cellvid or 'outofcontext', self.cw_rset, row=row, col=col)
        else:
            # XXX why do we need a fallback view here?
            self.wview(cellvid or 'final', self.cw_rset, 'null', row=row, col=col)


class InitialTableView(TableView):
    """same display as  table view but consider two rql queries :

    * the default query (ie `rql` form parameter), which is only used to select
      this view and to build the filter form. This query should have the same
      structure as the actual without actual restriction (but link to
      restriction variables) and usually with a limit for efficiency (limit set
      to 2 is advised)

    * the actual query (`actualrql` form parameter) whose results will be
      displayed with default restrictions set
    """
    __regid__ = 'initialtable'
    __select__ = nonempty_rset()
    # should not be displayed in possible view since it expects some specific
    # parameters
    title = None

    def call(self, title=None, subvid=None, headers=None, divid=None,
             paginate=False, displaycols=None, displayactions=None,
             mainindex=None):
        """Dumps a table displaying a composite query"""
        try:
            actrql = self._cw.form['actualrql']
        except KeyError:
            actrql = self.cw_rset.printable_rql()
        else:
            self._cw.ensure_ro_rql(actrql)
        displaycols = self.displaycols(displaycols, headers)
        if displayactions is None and 'displayactions' in self._cw.form:
            displayactions = True
        if divid is None and 'divid' in self._cw.form:
            divid = self._cw.form['divid']
        self.w(u'<div class="section">')
        if not title and 'title' in self._cw.form:
            # pop title so it's not displayed by the table view as well
            title = self._cw.form.pop('title')
        if title:
            self.w(u'<h2>%s</h2>\n' % title)
        if mainindex is None:
            mainindex = self.main_var_index()
        if mainindex is not None:
            actions = self.form_filter(divid, displaycols, displayactions,
                                       displayfilter=True, paginate=paginate,
                                       hidden=True)
        else:
            actions = ()
        if not subvid and 'subvid' in self._cw.form:
            subvid = self._cw.form.pop('subvid')
        self._cw.view('table', self._cw.execute(actrql),
                      'noresult', w=self.w, displayfilter=False, subvid=subvid,
                      displayactions=displayactions, displaycols=displaycols,
                      actions=actions, headers=headers, divid=divid)
        self.w(u'</div>\n')


class EditableInitialTableTableView(InitialTableView):
    __regid__ = 'editable-initialtable'
    finalview = 'editable-final'


class EntityAttributesTableView(EntityView):
    """This table displays entity attributes in a table and allow to set a
    specific method to help building cell content for each attribute as well as
    column header.

    Table will render entity cell by using the appropriate build_COLNAME_cell
    methods if defined otherwise cell content will be entity.COLNAME.

    Table will render column header using the method header_for_COLNAME if
    defined otherwise COLNAME will be used.
    """
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.14] %(cls)s is deprecated'
    __abstract__ = True
    columns = ()
    table_css = "listing"
    css_files = ()

    def call(self, columns=None):
        if self.css_files:
            self._cw.add_css(self.css_files)
        _ = self._cw._
        self.columns = columns or self.columns
        sample = self.cw_rset.get_entity(0, 0)
        self.w(u'<table class="%s">' % self.table_css)
        self.table_header(sample)
        self.w(u'<tbody>')
        for row in xrange(self.cw_rset.rowcount):
            self.cell_call(row=row, col=0)
        self.w(u'</tbody>')
        self.w(u'</table>')

    def cell_call(self, row, col):
        _ = self._cw._
        entity = self.cw_rset.get_entity(row, col)
        entity.complete()
        infos = {}
        for col in self.columns:
            meth = getattr(self, 'build_%s_cell' % col, None)
            # find the build method or try to find matching attribute
            if meth:
                content = meth(entity)
            else:
                content = entity.printable_value(col)
            infos[col] = content
        self.w(u"""<tr onmouseover="$(this).addClass('highlighted');"
            onmouseout="$(this).removeClass('highlighted')">""")
        line = u''.join(u'<td>%%(%s)s</td>' % col for col in self.columns)
        self.w(line % infos)
        self.w(u'</tr>\n')

    def table_header(self, sample):
        """builds the table's header"""
        self.w(u'<thead><tr>')
        for column in self.columns:
            meth = getattr(self, 'header_for_%s' % column, None)
            if meth:
                colname = meth(sample)
            else:
                colname = self._cw._(column)
            self.w(u'<th>%s</th>' % xml_escape(colname))
        self.w(u'</tr></thead>\n')

