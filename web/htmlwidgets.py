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
"""html widgets

those are in cubicweb since we need to know available widgets at schema
serialization time

"""

from math import floor
import random

from logilab.mtconverter import xml_escape

from cubicweb.utils import UStringIO
from cubicweb.uilib import toggle_action, htmlescape
from cubicweb.web import jsonize

# XXX HTMLWidgets should have access to req (for datadir / static urls,
#     i18n strings, etc.)
class HTMLWidget(object):

    def _initialize_stream(self, w=None):
        if w:
            self.w = w
        else:
            self._stream = UStringIO()
            self.w = self._stream.write

    def _render(self):
        raise NotImplementedError

    def render(self, w=None):
        self._initialize_stream(w)
        self._render()
        if w is None:
            return self._stream.getvalue()

    def is_empty(self):
        return False


class BoxWidget(HTMLWidget):
    def __init__(self, title, id, items=None, _class="boxFrame",
                 islist=True, shadow=True, escape=True):
        self.title = title
        self.id = id
        self.items = items or []
        self._class = _class
        self.islist = islist
        self.shadow = shadow
        self.escape = escape

    def __len__(self):
        return len(self.items)

    def is_empty(self):
        return len(self) == 0

    def append(self, item):
        self.items.append(item)

    def extend(self, items):
        self.items.extend(items)

    title_class = 'boxTitle'
    main_div_class = 'boxContent'
    listing_class = 'boxListing'

    def box_begin_content(self):
        self.w(u'<div class="%s">\n' % self.main_div_class)
        if self.islist:
            self.w(u'<ul class="%s">' % self.listing_class)

    def box_end_content(self):
        if self.islist:
            self.w(u'</ul>\n')
        self.w(u'</div>\n')
        if self.shadow:
            self.w(u'<div class="shadow">&#160;</div>')

    def _render(self):
        if self.id:
            self.w(u'<div class="%s" id="%s">' % (self._class, self.id))
        else:
            self.w(u'<div class="%s">' % self._class)
        if self.title:
            if self.escape:
                title = '<span>%s</span>' % xml_escape(self.title)
            else:
                title = '<span>%s</span>' % self.title
            self.w(u'<div class="%s">%s</div>' % (self.title_class, title))
        if self.items:
            self.box_begin_content()
            for item in self.items:
                item.render(self.w)
            self.box_end_content()
        self.w(u'</div>')


class SideBoxWidget(BoxWidget):
    """default CubicWeb's sidebox widget"""
    title_class = u'sideBoxTitle'
    main_div_class = u'sideBoxBody'
    listing_class = ''

    def __init__(self, title, id=None):
        super(SideBoxWidget, self).__init__(title, id=id, _class='sideBox',
                                            shadow=False)


class MenuWidget(BoxWidget):
    main_div_class = 'menuContent'
    listing_class = 'menuListing'

    def box_end_content(self):
        if self.islist:
            self.w(u'</ul>\n')
        self.w(u'</div>\n')


class RawBoxItem(HTMLWidget):
    """a simpe box item displaying raw data"""
    def __init__(self, label, liclass=None):
        self.label = label
        self.liclass = liclass

    def _start_li(self):
        if self.liclass is None:
            return u'<li>'
        else:
            return u'<li class="%s">' % self.liclass

        return self.label

    def _render(self):
        self.w(u'%s%s</li>' % (self._start_li(), self.label))


class BoxMenu(RawBoxItem):
    """a menu in a box"""
    link_class = 'boxMenu'

    def __init__(self, label, items=None, isitem=True, liclass=None, ident=None,
                 link_class=None):
        super(BoxMenu, self).__init__(label, liclass)
        self.items = items or []
        self.isitem = isitem
        self.ident = ident or u'boxmenu_%s' % label.replace(' ', '_').replace("'", '')
        if link_class:
            self.link_class = link_class

    def append(self, item):
        self.items.append(item)

    def _begin_menu(self, ident):
        self.w(u'<ul id="%s" class="hidden">' % ident)

    def _end_menu(self):
        self.w(u'</ul>')

    def _render(self):
        if self.isitem:
            self.w(self._start_li())
        ident = self.ident
        self.w(u'<a href="%s" class="%s">%s</a>' % (
            toggle_action(ident), self.link_class, self.label))
        self._begin_menu(ident)
        for item in self.items:
            item.render(self.w)
        self._end_menu()
        if self.isitem:
            self.w(u'</li>')


class PopupBoxMenu(BoxMenu):
    """like BoxMenu but uses div and specific css class
    in order to behave like a popup menu
    """
    link_class = 'popupMenu'

    def _begin_menu(self, ident):
        self.w(u'<div class="popupWrapper"><div id="%s" class="hidden popup"><ul>' % ident)

    def _end_menu(self):
        self.w(u'</ul></div></div>')


