"""xbel views

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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
        title = self.page_title()
        url = self._cw.build_url(rql=self._cw.form.get('rql', ''))
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

