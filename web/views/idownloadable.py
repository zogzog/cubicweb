# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
Specific views for entities adapting to IDownloadable
=====================================================
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import BINARY_ENCODINGS, TransformError, xml_escape
from logilab.common.deprecation import class_renamed, deprecated

from cubicweb import tags
from cubicweb.view import EntityView
from cubicweb.predicates import (one_line_rset, is_instance, match_context_prop,
                                 adaptable, has_mimetype)
from cubicweb.mttransforms import ENGINE
from cubicweb.web import component, httpcache
from cubicweb.web.views import primary, baseviews


class DownloadBox(component.EntityCtxComponent):
    """add download box"""
    __regid__ = 'download_box'    # no download box for images
    __select__ = (component.EntityCtxComponent.__select__ &
                  adaptable('IDownloadable') & ~has_mimetype('image/'))

    order = 10
    title = _('download')

    def init_rendering(self):
        self.items = [self.entity]

    def render_body(self, w):
        for item in self.items:
            idownloadable = item.cw_adapt_to('IDownloadable')
            w(u'<a href="%s"><img src="%s" alt="%s"/> %s</a>'
              % (xml_escape(idownloadable.download_url()),
                 self._cw.uiprops['DOWNLOAD_ICON'],
                 self._cw._('download icon'),
                 xml_escape(idownloadable.download_file_name())))


class DownloadView(EntityView):
    """download view

    this view is replacing the deprecated 'download' controller and allow
    downloading of entities providing the necessary interface
    """
    __regid__ = 'download'
    __select__ = one_line_rset() & adaptable('IDownloadable')

    templatable = False
    content_type = 'application/octet-stream'
    binary = True
    http_cache_manager = httpcache.EntityHTTPCacheManager
    add_to_breadcrumbs = False

    def set_request_content_type(self):
        """overriden to set the correct filetype and filename"""
        entity = self.cw_rset.complete_entity(self.cw_row or 0, self.cw_col or 0)
        adapter = entity.cw_adapt_to('IDownloadable')
        encoding = adapter.download_encoding()
        if encoding in BINARY_ENCODINGS:
            contenttype = 'application/%s' % encoding
            encoding = None
        else:
            contenttype = adapter.download_content_type()
        self._cw.set_content_type(contenttype or self.content_type,
                                  filename=adapter.download_file_name(),
                                  encoding=encoding,
                                  disposition='attachment')

    def call(self):
        entity = self.cw_rset.complete_entity(self.cw_row or 0, self.cw_col or 0)
        adapter = entity.cw_adapt_to('IDownloadable')
        self.w(adapter.download_data())

    def last_modified(self):
        return self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0).modification_date


class DownloadLinkView(EntityView):
    """view displaying a link to download the file"""
    __regid__ = 'downloadlink'
    __select__ = adaptable('IDownloadable')
    title = None # should not be listed in possible views


    def cell_call(self, row, col, title=None, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        url = xml_escape(entity.cw_adapt_to('IDownloadable').download_url())
        self.w(u'<a href="%s">%s</a>' % (url, xml_escape(title or entity.dc_title())))


class IDownloadablePrimaryView(primary.PrimaryView):
    __select__ = adaptable('IDownloadable')

    def render_entity_attributes(self, entity):
        self.w(u'<div class="content">')
        adapter = entity.cw_adapt_to('IDownloadable')
        contenttype = adapter.download_content_type()
        if contenttype.startswith('image/'):
            self._cw.add_js('cubicweb.image.js')
            self.wview('image', entity.cw_rset, row=entity.cw_row, col=entity.cw_col,
                       link=True, klass='contentimage')
            super(IDownloadablePrimaryView, self).render_entity_attributes(entity)
        elif contenttype.endswith('html'):
            self.wview('downloadlink', entity.cw_rset, title=self._cw._('download'), row=entity.cw_row)
            self.wview('ehtml', entity.cw_rset, row=entity.cw_row, col=entity.cw_col,
                       height='600px', width='100%')
        else:
            super(IDownloadablePrimaryView, self).render_entity_attributes(entity)
            self.wview('downloadlink', entity.cw_rset, title=self._cw._('download'), row=entity.cw_row)
            self.render_data(entity, contenttype, 'text/html')
        self.w(u'</div>')

    def render_data(self, entity, sourcemt, targetmt):
        adapter = entity.cw_adapt_to('IDownloadable')
        if ENGINE.find_path(sourcemt, targetmt):
            try:
                self.w(entity._cw_mtc_transform(adapter.download_data(), sourcemt,
                                                targetmt, adapter.download_encoding()))
            except Exception as ex:
                self.exception('while rendering data for %s', entity)
                msg = self._cw._("can't display data, unexpected error: %s") \
                      % xml_escape(unicode(ex))
                self.w('<div class="error">%s</div>' % msg)
            return True
        return False


class IDownloadableOneLineView(baseviews.OneLineView):
    __select__ = adaptable('IDownloadable')

    def cell_call(self, row, col, title=None, **kwargs):
        """the oneline view is a link to download the file"""
        entity = self.cw_rset.get_entity(row, col)
        url = xml_escape(entity.absolute_url())
        adapter = entity.cw_adapt_to('IDownloadable')
        name = xml_escape(title or entity.dc_title())
        durl = xml_escape(adapter.download_url())
        self.w(u'<a href="%s">%s</a> [<a href="%s">%s</a>]' %
               (url, name, durl, self._cw._('download')))


class AbstractEmbeddedView(EntityView):
    __abstract__ = True

    _embedding_tag = None

    def call(self, **kwargs):
        rset = self.cw_rset
        for i in xrange(len(rset)):
            self.w(u'<div class="efile">')
            self.wview(self.__regid__, rset, row=i, col=0, **kwargs)
            self.w(u'</div>')

    def cell_call(self, row, col, link=False, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        adapter = entity.cw_adapt_to('IDownloadable')
        tag = self._embedding_tag(src=adapter.download_url(), # pylint: disable=E1102
                                  alt=(self._cw._('download %s') % adapter.download_file_name()),
                                  **kwargs)
        if link:
            self.w(u'<a href="%s">%s</a>' % (adapter.download_url(), tag))
        else:
            self.w(tag)


class ImageView(AbstractEmbeddedView):
    """image embedded view"""
    __regid__ = 'image'
    __select__ = has_mimetype('image/')

    title = _('image')
    _embedding_tag = tags.img


class EHTMLView(AbstractEmbeddedView):
    """html embedded view"""
    __regid__ = 'ehtml'
    __select__ = has_mimetype('text/html')

    title = _('embedded html')
    _embedding_tag = tags.iframe



