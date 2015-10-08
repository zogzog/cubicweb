# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Set of HTML base actions"""

__docformat__ = "restructuredtext en"
_ = unicode

from warnings import warn

from logilab.mtconverter import xml_escape
from logilab.common.registry import objectify_predicate, yes

from cubicweb.schema import display_name
from cubicweb.predicates import (EntityPredicate,
    one_line_rset, multi_lines_rset, one_etype_rset, relation_possible,
    nonempty_rset, non_final_entity, score_entity,
    authenticated_user, match_user_groups, match_search_state,
    has_permission, has_add_permission, is_instance, debug_mode,
    )
from cubicweb.web import controller, action
from cubicweb.web.views import uicfg, linksearch_select_url, vid_from_rset


class has_editable_relation(EntityPredicate):
    """accept if some relations for an entity found in the result set is
    editable by the logged user.

    See `EntityPredicate` documentation for behaviour when row is not specified.
    """

    def score_entity(self, entity):
        # if user has no update right but it can modify some relation,
        # display action anyway
        form = entity._cw.vreg['forms'].select('edition', entity._cw,
                                               entity=entity, mainform=False)
        for dummy in form.editable_relations():
            return 1
        for dummy in form.inlined_form_views():
            return 1
        for dummy in form.editable_attributes(strict=True):
            return 1
        return 0

@objectify_predicate
def match_searched_etype(cls, req, rset=None, **kwargs):
    return req.match_search_state(rset)

@objectify_predicate
def view_is_not_default_view(cls, req, rset=None, **kwargs):
    # interesting if it propose another view than the current one
    vid = req.form.get('vid')
    if vid and vid != vid_from_rset(req, rset, req.vreg.schema):
        return 1
    return 0

@objectify_predicate
def addable_etype_empty_rset(cls, req, rset=None, **kwargs):
    if rset is not None and not rset.rowcount:
        rqlst = rset.syntax_tree()
        if len(rqlst.children) > 1:
            return 0
        select = rqlst.children[0]
        if len(select.defined_vars) == 1 and len(select.solutions) == 1:
            rset._searched_etype = select.solutions[0].itervalues().next()
            eschema = req.vreg.schema.eschema(rset._searched_etype)
            if not (eschema.final or eschema.is_subobject(strict=True)) \
                   and eschema.has_perm(req, 'add'):
                return 1
    return 0

class has_undoable_transactions(EntityPredicate):
    "Select entities having public (i.e. end-user) undoable transactions."

    def score_entity(self, entity):
        if not entity._cw.vreg.config['undo-enabled']:
            return 0
        if entity._cw.cnx.undoable_transactions(eid=entity.eid):
            return 1
        else:
            return 0


# generic 'main' actions #######################################################

class SelectAction(action.Action):
    """base class for link search actions. By default apply on
    any size entity result search it the current state is 'linksearch'
    if accept match.
    """
    __regid__ = 'select'
    __select__ = (match_search_state('linksearch') & nonempty_rset()
                  & match_searched_etype())

    title = _('select')
    category = 'mainactions'
    order = 0

    def url(self):
        return linksearch_select_url(self._cw, self.cw_rset)


class CancelSelectAction(action.Action):
    __regid__ = 'cancel'
    __select__ = match_search_state('linksearch')

    title = _('cancel select')
    category = 'mainactions'
    order = 10

    def url(self):
        target, eid, r_type, searched_type = self._cw.search_state[1]
        return self._cw.build_url(str(eid),
                                  vid='edition', __mode='normal')


class ViewAction(action.Action):
    __regid__ = 'view'
    __select__ = (action.Action.__select__ &
                  match_user_groups('users', 'managers') &
                  view_is_not_default_view() &
                  non_final_entity())

    title = _('view')
    category = 'mainactions'
    order = 0

    def url(self):
        params = self._cw.form.copy()
        for param in ('vid', '__message') + controller.NAV_FORM_PARAMETERS:
            params.pop(param, None)
        if self._cw.ajax_request:
            path = 'view'
            if self.cw_rset is not None:
                params = {'rql': self.cw_rset.printable_rql()}
        else:
            path = self._cw.relative_path(includeparams=False)
        return self._cw.build_url(path, **params)


