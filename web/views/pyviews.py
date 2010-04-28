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
"""Views to display bare python values

"""
__docformat__ = "restructuredtext en"

from cubicweb.view import View
from cubicweb.selectors import match_kwargs

class PyValTableView(View):
    __regid__ = 'pyvaltable'
    __select__ = match_kwargs('pyvalue')

    def call(self, pyvalue, headers=None):
        if headers is None:
            headers = self._cw.form.get('headers')
        w = self.w
        w(u'<table class="listing">\n')
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
            for cell in row:
                w(u'<td>%s</td>' % cell)
            w(u'</tr>\n')
        w(u'</tbody>')
        w(u'</table>\n')


class PyValListView(View):
    __regid__ = 'pyvallist'
    __select__ = match_kwargs('pyvalue')

    def call(self, pyvalue):
        self.w(u'<ul>\n')
        for line in pyvalue:
            self.w(u'<li>%s</li>\n' % line)
        self.w(u'</ul>\n')
