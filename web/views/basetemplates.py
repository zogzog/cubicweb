# -*- coding: utf-8 -*-
"""default templates for CubicWeb web client

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb import NoSelectableObject, ObjectNotFound
from cubicweb.common.view import Template, MainTemplate,  NOINDEX, NOFOLLOW
from cubicweb.common.utils import make_uid

from cubicweb.web.views.baseviews import vid_from_rset

# main templates ##############################################################


class LogInOutTemplate(MainTemplate):
    
    def call(self):
        self.set_request_content_type()
        w = self.w
        self.write_doctype()
        lang = self.req.lang
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
        self.template('htmlheader', rset=self.rset)
        w(u'<title>%s</title>\n' % html_escape(page_title))
        

class LogInTemplate(LogInOutTemplate):
    id = 'login'
    title = 'log in'

    def content(self, w):
        self.template('logform', rset=self.rset, id='loginBox', klass='')
        

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

        
class TheMainTemplate(MainTemplate):
    """default main template :
    
    - call header / footer templates
    - build result set
    - guess and call an appropriate view through the view manager
    """
    id = 'main'

    def _select_view_and_rset(self):
        req = self.req
        if self.rset is None and not hasattr(req, '_rql_processed'):
            req._rql_processed = True
            rset = self.process_rql(req.form.get('rql'))
        else:
            rset = self.rset
        # handle special "method" param when necessary
        # XXX this should probably not be in the template (controller ?), however:
        #     * we need to have the displayed rset
        #     * we don't want to handle it in each view
        if rset and rset.rowcount == 1 and '__method' in req.form:
            entity = rset.get_entity(0, 0)
            try:
                method = getattr(entity, req.form.pop('__method'))
                method()
            except Exception, ex:
                self.exception('while handling __method')
                req.set_message(req._("error while handling __method: %s") % req._(ex))
        vid = req.form.get('vid') or vid_from_rset(req, rset, self.schema)
        try:
            view = self.vreg.select_view(vid, req, rset)
        except ObjectNotFound:
            self.warning("the view %s could not be found", vid)
            req.set_message(req._("The view %s could not be found") % vid)
            vid = vid_from_rset(req, rset, self.schema)
            view = self.vreg.select_view(vid, req, rset)
        except NoSelectableObject:
            if rset:
                req.set_message(req._("The view %s can not be applied to this query") % vid)
            else:
                req.set_message(req._("You have no access to this view or it's not applyable to current data"))
            self.warning("the view %s can not be applied to this query", vid)
            vid = vid_from_rset(req, rset, self.schema)
            view = self.vreg.select_view(vid, req, rset)
        return view, rset
    
    def call(self):
        view, rset = self._select_view_and_rset()
        req = self.req
        # update breadcrumps **before** validating cache, unless the view
        # specifies explicitly it should not be added to breadcrumb or the
        # view is a binary view
        if view.add_to_breadcrumbs and not view.binary:
            req.update_breadcrumbs()
        view.set_http_cache_headers()
        req.validate_cache()
        with_templates = not view.binary and view.templatable and \
                         not req.form.has_key('__notemplate')
        if not with_templates:
            view.set_request_content_type()
            self.set_stream(templatable=False)
        else:
            self.set_request_content_type()
            content_type = self.content_type
            self.template_header(content_type, view)
        if view.binary:
            # have to replace our unicode stream using view's binary stream
            view.dispatch()
            assert self._stream, 'duh, template used as a sub-view ?? (%s)' % self._stream
            self._stream = view._stream
        else:
            view.dispatch(w=self.w)
        if with_templates:
            self.template_footer(view)

            
    def process_rql(self, rql):
        """execute rql if specified"""
        if rql:
            self.ensure_ro_rql(rql)
            if not isinstance(rql, unicode):
                rql = unicode(rql, self.req.encoding)
            pp = self.vreg.select_component('magicsearch', self.req)
            self.rset = pp.process_query(rql, self.req)
            return self.rset
        return None

    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        page_title = page_title or view.page_title()
        additional_headers = additional_headers or view.html_headers()
        self.template_html_header(content_type, page_title, additional_headers)
        self.template_body_header(view)
        # display entity type restriction component
        etypefilter = self.vreg.select_component('etypenavigation',
                                                 self.req, self.rset)
        if etypefilter and etypefilter.propval('visible'):
            etypefilter.dispatch(w=self.w)
        self.pagination(self.req, self.rset, self.w, not (view and view.need_navigation))
        self.w(u'<div id="contentmain">\n')
    
    def template_html_header(self, content_type, page_title, additional_headers=()):
        w = self.whead
        lang = self.req.lang
        self.write_doctype()
        w(u'<base href="%s" />' % html_escape(self.req.base_url()))
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self.req.encoding))
        w(u'\n'.join(additional_headers) + u'\n')
        self.template('htmlheader', rset=self.rset)
        if page_title:
            w(u'<title>%s</title>\n' % html_escape(page_title))

    def template_body_header(self, view):
        w = self.w
        w(u'<body>\n')
        self.template('header', rset=self.rset, view=view)
        w(u'<div id="page"><table width="100%" border="0" id="mainLayout"><tr>\n')
        self.nav_column(view, 'left')
        w(u'<td id="contentcol">\n')
        rqlcomp = self.vreg.select_component('rqlinput', self.req, self.rset)
        if rqlcomp:
            rqlcomp.dispatch(w=self.w, view=view)
        msgcomp = self.vreg.select_component('applmessages', self.req, self.rset)
        if msgcomp:
            msgcomp.dispatch(w=self.w)
        self.content_header(view)
        w(u'<div id="pageContent">\n')
        vtitle = self.req.form.get('vtitle')
        if vtitle:
            w(u'<h1 class="vtitle">%s</h1>\n' % html_escape(vtitle))
            
    def template_footer(self, view=None):
        self.w(u'</div>\n') # close id=contentmain
        self.w(u'</div>\n') # closes id=pageContent
        self.content_footer(view)
        self.w(u'</td>\n')
        self.nav_column(view, 'right')
        self.w(u'</tr></table></div>\n')
        self.template('footer', rset=self.rset)
        self.w(u'</body>')

    def nav_column(self, view, context):
        boxes = list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                 view=view, context=context))
        if boxes:
            self.w(u'<td class="navcol"><div class="navboxes">\n')
            for box in boxes:
                box.dispatch(w=self.w, view=view)
            self.w(u'</div></td>\n')

    def content_header(self, view=None):
        """by default, display informal messages in content header"""
        self.template('contentheader', rset=self.rset, view=view)
            
    def content_footer(self, view=None):
        self.template('contentfooter', rset=self.rset, view=view)


class ErrorTemplate(TheMainTemplate):
    """fallback template if an internal error occured during displaying the
    main template. This template may be called for authentication error,
    which means that req.cnx and req.user may not be set.
    """
    id = 'error'
    
    def call(self):
        """display an unexpected error"""
        self.set_request_content_type()
        self.req.reset_headers()
        view = self.vreg.select_view('error', self.req, self.rset)
        self.template_header(self.content_type, view, self.req._('an error occured'),
                             [NOINDEX, NOFOLLOW])
        view.dispatch(w=self.w)
        self.template_footer(view)
    
    def template_header(self, content_type, view=None, page_title='', additional_headers=()):
        w = self.whead
        lang = self.req.lang
        self.write_doctype()
        w(u'<meta http-equiv="content-type" content="%s; charset=%s"/>\n'
          % (content_type, self.req.encoding))
        w(u'\n'.join(additional_headers))
        self.template('htmlheader', rset=self.rset)
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
        self.template('htmlheader', rset=self.rset)
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
                box.dispatch(w=w)
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
        self.vreg.select_component('logo', self.req, self.rset).dispatch(w=self.w)
        self.w(u'</td>\n')
        self.w(u'</tr></table>\n')

# page parts templates ########################################################

class HTMLHeader(Template):
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
        req.html_headers.define_var('pageid', pid);


class HTMLPageHeader(Template):
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
        self.vreg.select_component('logo', self.req, self.rset).dispatch(w=self.w)
        self.w(u'</td>\n')
        # appliname and breadcrumbs
        self.w(u'<td id="headtext">')
        comp = self.vreg.select_component('appliname', self.req, self.rset)
        if comp and comp.propval('visible'):
            comp.dispatch(w=self.w)
        comp = self.vreg.select_component('breadcrumbs', self.req, self.rset, view=view)
        if comp and comp.propval('visible'):
            comp.dispatch(w=self.w, view=view)
        self.w(u'</td>')
        # logged user and help
        self.w(u'<td>\n')
        comp = self.vreg.select_component('loggeduserlink', self.req, self.rset)
        comp.dispatch(w=self.w)
        self.w(u'</td><td>')
        helpcomp = self.vreg.select_component('help', self.req, self.rset)
        if helpcomp: # may not be available if Card is not defined in the schema
            helpcomp.dispatch(w=self.w)
        self.w(u'</td>')
        # lastcolumn
        self.w(u'<td id="lastcolumn">')
        self.w(u'</td>\n')
        self.w(u'</tr></table>\n')
        self.template('logform', rset=self.rset, id='popupLoginBox', klass='hidden',
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



class HTMLPageFooter(Template):
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
        self.w(u'© 2001-2008 <a href="http://www.logilab.fr">Logilab S.A.</a>')
        self.w(u'</div>')


class HTMLContentHeader(Template):
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
                comp.dispatch(w=self.w, view=view)
            self.w(u'</div><div class="clear"></div>')


class HTMLContentFooter(Template):
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
                comp.dispatch(w=self.w, view=view)
            self.w(u'</div>')


class LogFormTemplate(Template):
    id = 'logform'
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
        self.w(u'<td><label for="__login">%s</label></td>' % _('login'))
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

