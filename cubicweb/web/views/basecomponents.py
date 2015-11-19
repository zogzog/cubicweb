# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Bases HTML components:

* the rql input form
* the logged user link
"""

from cubicweb import _

from logilab.mtconverter import xml_escape
from logilab.common.registry import yes
from logilab.common.deprecation import class_renamed
from rql import parse

from cubicweb.predicates import (match_form_params, match_context,
                                 multi_etypes_rset, configuration_values,
                                 anonymous_user, authenticated_user)
from cubicweb.schema import display_name
from cubicweb.utils import wrap_on_write
from cubicweb.uilib import toggle_action
from cubicweb.web import component
from cubicweb.web.htmlwidgets import MenuWidget, PopupBoxMenu

VISIBLE_PROP_DEF = {
    _('visible'):  dict(type='Boolean', default=True,
                        help=_('display the component or not')),
    }

class RQLInputForm(component.Component):
    """build the rql input form, usually displayed in the header"""
    __regid__ = 'rqlinput'
    cw_property_defs = VISIBLE_PROP_DEF
    visible = False

    def call(self, view=None):
        req = self._cw
        if hasattr(view, 'filter_box_context_info'):
            rset = view.filter_box_context_info()[0]
        else:
            rset = self.cw_rset
        # display multilines query as one line
        rql = rset is not None and rset.printable_rql() or req.form.get('rql', '')
        rql = rql.replace(u"\n", u" ")
        rql_suggestion_comp = self._cw.vreg['components'].select_or_none('rql.suggestions', self._cw)
        if rql_suggestion_comp is not None:
            # enable autocomplete feature only if the rql
            # suggestions builder is available
            self._cw.add_css('jquery.ui.css')
            self._cw.add_js(('cubicweb.ajax.js', 'jquery.ui.js'))
            self._cw.add_onload('$("#rql").autocomplete({source: "%s"});'
                                % (req.build_url('json', fname='rql_suggest')))
        self.w(u'''<div id="rqlinput" class="%s"><form action="%s"><fieldset>
<input type="text" id="rql" name="rql" value="%s"  title="%s" accesskey="q" class="searchField" />
''' % (not self.cw_propval('visible') and 'hidden' or '',
       req.build_url('view'), xml_escape(rql), req._('full text or RQL query')))
        if req.search_state[0] != 'normal':
            self.w(u'<input type="hidden" name="__mode" value="%s"/>'
                   % ':'.join(req.search_state[1]))
        self.w(u'</fieldset></form></div>')



class HeaderComponent(component.CtxComponent): # XXX rename properly along with related context
    """if the user is the anonymous user, build a link to login else display a menu
    with user'action (preference, logout, etc...)
    """
    __abstract__ = True
    cw_property_defs = component.override_ctx(
        component.CtxComponent,
        vocabulary=['header-center', 'header-left', 'header-right', ])
    # don't want user to hide this component using an cwproperty
    site_wide = True
    context = _('header-center')


class ApplLogo(HeaderComponent):
    """build the instance logo, usually displayed in the header"""
    __regid__ = 'logo'
    __select__ = yes() # no need for a cnx
    order = -1
    context = _('header-left')

    def render(self, w):
        w(u'<a id="logo" href="%s"></a>' % self._cw.base_url())


class ApplicationName(HeaderComponent):
    """display the instance name"""
    __regid__ = 'appliname'

    # XXX support kwargs for compat with other components which gets the view as
    # argument
    def render(self, w, **kwargs):
        title = self._cw.property_value('ui.site-title')
        if title:
            w(u'<span id="appliName"><a href="%s">%s</a></span>' % (
                self._cw.base_url(), xml_escape(title)))


class CookieLoginComponent(HeaderComponent):
    __regid__ = 'anonuserlink'
    __select__ = (HeaderComponent.__select__ & anonymous_user()
                  & configuration_values('auth-mode', 'cookie'))
    context = 'header-right'
    loginboxid = 'popupLoginBox'
    _html = u"""<a class="logout icon-login" title="%s" href="javascript:
