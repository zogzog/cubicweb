"""abstract action classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.appobject import AppRsetObject
from cubicweb.common.registerers import action_registerer
from cubicweb.common.selectors import add_etype_selector, \
     match_search_state, searchstate_accept_one, \
     searchstate_accept_one_but_etype
    
_ = unicode


class Action(AppRsetObject):
    """abstract action. Handle the .search_states attribute to match
    request search state. 
    """
    __registry__ = 'actions'
    __registerer__ = action_registerer
    __selectors__ = (match_search_state,)
    # by default actions don't appear in link search mode
    search_states = ('normal',) 
    property_defs = {
        'visible':  dict(type='Boolean', default=True,
                         help=_('display the action or not')),
        'order':    dict(type='Int', default=99,
                         help=_('display order of the action')),
        'category': dict(type='String', default='moreactions',
                         vocabulary=('mainactions', 'moreactions', 'addrelated',
                                     'useractions', 'siteactions', 'hidden'),
                         help=_('context where this component should be displayed')),
    }
    site_wide = True # don't want user to configuration actions eproperties
    category = 'moreactions'
    
    @classmethod
    def accept_rset(cls, req, rset, row, col):
        user = req.user
        action = cls.schema_action
        if row is None:
            score = 0
            need_local_check = [] 
            geteschema = cls.schema.eschema
            for etype in rset.column_types(0):
                accepted = cls.accept(user, etype)
                if not accepted:
                    return 0
                if action:
                    eschema = geteschema(etype)
                    if not user.matching_groups(eschema.get_groups(action)):
                        if eschema.has_local_role(action):
                            # have to ckeck local roles
                            need_local_check.append(eschema)
                            continue
                        else:
                            # even a local role won't be enough
                            return 0
                score += accepted
            if need_local_check:
                # check local role for entities of necessary types
                for i, row in enumerate(rset):
                    if not rset.description[i][0] in need_local_check:
                        continue
                    if not cls.has_permission(rset.get_entity(i, 0), action):
                        return 0
                    score += 1
            return score
        col = col or 0
        etype = rset.description[row][col]
        score = cls.accept(user, etype)
        if score and action:
            if not cls.has_permission(rset.get_entity(row, col), action):
                return 0
        return score
    
    @classmethod
    def has_permission(cls, entity, action):
        """defined in a separated method to ease overriding (see ModifyAction
        for instance)
        """
        return entity.has_perm(action)
    
    def url(self):
        """return the url associated with this action"""
        raise NotImplementedError
    
    def html_class(self):
        if self.req.selected(self.url()):
            return 'selected'
        if self.category:
            return 'box' + self.category.capitalize()

class UnregisteredAction(Action):
    """non registered action used to build boxes. Unless you set them
    explicitly, .vreg and .schema attributes at least are None.
    """
    category = None
    id = None
    
    def __init__(self, req, rset, title, path, **kwargs):
        Action.__init__(self, req, rset)
        self.title = req._(title)
        self._path = path
        self.__dict__.update(kwargs)
        
    def url(self):
        return self._path


class AddEntityAction(Action):
    """link to the entity creation form. Concrete class must set .etype and
    may override .vid
    """
    __selectors__ = (add_etype_selector, match_search_state)
    vid = 'creation'
    etype = None
    
    def url(self):
        return self.build_url(vid=self.vid, etype=self.etype)


class EntityAction(Action):
    """an action for an entity. By default entity actions are only
    displayable on single entity result if accept match.
    """
    __selectors__ = (searchstate_accept_one,)
    schema_action = None
    condition = None
    
    @classmethod
    def accept(cls, user, etype):
        score = super(EntityAction, cls).accept(user, etype)
        if not score:
            return 0
        # check if this type of entity has the necessary relation
        if hasattr(cls, 'rtype') and not cls.relation_possible(etype):
            return 0
        return score

    
class LinkToEntityAction(EntityAction):
    """base class for actions consisting to create a new object
    with an initial relation set to an entity.
    Additionaly to EntityAction behaviour, this class is parametrized
    using .etype, .rtype and .target attributes to check if the
    action apply and if the logged user has access to it
    """
    etype = None
    rtype = None
    target = None
    category = 'addrelated'

    @classmethod
    def accept_rset(cls, req, rset, row, col):
        entity = rset.get_entity(row or 0, col or 0)
        # check if this type of entity has the necessary relation
        if hasattr(cls, 'rtype') and not cls.relation_possible(entity.e_schema):
            return 0
        score = cls.accept(req.user, entity.e_schema)
        if not score:
            return 0
        if not cls.check_perms(req, entity):
            return 0
        return score

    @classmethod
    def check_perms(cls, req, entity):
        if not cls.check_rtype_perm(req, entity):
            return False
        # XXX document this:
        # if user can create the relation, suppose it can create the entity
        # this is because we usually can't check "add" permission before the
        # entity has actually been created, and schema security should be
        # defined considering this
        #if not cls.check_etype_perm(req, entity):
        #    return False
        return True
        
    @classmethod
    def check_etype_perm(cls, req, entity):
        eschema = cls.schema.eschema(cls.etype)
        if not eschema.has_perm(req, 'add'):
            #print req.user.login, 'has no add perm on etype', cls.etype
            return False
        #print 'etype perm ok', cls
        return True

    @classmethod
    def check_rtype_perm(cls, req, entity):
        rschema = cls.schema.rschema(cls.rtype)
        # cls.target is telling us if we want to add the subject or object of
        # the relation
        if cls.target == 'subject':
            if not rschema.has_perm(req, 'add', toeid=entity.eid):
                #print req.user.login, 'has no add perm on subject rel', cls.rtype, 'with', entity
                return False
        elif not rschema.has_perm(req, 'add', fromeid=entity.eid):
            #print req.user.login, 'has no add perm on object rel', cls.rtype, 'with', entity
            return False
        #print 'rtype perm ok', cls
        return True
            
    def url(self):
        current_entity = self.rset.get_entity(self.row or 0, self.col or 0)
        linkto = '%s:%s:%s' % (self.rtype, current_entity.eid, self.target)
        return self.build_url(vid='creation', etype=self.etype,
                              __linkto=linkto,
                              __redirectpath=current_entity.rest_path(), # should not be url quoted!
                              __redirectvid=self.req.form.get('__redirectvid', ''))


class LinkToEntityAction2(LinkToEntityAction):
    """LinkToEntity action where the action is not usable on the same
    entity's type as the one refered by the .etype attribute
    """
    __selectors__ = (searchstate_accept_one_but_etype,)
    
