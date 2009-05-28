"""Specific views for entities implementing IDownloadable

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import BINARY_ENCODINGS, TransformError, html_escape

from cubicweb.view import EntityView
from cubicweb.selectors import (one_line_rset, score_entity,
                                implements, match_context_prop)
from cubicweb.interfaces import IDownloadable
from cubicweb.common.mttransforms import ENGINE
from cubicweb.web.box import EntityBoxTemplate
from cubicweb.web.views import primary, baseviews


def is_image(entity):
    mt = entity.download_content_type()
    if not (mt and mt.startswith('image/')):
        return 0
    return 1

def download_box(w, entity, title=None, label=None):
    req = entity.req
    w(u'<div class="sideBox">')
    if title is None:
        title = req._('download')
    w(u'<div class="sideBoxTitle downloadBoxTitle"><span>%s</span></div>'
      % html_escape(title))
    w(u'<div class="sideBox downloadBox"><div class="sideBoxBody">')
    w(u'<a href="%s"><img src="%s" alt="%s"/> %s</a>'
      % (html_escape(entity.download_url()),
         req.external_resource('DOWNLOAD_ICON'),
         _('download icon'), html_escape(label or entity.dc_title())))
    w(u'</div>')
    w(u'</div>\n</div>\n')


class DownloadBox(EntityBoxTemplate):
    id = 'download_box'
    # no download box for images
    # XXX primary_view selector ?
    __select__ = (one_line_rset() & implements(IDownloadable) &
                  match_context_prop() & ~score_entity(is_image))
    order = 10

    def cell_call(self, row, col, title=None, label=None, **kwargs):
        entity = self.entity(row, col)
        download_box(self.w, entity, title, label)


class DownloadView(EntityView):
    """this view is replacing the deprecated 'download' controller and allow
    downloading of entities providing the necessary interface
    """
    id = 'download'
    __select__ = one_line_rset() & implements(IDownloadable)

    templatable = False
    content_type = 'application/octet-stream'
    binary = True
    add_to_breadcrumbs = False

    def set_request_content_type(self):
        """overriden to set the correct filetype and filename"""
        entity = self.complete_entity(0)
        encoding = entity.download_encoding()
        if encoding in BINARY_ENCODINGS:
            contenttype = 'application/%s' % encoding
            encoding = None
        else:
            contenttype = entity.download_content_type()
        self.req.set_content_type(contenttype or self.content_type,
                                  filename=entity.download_file_name(),
                                  encoding=encoding)

    def call(self):
        self.w(self.complete_entity(0).download_data())


class DownloadLinkView(EntityView):
    """view displaying a link to download the file"""
    id = 'downloadlink'
    __select__ = implements(IDownloadable)
    title = None # should not be listed in possible views


    def cell_call(self, row, col, title=None, **kwargs):
        entity = self.entity(row, col)
        url = html_escape(entity.download_url())
        self.w(u'<a href="%s">%s</a>' % (url, html_escape(title or entity.dc_title())))


class IDownloadablePrimaryView(primary.PrimaryView):
    __select__ = implements(IDownloadable)

    def render_entity_attributes(self, entity):
        super(IDownloadablePrimaryView, self).render_entity_attributes(entity)
        self.w(u'<div class="content">')
        contenttype = entity.download_content_type()
        if contenttype.startswith('image/'):
            self.wview('image', entity.rset, row=entity.row)
        else:
            self.wview('downloadlink', entity.rset, title=self.req._('download'), row=entity.row)
            try:
                if ENGINE.has_input(contenttype):
                    self.w(entity.printable_value('data'))
            except TransformError:
                pass
            except Exception, ex:
                msg = self.req._("can't display data, unexpected error: %s") % ex
                self.w('<div class="error">%s</div>' % msg)
        self.w(u'</div>')


class IDownloadableLineView(baseviews.OneLineView):
    __select__ = implements(IDownloadable)

    def cell_call(self, row, col, title=None, **kwargs):
        """the secondary view is a link to download the file"""
        entity = self.entity(row, col)
        url = html_escape(entity.absolute_url())
        name = html_escape(entity.download_file_name())
        durl = html_escape(entity.download_url())
        self.w(u'<a href="%s">%s</a> [<a href="%s">%s</a>]' %
               (url, name, durl, self.req._('download')))


class ImageView(EntityView):
    id = 'image'
    __select__ = implements(IDownloadable) & score_entity(is_image)

    title = _('image')

    def call(self):
        rset = self.rset
        for i in xrange(len(rset)):
            self.w(u'<div class="efile">')
            self.wview(self.id, rset, row=i, col=0)
            self.w(u'</div>')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        #if entity.data_format.startswith('image/'):
        self.w(u'<img src="%s" alt="%s"/>' % (html_escape(entity.download_url()),
                                              html_escape(entity.download_file_name())))

