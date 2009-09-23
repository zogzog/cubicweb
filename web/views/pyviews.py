"""Views to display bare python values

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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
        self.w(u'<table class="listing">\n')
        if headers:
            self.w(u'<tr>')
            for header in headers:
                self.w(u'<th>%s</th>' % header)
            self.w(u'</tr>\n')
        for row in pyvalue:
            self.w(u'<tr>')
            for cell in row:
                self.w(u'<td>%s</td>' % cell)
            self.w(u'</tr>\n')
        self.w(u'</table>\n')


class PyValListView(View):
    __regid__ = 'pyvallist'
    __select__ = match_kwargs('pyvalue')

    def call(self, pyvalue):
        self.w(u'<ul>\n')
        for line in pyvalue:
            self.w(u'<li>%s</li>\n' % line)
        self.w(u'</ul>\n')
