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

import hashlib

from logilab.mtconverter import xml_escape

from cubicweb.schema import display_name
from cubicweb.selectors import one_line_rset, is_instance, match_user_groups
from cubicweb.view import EntityView, StartupView
from cubicweb.web import action, uicfg, formwidgets
from cubicweb.web.views import tabs, tableview, actions

_pvs = uicfg.primaryview_section
_pvs.tag_attribute(('CWUser', 'login'), 'hidden')
_pvs.tag_attribute(('CWGroup', 'name'), 'hidden')
_pvs.tag_subject_of(('CWGroup', 'read_permission', '*'), 'relations')
_pvs.tag_subject_of(('CWGroup', 'add_permission', '*'), 'relations')
_pvs.tag_subject_of(('CWGroup', 'delete_permission', '*'), 'relations')
_pvs.tag_subject_of(('CWGroup', 'update_permission', '*'), 'relations')
_pvs.tag_object_of(('*', 'in_group', 'CWGroup'), 'relations')
_pvs.tag_object_of(('*', 'require_group', 'CWGroup'), 'relations')

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
        login = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0).login
        return self._cw.build_url('cwuser/%s'%login, vid='propertiesform')


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

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
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
                   % hashlib.sha1(emailaddr.encode('utf-8')).hexdigest())
        self.w(u'</foaf:Person>\n')


# group views ##################################################################

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
        _ = self._cw._
        rql = 'Any U, FN, LN, CD, LL ORDERBY L WHERE U in_group G, ' \
              'U login L, U firstname FN, U surname LN, U creation_date CD, ' \
              'U last_login_time LL, G eid %(x)s'
        rset = self._cw.execute(rql, {'x': entity.eid})
        headers = (_(u'user'), _(u'first name'), _(u'last name'),
                   _(u'creation date'), _(u'last login time'))
        self.wview('editable-table', rset, 'null', displayfilter=True,
                   displaycols=range(5), mainindex=0, headers=headers)

class CWGroupPermTab(EntityView):
    __regid__ = 'cwgroup-permissions'
    __select__ = is_instance('CWGroup')

    def cell_call(self, row, col):
        self._cw.add_css(('cubicweb.schema.css','cubicweb.acl.css'))
        access_types = ('read', 'delete', 'add', 'update')
        w = self.w
        entity = self.cw_rset.get_entity(row, col)
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

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        self.w(u'<a href="%s" class="%s">%s</a>' % (
            entity.absolute_url(), entity.name, entity.printable_value('name')))


# user / groups management views ###############################################

class ManageUsersAction(actions.ManagersAction):
    __regid__ = 'cwuser' # see rewrite rule /cwuser
    title = _('users and groups')
    category = 'manage'


class CWUserManagementView(StartupView):
    __regid__ = 'cw.user-management'
    rql = ('Any U, F, S, U, L ORDERBY L WHERE U is CWUser, U login L, U firstname F, U surname S')
    title = _('users and groups management')

    def call(self, **kwargs):
        self.w('<h1>%s</h1>' % self._cw._(self.title))
        for etype in ('CWUser', 'CWGroup'):
            eschema = self._cw.vreg.schema.eschema(etype)
            if eschema.has_perm(self._cw, 'add'):
                self.w(u'<a href="%s" class="addButton right">%s</a>' % (
                    self._cw.build_url('add/%s' % eschema),
                    self._cw._('add a %s' % etype).capitalize()))
        self.w(u'<div class="clear"></div>')
        self.wview('cw.user-table', self._cw.execute(self.rql))


class CWUserTable(tableview.EditableTableView):
    __regid__ = 'cw.user-table'
    __select__ = is_instance('CWUser')

    def call(self, **kwargs):
        headers = (display_name(self._cw, 'CWUser', 'plural'),
                   self._cw._('firstname'), self._cw._('surname'),
                   display_name(self._cw, 'CWGroup', 'plural'))
        super(CWUserTable, self).call(
            paginate=True, cellvids={3: 'cw.user-table.group-cell'},
            headers=headers, **kwargs)


class CWUserGroupCell(EntityView):
    __regid__ = 'cw.user-table.group-cell'
    __select__ = is_instance('CWUser')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        self.w(entity.view('reledit', rtype='in_group', role='subject'))
