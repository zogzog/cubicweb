"""Bases HTML components:

* the rql input form
* the logged user link
* pdf view link

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape
from rql import parse

from cubicweb.selectors import yes, two_etypes_rset, match_form_params
from cubicweb.schema import display_name
from cubicweb.common.uilib import toggle_action
from cubicweb.web import component
from cubicweb.web.htmlwidgets import (MenuWidget, PopupBoxMenu, BoxSeparator,
                                      BoxLink)

VISIBLE_PROP_DEF = {
    _('visible'):  dict(type='Boolean', default=True,
                        help=_('display the component or not')),
    }

class RQLInputForm(component.Component):
    """build the rql input form, usually displayed in the header"""
    id = 'rqlinput'
    property_defs = VISIBLE_PROP_DEF
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
<input type="submit" value="" class="rqlsubmit" tabindex="%s" />
</fieldset>
''' % (not self.propval('visible') and 'hidden' or '',
       self.build_url('view'), xml_escape(rql), req._('full text or RQL query'), req.next_tabindex(),
        req.next_tabindex()))
        if self.req.search_state[0] != 'normal':
            self.w(u'<input type="hidden" name="__mode" value="%s"/>'
                   % ':'.join(req.search_state[1]))
        self.w(u'</form></div>')


class ApplLogo(component.Component):
    """build the instance logo, usually displayed in the header"""
    id = 'logo'
    property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True

    def call(self):
        self.w(u'<a href="%s"><img class="logo" src="%s" alt="logo"/></a>'
               % (self.req.base_url(), self.req.external_resource('LOGO')))

class UserLink(component.Component):
    """if the user is the anonymous user, build a link to login
    else a link to the connected user object with a loggout link
    """
    property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True
    id = 'loggeduserlink'

    def call(self):
        if not self.req.cnx.anonymous_connection:
            # display useractions and siteactions
            actions = self.vreg['actions'].possible_actions(self.req, rset=self.rset)
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
            self.w(u'''&#160;[<a class="logout" href="javascript: popupLoginBox();">%s</a>]'''
                   % (self.req._('i18n_login_popup')))
        else:
            self.w(self.req._('anonymous'))
            self.w(u'&#160;[<a class="logout" href="%s">%s</a>]'
                   % (self.build_url('login'), self.req._('login')))


class ApplicationMessage(component.Component):
    """display messages given using the __message parameter into a special div
    section
    """
    __select__ = yes()
    id = 'applmessages'
    # don't want user to hide this component using an cwproperty
    property_defs = {}

    def call(self):
        msgs = [msg for msg in (self.req.get_shared_data('sources_error', pop=True),
                                self.req.message) if msg]
        self.w(u'<div id="appMsg" onclick="%s" class="%s">\n' %
               (toggle_action('appMsg'), (msgs and ' ' or 'hidden')))
        for msg in msgs:
            self.w(u'<div class="message" id="%s">%s</div>' % (
                self.div_id(), msg))
        self.w(u'</div>')


class ApplicationName(component.Component):
    """display the instance name"""
    id = 'appliname'
    property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True

    def call(self):
        title = self.req.property_value('ui.site-title')
        if title:
            self.w(u'<span id="appliName"><a href="%s">%s</a></span>' % (
                self.req.base_url(), xml_escape(title)))


class SeeAlsoVComponent(component.RelatedObjectsVComponent):
    """display any entity's see also"""
    id = 'seealso'
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
    id = 'etypenavigation'
    __select__ = two_etypes_rset() | match_form_params('__restrtype', '__restrtypes',
                                                       '__restrrql')
    property_defs = VISIBLE_PROP_DEF
    # don't want user to hide this component using an cwproperty
    site_wide = True
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
                        xml_escape(url), elabel))
                rqlst.recover()
        if on_etype:
            url = self.build_url(rql=restrrql)
            html.insert(0, u'<span><a href="%s">%s</a></span>' % (
                    url, _('Any')))
        else:
            html.insert(0, u'<span class="selected">%s</span>' % _('Any'))
        self.w(u'&#160;|&#160;'.join(html))
        self.w(u'</div>')


class PdfViewComponent(component.EntityVComponent):
    id = 'view_page_as_pdf'
    context = 'ctxtoolbar'

    def cell_call(self, row, col, view):
        entity = self.entity(row, col)
        url = entity.absolute_url(vid=view.id, __template='pdf-main-template')
        iconurl = self.req.build_url('data/pdf_icon.gif')
        label = self.req._('Download page as pdf')
        self.w(u'<a href="%s" title="%s" class="toolbarButton"><img src="%s" alt="%s"/></a>' %
               (xml_escape(url), label, iconurl, label))



class MetaDataComponent(component.EntityVComponent):
    id = 'metadata'
    context = 'navbottom'
    order = 1

    def cell_call(self, row, col, view=None):
        self.wview('metadata', self.rset, row=row, col=col)


def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__, (SeeAlsoVComponent,))
    if 'see_also' in vreg.schema:
        vreg.register(SeeAlsoVComponent)