cw.htmlhelpers.popupLoginBox('%s', '__login');">%s</a>"""

    def render(self, w):
        # XXX bw compat, though should warn about subclasses redefining call
        self.w = w
        self.call()

    def call(self):
        self._cw.add_css('cubicweb.pictograms.css')
        self.w(self._html % (self._cw._('login / password'),
                             self.loginboxid, self._cw._('i18n_login_popup')))
        self._cw.view('logform', rset=self.cw_rset, id=self.loginboxid,
                      klass='%s hidden' % self.loginboxid, title=False,
                      showmessage=False, w=self.w)


class HTTPLoginComponent(CookieLoginComponent):
    __select__ = (HeaderComponent.__select__ & anonymous_user()
                  & configuration_values('auth-mode', 'http'))

    def render(self, w):
        # this redirects to the 'login' controller which in turn
        # will raise a 401/Unauthorized
        req = self._cw
        w(u'[<a class="logout" title="%s" href="%s">%s</a>]'
          % (req._('login / password'), req.build_url('login'), req._('login')))


_UserLink = class_renamed('_UserLink', HeaderComponent)
AnonUserLink = class_renamed('AnonUserLink', CookieLoginComponent)
AnonUserLink.__abstract__ = True
AnonUserLink.__select__ &= yes(1)


class AnonUserStatusLink(HeaderComponent):
    __regid__ = 'userstatus'
    __select__ = anonymous_user()
    context = _('header-right')
    order = HeaderComponent.order - 10

    def render(self, w):
        pass

class AuthenticatedUserStatus(AnonUserStatusLink):
    __select__ = authenticated_user()

    def render(self, w):
        # display useractions and siteactions
        self._cw.add_css('cubicweb.pictograms.css')
        actions = self._cw.vreg['actions'].possible_actions(self._cw, rset=self.cw_rset,
                                                            view=self.cw_extra_kwargs['view'])
        box = MenuWidget('', 'userActionsBox', _class='', islist=False)
        menu = PopupBoxMenu(self._cw.user.login, isitem=False, link_class='icon-user')
        box.append(menu)
        for action in actions.get('useractions', ()):
            menu.append(self.action_link(action))
        if actions.get('useractions') and actions.get('siteactions'):
            menu.append(self.separator())
        for action in actions.get('siteactions', ()):
            menu.append(self.action_link(action))
        box.render(w=w)


class ApplicationMessage(component.Component):
    """display messages given using the __message/_cwmsgid parameter into a
    special div section
    """
    __select__ = yes()
    __regid__ = 'applmessages'
    # don't want user to hide this component using a cwproperty
    cw_property_defs = {}

    def call(self, msg=None):
        if msg is None:
            msg = self._cw.message # XXX don't call self._cw.message twice
        self.w(u'<div id="appMsg" onclick="%s" class="%s">\n' %
               (toggle_action('appMsg'), (msg and ' ' or 'hidden')))
        self.w(u'<div class="message" id="%s">%s</div>' % (self.domid, msg))
        self.w(u'</div>')


# contextual components ########################################################


class MetaDataComponent(component.EntityCtxComponent):
    __regid__ = 'metadata'
    context = 'navbottom'
    order = 1

    def render_body(self, w):
        self.entity.view('metadata', w=w)


class SectionLayout(component.Layout):
    __select__ = match_context('navtop', 'navbottom',
                               'navcontenttop', 'navcontentbottom')
    cssclass = 'section'

    def render(self, w):
        if self.init_rendering():
            view = self.cw_extra_kwargs['view']
            w(u'<div class="%s %s" id="%s">' % (self.cssclass, view.cssclass,
                                                view.domid))
            with wrap_on_write(w, '<h4>') as wow:
                view.render_title(wow)
            view.render_body(w)
            w(u'</div>\n')
