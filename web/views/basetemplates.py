# -*- coding: utf-8 -*-
"""default templates for CubicWeb web client

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb.appobject import objectify_selector
from cubicweb.selectors import match_kwargs
from cubicweb.view import View, MainTemplate, NOINDEX, NOFOLLOW
from cubicweb.utils import UStringIO, can_do_pdf_conversion
from cubicweb.schema import display_name

# main templates ##############################################################

class LogInOutTemplate(MainTemplate):

    def call(self):
        self.set_request_content_type()
        w = self.w
        self.write_doctype()
        self.template_header('text/html', self._cw._('login_action'))
        w(u'<body>\n')
        self.content(w)
        w(u'</body>')

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        w = self.whead
        # explictly close the <base> tag to avoid IE 6 bugs while browsing DOM
        w(u'<base href="%s"></base>' % xml_escape(self._cw.base_url()))
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self._cw.encoding))
        w(NOINDEX)
        w(NOFOLLOW)
        w(u'\n'.join(additional_headers) + u'\n')
        self.wview('htmlheader', rset=self.cw_rset)
        w(u'<title>%s</title>\n' % xml_escape(page_title))


class LogInTemplate(LogInOutTemplate):
    __regid__ = 'login'
    title = 'log in'

    def content(self, w):
        self.wview('logform', rset=self.cw_rset, id='loginBox', klass='')


class LoggedOutTemplate(LogInOutTemplate):
    __regid__ = 'loggedout'
    title = 'logged out'

    def content(self, w):
        # FIXME Deprecated code ?
        msg = self._cw._('you have been logged out')
        w(u'<h2>%s</h2>\n' % msg)
        if self._cw.vreg.config['anonymous-user']:
            indexurl = self._cw.build_url('view', vid='index', __message=msg)
            w(u'<p><a href="%s">%s</a><p>' % (
                xml_escape(indexurl),
                self._cw._('go back to the index page')))

@objectify_selector
def templatable_view(cls, req, rset, *args, **kwargs):
    view = kwargs.pop('view', None)
    if view is None:
        return 1
    if view.binary:
        return 0
    if req.form.has_key('__notemplate'):
        return 0
    return view.templatable


class NonTemplatableViewTemplate(MainTemplate):
    """main template for any non templatable views (xml, binaries, etc.)"""
    __regid__ = 'main-template'
    __select__ = ~templatable_view()

    def call(self, view):
        view.set_request_content_type()
        view.set_stream()
        if (self._cw.form.has_key('__notemplate') and view.templatable
            and view.content_type == self._cw.html_content_type()):
            view.w(self._cw.document_surrounding_div())
            view.render()
            view.w(u'</div>')
        else:
            view.render()
        # have to replace our stream by view's stream (which may be a binary
        # stream)
        self._stream = view._stream


class TheMainTemplate(MainTemplate):
    """default main template :

    - call header / footer templates
    """
    __regid__ = 'main-template'
    __select__ = templatable_view()

    def call(self, view):
        self.set_request_content_type()
        self.template_header(self.content_type, view)
        w = self.w
        w(u'<div id="pageContent">\n')
        vtitle = self._cw.form.get('vtitle')
        if vtitle:
            w(u'<h1 class="vtitle">%s</h1>\n' % xml_escape(vtitle))
        # display entity type restriction component
        etypefilter = self._cw.vreg['components'].select_or_none(
            'etypenavigation', self._cw, rset=self.cw_rset)
        if etypefilter and etypefilter.cw_propval('visible'):
            etypefilter.render(w=w)
        self.nav_html = UStringIO()
        if view:
            view.paginate(w=self.nav_html.write)
        w(_(self.nav_html.getvalue()))
        w(u'<div id="contentmain">\n')
        view.render(w=w)
        w(u'</div>\n') # close id=contentmain
        w(_(self.nav_html.getvalue()))
        w(u'</div>\n') # closes id=pageContent
        self.template_footer(view)

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        page_title = page_title or view.page_title()
        additional_headers = additional_headers or view.html_headers()
        self.template_html_header(content_type, page_title, additional_headers)
        self.template_body_header(view)

    def template_html_header(self, content_type, page_title, additional_headers=()):
        w = self.whead
        lang = self._cw.lang
        self.write_doctype()
        # explictly close the <base> tag to avoid IE 6 bugs while browsing DOM
        w(u'<base href="%s"></base>' % xml_escape(self._cw.base_url()))
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self._cw.encoding))
        w(u'\n'.join(additional_headers) + u'\n')
        self.wview('htmlheader', rset=self.cw_rset)
        if page_title:
            w(u'<title>%s</title>\n' % xml_escape(page_title))

    def template_body_header(self, view):
        w = self.w
        w(u'<body>\n')
        self.wview('header', rset=self.cw_rset, view=view)
        w(u'<div id="page"><table width="100%" border="0" id="mainLayout"><tr>\n')
        self.nav_column(view, 'left')
        w(u'<td id="contentcol">\n')
        components = self._cw.vreg['components']
        rqlcomp = components.select_or_none('rqlinput', self._cw, rset=self.cw_rset)
        if rqlcomp:
            rqlcomp.render(w=self.w, view=view)
        msgcomp = components.select_or_none('applmessages', self._cw, rset=self.cw_rset)
        if msgcomp:
            msgcomp.render(w=self.w)
        self.content_header(view)

    def template_footer(self, view=None):
        self.content_footer(view)
        self.w(u'</td>\n')
        self.nav_column(view, 'right')
        self.w(u'</tr></table></div>\n')
        self.wview('footer', rset=self.cw_rset)
        self.w(u'</body>')

    def nav_column(self, view, context):
        boxes = list(self._cw.vreg['boxes'].poss_visible_objects(
            self._cw, rset=self.cw_rset, view=view, context=context))
        if boxes:
            self.w(u'<td class="navcol"><div class="navboxes">\n')
            for box in boxes:
                box.render(w=self.w, view=view)
            self.w(u'</div></td>\n')

    def content_header(self, view=None):
        """by default, display informal messages in content header"""
        self.wview('contentheader', rset=self.cw_rset, view=view)

    def content_footer(self, view=None):
        self.wview('contentfooter', rset=self.cw_rset, view=view)


class ErrorTemplate(TheMainTemplate):
    """fallback template if an internal error occured during displaying the
    main template. This template may be called for authentication error,
    which means that req.cnx and req.user may not be set.
    """
    __regid__ = 'error-template'

    def call(self):
        """display an unexpected error"""
        self.set_request_content_type()
        self._cw.reset_headers()
        view = self._cw.vreg['views'].select('error', self._cw, rset=self.cw_rset)
        self.template_header(self.content_type, view, self._cw._('an error occured'),
                             [NOINDEX, NOFOLLOW])
        view.render(w=self.w)
        self.template_footer(view)

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        w = self.whead
        lang = self._cw.lang
        self.write_doctype()
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self._cw.encoding))
        w(u'\n'.join(additional_headers))
        self.wview('htmlheader', rset=self.cw_rset)
        w(u'<title>%s</title>\n' % xml_escape(page_title))
        self.w(u'<body>\n')

    def template_footer(self, view=None):
        self.w(u'</body>')


class SimpleMainTemplate(TheMainTemplate):

    __regid__ = 'main-no-top'

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        page_title = page_title or view.page_title()
        additional_headers = additional_headers or view.html_headers()
        whead = self.whead
        lang = self._cw.lang
        self.write_doctype()
        whead(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
              % (content_type, self._cw.encoding))
        whead(u'\n'.join(additional_headers) + u'\n')
        self.wview('htmlheader', rset=self.cw_rset)
        w = self.w
        w(u'<title>%s</title>\n' % xml_escape(page_title))
        w(u'<body>\n')
        w(u'<div id="page">')
        w(u'<table width="100%" height="100%" border="0"><tr>\n')
        w(u'<td class="navcol">\n')
        self.topleft_header()
        boxes = list(self._cw.vreg['boxes'].poss_visible_objects(
            self._cw, rset=self.cw_rset, view=view, context='left'))
        if boxes:
            w(u'<div class="navboxes">\n')
            for box in boxes:
                box.render(w=w)
            self.w(u'</div>\n')
        w(u'</td>')
        w(u'<td id="contentcol" rowspan="2">')
        w(u'<div id="pageContent">\n')
        vtitle = self._cw.form.get('vtitle')
        if vtitle:
            w(u'<h1 class="vtitle">%s</h1>' % xml_escape(vtitle))

    def topleft_header(self):
        logo = self._cw.vreg['components'].select_or_none('logo', self._cw,
                                                      rset=self.cw_rset)
        if logo and logo.cw_propval('visible'):
            self.w(u'<table id="header"><tr>\n')
            self.w(u'<td>')
            logo.render(w=self.w)
            self.w(u'</td>\n')
            self.w(u'</tr></table>\n')

if can_do_pdf_conversion():
    from xml.etree.cElementTree import ElementTree
    from subprocess import Popen as sub
    from StringIO import StringIO
    from tempfile import NamedTemporaryFile
    from cubicweb.ext.xhtml2fo import ReportTransformer

    class PdfMainTemplate(TheMainTemplate):
        __regid__ = 'pdf-main-template'

        def call(self, view):
            """build the standard view, then when it's all done, convert xhtml to pdf
            """
            super(PdfMainTemplate, self).call(view)
            section = self._cw.form.pop('section', 'contentmain')
            pdf = self.to_pdf(self._stream, section)
            self._cw.set_content_type('application/pdf', filename='report.pdf')
            self.binary = True
            self.w = None
            self.set_stream()
            # pylint needs help
            self.w(pdf)

        def to_pdf(self, stream, section):
            # XXX see ticket/345282
            stream = stream.getvalue().replace('&nbsp;', '&#160;').encode('utf-8')
            xmltree = ElementTree()
            xmltree.parse(StringIO(stream))
            foptree = ReportTransformer(section).transform(xmltree)
            foptmp = NamedTemporaryFile()
            pdftmp = NamedTemporaryFile()
            foptree.write(foptmp)
            foptmp.flush()
            fopproc = sub(['/usr/bin/fop', foptmp.name, pdftmp.name])
            fopproc.wait()
            pdftmp.seek(0)
            pdf = pdftmp.read()
            return pdf

# page parts templates ########################################################

class HTMLHeader(View):
    """default html headers"""
    __regid__ = 'htmlheader'

    def call(self, **kwargs):
        self.favicon()
        self.stylesheets()
        self.javascripts()
        self.alternates()

    def favicon(self):
        favicon = self._cw.external_resource('FAVICON', None)
        if favicon:
            self.whead(u'<link rel="shortcut icon" href="%s"/>\n' % favicon)

    def stylesheets(self):
        req = self._cw
        add_css = req.add_css
        for css in req.external_resource('STYLESHEETS'):
            add_css(css, localfile=False)
        for css in req.external_resource('STYLESHEETS_PRINT'):
            add_css(css, u'print', localfile=False)
        for css in req.external_resource('IE_STYLESHEETS'):
            add_css(css, localfile=False, ieonly=True)

    def javascripts(self):
        for jscript in self._cw.external_resource('JAVASCRIPTS'):
            self._cw.add_js(jscript, localfile=False)

    def alternates(self):
        urlgetter = self._cw.vreg['components'].select_or_none('rss_feed_url',
                                                           self._cw, rset=self.cw_rset)
        if urlgetter is not None:
            self.whead(u'<link rel="alternate" type="application/rss+xml" title="RSS feed" href="%s"/>\n'
                       %  xml_escape(urlgetter.feed_url()))


class HTMLPageHeader(View):
    """default html page header"""
    __regid__ = 'header'
    main_cell_components = ('appliname', 'breadcrumbs')

    def call(self, view, **kwargs):
        self.main_header(view)
        self.w(u'''
  <div id="stateheader">''')
        self.state_header()
        self.w(u'''
  </div>
  ''')

    def main_header(self, view):
        """build the top menu with authentification info and the rql box"""
        self.w(u'<table id="header"><tr>\n')
        self.w(u'<td id="firstcolumn">')
        logo = self._cw.vreg['components'].select_or_none(
            'logo', self._cw, rset=self.cw_rset)
        if logo and logo.cw_propval('visible'):
            logo.render(w=self.w)
        self.w(u'</td>\n')
        # appliname and breadcrumbs
        self.w(u'<td id="headtext">')
        for cid in self.main_cell_components:
            comp = self._cw.vreg['components'].select_or_none(
                cid, self._cw, rset=self.cw_rset)
            if comp and comp.cw_propval('visible'):
                comp.render(w=self.w)
        self.w(u'</td>')
        # logged user and help
        self.w(u'<td>\n')
        comp = self._cw.vreg['components'].select_or_none(
            'loggeduserlink', self._cw, rset=self.cw_rset)
        if comp and comp.cw_propval('visible'):
            comp.render(w=self.w)
        self.w(u'</td>')
        # lastcolumn
        self.w(u'<td id="lastcolumn">')
        self.w(u'</td>\n')
        self.w(u'</tr></table>\n')
        self.wview('logform', rset=self.cw_rset, id='popupLoginBox', klass='hidden',
                   title=False, message=False)

    def state_header(self):
        state = self._cw.search_state
        if state[0] == 'normal':
            return
        _ = self._cw._
        value = self.view('oneline', self._cw.eid_rset(state[1][1]))
        msg = ' '.join((_("searching for"),
                        display_name(self._cw, state[1][3]),
                        _("to associate with"), value,
                        _("by relation"), '"',
                        display_name(self._cw, state[1][2], state[1][0]),
                        '"'))
        return self.w(u'<div class="stateMessage">%s</div>' % msg)



class HTMLPageFooter(View):
    """default html page footer: include footer actions
    """
    __regid__ = 'footer'

    def call(self, **kwargs):
        req = self._cw
        self.w(u'<div class="footer">')
        actions = self._cw.vreg['actions'].possible_actions(self._cw,
                                                            rset=self.cw_rset)
        footeractions = actions.get('footer', ())
        for i, action in enumerate(footeractions):
            self.w(u'<a href="%s">%s</a>' % (action.url(),
                                             self._cw._(action.title)))
            if i < (len(footeractions) - 1):
                self.w(u' | ')
        self.w(u'</div>')


class HTMLContentHeader(View):
    """default html page content header:
    * include message component if selectable for this request
    * include selectable content navigation components
    """
    __regid__ = 'contentheader'

    def call(self, view, **kwargs):
        """by default, display informal messages in content header"""
        components = self._cw.vreg['contentnavigation'].poss_visible_objects(
            self._cw, rset=self.cw_rset, view=view, context='navtop')
        if components:
            self.w(u'<div id="contentheader">')
            for comp in components:
                comp.render(w=self.w, view=view)
            self.w(u'</div><div class="clear"></div>')


class HTMLContentFooter(View):
    """default html page content footer: include selectable content navigation
    components
    """
    __regid__ = 'contentfooter'

    def call(self, view, **kwargs):
        components = self._cw.vreg['contentnavigation'].poss_visible_objects(
            self._cw, rset=self.cw_rset, view=view, context='navbottom')
        if components:
            self.w(u'<div id="contentfooter">')
            for comp in components:
                comp.render(w=self.w, view=view)
            self.w(u'</div>')


class LogFormTemplate(View):
    __regid__ = 'logform'
    __select__ = match_kwargs('id', 'klass')

    title = 'log in'

    def call(self, id, klass, title=True, message=True):
        self._cw.add_css('cubicweb.login.css')
        self.w(u'<div id="%s" class="%s">' % (id, klass))
        if title:
            stitle = self._cw.property_value('ui.site-title')
            if stitle:
                stitle = xml_escape(stitle)
            else:
                stitle = u'&#160;'
            self.w(u'<div id="loginTitle">%s</div>' % stitle)
        self.w(u'<div id="loginContent">\n')

        if message:
            self.display_message()
        if self._cw.vreg.config['auth-mode'] == 'http':
            # HTTP authentication
            pass
        else:
            # Cookie authentication
            self.login_form(id)
        self.w(u'</div></div>\n')

    def display_message(self):
        message = self._cw.message
        if message:
            self.w(u'<div class="simpleMessage">%s</div>\n' % message)

    def login_form(self, id):
        _ = self._cw._
        # XXX turn into a form
        self.w(u'<form method="post" action="%s" id="login_form">\n'
               % xml_escape(login_form_url(self._cw.vreg.config, self._cw)))
        self.w(u'<table>\n')
        self.add_fields()
        self.w(u'<tr>\n')
        self.w(u'<td>&#160;</td><td><input type="submit" class="loginButton right" value="%s" />\n</td>' % _('log in'))
        self.w(u'</tr>\n')
        self.w(u'</table>\n')
        self.w(u'</form>\n')
        self._cw.html_headers.add_onload('jQuery("#__login:visible").focus()')

    def add_fields(self):
        msg = (self._cw.vreg.config['allow-email-login'] and _('login or email')) or _('login')
        self.add_field('__login', msg, 'text')
        self.add_field('__password', self._cw._('password'), 'password')

    def add_field(self, name, label, inputtype):
        self.w(u'<tr>\n')
        self.w(u'<td><label for="%s" >%s</label></td>' % (name, label))
        self.w(u'<td><input name="%s" id="%s" class="data" type="%s" /></td>\n' %
               (name, name, inputtype))
        self.w(u'</tr>\n')


def login_form_url(config, req):
    if req.https:
        return req.url()
    if config.get('https-url'):
        return req.url().replace(req.base_url(), config['https-url'])
    return req.url()
