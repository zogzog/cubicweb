"""Specific views for entities implementing IDownloadable

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import BINARY_ENCODINGS, TransformError, html_escape

from cubicweb.interfaces import IDownloadable
from cubicweb.common.mttransforms import ENGINE
from cubicweb.common.selectors import (one_line_rset, score_entity_selector,
                                       implement_interface, match_context_prop)
from cubicweb.web.box import EntityBoxTemplate
from cubicweb.web.views import baseviews

_ = unicode

def download_box(w, entity, title=None, label=None):
    req = entity.req
    w(u'<div class="sideRelated">')
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
    __selectors__ = (one_line_rset, implement_interface, match_context_prop)
    accepts_interfaces = (IDownloadable,)
    order = 10
    def cell_call(self, row, col, title=None, label=None, **kwargs):
        entity = self.entity(row, col)
        download_box(self.w, entity, title, label)


class DownloadView(baseviews.EntityView):
    """this view is replacing the deprecated 'download' controller and allow downloading
    of entities providing the necessary interface
    """
    id = 'download'
    __selectors__ = (one_line_rset, implement_interface)
    accepts_interfaces = (IDownloadable,)

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


class DownloadLinkView(baseviews.EntityView):
    """view displaying a link to download the file"""
    id = 'downloadlink'
    title = None # should not be listed in possible views
    __selectors__ = (implement_interface,)

    accepts_interfaces = (IDownloadable,)
    
    def cell_call(self, row, col, title=None, **kwargs):
        entity = self.entity(row, col)
        url = html_escape(entity.download_url())
        self.w(u'<a href="%s">%s</a>' % (url, html_escape(title or entity.dc_title())))


                                                                                
class IDownloadablePrimaryView(baseviews.PrimaryView):
    __selectors__ = (implement_interface,)
    #skip_attrs = ('eid', 'data',) # XXX
    accepts_interfaces = (IDownloadable,)

    def render_entity_title(self, entity):
        self.w(u'<h1>%s %s</h1>'
               % (entity.dc_type().capitalize(),
                  html_escape(entity.dc_title())))
    
    def render_entity_attributes(self, entity, siderelations):
        super(IDownloadablePrimaryView, self).render_entity_attributes(entity, siderelations)
        self.wview('downloadlink', entity.rset, title=self.req._('download'), row=entity.row)
        self.w(u'<div class="content">')
        contenttype = entity.download_content_type()
        if contenttype.startswith('image/'):
            self.wview('image', entity.rset, row=entity.row)
        else:
            try:
                if ENGINE.has_input(contenttype):
                    self.w(entity.printable_value('data'))
            except TransformError:
                pass
            except Exception, ex:
                msg = self.req._("can't display data, unexpected error: %s") % ex
                self.w('<div class="error">%s</div>' % msg)
        self.w(u'</div>')
            
    def is_side_related(self, rschema, eschema):
        """display all relations as side related"""
        return True


class IDownloadableLineView(baseviews.OneLineView):
    __selectors__ = (implement_interface,)
    # don't kick default oneline view
    accepts_interfaces = (IDownloadable,)
    

    def cell_call(self, row, col, title=None, **kwargs):
        """the secondary view is a link to download the file"""
        entity = self.entity(row, col)
        url = html_escape(entity.absolute_url())
        name = html_escape(entity.download_file_name())
        durl = html_escape(entity.download_url())
        self.w(u'<a href="%s">%s</a> [<a href="%s">%s</a>]' %
               (url, name, durl, self.req._('download')))


class ImageView(baseviews.EntityView):
    __selectors__ = (implement_interface, score_entity_selector)
    id = 'image'
    title = _('image')
    accepts_interfaces = (IDownloadable,)
    
    def call(self):
        rset = self.rset
        for i in xrange(len(rset)):
            self.w(u'<div class="efile">')
            self.wview(self.id, rset, row=i, col=0)
            self.w(u'</div>')

    @classmethod
    def score_entity(cls, entity):
        mt = entity.download_content_type()
        if not (mt and mt.startswith('image/')):
            return 0
        return 1
    
    def cell_call(self, row, col):
        entity = self.entity(row, col)
        #if entity.data_format.startswith('image/'):
        self.w(u'<img src="%s" alt="%s"/>' % (html_escape(entity.download_url()),
                                              html_escape(entity.download_file_name())))

