"""Bases HTML components:

* the rql input form
* the logged user link
* the workflow history section for workflowable objects

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from rql import parse

from cubicweb import Unauthorized
from cubicweb.common.uilib import html_escape, toggle_action
from cubicweb.common.selectors import yes_selector
from cubicweb.schema import display_name
from cubicweb.common.selectors import (chainfirst, multitype_selector,
                                    req_form_params_selector)

from cubicweb.web.htmlwidgets import MenuWidget, PopupBoxMenu, BoxSeparator, BoxLink
from cubicweb.web.component import (SingletonVComponent, EntityVComponent, 
                                 RelatedObjectsVComponent)

_ = unicode


class RQLInputForm(SingletonVComponent):
    """build the rql input form, usually displayed in the header"""
    id = 'rqlinput'
    visible = False
       
    def call(self, view=None):
        if hasattr(view, 'filter_box_context_info'):
            rset = view.filter_box_context_info()[0]
        else:
            rset = self.rset
        # display multilines query as one line
        rql = rset is not None and rset.printable_rql(encoded=False) or self.req.form.get('rql', '')
        rql = rql.replace(u"\n", u" ")
        req = self.req
        self.w(u'''<div id="rqlinput" class="%s">
          <form action="%s">
<fieldset>
<input type="text" id="rql" name="rql" value="%s"  title="%s" tabindex="%s" accesskey="q" class="searchField" />
<input type="submit" value="%s" class="searchButton" tabindex="%s" />
</fieldset>
''' % (not self.propval('visible') and 'hidden' or '', 
       self.build_url('view'), html_escape(rql), req._('full text or RQL query'), req.next_tabindex(),
       req._('search'), req.next_tabindex()))
        if self.req.search_state[0] != 'normal':
            self.w(u'<input type="hidden" name="__mode" value="%s"/>'
                   % ':'.join(req.search_state[1]))
        self.w(u'</form></div>')


class ApplLogo(SingletonVComponent):
    """build the application logo, usually displayed in the header"""
    id = 'logo'
    site_wide = True # don't want user to hide this component using an eproperty
    def call(self):
        self.w(u'<a href="%s"><img class="logo" src="%s" alt="logo"/></a>'
               % (self.req.base_url(), self.req.external_resource('LOGO')))


class ApplHelp(SingletonVComponent):
    """build the help button, usually displayed in the header"""
    id = 'help'
    def call(self):
        self.w(u'<a href="%s" class="help" title="%s">&nbsp;</a>'
               % (self.build_url(_restpath='doc/main'),
                  self.req._(u'help'),))


class UserLink(SingletonVComponent):
    """if the user is the anonymous user, build a link to login
    else a link to the connected user object with a loggout link
    """
    id = 'loggeduserlink'
    site_wide = True # don't want user to hide this component using an eproperty

    def call(self):
        if not self.req.cnx.anonymous_connection:
            # display useractions and siteactions
            actions = self.vreg.possible_actions(self.req, self.rset)
            box = MenuWidget('', 'userActionsBox', _class='', islist=False)
            menu = PopupBoxMenu(self.req.user.login, isitem=False)
            box.append(menu)
            for action in actions.get('useractions', ()):
                menu.append(BoxLink(action.url(), self.req._(action.title),
                                    action.html_class()))
            if actions.get('useractions') and actions.get('siteactions'):
                menu.append(BoxSeparator())
            for action in actions.get('siteactions', ()):
                menu.append(BoxLink(action.url(), self.req._(action.title),
                                    action.html_class()))
            box.render(w=self.w)
        else:
            self.anon_user_link()
            
    def anon_user_link(self):
        if self.config['auth-mode'] == 'cookie':
            self.w(self.req._('anonymous'))
            self.w(u'''&nbsp;[<a class="logout" href="javascript: popupLoginBox();">%s</a>]'''
                   % (self.req._('i18n_login_popup')))
        else:
            self.w(self.req._('anonymous'))
            self.w(u'&nbsp;[<a class="logout" href="%s">%s</a>]'
                   % (self.build_url('login'), self.req._('login')))


class ApplicationMessage(SingletonVComponent):
    """display application's messages given using the __message parameter
    into a special div section
    """
    __selectors__ = yes_selector,
    id = 'applmessages'
    site_wide = True # don't want user to hide this component using an eproperty

    def call(self):
        msgs = [msg for msg in (self.req.get_shared_data('sources_error', pop=True),
                                self.req.message) if msg]
        self.w(u'<div id="appMsg" onclick="%s" class="%s">\n' %
               (toggle_action('appMsg'), (msgs and ' ' or 'hidden')))
        for msg in msgs:
            self.w(u'<div class="message" id="%s">%s</div>' % (
                self.div_id(), msg))
        self.w(u'</div>')


class WFHistoryVComponent(EntityVComponent):
    """display the workflow history for entities supporting it"""
    id = 'wfhistory'
    accepts = ('Any',)
    context = 'navcontentbottom'
    rtype = 'wf_info_for'
    target = 'subject'
    title = _('Workflow history')

    def call(self, view=None):
        _ = self.req._
        eid = self.rset[0][0]
        sel = 'Any FS,TS,WF,D'
        rql = ' ORDERBY D DESC WHERE WF wf_info_for X,'\
              'WF from_state FS, WF to_state TS, WF comment C,'\
              'WF creation_date D'
        if self.vreg.schema.eschema('EUser').has_perm(self.req, 'read'):
            sel += ',U,C'
            rql += ', WF owned_by U?'
            displaycols = range(5)
            headers = (_('from_state'), _('to_state'), _('comment'), _('date'),
                       _('EUser'))            
        else:
            sel += ',C'
            displaycols = range(4)
            headers = (_('from_state'), _('to_state'), _('comment'), _('date'))
        rql = '%s %s, X eid %%(x)s' % (sel, rql)
        try:
            rset = self.req.execute(rql, {'x': eid}, 'x')
        except Unauthorized:
            return
        if rset:
            self.wview('table', rset, title=_(self.title), displayactions=False,
                       displaycols=displaycols, headers=headers)


class ApplicationName(SingletonVComponent):
    """display the application name"""
    id = 'appliname'

    def call(self):
        self.w(u'<span id="appliName"><a href="%s">%s</a></span>' % (self.req.base_url(),
                                                         self.req.property_value('ui.site-title')))
        

class SeeAlsoVComponent(RelatedObjectsVComponent):
    """display any entity's see also"""
    id = 'seealso'
    context = 'navcontentbottom'
    rtype = 'see_also'
    target = 'object'
    order = 40
    # register msg not generated since no entity use see_also in cubicweb itself
    title = _('contentnavigation_seealso')
    help = _('contentnavigation_seealso_description')

    
