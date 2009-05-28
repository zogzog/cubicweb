"""generic table view, including filtering abilities


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps

from logilab.mtconverter import html_escape

from cubicweb.selectors import nonempty_rset, match_form_params
from cubicweb.utils import make_uid
from cubicweb.view import EntityView, AnyRsetView
from cubicweb.common.uilib import toggle_action, limitsize, htmlescape
from cubicweb.web import jsonize
from cubicweb.web.htmlwidgets import (TableWidget, TableColumn, MenuWidget,
                                      PopupBoxMenu, BoxLink)
from cubicweb.web.facet import prepare_facets_rqlst, filter_hiddens

class TableView(AnyRsetView):
    id = 'table'
    title = _('table')
    finalview = 'final'

    def form_filter(self, divid, displaycols, displayactions, displayfilter,
                    hidden=True):
        rqlst = self.rset.syntax_tree()
        # union not yet supported
        if len(rqlst.children) != 1:
            return ()
        rqlst.save_state()
        mainvar, baserql = prepare_facets_rqlst(rqlst, self.rset.args)
        wdgs = [facet.get_widget() for facet in self.vreg.possible_vobjects(
            'facets', self.req, self.rset, context='tablefilter',
            filtered_variable=mainvar)]
        wdgs = [wdg for wdg in wdgs if wdg is not None]
        rqlst.recover()
        if wdgs:
            self._generate_form(divid, baserql, wdgs, hidden,
                               vidargs={'displaycols': displaycols,
                                        'displayactions': displayactions,
                                        'displayfilter': displayfilter})
            return self.show_hide_actions(divid, not hidden)
        return ()

    def _generate_form(self, divid, baserql, fwidgets, hidden=True, vidargs={}):
        """display a form to filter table's content. This should only
        occurs when a context eid is given
        """
        self.req.add_js( ('cubicweb.ajax.js', 'cubicweb.formfilter.js'))
        # drop False / None values from vidargs
        vidargs = dict((k, v) for k, v in vidargs.iteritems() if v)
        self.w(u'<form method="post" cubicweb:facetargs="%s" action="">' %
               html_escape(dumps([divid, 'table', False, vidargs])))
        self.w(u'<fieldset id="%sForm" class="%s">' % (divid, hidden and 'hidden' or ''))
        self.w(u'<input type="hidden" name="divid" value="%s" />' % divid)
        filter_hiddens(self.w, facets=','.join(wdg.facet.id for wdg in fwidgets), baserql=baserql)
        self.w(u'<table class="filter">\n')
        self.w(u'<tr>\n')
        for wdg in fwidgets:
            self.w(u'<td>')
            wdg.render(w=self.w)
            self.w(u'</td>\n')
        self.w(u'</tr>\n')
        self.w(u'</table>\n')
        self.w(u'</fieldset>\n')
        self.w(u'</form>\n')

    def main_var_index(self):
        """returns the index of the first non-attribute variable among the RQL
        selected variables
        """
        eschema = self.vreg.schema.eschema
        for i, etype in enumerate(self.rset.description[0]):
            try:
                if not eschema(etype).is_final():
                    return i
            except KeyError: # XXX possible?
                continue
        return None

    def displaycols(self, displaycols):
        if displaycols is None:
            if 'displaycols' in self.req.form:
                displaycols = [int(idx) for idx in self.req.form['displaycols']]
            else:
                displaycols = range(len(self.rset.syntax_tree().children[0].selection))
        return displaycols

    def call(self, title=None, subvid=None, displayfilter=None, headers=None,
             displaycols=None, displayactions=None, actions=(), divid=None,
             cellvids=None, cellattrs=None):
        """Dumps a table displaying a composite query

        :param title: title added before table
        :param subvid: cell view
        :param displayfilter: filter that selects rows to display
        :param headers: columns' titles
        """
        rset = self.rset
        req = self.req
        req.add_js('jquery.tablesorter.js')
        req.add_css(('cubicweb.tablesorter.css', 'cubicweb.tableview.css'))
        rqlst = rset.syntax_tree()
        # get rql description first since the filter form may remove some
        # necessary information
        rqlstdescr = rqlst.get_description()[0] # XXX missing Union support
        mainindex = self.main_var_index()
        hidden = True
        if not subvid and 'subvid' in req.form:
            subvid = req.form.pop('subvid')
        divid = divid or req.form.get('divid') or 'rs%s' % make_uid(id(rset))
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
        displaycols = self.displaycols(displaycols)
        fromformfilter = 'fromformfilter' in req.form
        # if fromformfilter is true, this is an ajax call and we only want to
        # replace the inner div, so don't regenerate everything under the if
        # below
        if not fromformfilter:
            div_class = 'section'
            self.w(u'<div class="%s">' % div_class)
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
            for action in self.vreg.possible_actions(req, self.rset).get('mainactions', ()):
                actions.append( (action.url(), req._(action.title), action.html_class(), None) )
            self.w(u' cubicweb:displayactions="1">') # close <div tag
        else:
            self.w(u'>') # close <div tag
        # render actions menu
        if actions:
            self.render_actions(divid, actions)
        # render table
        table = TableWidget(self)
        for column in self.get_columns(rqlstdescr, displaycols, headers, subvid,
                                       cellvids, cellattrs, mainindex):
            table.append_column(column)
        table.render(self.w)
        self.w(u'</div>\n')
        if not fromformfilter:
            self.w(u'</div>\n')


    def show_hide_actions(self, divid, currentlydisplayed=False):
        showhide = u';'.join(toggle_action('%s%s' % (divid, what))[11:]
                             for what in ('Form', 'Show', 'Hide', 'Actions'))
        showhide = 'javascript:' + showhide
        showlabel = self.req._('show filter form')
        hidelabel = self.req._('hide filter form')
        if currentlydisplayed:
            return [(showhide, showlabel, 'hidden', '%sShow' % divid),
                    (showhide, hidelabel, None, '%sHide' % divid)]
        return [(showhide, showlabel, None, '%sShow' % divid),
                (showhide, hidelabel, 'hidden', '%sHide' % divid)]

    def render_actions(self, divid, actions):
        box = MenuWidget('', 'tableActionsBox', _class='', islist=False)
        label = '<img src="%s" alt="%s"/>' % (
            self.req.datadir_url + 'liveclipboard-icon.png',
            html_escape(self.req._('action(s) on this selection')))
        menu = PopupBoxMenu(label, isitem=False, link_class='actionsBox',
                            ident='%sActions' % divid)
        box.append(menu)
        for url, label, klass, ident in actions:
            menu.append(BoxLink(url, label, klass, ident=ident, escape=True))
        box.render(w=self.w)
        self.w(u'<div class="clear"/>')

    def get_columns(self, rqlstdescr, displaycols, headers, subvid, cellvids,
                    cellattrs, mainindex):
        columns = []
        for colindex, attr in enumerate(rqlstdescr):
            if colindex not in displaycols:
                continue
            # compute column header
            if headers is not None:
                label = headers[displaycols.index(colindex)]
            elif colindex == 0 or attr == 'Any': # find a better label
                label = ','.join(display_name(self.req, et)
                                 for et in self.rset.column_types(colindex))
            else:
                label = display_name(self.req, attr)
            if colindex == mainindex:
                label += ' (%s)' % self.rset.rowcount
            column = TableColumn(label, colindex)
            coltype = self.rset.description[0][colindex]
            # compute column cell view (if coltype is None, it's a left outer
            # join, use the default non final subvid)
            if cellvids and colindex in cellvids:
                column.append_renderer(cellvids[colindex], colindex)
            elif coltype is not None and self.schema.eschema(coltype).is_final():
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
        self.view('cell', self.rset, row=row, col=col, cellvid=cellvid, w=w)

    def get_rows(self):
        return self.rset

    @htmlescape
    @jsonize
    @limitsize(10)
    def sortvalue(self, row, col):
        # XXX it might be interesting to try to limit value's
        #     length as much as possible (e.g. by returning the 10
        #     first characters of a string)
        val = self.rset[row][col]
        if val is None:
            return u''
        etype = self.rset.description[row][col]
        if self.schema.eschema(etype).is_final():
            entity, rtype = self.rset.related_entity(row, col)
            if entity is None:
                return val # remove_html_tags() ?
            return entity.sortvalue(rtype)
        entity = self.rset.get_entity(row, col)
        return entity.sortvalue()


class EditableTableView(TableView):
    id = 'editable-table'
    finalview = 'editable-final'
    title = _('editable-table')


class CellView(EntityView):
    __select__ = nonempty_rset()

    id = 'cell'

    def cell_call(self, row, col, cellvid=None):
        """
        :param row, col: indexes locating the cell value in view's result set
        :param cellvid: cell view (defaults to 'outofcontext')
        """
        etype, val = self.rset.description[row][col], self.rset[row][col]
        if val is not None and not self.schema.eschema(etype).is_final():
            e = self.rset.get_entity(row, col)
            e.view(cellvid or 'outofcontext', w=self.w)
        elif val is None:
            # This is usually caused by a left outer join and in that case,
            # regular views will most certainly fail if they don't have
            # a real eid
            self.wview('final', self.rset, row=row, col=col)
        else:
            self.wview(cellvid or 'final', self.rset, 'null', row=row, col=col)


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
    id = 'initialtable'
    __select__ = nonempty_rset() & match_form_params('actualrql')
    # should not be displayed in possible view since it expects some specific
    # parameters
    title = None

    def call(self, title=None, subvid=None, headers=None, divid=None,
             displaycols=None, displayactions=None):
        """Dumps a table displaying a composite query"""
        actrql = self.req.form['actualrql']
        self.ensure_ro_rql(actrql)
        displaycols = self.displaycols(displaycols)
        if displayactions is None and 'displayactions' in self.req.form:
            displayactions = True
        if divid is None and 'divid' in self.req.form:
            divid = self.req.form['divid']
        self.w(u'<div class="section">')
        if not title and 'title' in self.req.form:
            # pop title so it's not displayed by the table view as well
            title = self.req.form.pop('title')
        if title:
            self.w(u'<h2>%s</h2>\n' % title)
        mainindex = self.main_var_index()
        if mainindex is not None:
            actions = self.form_filter(divid, displaycols, displayactions, True)
        else:
            actions = ()
        if not subvid and 'subvid' in self.req.form:
            subvid = self.req.form.pop('subvid')
        self.view('table', self.req.execute(actrql),
                  'noresult', w=self.w, displayfilter=False, subvid=subvid,
                  displayactions=displayactions, displaycols=displaycols,
                  actions=actions, headers=headers, divid=divid)
        self.w(u'</div>\n')


class EditableInitialTableTableView(InitialTableView):
    id = 'editable-initialtable'
    finalview = 'editable-final'
