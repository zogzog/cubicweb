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
"""Basic views for python values (eg without any result set)
"""
__docformat__ = "restructuredtext en"

from cubicweb.view import View
from cubicweb.selectors import match_kwargs


class PyValTableView(View):
    """display a list of list of values into an HTML table.

    Take care, content is NOT xml-escaped.

    If `headers` is specfied, it is expected to be a list of headers to be
    inserted as first row (in <thead>).

    If `colheaders` is True, the first column will be considered as an headers
    column an its values will be inserted inside <th> instead of <td>.

    `cssclass` is the CSS class used on the <table> tag, and default to
    'listing' (so that the table will look similar to those generated by the
    table view).
    """
    __regid__ = 'pyvaltable'
    __select__ = match_kwargs('pyvalue')

    def call(self, pyvalue, headers=None, colheaders=False,
             cssclass='listing'):
        if headers is None:
            headers = self._cw.form.get('headers')
        w = self.w
        w(u'<table class="%s">\n' % cssclass)
        if headers:
            w(u'<thead>')
            w(u'<tr>')
            for header in headers:
                w(u'<th>%s</th>' % header)
            w(u'</tr>\n')
            w(u'</thead>')
        w(u'<tbody>')
        for row in pyvalue:
            w(u'<tr>')
            if colheaders:
                w(u'<th>%s</th>' % row[0])
                row = row[1:]
            for cell in row:
                w(u'<td>%s</td>' % cell)
            w(u'</tr>\n')
        w(u'</tbody>')
        w(u'</table>\n')


class PyValListView(View):
    """display a list of values into an html list.

    Take care, content is NOT xml-escaped.
    """
    __regid__ = 'pyvallist'
    __select__ = match_kwargs('pyvalue')

    def call(self, pyvalue):
        self.w(u'<ul>\n')
        for line in pyvalue:
            self.w(u'<li>%s</li>\n' % line)
        self.w(u'</ul>\n')
