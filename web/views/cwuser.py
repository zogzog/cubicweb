# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Specific views for users and groups"""

__docformat__ = "restructuredtext en"
_ = unicode

from hashlib import sha1 # pylint: disable=E0611

from logilab.mtconverter import xml_escape

from cubicweb import tags
from cubicweb.schema import display_name
from cubicweb.predicates import one_line_rset, is_instance, match_user_groups
from cubicweb.view import EntityView, StartupView
from cubicweb.web import action, formwidgets
from cubicweb.web.views import uicfg, tabs, tableview, actions, add_etype_button

_pvs = uicfg.primaryview_section
_pvs.tag_attribute(('CWUser', 'login'), 'hidden')

_affk = uicfg.autoform_field_kwargs
_affk.tag_subject_of(('CWUser', 'in_group', 'CWGroup'),
                    {'widget': formwidgets.InOutWidget})

class UserPreferencesEntityAction(action.Action):
    __regid__ = 'prefs'
    __select__ = (one_line_rset() & is_instance('CWUser') &
                  match_user_groups('owners', 'managers'))

    title = _('preferences')
    category = 'mainactions'

    def url(self):
        user = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        return user.absolute_url(vid='propertiesform')


class FoafView(EntityView):
    __regid__ = 'foaf'
    __select__ = is_instance('CWUser')

    title = _('foaf')
    templatable = False
    content_type = 'text/xml'

    def call(self):
        self.w(u'''<?xml version="1.0" encoding="%s"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3org/2000/01/rdf-schema#"
         xmlns:foaf="http://xmlns.com/foaf/0.1/"> '''% self._cw.encoding)
        for i in xrange(self.cw_rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</rdf:RDF>\n')

    def entity_call(self, entity, **kwargs):
        entity.complete()
        # account
        self.w(u'<foaf:OnlineAccount rdf:about="%s">\n' % entity.absolute_url())
        self.w(u'  <foaf:accountName>%s</foaf:accountName>\n' % entity.login)
        self.w(u'</foaf:OnlineAccount>\n')
        # person
        self.w(u'<foaf:Person rdf:about="%s#user">\n' % entity.absolute_url())
        self.w(u'  <foaf:account rdf:resource="%s" />\n' % entity.absolute_url())
        if entity.surname:
            self.w(u'<foaf:familyName>%s</foaf:familyName>\n'
                   % xml_escape(entity.surname))
        if entity.firstname:
            self.w(u'<foaf:givenName>%s</foaf:givenName>\n'
                   % xml_escape(entity.firstname))
        emailaddr = entity.cw_adapt_to('IEmailable').get_email()
        if emailaddr:
            self.w(u'<foaf:mbox_sha1sum>%s</foaf:mbox_sha1sum>\n'
                   % sha1(emailaddr.encode('utf-8')).hexdigest())
        self.w(u'</foaf:Person>\n')


# group views ##################################################################

_pvs.tag_attribute(('CWGroup', 'name'), 'hidden')
_pvs.tag_subject_of(('CWGroup', 'read_permission', '*'), 'relations')
_pvs.tag_subject_of(('CWGroup', 'add_permission', '*'), 'relations')
_pvs.tag_subject_of(('CWGroup', 'delete_permission', '*'), 'relations')
_pvs.tag_subject_of(('CWGroup', 'update_permission', '*'), 'relations')
_pvs.tag_object_of(('CWUser', 'in_group', 'CWGroup'), 'hidden')
_pvs.tag_object_of(('*', 'require_group', 'CWGroup'), 'hidden')


class CWGroupPrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWGroup')
    tabs = [_('cwgroup-main'), _('cwgroup-permissions')]
    default_tab = 'cwgroup-main'


class CWGroupMainTab(tabs.PrimaryTab):
    __regid__ = 'cwgroup-main'
    __select__ = tabs.PrimaryTab.__select__ & is_instance('CWGroup')

    def render_entity_attributes(self, entity):
        rset = self._cw.execute(
            'Any U, FN, LN, CD, LL ORDERBY L WHERE U in_group G, '
            'U login L, U firstname FN, U surname LN, U creation_date CD, '
            'U last_login_time LL, G eid %(x)s', {'x': entity.eid})
        self.wview('cwgroup.users', rset, 'null')

class CWGroupUsersTable(tableview.RsetTableView):
    __regid__ = 'cwgroup.users'
    __select__ = is_instance('CWUser')
    headers = (_(u'user'), _(u'first name'), _(u'last name'),
               _(u'creation date'), _(u'last login time'))
    layout_args = {'display_filter': 'top'}
    finalvid = 'editable-final'


class CWGroupPermTab(EntityView):
    __regid__ = 'cwgroup-permissions'
    __select__ = is_instance('CWGroup')

    def entity_call(self, entity):
        self._cw.add_css(('cubicweb.schema.css','cubicweb.acl.css'))
        access_types = ('read', 'delete', 'add', 'update')
        w = self.w
        objtype_access = {'CWEType': ('read', 'delete', 'add', 'update'),
                          'CWRelation': ('add', 'delete')}
        rql_cwetype = 'DISTINCT Any X WHERE X %s_permission CWG, X is CWEType, ' \
                      'CWG eid %%(e)s'
        rql_cwrelation = 'DISTINCT Any RT WHERE X %s_permission CWG, X is CWRelation, ' \
                         'X relation_type RT, CWG eid %%(e)s'
        self.render_objtype_access(entity, 'CWEType', objtype_access, rql_cwetype)
        self.render_objtype_access(entity, 'CWRelation', objtype_access, rql_cwrelation)

    def render_objtype_access(self, entity, objtype, objtype_access, rql):
        self.w(u'<h4>%s</h4>' % self._cw._(objtype))
        for access_type in objtype_access[objtype]:
            rset = self._cw.execute(rql % access_type, {'e': entity.eid})
            if rset:
                self.w(u'<div>%s:</div>' % self._cw.__(access_type + '_permission'))
                self.w(u'<div>%s</div><br/>' % self._cw.view('csv', rset, 'null'))


class CWGroupInContextView(EntityView):
    __regid__ = 'incontext'
    __select__ = is_instance('CWGroup')

    def entity_call(self, entity, **kwargs):
        entity.complete()
        self.w(u'<a href="%s" class="%s">%s</a>' % (
            entity.absolute_url(), xml_escape(entity.name),
            entity.printable_value('name')))


# user / groups management views ###############################################

class ManageUsersAction(actions.ManagersAction):
    __regid__ = 'cwuser' # see rewrite rule /cwuser
    title = _('users and groups')
    category = 'manage'


class UsersAndGroupsManagementView(tabs.TabsMixin, StartupView):
    __regid__ = 'cw.users-and-groups-management'
    __select__ = StartupView.__select__ & match_user_groups('managers')
    title = _('Users and groups management')
    tabs = [_('cw.users-management'), _('cw.groups-management'),]
    default_tab = 'cw.users-management'

    def call(self, **kwargs):
        """The default view representing the instance's management"""
        self.w(u'<h1>%s</h1>' % self._cw._(self.title))
        self.render_tabs(self.tabs, self.default_tab)


class CWUserManagementView(StartupView):
    __regid__ = 'cw.users-management'
    __select__ = StartupView.__select__ & match_user_groups('managers')
    cache_max_age = 0 # disable caching
    # XXX one could wish to display for instance only user's firstname/surname
    # for non managers but filtering out NULL caused crash with an ldapuser
    # source. The ldapuser source has been dropped and this code can be updated.
    rql = ('Any U,US,F,S,U,UAA,UDS, L,UAA,USN,UDSN ORDERBY L WHERE U is CWUser, '
           'U login L, U firstname F, U surname S, '
           'U in_state US, US name USN, '
           'U primary_email UA?, UA address UAA, '
           'U cw_source UDS, US name UDSN')

    def call(self, **kwargs):
        self.w(add_etype_button(self._cw, 'CWUser'))
        self.w(u'<div class="clear"></div>')
        self.wview('cw.users-table', self._cw.execute(self.rql))


class CWUsersTable(tableview.EntityTableView):
    __regid__ = 'cw.users-table'
    __select__ = is_instance('CWUser')
    columns = ['user', 'in_state', 'firstname', 'surname',
               'in_group', 'primary_email', 'cw_source']
    layout_args = {'display_filter': 'top'}
    finalvid = 'editable-final'

    column_renderers = {
        'user': tableview.EntityTableColRenderer(
            renderfunc=lambda w,x: w(tags.a(x.login, href=x.absolute_url())),
            sortfunc=lambda x: x.login),
        'in_state': tableview.EntityTableColRenderer(
            renderfunc=lambda w,x: w(x.cw_adapt_to('IWorkflowable').printable_state),
            sortfunc=lambda x: x.cw_adapt_to('IWorkflowable').printable_state),
        'in_group': tableview.EntityTableColRenderer(
            renderfunc=lambda w,x: x.view('reledit', rtype='in_group', role='subject', w=w)),
        'primary_email': tableview.RelatedEntityColRenderer(
            getrelated=lambda x:x.primary_email and x.primary_email[0] or None),
        'cw_source': tableview.RelatedEntityColRenderer(
            getrelated=lambda x: x.cw_source[0]),
        }


class CWGroupsManagementView(StartupView):
    __regid__ = 'cw.groups-management'
    __select__ = StartupView.__select__ & match_user_groups('managers')
    cache_max_age = 0 # disable caching
    rql = ('Any G,GN ORDERBY GN WHERE G is CWGroup, G name GN, NOT G name "owners"')

    def call(self, **kwargs):
        self.w(add_etype_button(self._cw, 'CWGroup'))
        self.w(u'<div class="clear"></div>')
        self.wview('cw.groups-table', self._cw.execute(self.rql))


class CWGroupsTable(tableview.EntityTableView):
    __regid__ = 'cw.groups-table'
    __select__ = is_instance('CWGroup')
    columns = ['group', 'nb_users']
    layout_args = {'display_filter': 'top'}

    column_renderers = {
        'group': tableview.MainEntityColRenderer(),
        'nb_users': tableview.EntityTableColRenderer(
            header=_('num. users'),
            renderfunc=lambda w,x: w(unicode(x.num_users())),
            sortfunc=lambda x: x.num_users()),
        }
