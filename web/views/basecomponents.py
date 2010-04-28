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
"""Bases HTML components:

* the rql input form
* the logged user link

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape
from rql import parse

from cubicweb.selectors import (yes, multi_etypes_rset, match_form_params,
                                anonymous_user, authenticated_user)
from cubicweb.schema import display_name
from cubicweb.uilib import toggle_action
from cubicweb.web import component
from cubicweb.web.htmlwidgets import (MenuWidget, PopupBoxMenu, BoxSeparator,
                                      BoxLink)

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
        if hasattr(view, 'filter_box_context_info'):
            rset = view.filter_box_context_info()[0]
        else:
            rset = self.cw_rset
        # display multilines query as one line
        rql = rset is not None and rset.printable_rql(encoded=False) or self._cw.form.get('rql', '')
        rql = rql.replace(u"\n", u" ")
        req = self._cw
        self.w(u'''<div id="rqlinput" class="%s">
          <form action="%s">
<fieldset>
<input type="text" id="rql" name="rql" value="%s"  title="%s" tabindex="%s" accesskey="q" class="searchField" />
<input type="submit" value="" class="rqlsubmit" tabindex="%s" />
</fieldset>
''' % (not self.cw_propval('visible') and 'hidden' or '',
       self._cw.build_url('view'), xml_escape(rql), req._('full text or RQL query'), req.next_tabindex(),
        req.next_tabindex()))
        if self._cw.search_state[0] != 'normal':
            self.w(u'<input type="hidden" name="__mode" value="%s"/>'
                   % ':'.join(req.search_state[1]))
        self.w(u'</form></div>')


class ApplLogo(component.Component):
    """build the instance logo, usually displayed in the header"""
    __regid__ = 'logo'
    cw_property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True

    def call(self):
        self.w(u'<a href="%s"><img class="logo" src="%s" alt="logo"/></a>'
               % (self._cw.base_url(), self._cw.external_resource('LOGO')))


class ApplHelp(component.Component):
    """build the help button, usually displayed in the header"""
    __regid__ = 'help'
    cw_property_defs = VISIBLE_PROP_DEF
    def call(self):
        self.w(u'<a href="%s" class="help" title="%s">&#160;</a>'
               % (self._cw.build_url(_restpath='doc/main'),
                  self._cw._(u'help'),))


class _UserLink(component.Component):
    """if the user is the anonymous user, build a link to login else display a menu
    with user'action (preference, logout, etc...)
    """
    cw_property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True
    __regid__ = 'loggeduserlink'


class AnonUserLink(_UserLink):
    __select__ = _UserLink.__select__ & anonymous_user()
    def call(self):
        if self._cw.vreg.config['auth-mode'] == 'cookie':
            self.w(self._cw._('anonymous'))
            self.w(u'''&#160;[<a class="logout" href="javascript: popupLoginBox();">%s</a>]'''
                   % (self._cw._('i18n_login_popup')))
        else:
            self.w(self._cw._('anonymous'))
            self.w(u'&#160;[<a class="logout" href="%s">%s</a>]'
                   % (self._cw.build_url('login'), self._cw._('login')))


class UserLink(_UserLink):
    __select__ = _UserLink.__select__ & authenticated_user()

    def call(self):
        # display useractions and siteactions
        actions = self._cw.vreg['actions'].possible_actions(self._cw, rset=self.cw_rset)
        box = MenuWidget('', 'userActionsBox', _class='', islist=False)
        menu = PopupBoxMenu(self._cw.user.login, isitem=False)
        box.append(menu)
        for action in actions.get('useractions', ()):
            menu.append(BoxLink(action.url(), self._cw._(action.title),
                                action.html_class()))
        if actions.get('useractions') and actions.get('siteactions'):
            menu.append(BoxSeparator())
        for action in actions.get('siteactions', ()):
            menu.append(BoxLink(action.url(), self._cw._(action.title),
                                action.html_class()))
        box.render(w=self.w)


class ApplicationMessage(component.Component):
    """display messages given using the __message parameter into a special div
    section
    """
    __select__ = yes()
    __regid__ = 'applmessages'
    # don't want user to hide this component using an cwproperty
    cw_property_defs = {}

    def call(self):
        msgs = [msg for msg in (self._cw.get_shared_data('sources_error', pop=True),
                                self._cw.message) if msg]
        self.w(u'<div id="appMsg" onclick="%s" class="%s">\n' %
               (toggle_action('appMsg'), (msgs and ' ' or 'hidden')))
        for msg in msgs:
            self.w(u'<div class="message" id="%s">%s</div>' % (
                self.div_id(), msg))
        self.w(u'</div>')


class ApplicationName(component.Component):
    """display the instance name"""
    __regid__ = 'appliname'
    cw_property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True

    def call(self):
        title = self._cw.property_value('ui.site-title')
        if title:
            self.w(u'<span id="appliName"><a href="%s">%s</a></span>' % (
                self._cw.base_url(), xml_escape(title)))


class SeeAlsoVComponent(component.RelatedObjectsVComponent):
    """display any entity's see also"""
    __regid__ = 'seealso'
    context = 'navcontentbottom'
    rtype = 'see_also'
    role = 'subject'
    order = 40
    # register msg not generated since no entity use see_also in cubicweb itself
    title = _('contentnavigation_seealso')
    help = _('contentnavigation_seealso_description')


