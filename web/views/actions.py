"""Set of HTML base actions

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from cubicweb.appobject import objectify_selector
from cubicweb.selectors import (EntitySelector, yes,
    one_line_rset, two_lines_rset, one_etype_rset, relation_possible,
    nonempty_rset, non_final_entity,
    authenticated_user, match_user_groups, match_search_state,
    has_permission, has_add_permission,
    )
from cubicweb.web import uicfg, controller
from cubicweb.web.action import Action
from cubicweb.web.views import linksearch_select_url, vid_from_rset
from cubicweb.web.views.autoform import AutomaticEntityForm


class has_editable_relation(EntitySelector):
    """accept if some relations for an entity found in the result set is
    editable by the logged user.

    See `EntitySelector` documentation for behaviour when row is not specified.
    """

    def score_entity(self, entity):
        # if user has no update right but it can modify some relation,
        # display action anyway
        for dummy in AutomaticEntityForm.esrelations_by_category(
            entity, 'generic', 'add', strict=True):
            return 1
        for rschema, targetschemas, role in AutomaticEntityForm.erelations_by_category(
            entity, ('primary', 'secondary'), 'add', strict=True):
            if not rschema.final:
                return 1
        return 0

@objectify_selector
def match_searched_etype(cls, req, rset=None, **kwargs):
    return req.match_search_state(rset)

@objectify_selector
def view_is_not_default_view(cls, req, rset=None, **kwargs):
    # interesting if it propose another view than the current one
    vid = req.form.get('vid')
    if vid and vid != vid_from_rset(req, rset, cls.schema):
        return 1
    return 0

@objectify_selector
def addable_etype_empty_rset(cls, req, rset=None, **kwargs):
    if rset is not None and not rset.rowcount:
        rqlst = rset.syntax_tree()
        if len(rqlst.children) > 1:
            return 0
        select = rqlst.children[0]
        if len(select.defined_vars) == 1 and len(select.solutions) == 1:
            rset._searched_etype = select.solutions[0].itervalues().next()
            eschema = cls.schema.eschema(rset._searched_etype)
            if not (eschema.final or eschema.is_subobject(strict=True)) \
                   and eschema.has_perm(req, 'add'):
                return 1
    return 0

# generic 'main' actions #######################################################

class SelectAction(Action):
    """base class for link search actions. By default apply on
    any size entity result search it the current state is 'linksearch'
    if accept match.
    """
    id = 'select'
    __select__ = match_search_state('linksearch') & nonempty_rset() & match_searched_etype()

    title = _('select')
    category = 'mainactions'
    order = 0

    def url(self):
        return linksearch_select_url(self.req, self.rset)


class CancelSelectAction(Action):
    id = 'cancel'
    __select__ = match_search_state('linksearch')

    title = _('cancel select')
    category = 'mainactions'
    order = 10

    def url(self):
        target, eid, r_type, searched_type = self.req.search_state[1]
        return self.build_url(str(eid),
                              vid='edition', __mode='normal')


class ViewAction(Action):
    id = 'view'
    __select__ = (match_search_state('normal') &
                  match_user_groups('users', 'managers') &
                  view_is_not_default_view() &
                  non_final_entity())

    title = _('view')
    category = 'mainactions'
    order = 0

    def url(self):
        params = self.req.form.copy()
        for param in ('vid', '__message') + controller.NAV_FORM_PARAMETERS:
            params.pop(param, None)
        return self.build_url(self.req.relative_path(includeparams=False),
                              **params)


class ModifyAction(Action):
    id = 'edit'
    __select__ = (match_search_state('normal') &
                  one_line_rset() &
                  (has_permission('update') | has_editable_relation('add')))

    title = _('modify')
    category = 'mainactions'
    order = 10

    def url(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return entity.absolute_url(vid='edition')


class MultipleEditAction(Action):
    id = 'muledit' # XXX get strange conflicts if id='edit'
    __select__ = (match_search_state('normal') &
                  two_lines_rset() & one_etype_rset() &
                  has_permission('update'))

    title = _('modify')
    category = 'mainactions'
    order = 10

    def url(self):
        return self.build_url('view', rql=self.rset.rql, vid='muledit')


# generic "more" actions #######################################################

class ManagePermissionsAction(Action):
    id = 'managepermission'
    __select__ = one_line_rset() & non_final_entity() & match_user_groups('managers')

    title = _('manage permissions')
    category = 'moreactions'
    order = 15

    @classmethod
    def registered(cls, vreg):
        super(ManagePermissionsAction, cls).registered(vreg)
        if 'require_permission' in vreg.schema:
            cls.__select__ = (one_line_rset() & non_final_entity() &
                              (match_user_groups('managers')
                               | relation_possible('require_permission', 'subject', 'CWPermission',
                                                   action='add')))
        return super(ManagePermissionsAction, cls).registered(vreg)

    def url(self):
        return self.rset.get_entity(self.row or 0, self.col or 0).absolute_url(vid='security')


class DeleteAction(Action):
    id = 'delete'
    __select__ = has_permission('delete')

    title = _('delete')
    category = 'moreactions'
    order = 20

    def url(self):
        if len(self.rset) == 1:
            entity = self.rset.get_entity(self.row or 0, self.col or 0)
            return self.build_url(entity.rest_path(), vid='deleteconf')
        return self.build_url(rql=self.rset.printable_rql(), vid='deleteconf')


class CopyAction(Action):
    id = 'copy'
    __select__ = one_line_rset() & has_permission('add')

    title = _('copy')
    category = 'moreactions'
    order = 30

    def url(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return entity.absolute_url(vid='copy')


class AddNewAction(MultipleEditAction):
    """when we're seeing more than one entity with the same type, propose to
    add a new one
    """
    id = 'addentity'
    __select__ = (match_search_state('normal') &
                  (addable_etype_empty_rset()
                   | (two_lines_rset() & one_etype_rset & has_add_permission()))
                  )

    category = 'moreactions'
    order = 40

    @property
    def rsettype(self):
        if self.rset:
            return self.rset.description[0][0]
        return self.rset._searched_etype

    @property
    def title(self):
        return self.req.__('add a %s' % self.rsettype) # generated msgid

    def url(self):
        return self.build_url('add/%s' % self.rsettype)


class AddRelatedActions(Action):
    """fill 'addrelated' sub-menu of the actions box"""
    id = 'addrelated'
    __select__ = Action.__select__ & one_line_rset() & non_final_entity()

    submenu = _('addrelated')
    order = 20

    def fill_menu(self, box, menu):
        # when there is only one item in the sub-menu, replace the sub-menu by
        # item's title prefixed by 'add'
        menu.label_prefix = self.req._('add')
        super(AddRelatedActions, self).fill_menu(box, menu)

    def actual_actions(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        eschema = entity.e_schema
        for rschema, teschema, x in self.add_related_schemas(entity):
            if x == 'subject':
                label = 'add %s %s %s %s' % (eschema, rschema, teschema, x)
                url = self.linkto_url(entity, rschema, teschema, 'object')
            else:
                label = 'add %s %s %s %s' % (teschema, rschema, eschema, x)
                url = self.linkto_url(entity, rschema, teschema, 'subject')
            yield self.build_action(self.req._(label), url)

    def add_related_schemas(self, entity):
        """this is actually used ui method to generate 'addrelated' actions from
        the schema.

        If you don't want any auto-generated actions, you should overrides this
        method to return an empty list. If you only want some, you can configure
        them by using uicfg.actionbox_appearsin_addmenu
        """
        appearsin_addmenu = uicfg.actionbox_appearsin_addmenu
        req = self.req
        eschema = entity.e_schema
        for role, rschemas in (('subject', eschema.subject_relations()),
                               ('object', eschema.object_relations())):
            for rschema in rschemas:
                if rschema.final:
                    continue
                # check the relation can be added as well
                # XXX consider autoform_permissions_overrides?
                if role == 'subject'and not rschema.has_perm(req, 'add',
                                                             fromeid=entity.eid):
                    continue
                if role == 'object'and not rschema.has_perm(req, 'add',
                                                            toeid=entity.eid):
                    continue
                # check the target types can be added as well
                for teschema in rschema.targets(eschema, role):
                    if not appearsin_addmenu.etype_get(eschema, rschema,
                                                       role, teschema):
                        continue
                    if teschema.has_local_role('add') or teschema.has_perm(req, 'add'):
                        yield rschema, teschema, role

    def linkto_url(self, entity, rtype, etype, target):
        return self.build_url('add/%s' % etype,
                              __linkto='%s:%s:%s' % (rtype, entity.eid, target),
                              __redirectpath=entity.rest_path(), # should not be url quoted!
                              __redirectvid=self.req.form.get('vid', ''))


# logged user actions #########################################################

class UserPreferencesAction(Action):
    id = 'myprefs'
    __select__ = authenticated_user()

    title = _('user preferences')
    category = 'useractions'
    order = 10

    def url(self):
        return self.build_url(self.id)


class UserInfoAction(Action):
    id = 'myinfos'
    __select__ = authenticated_user()

    title = _('personnal informations')
    category = 'useractions'
    order = 20

    def url(self):
        return self.build_url('cwuser/%s'%self.req.user.login, vid='edition')


class LogoutAction(Action):
    id = 'logout'
    __select__ = authenticated_user()

    title = _('logout')
    category = 'useractions'
    order = 30

    def url(self):
        return self.build_url(self.id)


# site actions ################################################################

class ManagersAction(Action):
    __abstract__ = True
    __select__ = match_user_groups('managers')

    category = 'siteactions'

    def url(self):
        return self.build_url(self.id)


class SiteConfigurationAction(ManagersAction):
    id = 'siteconfig'
    title = _('site configuration')
    order = 10


class ManageAction(ManagersAction):
    id = 'manage'
    title = _('manage')
    order = 20

class SiteInfoAction(ManagersAction):
    id = 'siteinfo'
    title = _('info')
    order = 30
    __select__ = match_user_groups('users','managers')


class PoweredByAction(Action):
    id = 'poweredby'
    __select__ = yes()

    category = 'footer'
    order = 3
    title = _('powered by CubicWeb')

    def url(self):
        return 'http://www.cubicweb.org'


from logilab.common.deprecation import class_moved
from cubicweb.web.views.bookmark import FollowAction
FollowAction = class_moved(FollowAction)

## default actions ui configuration ###########################################

addmenu = uicfg.actionbox_appearsin_addmenu
addmenu.tag_subject_of(('*', 'is', '*'), False)
addmenu.tag_object_of(('*', 'is', '*'), False)
addmenu.tag_subject_of(('*', 'is_instance_of', '*'), False)
addmenu.tag_object_of(('*', 'is_instance_of', '*'), False)
addmenu.tag_subject_of(('*', 'identity', '*'), False)
addmenu.tag_object_of(('*', 'identity', '*'), False)
addmenu.tag_subject_of(('*', 'owned_by', '*'), False)
addmenu.tag_subject_of(('*', 'created_by', '*'), False)
addmenu.tag_subject_of(('*', 'require_permission', '*'), False)
addmenu.tag_subject_of(('*', 'wf_info_for', '*'), False)
addmenu.tag_object_of(('*', 'wf_info_for', '*'), False)
addmenu.tag_object_of(('*', 'state_of', 'CWEType'), True)
addmenu.tag_object_of(('*', 'transition_of', 'CWEType'), True)
addmenu.tag_object_of(('*', 'relation_type', 'CWRType'), True)
addmenu.tag_object_of(('*', 'from_entity', 'CWEType'), False)
addmenu.tag_object_of(('*', 'to_entity', 'CWEType'), False)
addmenu.tag_object_of(('*', 'in_group', 'CWGroup'), True)
addmenu.tag_object_of(('*', 'owned_by', 'CWUser'), False)
addmenu.tag_object_of(('*', 'created_by', 'CWUser'), False)
addmenu.tag_object_of(('*', 'bookmarked_by', 'CWUser'), True)
addmenu.tag_subject_of(('Transition', 'destination_state', '*'), True)
addmenu.tag_object_of(('*', 'allowed_transition', 'Transition'), True)
addmenu.tag_object_of(('*', 'destination_state', 'State'), True)
addmenu.tag_subject_of(('State', 'allowed_transition', '*'), True)
