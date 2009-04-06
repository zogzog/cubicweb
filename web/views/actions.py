"""Set of HTML base actions

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.selectors import (searchstate_accept, match_user_group, yes,
                                       one_line_rset, two_lines_rset, one_etype_rset,
                                       authenticated_user, none_rset,
                                       match_search_state, chainfirst, chainall)

from cubicweb.web.action import Action, EntityAction,  LinkToEntityAction
from cubicweb.web.views import linksearch_select_url, linksearch_match
from cubicweb.web.views.baseviews import vid_from_rset

_ = unicode

# generic primary actions #####################################################

class SelectAction(EntityAction):
    """base class for link search actions. By default apply on
    any size entity result search it the current state is 'linksearch'
    if accept match.
    """
    category = 'mainactions'    
    __selectors__ = (searchstate_accept,)
    search_states = ('linksearch',)
    order = 0
    
    id = 'select'
    title = _('select')
    
    @classmethod
    def accept_rset(cls, req, rset, row, col):
        return linksearch_match(req, rset)
    
    def url(self):
        return linksearch_select_url(self.req, self.rset)


class CancelSelectAction(Action):
    category = 'mainactions'
    search_states = ('linksearch',)
    order = 10
    
    id = 'cancel'
    title = _('cancel select')
    
    def url(self):
        target, link_eid, r_type, searched_type = self.req.search_state[1]
        return self.build_url(rql="Any X WHERE X eid %s" % link_eid,
                              vid='edition', __mode='normal')


class ViewAction(Action):
    category = 'mainactions'    
    __selectors__ = (match_user_group, searchstate_accept)
    require_groups = ('users', 'managers')
    order = 0
    
    id = 'view'
    title = _('view')
    
    @classmethod
    def accept_rset(cls, req, rset, row, col):
        # interesting if it propose another view than the current one
        vid = req.form.get('vid')
        if vid and vid != vid_from_rset(req, rset, cls.schema):
            return 1
        return 0
    
    def url(self):
        params = self.req.form.copy()
        params.pop('vid', None)
        params.pop('__message', None)
        return self.build_url(self.req.relative_path(includeparams=False),
                              **params)


class ModifyAction(EntityAction):
    category = 'mainactions'
    __selectors__ = (one_line_rset, searchstate_accept)
    schema_action = 'update'
    order = 10
    
    id = 'edit'
    title = _('modify')
    
    @classmethod
    def has_permission(cls, entity, action):
        if entity.has_perm(action):
            return True
        # if user has no update right but it can modify some relation,
        # display action anyway
        for dummy in entity.srelations_by_category(('generic', 'metadata'),
                                                   'add'):
            return True
        for rschema, targetschemas, role in entity.relations_by_category(
            ('primary', 'secondary'), 'add'):
            if not rschema.is_final():
                return True
        return False

    def url(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return entity.absolute_url(vid='edition')
        

class MultipleEditAction(EntityAction):
    category = 'mainactions'
    __selectors__ = (two_lines_rset, one_etype_rset,
                     searchstate_accept)
    schema_action = 'update'
    order = 10
    
    id = 'muledit' # XXX get strange conflicts if id='edit'
    title = _('modify')
    
    def url(self):
        return self.build_url('view', rql=self.rset.rql, vid='muledit')


# generic secondary actions ###################################################

class ManagePermissions(LinkToEntityAction):
    accepts = ('Any',)
    category = 'moreactions'
    id = 'addpermission'
    title = _('manage permissions')
    order = 100

    etype = 'EPermission'
    rtype = 'require_permission'
    target = 'object'
    
    def url(self):
        return self.rset.get_entity(0, 0).absolute_url(vid='security')

    
class DeleteAction(EntityAction):
    category = 'moreactions' 
    __selectors__ = (searchstate_accept,)
    schema_action = 'delete'
    order = 20
    
    id = 'delete'
    title = _('delete')
    
    def url(self):
        if len(self.rset) == 1:
            entity = self.rset.get_entity(0, 0)
            return self.build_url(entity.rest_path(), vid='deleteconf')
        return self.build_url(rql=self.rset.printable_rql(), vid='deleteconf')
    
        
class CopyAction(EntityAction):
    category = 'moreactions'
    schema_action = 'add'
    order = 30
    
    id = 'copy'
    title = _('copy')
    
    def url(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return entity.absolute_url(vid='copy')


class AddNewAction(MultipleEditAction):
    """when we're seeing more than one entity with the same type, propose to
    add a new one
    """
    category = 'moreactions'
    id = 'addentity'
    order = 40
    
    def etype_rset_selector(cls, req, rset, **kwargs):
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

    def has_add_perm_selector(cls, req, rset, **kwargs):
        eschema = cls.schema.eschema(rset.description[0][0])
        if not (eschema.is_final() or eschema.is_subobject(strict=True)) \
               and eschema.has_perm(req, 'add'):
            return 1
        return 0
    __selectors__ = (match_search_state,
                     chainfirst(etype_rset_selector,
                                chainall(two_lines_rset, one_etype_rset,
                                         has_add_perm_selector)))

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
    category = 'useractions'
    __selectors__ = authenticated_user,
    order = 10
    
    id = 'myprefs'
    title = _('user preferences')

    def url(self):
        return self.build_url(self.id)


class UserInfoAction(Action):
    category = 'useractions'
    __selectors__ = authenticated_user,
    order = 20
    
    id = 'myinfos'
    title = _('personnal informations')

    def url(self):
        return self.build_url('euser/%s'%self.req.user.login, vid='edition')


class LogoutAction(Action):
    category = 'useractions'
    __selectors__ = authenticated_user,
    order = 30
    
    id = 'logout'
    title = _('logout')

    def url(self):
        return self.build_url(self.id)

    
# site actions ################################################################

class ManagersAction(Action):
    category = 'siteactions'
    __abstract__ = True
    __selectors__ = match_user_group,
    require_groups = ('managers',)

    def url(self):
        return self.build_url(self.id)

    
class SiteConfigurationAction(ManagersAction):
    order = 10
    id = 'siteconfig'
    title = _('site configuration')

    
class ManageAction(ManagersAction):
    order = 20
    id = 'manage'
    title = _('manage')


class ViewSchemaAction(Action):
    category = 'siteactions'
    id = 'schema'
    title = _("site schema")
    __selectors__ = yes,
    order = 30
    
    def url(self):
        return self.build_url(self.id)


# content type specific actions ###############################################

class FollowAction(EntityAction):
    category = 'mainactions'
    accepts = ('Bookmark',)
    
    id = 'follow'
    title = _('follow')
    
    def url(self):
        return self.rset.get_entity(self.row or 0, self.col or 0).actual_url()

class UserPreferencesEntityAction(EntityAction):
    __selectors__ = EntityAction.__selectors__ + (one_line_rset, match_user_group,)
    require_groups = ('owners', 'managers')
    category = 'mainactions'
    accepts = ('EUser',)
    
    id = 'prefs'
    title = _('preferences')
    
    def url(self):
        login = self.rset.get_entity(self.row or 0, self.col or 0).login
        return self.build_url('euser/%s'%login, vid='epropertiesform')

# schema view action
def schema_view(cls, req, rset, row=None, col=None, view=None,
                **kwargs):
    if view is None or not view.id == 'schema':
        return 0
    return 1

class DownloadOWLSchemaAction(Action):
    category = 'mainactions'
    id = 'download_as_owl'
    title = _('download schema as owl')
    __selectors__ = none_rset, schema_view
   
    def url(self):
        return self.build_url('view', vid='owl')

