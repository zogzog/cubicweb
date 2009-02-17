"""Set of HTML base actions

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.vregistry import objectify_selector
from cubicweb.selectors import (
    yes, one_line_rset, two_lines_rset, one_etype_rset, relation_possible,
    non_final_entity,
    authenticated_user, match_user_groups, match_search_state,
    has_editable_relation, has_permission, has_add_permission,
    )

from cubicweb.web.action import Action
from cubicweb.web.views import linksearch_select_url
from cubicweb.web.views.baseviews import vid_from_rset

_ = unicode

@objectify_selector
def match_searched_etype(cls, req, rset, row=None, col=None, **kwargs):
    return req.match_search_state(rset)

@objectify_selector
def view_is_not_default_view(cls, req, rset, row, col, **kwargs):
    # interesting if it propose another view than the current one
    vid = req.form.get('vid')
    if vid and vid != vid_from_rset(req, rset, cls.schema):
        return 1
    return 0

@objectify_selector
def addable_etype_empty_rset(cls, req, rset, **kwargs):
    if rset is not None and not rset.rowcount:
        rqlst = rset.syntax_tree()
        if len(rqlst.children) > 1:
            return 0
        select = rqlst.children[0]
        if len(select.defined_vars) == 1 and len(select.solutions) == 1:
            rset._searched_etype = select.solutions[0].itervalues().next()
            eschema = cls.schema.eschema(rset._searched_etype)
            if not (eschema.is_final() or eschema.is_subobject(strict=True)) \
                   and eschema.has_perm(req, 'add'):
                return 1
    return 0

# generic primary actions #####################################################

class SelectAction(Action):
    """base class for link search actions. By default apply on
    any size entity result search it the current state is 'linksearch'
    if accept match.
    """
    id = 'select'
    __select__ = match_search_state('linksearch') & match_searched_etype()
    
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
        params.pop('vid', None)
        params.pop('__message', None)
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
                     two_lines_rset(), one_etype_rset() &
                  has_permission('update'))

    title = _('modify')
    category = 'mainactions'
    order = 10
    
    def url(self):
        return self.build_url('view', rql=self.rset.rql, vid='muledit')


# generic secondary actions ###################################################

class ManagePermissionsAction(Action):
    id = 'addpermission'
    __select__ = match_user_groups('managers') 

    title = _('manage permissions')
    category = 'moreactions'
    order = 100

    @classmethod
    def registered(cls, vreg):
        super(ManagePermissionsAction, cls).registered(vreg)
        if 'require_permission' in vreg.schema:
            cls.__select__ |= relation_possible('require_permission', 'subject', 'EPermission',
                                                action='add')
        return super(ManagePermissionsAction, cls).registered(vreg)
    
    def url(self):
        return self.rset.get_entity(0, 0).absolute_url(vid='security')

    
class DeleteAction(Action):
    id = 'delete'
    __select__ = one_line_rset() & has_permission('delete')
    
    title = _('delete')
    category = 'moreactions' 
    order = 20
    
    def url(self):
        if len(self.rset) == 1:
            entity = self.rset.get_entity(0, 0)
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
        return self.build_url('euser/%s'%self.req.user.login, vid='edition')


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


class ViewSchemaAction(Action):
    id = 'schema'
    __select__ = yes()
    
    title = _("site schema")
    category = 'siteactions'
    order = 30
    
    def url(self):
        return self.build_url(self.id)