class EtypeRestrictionComponent(component.Component):
    """displays the list of entity types contained in the resultset
    to be able to filter accordingly.
    """
    __regid__ = 'etypenavigation'
    __select__ = multi_etypes_rset() | match_form_params('__restrtype', '__restrtypes',
                                                       '__restrrql')
    cw_property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True
    visible = False # disabled by default

    def call(self):
        _ = self._cw._
        self.w(u'<div id="etyperestriction">')
        restrtype = self._cw.form.get('__restrtype')
        restrtypes = self._cw.form.get('__restrtypes', '').split(',')
        restrrql = self._cw.form.get('__restrrql')
        if not restrrql:
            rqlst = self.cw_rset.syntax_tree()
            restrrql = rqlst.as_string(self._cw.encoding, self.cw_rset.args)
            restrtypes = self.cw_rset.column_types(0)
        else:
            rqlst = parse(restrrql)
        html = []
        on_etype = False
        etypes = sorted((display_name(self._cw, etype).capitalize(), etype)
                        for etype in restrtypes)
        for elabel, etype in etypes:
            if etype == restrtype:
                html.append(u'<span class="selected">%s</span>' % elabel)
                on_etype = True
            else:
                rqlst.save_state()
                for select in rqlst.children:
                    select.add_type_restriction(select.selection[0], etype)
                newrql = rqlst.as_string(self._cw.encoding, self.cw_rset.args)
                url = self._cw.build_url(rql=newrql, __restrrql=restrrql,
                                         __restrtype=etype, __restrtypes=','.join(restrtypes))
                html.append(u'<span><a href="%s">%s</a></span>' % (
                        xml_escape(url), elabel))
                rqlst.recover()
        if on_etype:
            url = self._cw.build_url(rql=restrrql)
            html.insert(0, u'<span><a href="%s">%s</a></span>' % (
                    url, _('Any')))
        else:
            html.insert(0, u'<span class="selected">%s</span>' % _('Any'))
        self.w(u'&#160;|&#160;'.join(html))
        self.w(u'</div>')


class MetaDataComponent(component.EntityVComponent):
    __regid__ = 'metadata'
    context = 'navbottom'
    order = 1

    def cell_call(self, row, col, view=None):
        self.wview('metadata', self.cw_rset, row=row, col=col)


def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__, (SeeAlsoVComponent,))
    if 'see_also' in vreg.schema:
        vreg.register(SeeAlsoVComponent)
