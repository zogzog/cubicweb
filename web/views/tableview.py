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
"""generic table view, including filtering abilities


"""
__docformat__ = "restructuredtext en"

try:
    from json import dumps
except ImportError:
    from simplejson import dumps

from logilab.mtconverter import xml_escape

from cubicweb.selectors import nonempty_rset, match_form_params
from cubicweb.utils import make_uid
from cubicweb.view import EntityView, AnyRsetView
from cubicweb import tags
from cubicweb.uilib import toggle_action, limitsize, htmlescape
from cubicweb.web import jsonize
from cubicweb.web.htmlwidgets import (TableWidget, TableColumn, MenuWidget,
                                      PopupBoxMenu, BoxLink)
from cubicweb.web.facet import prepare_facets_rqlst, filter_hiddens

class TableView(AnyRsetView):
    """The table view accepts any non-empty rset. It uses
    introspection on the result set to compute column names and the
    proper way to display the cells.
    It is however highly configurable and accepts a wealth of options.
    """
    __regid__ = 'table'
    title = _('table')
    finalview = 'final'

    def form_filter(self, divid, displaycols, displayactions, displayfilter,
                    hidden=True):
        rqlst = self.cw_rset.syntax_tree()
        # union not yet supported
        if len(rqlst.children) != 1:
            return ()
        rqlst = rqlst.copy()
        self._cw.vreg.rqlhelper.annotate(rqlst)
        mainvar, baserql = prepare_facets_rqlst(rqlst, self.cw_rset.args)
        wdgs = [facet.get_widget() for facet in self._cw.vreg['facets'].poss_visible_objects(
            self._cw, rset=self.cw_rset, rqlst=rqlst.children[0], context='tablefilter',
            filtered_variable=mainvar)]
        wdgs = [wdg for wdg in wdgs if wdg is not None]
        if wdgs:
            self._generate_form(divid, baserql, wdgs, hidden,
                               vidargs={'displaycols': displaycols,
                                        'displayactions': displayactions,
                                        'displayfilter': displayfilter})
            return self.show_hide_actions(divid, not hidden)
        return ()

    def _generate_form(self, divid, baserql, fwidgets, hidden=True, vidargs={}):
        """display a form to filter table's content. This should only
        occur when a context eid is given
        """
        w = self.w
        self._cw.add_css('cubicweb.facets.css')
        self._cw.add_js( ('cubicweb.ajax.js', 'cubicweb.facets.js'))
        # drop False / None values from vidargs
        vidargs = dict((k, v) for k, v in vidargs.iteritems() if v)
        w(u'<form method="post" cubicweb:facetargs="%s" action="">' %
          xml_escape(dumps([divid, 'table', False, vidargs])))
        w(u'<fieldset id="%sForm" class="%s">' % (divid, hidden and 'hidden' or ''))
        w(u'<input type="hidden" name="divid" value="%s" />' % divid)
        w(u'<input type="hidden" name="fromformfilter" value="1" />')
        filter_hiddens(w, facets=','.join(wdg.facet.__regid__ for wdg in fwidgets),
                       baserql=baserql)
        w(u'<table class="filter">\n')
        w(u'<tr>\n')
        for wdg in fwidgets:
            w(u'<td>')
            wdg.render(w=w)
            w(u'</td>\n')
        w(u'</tr>\n')
        w(u'</table>\n')
        w(u'</fieldset>\n')
        w(u'</form>\n')

    def main_var_index(self):
        """returns the index of the first non-attribute variable among the RQL
        selected variables
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

    def call(self, title=None, subvid=None, displayfilter=None, headers=None,
             displaycols=None, displayactions=None, actions=(), divid=None,
             cellvids=None, cellattrs=None, mainindex=None):
        """Produces a table displaying a composite query

        :param title: title added before table
        :param subvid: cell view
        :param displayfilter: filter that selects rows to display
        :param headers: columns' titles
        """
        req = self._cw
        req.add_js('jquery.tablesorter.js')
        req.add_css(('cubicweb.tablesorter.css', 'cubicweb.tableview.css'))
        # compute label first  since the filter form may remove some necessary
        # information from the rql syntax tree
        if mainindex is None:
            mainindex = self.main_var_index()
        computed_labels = self.columns_labels(mainindex)
        hidden = True
        if not subvid and 'subvid' in req.form:
            subvid = req.form.pop('subvid')
        divid = divid or req.form.get('divid') or 'rs%s' % make_uid(id(self.cw_rset))
        actions = list(actions)
        if mainindex is None:
            displayfilter, displayactions = False, False
        else:
            if displayfilter is None and 'displayfilter' in req.form:
                displayfilter = True
                if req.form['displayfilter'] == 'shown':
                    hidden = False
            if displayactions is None and 'displayactions' in req.form:
                displayactions = True
        displaycols = self.displaycols(displaycols, headers)
        fromformfilter = 'fromformfilter' in req.form
        # if fromformfilter is true, this is an ajax call and we only want to
        # replace the inner div, so don't regenerate everything under the if
        # below
        if not fromformfilter:
            self.w(u'<div class="section">')
            if not title and 'title' in req.form:
                title = req.form['title']
            if title:
                self.w(u'<h2 class="tableTitle">%s</h2>\n' % title)
            if displayfilter:
                actions += self.form_filter(divid, displaycols, displayfilter,
                                            displayactions)
        elif displayfilter:
            actions += self.show_hide_actions(divid, True)
        self.w(u'<div id="%s"' % divid)
        if displayactions:
            actionsbycat = self._cw.vreg['actions'].possible_actions(req, self.cw_rset)
            for action in actionsbycat.get('mainactions', ()):
                for action in action.actual_actions():
                    actions.append( (action.url(), req._(action.title),
                                     action.html_class(), None) )
            self.w(u' cubicweb:displayactions="1">') # close <div tag
        else:
            self.w(u'>') # close <div tag
        # render actions menu
        if actions:
            self.render_actions(divid, actions)
        # render table
        table = TableWidget(self)
        for column in self.get_columns(computed_labels, displaycols, headers,
                                       subvid, cellvids, cellattrs, mainindex):
            table.append_column(column)
        table.render(self.w)
        self.w(u'</div>\n')
        if not fromformfilter:
            self.w(u'</div>\n')

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
        label = tags.img(src=self._cw.external_resource('PUCE_DOWN'),
                         alt=xml_escape(self._cw._('action(s) on this selection')))
        menu = PopupBoxMenu(label, isitem=False, link_class='actionsBox',
                            ident='%sActions' % divid)
        box.append(menu)
        for url, label, klass, ident in actions:
            menu.append(BoxLink(url, label, klass, ident=ident, escape=True))
        box.render(w=self.w)
        self.w(u'<div class="clear"/>')

    def get_columns(self, computed_labels, displaycols, headers, subvid,
                    cellvids, cellattrs, mainindex):
        columns = []
        eschema = self._cw.vreg.schema.eschema
        for colindex, label in enumerate(computed_labels):
            if colindex not in displaycols:
                continue
            # compute column header
            if headers is not None:
                label = headers[displaycols.index(colindex)]
            if colindex == mainindex:
                label += ' (%s)' % self.cw_rset.rowcount
            column = TableColumn(label, colindex)
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
    __regid__ = 'cell'
    __select__ = nonempty_rset()

    def cell_call(self, row, col, cellvid=None):
        """
        :param row, col: indexes locating the cell value in view's result set
        :param cellvid: cell view (defaults to 'outofcontext')
        """
        etype, val = self.cw_rset.description[row][col], self.cw_rset[row][col]
        if val is not None and not self._cw.vreg.schema.eschema(etype).final:
            e = self.cw_rset.get_entity(row, col)
            e.view(cellvid or 'outofcontext', w=self.w)
        elif val is None:
            # This is usually caused by a left outer join and in that case,
            # regular views will most certainly fail if they don't have
            # a real eid
            self.wview('final', self.cw_rset, row=row, col=col)
        else:
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
    __select__ = nonempty_rset() & match_form_params('actualrql')
    # should not be displayed in possible view since it expects some specific
    # parameters
    title = None

    def call(self, title=None, subvid=None, headers=None, divid=None,
             displaycols=None, displayactions=None, mainindex=None):
        """Dumps a table displaying a composite query"""
        actrql = self._cw.form['actualrql']
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
            actions = self.form_filter(divid, displaycols, displayactions, True)
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
    __abstract__ = True
    columns = ()
    table_css = "listing"
    css_files = ()

    def call(self, columns=None):
        if self.css_files:
            self._cw.add_css(self.css_files)
        _ = self._cw._
        self.columns = columns or self.columns
        ecls = self._cw.vreg['etypes'].etype_class(self.cw_rset.description[0][0])
        self.w(u'<table class="%s">' % self.table_css)
        self.table_header(ecls)
        self.w(u'<tbody>')
        for row in xrange(self.cw_rset.rowcount):
            self.cell_call(row=row, col=0)
        self.w(u'</tbody>')
        self.w(u'</table>')

    def cell_call(self, row, col):
        _ = self._cw._
        entity = self.cw_rset.get_entity(row, col)
        infos = {}
        for col in self.columns:
            meth = getattr(self, 'build_%s_cell' % col, None)
            # find the build method or try to find matching attribute
            if meth:
                content = meth(entity)
            else:
                content = entity.printable_value(col)
            infos[col] = content
        self.w(u"""<tr onmouseover="addElementClass(this, 'highlighted');"
            onmouseout="removeElementClass(this, 'highlighted')">""")
        line = u''.join(u'<td>%%(%s)s</td>' % col for col in self.columns)
        self.w(line % infos)
        self.w(u'</tr>\n')

    def table_header(self, ecls):
        """builds the table's header"""
        self.w(u'<thead><tr>')
        _ = self._cw._
        for column in self.columns:
            meth = getattr(self, 'header_for_%s' % column, None)
            if meth:
                colname = meth(ecls)
            else:
                colname = _(column)
            self.w(u'<th>%s</th>' % xml_escape(colname))
        self.w(u'</tr></thead>\n')