class ModifyAction(action.Action):
    __regid__ = 'edit'
    __select__ = (action.Action.__select__
                  & one_line_rset() & has_editable_relation())

    title = _('modify')
    category = 'mainactions'
    order = 10

    def url(self):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        return entity.absolute_url(vid='edition')


class MultipleEditAction(action.Action):
    __regid__ = 'muledit' # XXX get strange conflicts if id='edit'
    __select__ = (action.Action.__select__ & multi_lines_rset() &
                  one_etype_rset() & has_permission('update'))

    title = _('modify')
    category = 'mainactions'
    order = 10

    def url(self):
        return self._cw.build_url('view', rql=self.cw_rset.printable_rql(), vid='muledit')


# generic "more" actions #######################################################

class ManagePermissionsAction(action.Action):
    __regid__ = 'managepermission'
    __select__ = (action.Action.__select__ & one_line_rset() &
                  non_final_entity() & match_user_groups('managers'))

    title = _('manage permissions')
    category = 'moreactions'
    order = 15

    def url(self):
        return self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0).absolute_url(vid='security')


class DeleteAction(action.Action):
    __regid__ = 'delete'
    __select__ = action.Action.__select__ & has_permission('delete')

    title = _('delete')
    category = 'moreactions'
    order = 20

    def url(self):
        if len(self.cw_rset) == 1:
            entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
            return self._cw.build_url(entity.rest_path(), vid='deleteconf')
        return self._cw.build_url(rql=self.cw_rset.printable_rql(), vid='deleteconf')


class CopyAction(action.Action):
    __regid__ = 'copy'
    __select__ = (action.Action.__select__ & one_line_rset()
                  & has_permission('add'))

    title = _('copy')
    category = 'moreactions'
    order = 30

    def url(self):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        return entity.absolute_url(vid='copy')


class AddNewAction(MultipleEditAction):
    """when we're seeing more than one entity with the same type, propose to
    add a new one
    """
    __regid__ = 'addentity'
    __select__ = (action.Action.__select__ &
                  (addable_etype_empty_rset()
                   | (multi_lines_rset() & one_etype_rset() & has_add_permission()))
                  )

    category = 'moreactions'
    order = 40

    @property
    def rsettype(self):
        if self.cw_rset:
            return self.cw_rset.description[0][0]
        return self.cw_rset._searched_etype

    @property
    def title(self):
        return self._cw.__('add a %s' % self.rsettype) # generated msgid

    def url(self):
        return self._cw.vreg["etypes"].etype_class(self.rsettype).cw_create_url(self._cw)


class AddRelatedActions(action.Action):
    """fill 'addrelated' sub-menu of the actions box"""
    __regid__ = 'addrelated'
    __select__ = action.Action.__select__ & one_line_rset() & non_final_entity()

    submenu = _('addrelated')
    order = 17

    def fill_menu(self, box, menu):
        # when there is only one item in the sub-menu, replace the sub-menu by
        # item's title prefixed by 'add'
        menu.label_prefix = self._cw._('add')
        super(AddRelatedActions, self).fill_menu(box, menu)

    def redirect_params(self, entity):
        return {'__redirectpath': entity.rest_path(), # should not be url quoted!
                '__redirectvid': self._cw.form.get('vid', '')}

    def actual_actions(self):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        eschema = entity.e_schema
        params = self.redirect_params(entity)
        for rschema, teschema, role in self.add_related_schemas(entity):
            if rschema.role_rdef(eschema, teschema, role).role_cardinality(role) in '1?':
                if entity.related(rschema, role):
                    continue
            if role == 'subject':
                label = 'add %s %s %s %s' % (eschema, rschema, teschema, role)
                url = self.linkto_url(entity, rschema, teschema, 'object', **params)
            else:
                label = 'add %s %s %s %s' % (teschema, rschema, eschema, role)
                url = self.linkto_url(entity, rschema, teschema, 'subject', **params)
            yield self.build_action(self._cw._(label), url)

    def add_related_schemas(self, entity):
        """this is actually used ui method to generate 'addrelated' actions from
        the schema.

        If you don't want any auto-generated actions, you should overrides this
        method to return an empty list. If you only want some, you can configure
        them by using uicfg.actionbox_appearsin_addmenu
        """
        appearsin_addmenu = self._cw.vreg['uicfg'].select(
            'actionbox_appearsin_addmenu', self._cw, entity=entity)
        req = self._cw
        eschema = entity.e_schema
        for role, rschemas in (('subject', eschema.subject_relations()),
                               ('object', eschema.object_relations())):
            for rschema in rschemas:
                if rschema.final:
                    continue
                for teschema in rschema.targets(eschema, role):
                    if not appearsin_addmenu.etype_get(eschema, rschema,
                                                       role, teschema):
                        continue
                    rdef = rschema.role_rdef(eschema, teschema, role)
                    # check the relation can be added
                    # XXX consider autoform_permissions_overrides?
                    if role == 'subject'and not rdef.has_perm(
                        req, 'add', fromeid=entity.eid):
                        continue
                    if role == 'object'and not rdef.has_perm(
                        req, 'add', toeid=entity.eid):
                        continue
                    # check the target types can be added as well
                    if teschema.may_have_permission('add', req):
                        yield rschema, teschema, role

    def linkto_url(self, entity, rtype, etype, target, **kwargs):
        return self._cw.vreg["etypes"].etype_class(etype).cw_create_url(
                self._cw, __linkto='%s:%s:%s' % (rtype, entity.eid, target),
                **kwargs)


