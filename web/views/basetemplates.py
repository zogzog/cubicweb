# -*- coding: utf-8 -*-
"""default templates for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.vregistry import objectify_selector
from cubicweb.selectors import match_kwargs
from cubicweb.view import View, MainTemplate, NOINDEX, NOFOLLOW
from cubicweb.utils import make_uid, UStringIO

# main templates ##############################################################

class LogInOutTemplate(MainTemplate):

    def call(self):
        self.set_request_content_type()
        w = self.w
        self.write_doctype()
        self.template_header('text/html', self.req._('login_action'))
        w(u'<body>\n')
        self.content(w)
        w(u'</body>')

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        w = self.whead
        # explictly close the <base> tag to avoid IE 6 bugs while browsing DOM
        w(u'<base href="%s"></base>' % html_escape(self.req.base_url()))
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self.req.encoding))
        w(NOINDEX)
        w(NOFOLLOW)
        w(u'\n'.join(additional_headers) + u'\n')
        self.wview('htmlheader', rset=self.rset)
        w(u'<title>%s</title>\n' % html_escape(page_title))


class LogInTemplate(LogInOutTemplate):
    id = 'login'
    title = 'log in'

    def content(self, w):
        self.wview('logform', rset=self.rset, id='loginBox', klass='')


class LoggedOutTemplate(LogInOutTemplate):
    id = 'loggedout'
    title = 'logged out'

    def content(self, w):
        # FIXME Deprecated code ?
        msg = self.req._('you have been logged out')
        w(u'<h2>%s</h2>\n' % msg)
        if self.config['anonymous-user']:
            indexurl = self.build_url('view', vid='index', __message=msg)
            w(u'<p><a href="%s">%s</a><p>' % (
                html_escape(indexurl),
                self.req._('go back to the index page')))

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
    id = 'main-template'
    __select__ = ~templatable_view()

    def call(self, view):
        view.set_request_content_type()
        view.set_stream()
        xhtml_wrap = (self.req.form.has_key('__notemplate') and view.templatable
                      and view.content_type == self.req.html_content_type())
        if xhtml_wrap:
            view.w(u'<?xml version="1.0"?>\n' + self.doctype)
            view.w(u'<div xmlns="http://www.w3.org/1999/xhtml" xmlns:cubicweb="http://www.logilab.org/2008/cubicweb">')
        # have to replace our unicode stream using view's binary stream
        view.render()
        if xhtml_wrap:
            view.w(u'</div>')
        self._stream = view._stream


class TheMainTemplate(MainTemplate):
    """default main template :

    - call header / footer templates
    """
    id = 'main-template'
    __select__ = templatable_view()

    def call(self, view):
        self.set_request_content_type()
        self.template_header(self.content_type, view)
        w = self.w
        w(u'<div id="pageContent">\n')
        vtitle = self.req.form.get('vtitle')
        if vtitle:
            w(u'<h1 class="vtitle">%s</h1>\n' % html_escape(vtitle))
        # display entity type restriction component
        etypefilter = self.vreg.select_component('etypenavigation',
                                                 self.req, self.rset)
        if etypefilter and etypefilter.propval('visible'):
            etypefilter.render(w=w)
        self.nav_html = UStringIO()
        if view and view.need_navigation:
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
        lang = self.req.lang
        self.write_doctype()
        w(u'<base href="%s" />' % html_escape(self.req.base_url()))
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self.req.encoding))
        w(u'\n'.join(additional_headers) + u'\n')
        self.wview('htmlheader', rset=self.rset)
        if page_title:
            w(u'<title>%s</title>\n' % html_escape(page_title))

    def template_body_header(self, view):
        w = self.w
        w(u'<body>\n')
        self.wview('header', rset=self.rset, view=view)
        w(u'<div id="page"><table width="100%" border="0" id="mainLayout"><tr>\n')
        self.nav_column(view, 'left')
        w(u'<td id="contentcol">\n')
        rqlcomp = self.vreg.select_component('rqlinput', self.req, self.rset)
        if rqlcomp:
            rqlcomp.render(w=self.w, view=view)
        msgcomp = self.vreg.select_component('applmessages', self.req, self.rset)
        if msgcomp:
            msgcomp.render(w=self.w)
        self.content_header(view)

    def template_footer(self, view=None):
        self.content_footer(view)
        self.w(u'</td>\n')
        self.nav_column(view, 'right')
        self.w(u'</tr></table></div>\n')
        self.wview('footer', rset=self.rset)
        self.w(u'</body>')

    def nav_column(self, view, context):
        boxes = list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                 view=view, context=context))
        if boxes:
            self.w(u'<td class="navcol"><div class="navboxes">\n')
            for box in boxes:
                box.render(w=self.w, view=view)
            self.w(u'</div></td>\n')

    def content_header(self, view=None):
        """by default, display informal messages in content header"""
        self.wview('contentheader', rset=self.rset, view=view)

    def content_footer(self, view=None):
        self.wview('contentfooter', rset=self.rset, view=view)


class ErrorTemplate(TheMainTemplate):
    """fallback template if an internal error occured during displaying the
    main template. This template may be called for authentication error,
    which means that req.cnx and req.user may not be set.
    """
    id = 'error-template'

    def call(self):
        """display an unexpected error"""
        self.set_request_content_type()
        self.req.reset_headers()
        view = self.vreg.select_view('error', self.req, self.rset)
        self.template_header(self.content_type, view, self.req._('an error occured'),
                             [NOINDEX, NOFOLLOW])
        view.render(w=self.w)
        self.template_footer(view)

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        w = self.whead
        lang = self.req.lang
        self.write_doctype()
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self.req.encoding))
        w(u'\n'.join(additional_headers))
        self.wview('htmlheader', rset=self.rset)
        w(u'<title>%s</title>\n' % html_escape(page_title))
        self.w(u'<body>\n')

    def template_footer(self, view=None):
        self.w(u'</body>')


class SimpleMainTemplate(TheMainTemplate):

    id = 'main-no-top'

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        page_title = page_title or view.page_title()
        additional_headers = additional_headers or view.html_headers()
        whead = self.whead
        lang = self.req.lang
        self.write_doctype()
        whead(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
              % (content_type, self.req.encoding))
        whead(u'\n'.join(additional_headers) + u'\n')
        self.wview('htmlheader', rset=self.rset)
        w = self.w
        w(u'<title>%s</title>\n' % html_escape(page_title))
        w(u'<body>\n')
        w(u'<div id="page">')
        w(u'<table width="100%" height="100%" border="0"><tr>\n')
        w(u'<td class="navcol">\n')
        self.topleft_header()
        boxes = list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                 view=view, context='left'))
        if boxes:
            w(u'<div class="navboxes">\n')
            for box in boxes:
                box.render(w=w)
            self.w(u'</div>\n')
        w(u'</td>')
        w(u'<td id="contentcol" rowspan="2">')
        w(u'<div id="pageContent">\n')
        vtitle = self.req.form.get('vtitle')
        if vtitle:
            w(u'<h1 class="vtitle">%s</h1>' % html_escape(vtitle))

    def topleft_header(self):
        self.w(u'<table id="header"><tr>\n')
        self.w(u'<td>')
        self.vreg.select_component('logo', self.req, self.rset).render(w=self.w)
        self.w(u'</td>\n')
        self.w(u'</tr></table>\n')

# page parts templates ########################################################

class HTMLHeader(View):
    """default html headers"""
    id = 'htmlheader'

    def call(self, **kwargs):
        self.favicon()
        self.stylesheets()
        self.javascripts()
        self.alternates()
        self.pageid()

    def favicon(self):
        favicon = self.req.external_resource('FAVICON', None)
        if favicon:
            self.whead(u'<link rel="shortcut icon" href="%s"/>\n' % favicon)

    def stylesheets(self):
        req = self.req
        add_css = req.add_css
        for css in req.external_resource('STYLESHEETS'):
            add_css(css, localfile=False)
        for css in req.external_resource('STYLESHEETS_PRINT'):
            add_css(css, u'print', localfile=False)
        for css in req.external_resource('IE_STYLESHEETS'):
            add_css(css, localfile=False, ieonly=True)

    def javascripts(self):
        for jscript in self.req.external_resource('JAVASCRIPTS'):
            self.req.add_js(jscript, localfile=False)

    def alternates(self):
        urlgetter = self.vreg.select_component('rss_feed_url', self.req, self.rset)
        if urlgetter is not None:
            url = urlgetter.feed_url()
            self.whead(u'<link rel="alternate" type="application/rss+xml" title="RSS feed" href="%s"/>\n'
                       %  html_escape(url))

    def pageid(self):
        req = self.req
        pid = make_uid(id(req))
        req.pageid = pid
        req.html_headers.define_var('pageid', pid)


class HTMLPageHeader(View):
    """default html page header"""
    id = 'header'

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
        self.vreg.select_component('logo', self.req, self.rset).render(w=self.w)
        self.w(u'</td>\n')
        # appliname and breadcrumbs
        self.w(u'<td id="headtext">')
        comp = self.vreg.select_component('appliname', self.req, self.rset)
        if comp and comp.propval('visible'):
            comp.render(w=self.w)
        comp = self.vreg.select_component('breadcrumbs', self.req, self.rset, view=view)
        if comp and comp.propval('visible'):
            comp.render(w=self.w, view=view)
        self.w(u'</td>')
        # logged user and help
        self.w(u'<td>\n')
        comp = self.vreg.select_component('loggeduserlink', self.req, self.rset)
        comp.render(w=self.w)
        self.w(u'</td><td>')
        helpcomp = self.vreg.select_component('help', self.req, self.rset)
        if helpcomp: # may not be available if Card is not defined in the schema
            helpcomp.render(w=self.w)
        self.w(u'</td>')
        # lastcolumn
        self.w(u'<td id="lastcolumn">')
        self.w(u'</td>\n')
        self.w(u'</tr></table>\n')
        self.wview('logform', rset=self.rset, id='popupLoginBox', klass='hidden',
                   title=False, message=False)

    def state_header(self):
        state = self.req.search_state
        if state[0] == 'normal':
            return
        _ = self.req._
        value = self.view('oneline', self.req.eid_rset(state[1][1]))
        msg = ' '.join((_("searching for"),
                        display_name(self.req, state[1][3]),
                        _("to associate with"), value,
                        _("by relation"), '"',
                        display_name(self.req, state[1][2], state[1][0]),
                        '"'))
        return self.w(u'<div class="stateMessage">%s</div>' % msg)



class HTMLPageFooter(View):
    """default html page footer: include logo if any, and close the HTML body
    """
    id = 'footer'

    def call(self, **kwargs):
        req = self.req
        self.w(u'<div class="footer">')
        # XXX Take object from the registry if in there? would be
        #     better anyway
        from cubicweb.web.views.wdoc import ChangeLogView
        self.w(u'<a href="%s">%s</a> | ' % (req.build_url('changelog'),
                                            req._(ChangeLogView.title).lower()))
        self.w(u'<a href="%s">%s</a> | ' % (req.build_url('doc/about'),
                                            req._('about this site')))
        self.w(u'© 2001-2009 <a href="http://www.logilab.fr">Logilab S.A.</a>')
        self.w(u'</div>')


class HTMLContentHeader(View):
    """default html page content header:
    * include message component if selectable for this request
    * include selectable content navigation components
    """
    id = 'contentheader'

    def call(self, view, **kwargs):
        """by default, display informal messages in content header"""
        components = self.vreg.possible_vobjects('contentnavigation',
                                                 self.req, self.rset,
                                                 view=view, context='navtop')
        if components:
            self.w(u'<div id="contentheader">')
            for comp in components:
                comp.render(w=self.w, view=view)
            self.w(u'</div><div class="clear"></div>')


class HTMLContentFooter(View):
    """default html page content footer: include selectable content navigation
    components
    """
    id = 'contentfooter'

    def call(self, view, **kwargs):
        components = self.vreg.possible_vobjects('contentnavigation',
                                                 self.req, self.rset,
                                                 view=view, context='navbottom')
        if components:
            self.w(u'<div id="contentfooter">')
            for comp in components:
                comp.render(w=self.w, view=view)
            self.w(u'</div>')


class LogFormTemplate(View):
    id = 'logform'
    __select__ = match_kwargs('id', 'klass')

    title = 'log in'

    def call(self, id, klass, title=True, message=True):
        self.req.add_css('cubicweb.login.css')
        self.w(u'<div id="%s" class="%s">' % (id, klass))
        if title:
            self.w(u'<div id="loginTitle">%s</div>'
                   % self.req.property_value('ui.site-title'))
        self.w(u'<div id="loginContent">\n')

        if message:
            self.display_message()
        if self.config['auth-mode'] == 'http':
            # HTTP authentication
            pass
        else:
            # Cookie authentication
            self.login_form(id)
        self.w(u'</div></div>\n')

    def display_message(self):
        message = self.req.message
        if message:
            self.w(u'<div class="simpleMessage">%s</div>\n' % message)

    def login_form(self, id):
        _ = self.req._
        self.w(u'<form method="post" action="%s" id="login_form">\n'
               % html_escape(login_form_url(self.config, self.req)))
        self.w(u'<table>\n')
        self.w(u'<tr>\n')
        msg = (self.config['allow-email-login'] and _('login or email')) or _('login')
        self.w(u'<td><label for="__login">%s</label></td>' % msg)
        self.w(u'<td><input name="__login" id="__login" class="data" type="text" /></td>')
        self.w(u'</tr><tr>\n')
        self.w(u'<td><label for="__password" >%s</label></td>' % _('password'))
        self.w(u'<td><input name="__password" id="__password" class="data" type="password" /></td>\n')
        self.w(u'</tr><tr>\n')
        self.w(u'<td>&nbsp;</td><td><input type="submit" class="loginButton right" value="%s" />\n</td>' % _('log in'))
        self.w(u'</tr>\n')
        self.w(u'</table>\n')
        self.w(u'</form>\n')
        self.req.html_headers.add_onload('jQuery("#__login:visible").focus()')


def login_form_url(config, req):
    if req.https:
        return req.url()
    if config.get('https-url'):
        return req.url().replace(req.base_url(), config['https-url'])
    return req.url()


## vregistry registration callback ############################################
def registration_callback(vreg):
    vreg.register_all(globals().values(), modname=__name__)
