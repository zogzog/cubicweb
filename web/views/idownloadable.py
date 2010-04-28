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
"""Specific views for entities implementing IDownloadable

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import BINARY_ENCODINGS, TransformError, xml_escape

from cubicweb.view import EntityView
from cubicweb.selectors import (one_line_rset, score_entity,
                                implements, match_context_prop)
from cubicweb.interfaces import IDownloadable
from cubicweb.mttransforms import ENGINE
from cubicweb.web.box import EntityBoxTemplate
from cubicweb.web.views import primary, baseviews


def is_image(entity):
    mt = entity.download_content_type()
    if not (mt and mt.startswith('image/')):
        return 0
    return 1

def download_box(w, entity, title=None, label=None, footer=u''):
    req = entity._cw
    w(u'<div class="sideBox">')
    if title is None:
        title = req._('download')
    w(u'<div class="sideBoxTitle downloadBoxTitle"><span>%s</span></div>'
      % xml_escape(title))
    w(u'<div class="sideBox downloadBox"><div class="sideBoxBody">')
    w(u'<a href="%s"><img src="%s" alt="%s"/> %s</a>'
      % (xml_escape(entity.download_url()),
         req.external_resource('DOWNLOAD_ICON'),
         _('download icon'), xml_escape(label or entity.dc_title())))
    w(u'%s</div>' % footer)
    w(u'</div></div>\n')


class DownloadBox(EntityBoxTemplate):
    __regid__ = 'download_box'
    # no download box for images
    # XXX primary_view selector ?
    __select__ = (one_line_rset() & implements(IDownloadable) &
                  match_context_prop() & ~score_entity(is_image))
    order = 10

    def cell_call(self, row, col, title=None, label=None, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        download_box(self.w, entity, title, label)


class DownloadView(EntityView):
    """this view is replacing the deprecated 'download' controller and allow
    downloading of entities providing the necessary interface
    """
    __regid__ = 'download'
    __select__ = one_line_rset() & implements(IDownloadable)

    templatable = False
    content_type = 'application/octet-stream'
    binary = True
    add_to_breadcrumbs = False

    def set_request_content_type(self):
        """overriden to set the correct filetype and filename"""
        entity = self.cw_rset.complete_entity(0, 0)
        encoding = entity.download_encoding()
        if encoding in BINARY_ENCODINGS:
            contenttype = 'application/%s' % encoding
            encoding = None
        else:
            contenttype = entity.download_content_type()
        self._cw.set_content_type(contenttype or self.content_type,
                                  filename=entity.download_file_name(),
                                  encoding=encoding)

    def call(self):
        self.w(self.cw_rset.complete_entity(0, 0).download_data())


class DownloadLinkView(EntityView):
    """view displaying a link to download the file"""
    __regid__ = 'downloadlink'
    __select__ = implements(IDownloadable)
    title = None # should not be listed in possible views


    def cell_call(self, row, col, title=None, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        url = xml_escape(entity.download_url())
        self.w(u'<a href="%s">%s</a>' % (url, xml_escape(title or entity.dc_title())))


class IDownloadablePrimaryView(primary.PrimaryView):
    __select__ = implements(IDownloadable)

    def render_entity_attributes(self, entity):
        super(IDownloadablePrimaryView, self).render_entity_attributes(entity)
        self.w(u'<div class="content">')
        contenttype = entity.download_content_type()
        if contenttype.startswith('image/'):
            self.wview('image', entity.cw_rset, row=entity.cw_row)
        else:
            self.wview('downloadlink', entity.cw_rset, title=self._cw._('download'), row=entity.cw_row)
            try:
                if ENGINE.has_input(contenttype):
                    self.w(entity.printable_value('data'))
            except TransformError:
                pass
            except Exception, ex:
                msg = self._cw._("can't display data, unexpected error: %s") \
                      % xml_escape(str(ex))
                self.w('<div class="error">%s</div>' % msg)
        self.w(u'</div>')


class IDownloadableLineView(baseviews.OneLineView):
    __select__ = implements(IDownloadable)

    def cell_call(self, row, col, title=None, **kwargs):
        """the oneline view is a link to download the file"""
        entity = self.cw_rset.get_entity(row, col)
        url = xml_escape(entity.absolute_url())
        name = xml_escape(title or entity.download_file_name())
        durl = xml_escape(entity.download_url())
        self.w(u'<a href="%s">%s</a> [<a href="%s">%s</a>]' %
               (url, name, durl, self._cw._('download')))


class ImageView(EntityView):
    __regid__ = 'image'
    __select__ = implements(IDownloadable) & score_entity(is_image)

    title = _('image')

    def call(self):
        rset = self.cw_rset
        for i in xrange(len(rset)):
            self.w(u'<div class="efile">')
            self.wview(self.__regid__, rset, row=i, col=0)
            self.w(u'</div>')

    def cell_call(self, row, col, width=None, height=None, link=False):
        entity = self.cw_rset.get_entity(row, col)
        #if entity.data_format.startswith('image/'):
        imgtag = u'<img src="%s" alt="%s" ' % (
            xml_escape(entity.download_url()),
            (self._cw._('download %s')  % xml_escape(entity.download_file_name())))
        if width:
            imgtag += u'width="%i" ' % width
        if height:
            imgtag += u'height="%i" ' % height
        imgtag += u'/>'
        if link:
            self.w(u'<a href="%s">%s</a>' % (entity.absolute_url(vid='download'),
                                             imgtag))
        else:
            self.w(imgtag)


