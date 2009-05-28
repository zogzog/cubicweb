"""Objects interacting together to provides the external page embeding
functionality.


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import re
from urlparse import urljoin
from urllib2 import urlopen, Request, HTTPError

from logilab.mtconverter import guess_encoding

from cubicweb import urlquote # XXX should use view.url_quote method
from cubicweb.selectors import (one_line_rset, score_entity,
                                match_search_state, implements)
from cubicweb.interfaces import IEmbedable
from cubicweb.view import NOINDEX, NOFOLLOW
from cubicweb.common.uilib import soup2xhtml
from cubicweb.web.controller import Controller
from cubicweb.web.action import Action
from cubicweb.web.views import basetemplates


class ExternalTemplate(basetemplates.TheMainTemplate):
    """template embeding an external web pages into CubicWeb web interface
    """
    id = 'external'

    def call(self, body):
        # XXX fallback to HTML 4 mode when embeding ?
        self.set_request_content_type()
        self.req.search_state = ('normal',)
        self.template_header(self.content_type, None, self.req._('external page'),
                             [NOINDEX, NOFOLLOW])
        self.content_header()
        self.w(body)
        self.content_footer()
        self.template_footer()


class EmbedController(Controller):
    id = 'embed'
    template = 'external'

    def publish(self, rset=None):
        req = self.req
        if 'custom_css' in req.form:
            req.add_css(req.form['custom_css'])
        embedded_url = req.form['url']
        allowed = self.config['embed-allowed']
        _ = req._
        if allowed is None or not allowed.match(embedded_url):
            body = '<h2>%s</h2><h3>%s</h3>' % (
                _('error while embedding page'),
                _('embedding this url is forbidden'))
        else:
            prefix = req.build_url(self.id, url='')
            authorization = req.get_header('Authorization')
            if authorization:
                headers = {'Authorization' : authorization}
            else:
                headers = {}
            try:
                body = embed_external_page(embedded_url, prefix,
                                           headers, req.form.get('custom_css'))
                body = soup2xhtml(body, self.req.encoding)
            except HTTPError, err:
                body = '<h2>%s</h2><h3>%s</h3>' % (
                    _('error while embedding page'), err)
        self.process_rql(req.form.get('rql'))
        return self.vreg.main_template(req, self.template, rset=self.rset, body=body)


def entity_has_embedable_url(entity):
    """return 1 if the entity provides an allowed embedable url"""
    url = entity.embeded_url()
    if not url or not url.strip():
        return 0
    allowed = entity.config['embed-allowed']
    if allowed is None or not allowed.match(url):
        return 0
    return 1


class EmbedAction(Action):
    """display an 'embed' link on entity implementing `embeded_url` method
    if the returned url match embeding configuration
    """
    id = 'embed'
    __select__ = (one_line_rset() & match_search_state('normal')
                  & implements(IEmbedable)
                  & score_entity(entity_has_embedable_url))

    title = _('embed')
    controller = 'embed'

    def url(self, row=0):
        entity = self.rset.get_entity(row, 0)
        url = urljoin(self.req.base_url(), entity.embeded_url())
        if self.req.form.has_key('rql'):
            return self.build_url(url=url, rql=self.req.form['rql'])
        return self.build_url(url=url)



# functions doing necessary substitutions to embed an external html page ######


BODY_RGX = re.compile('<body.*?>(.*?)</body>', re.I | re.S | re.U)
HREF_RGX = re.compile('<a\s+href="([^"]*)"', re.I | re.S | re.U)
SRC_RGX = re.compile('<img\s+src="([^"]*)"', re.I | re.S | re.U)


class replace_href:
    def __init__(self, prefix, custom_css=None):
        self.prefix = prefix
        self.custom_css = custom_css

    def __call__(self, match):
        original_url = match.group(1)
        url = self.prefix + urlquote(original_url, safe='')
        if self.custom_css is not None:
            if '?' in url:
                url = '%s&amp;custom_css=%s' % (url, self.custom_css)
            else:
                url = '%s?custom_css=%s' % (url, self.custom_css)
        return '<a href="%s"' % url


class absolutize_links:
    def __init__(self, embedded_url, tag, custom_css=None):
        self.embedded_url = embedded_url
        self.tag = tag
        self.custom_css = custom_css

    def __call__(self, match):
        original_url = match.group(1)
        if '://' in original_url:
            return match.group(0) # leave it unchanged
        return '%s="%s"' % (self.tag, urljoin(self.embedded_url, original_url))


def prefix_links(body, prefix, embedded_url, custom_css=None):
    filters = ((HREF_RGX, absolutize_links(embedded_url, '<a href', custom_css)),
               (SRC_RGX, absolutize_links(embedded_url, '<img src')),
               (HREF_RGX, replace_href(prefix, custom_css)))
    for rgx, repl in filters:
        body = rgx.sub(repl, body)
    return body


def embed_external_page(url, prefix, headers=None, custom_css=None):
    req = Request(url, headers=(headers or {}))
    content = urlopen(req).read()
    page_source = unicode(content, guess_encoding(content), 'replace')
    page_source = page_source
    match = BODY_RGX.search(page_source)
    if match is None:
        return page_source
    return prefix_links(match.group(1), prefix, url, custom_css)