class EtypeRestrictionComponent(SingletonVComponent):
    """displays the list of entity types contained in the resultset
    to be able to filter accordingly.
    """
    id = 'etypenavigation'
    __select__ = classmethod(chainfirst(multitype_selector, req_form_params_selector))
    form_params = ('__restrtype', '__restrtypes', '__restrrql')
    visible = False # disabled by default
    
    def call(self):
        _ = self.req._
        self.w(u'<div id="etyperestriction">')
        restrtype = self.req.form.get('__restrtype')
        restrtypes = self.req.form.get('__restrtypes', '').split(',')
        restrrql = self.req.form.get('__restrrql')
        if not restrrql:
            rqlst = self.rset.syntax_tree()
            restrrql = rqlst.as_string(self.req.encoding, self.rset.args)
            restrtypes = self.rset.column_types(0)
        else:
            rqlst = parse(restrrql)
        html = []
        on_etype = False
        etypes = sorted((display_name(self.req, etype).capitalize(), etype)
                        for etype in restrtypes)
        for elabel, etype in etypes:
            if etype == restrtype:
                html.append(u'<span class="selected">%s</span>' % elabel)
                on_etype = True
            else:
                rqlst.save_state()
                for select in rqlst.children:
                    select.add_type_restriction(select.selection[0], etype)
                newrql = rqlst.as_string(self.req.encoding, self.rset.args)
                url = self.build_url(rql=newrql, __restrrql=restrrql,
                                     __restrtype=etype, __restrtypes=','.join(restrtypes))
                html.append(u'<span><a href="%s">%s</a></span>' % (
                        html_escape(url), elabel))
                rqlst.recover()
        if on_etype:
            url = self.build_url(rql=restrrql)
            html.insert(0, u'<span><a href="%s">%s</a></span>' % (
                    url, _('Any')))
        else:
            html.insert(0, u'<span class="selected">%s</span>' % _('Any'))
        self.w(u'&nbsp;|&nbsp;'.join(html))
        self.w(u'</div>')
        