class BoxField(HTMLWidget):
    """couples label / value meant to be displayed in a box"""
    def __init__(self, label, value):
        self.label = label
        self.value = value

    def _render(self):
        self.w(u'<li><div><span class="label">%s</span>&#160;'
               u'<span class="value">%s</span></div></li>'
               % (self.label, self.value))

class BoxSeparator(HTMLWidget):
    """a menu separator"""

    def _render(self):
        self.w(u'</ul><hr class="boxSeparator"/><ul>')


class BoxLink(HTMLWidget):
    """a link in a box"""
    def __init__(self, href, label, _class='', title='', ident='', escape=False):
        self.href = href
        if escape:
            self.label = xml_escape(label)
        else:
            self.label = label
        self._class = _class or ''
        self.title = title
        self.ident = ident

    def _render(self):
        link = u'<a href="%s" title="%s">%s</a>' % (
            xml_escape(self.href), xml_escape(self.title), self.label)
        if self.ident:
            self.w(u'<li id="%s" class="%s">%s</li>\n' % (self.ident, self._class, link))
        else:
            self.w(u'<li class="%s">%s</li>\n' % (self._class, link))


class BoxHtml(HTMLWidget):
    """a form in a box"""
    def __init__(self, rawhtml):
        self.rawhtml = rawhtml

    def _render(self):
        self.w(self.rawhtml)


class TableColumn(object):
    def __init__(self, name, rset_sortcol):
        """
        :param name: the column's name
        :param rset_sortcol: the model's column used to sort this column view
        """
        self.name = name
        self.cellrenderers = []
        self.rset_sortcol = rset_sortcol
        self.cell_attrs = {}

    def append_renderer(self, cellvid, colindex):
        # XXX (adim) : why do we need colindex here ?
        self.cellrenderers.append( (cellvid, colindex) )

    def add_attr(self, attr, value):
        self.cell_attrs[attr] = value

class SimpleTableModel(object):
    """
    uses a list of lists as a storage backend

    NB: the model expectes the cellvid passed to
    TableColumn.append_renderer to be a callable accepting a single
    argument and returning a unicode object
    """
    def __init__(self, rows):
        self._rows = rows


    def get_rows(self):
        return self._rows

    def render_cell(self, cellvid, rowindex, colindex, w):
        value = self._rows[rowindex][colindex]
        w(cellvid(value))

    @htmlescape
    @jsonize
    def sortvalue(self, rowindex, colindex):
        value =  self._rows[rowindex][colindex]
        if value is None:
            return u''
        elif isinstance(value, int):
            return u'%09d' % value
        else:
            return unicode(value)


class TableWidget(HTMLWidget):
    """
    Display data in a Table with sortable column.

    When using remember to include the required css and js with:

    self._cw.add_js('jquery.tablesorter.js')
    self._cw.add_css(('cubicweb.tablesorter.css', 'cubicweb.tableview.css'))
    """
    highlight = "onmouseover=\"addElementClass(this, 'highlighted');\" " \
                "onmouseout=\"removeElementClass(this, 'highlighted');\""

    def __init__(self, model):
        self.model = model
        self.columns = []

    def append_column(self, column):
        """
        :type column: TableColumn
        """
        self.columns.append(column)

    def _render(self):
        self.w(u'<table class="listing">')
        self.w(u'<thead>')
        self.w(u'<tr class="header">')
        for column in self.columns:
            attrs = ('%s="%s"' % (name, value) for name, value in column.cell_attrs.iteritems())
            self.w(u'<th %s>%s</th>' % (' '.join(attrs), column.name))
        self.w(u'</tr>')
        self.w(u'</thead><tbody>')
        for rowindex in xrange(len(self.model.get_rows())):
            klass = (rowindex%2==1) and 'odd' or 'even'
            self.w(u'<tr class="%s" %s>' % (klass, self.highlight))
            for column, sortvalue in self.itercols(rowindex):
                attrs = dict(column.cell_attrs)
                attrs["cubicweb:sortvalue"] = 'json:' + sortvalue
                attrs = ('%s="%s"' % (name, value) for name, value in attrs.iteritems())
                self.w(u'<td %s>' % (' '.join(attrs)))
                for cellvid, colindex in column.cellrenderers:
                    self.model.render_cell(cellvid, rowindex, colindex, w=self.w)
                self.w(u'</td>')
            self.w(u'</tr>')
        self.w(u'</tbody>')
        self.w(u'</table>')

    def itercols(self, rowindex):
        for column in self.columns:
            yield column, self.model.sortvalue(rowindex, column.rset_sortcol)