class ViewSameCWEType(action.Action):
    """when displaying the schema of a CWEType, offer to list entities of that type
    """
    __regid__ = 'entitiesoftype'
    __select__ = one_line_rset() & is_instance('CWEType') & score_entity(lambda x: not x.final)
    category = 'mainactions'
    order = 40

    @property
    def etype(self):
        return self.cw_rset.get_entity(0,0).name

    @property
    def title(self):
        return self._cw.__('view all %s') % display_name(self._cw, self.etype, 'plural').lower()

    def url(self):
        return self._cw.build_url(self.etype)

# logged user actions #########################################################

class UserPreferencesAction(action.Action):
    __regid__ = 'myprefs'
    __select__ = authenticated_user()

    title = _('user preferences')
    category = 'useractions'
    order = 10

    def url(self):
        return self._cw.build_url(self.__regid__)


class UserInfoAction(action.Action):
    __regid__ = 'myinfos'
    __select__ = authenticated_user()

    title = _('profile')
    category = 'useractions'
    order = 20

    def url(self):
        return self._cw.build_url('cwuser/%s'%self._cw.user.login, vid='edition')


class LogoutAction(action.Action):
    __regid__ = 'logout'
    __select__ = authenticated_user()

    title = _('logout')
    category = 'useractions'
    order = 30

    def url(self):
        return self._cw.build_url(self.__regid__)


# site actions ################################################################

class ManagersAction(action.Action):
    __abstract__ = True
    __select__ = match_user_groups('managers')

    category = 'siteactions'

    def url(self):
        return self._cw.build_url(self.__regid__)


class SiteConfigurationAction(ManagersAction):
    __regid__ = 'siteconfig'
    title = _('site configuration')
    order = 10
    category = 'manage'


class ManageAction(ManagersAction):
    __regid__ = 'manage'
    title = _('manage')
    order = 20


# footer actions ###############################################################

class PoweredByAction(action.Action):
    __regid__ = 'poweredby'
    __select__ = yes()

    category = 'footer'
    order = 3
    title = _('Powered by CubicWeb')

    def url(self):
        return 'http://www.cubicweb.org'

## default actions ui configuration ###########################################

addmenu = uicfg.actionbox_appearsin_addmenu
addmenu.tag_object_of(('*', 'relation_type', 'CWRType'), True)
addmenu.tag_object_of(('*', 'from_entity', 'CWEType'), False)
addmenu.tag_object_of(('*', 'to_entity', 'CWEType'), False)
addmenu.tag_object_of(('*', 'in_group', 'CWGroup'), True)
addmenu.tag_object_of(('*', 'bookmarked_by', 'CWUser'), True)
