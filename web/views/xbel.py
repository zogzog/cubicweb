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
"""xbel views

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape

from cubicweb.selectors import implements
from cubicweb.view import EntityView
from cubicweb.web.views.xmlrss import XMLView


class XbelView(XMLView):
    __regid__ = 'xbel'
    title = _('xbel')
    templatable = False
    content_type = 'text/xml' #application/xbel+xml

    def cell_call(self, row, col):
        self.wview('xbelitem', self.cw_rset, row=row, col=col)

    def call(self):
        """display a list of entities by calling their <item_vid> view"""
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % self._cw.encoding)
        self.w(u'<!DOCTYPE xbel PUBLIC "+//IDN python.org//DTD XML Bookmark Exchange Language 1.0//EN//XML" "http://www.python.org/topics/xml/dtds/xbel-1.0.dtd">')
        self.w(u'<xbel version="1.0">')
        self.w(u'<title>%s</title>' % self._cw._('bookmarks'))
        for i in xrange(self.cw_rset.rowcount):
            self.cell_call(i, 0)
        self.w(u"</xbel>")


class XbelItemView(EntityView):
    __regid__ = 'xbelitem'

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        self.w(u'<bookmark href="%s">' % xml_escape(self.url(entity)))
        self.w(u'  <title>%s</title>' % xml_escape(entity.dc_title()))
        self.w(u'</bookmark>')

    def url(self, entity):
        return entity.absolute_url()


class XbelItemBookmarkView(XbelItemView):
    __select__ = implements('Bookmark')

    def url(self, entity):
        return entity.actual_url()

