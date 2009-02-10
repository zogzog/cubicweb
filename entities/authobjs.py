from logilab.common.decorators import cached

from cubicweb import Unauthorized
from cubicweb.entities import AnyEntity, fetch_config

class EGroup(AnyEntity):
    id = 'EGroup'
    fetch_attrs, fetch_order = fetch_config(['name'])
    __rtags__ = dict(in_group='create')

    def db_key_name(self):
        """XXX goa specific"""
        return self.get('name')

    
class EUser(AnyEntity):
    id = 'EUser'
    fetch_attrs, fetch_order = fetch_config(['login', 'firstname', 'surname'])
    
    __rtags__ = { 'firstname'  : 'secondary',
                  'surname'    : 'secondary',
                  'last_login_time' : 'generated',
                  'todo_by'    : 'create',
                  'use_email'  : 'inlineview', # 'primary',
                  'in_state'   : 'primary', 
                  'in_group'   : 'primary', 
                  ('owned_by', '*', 'object') : ('generated', 'link'),
                  ('created_by','*','object') : ('generated', 'link'),
                  }
    
    # used by repository to check if  the user can log in or not
    AUTHENTICABLE_STATES = ('activated',)

    # low level utilities #####################################################
    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups', None)
        properties = kwargs.pop('properties', None)
        super(EUser, self).__init__(*args, **kwargs)
        if groups is not None:
            self._groups = groups
        if properties is not None:
            self._properties = properties
            
    @property
    def groups(self):
        try:
            return self._groups
        except AttributeError:
            self._groups = set(g.name for g in self.in_group)
            return self._groups
        
    @property
    def properties(self):
        try:
            return self._properties
        except AttributeError:
            self._properties = dict((p.pkey, p.value) for p in self.reverse_for_user)
            return self._properties

    def property_value(self, key):
        try:
            # properties stored on the user aren't correctly typed
            # (e.g. all values are unicode string)
            return self.vreg.typed_value(key, self.properties[key])
        except KeyError:
            pass
        except ValueError:
            self.warning('incorrect value for eproperty %s of user %s', key, self.login)
        return self.vreg.property_value(key)
    
    def matching_groups(self, groups):
        """return the number of the given group(s) in which the user is

        :type groups: str or iterable(str)
        :param groups: a group name or an iterable on group names
        """
        if isinstance(groups, basestring):
            groups = frozenset((groups,))
        elif isinstance(groups, (tuple, list)):
            groups = frozenset(groups)
        return len(groups & self.groups)

    def is_in_group(self, group):
        """convience / shortcut method to test if the user belongs to `group`
        """
        return self.matching_groups(group) == 1

    def is_anonymous(self):
        """ checks if user is an anonymous user"""
        #FIXME on the web-side anonymous user is detected according
        # to config['anonymous-user'], we don't have this info on
        # the server side. 
        return self.groups == frozenset(('guests', ))

    def owns(self, eid):
        if hasattr(self.req, 'unsafe_execute'):
            # use unsafe_execute on the repository side, in case
            # session's user doesn't have access to EUser
            execute = self.req.unsafe_execute
        else:
            execute = self.req.execute
        try:
            return execute('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                           {'x': eid, 'u': self.eid}, 'x')
        except Unauthorized:
            return False
    owns = cached(owns, keyarg=1)

    def has_permission(self, pname, contexteid=None):
        rql = 'Any P WHERE P is EPermission, U eid %(u)s, U in_group G, '\
              'P name %(pname)s, P require_group G'
        kwargs = {'pname': pname, 'u': self.eid}
        cachekey = None
        if contexteid is not None:
            rql += ', X require_permission P, X eid %(x)s'
            kwargs['x'] = contexteid
            cachekey = 'x'
        try:
            return self.req.execute(rql, kwargs, cachekey)
        except Unauthorized:
            return False
    
    # presentation utilities ##################################################
    
    def name(self):
        """construct a name using firstname / surname or login if not defined"""
        
        if self.firstname and self.surname:
            return self.req._('%(firstname)s %(surname)s') % {
                'firstname': self.firstname, 'surname' : self.surname}
        if self.firstname:
            return self.firstname
        return self.login

    def dc_title(self):
        return self.login

    dc_long_title = name

    def db_key_name(self):
        """XXX goa specific"""
        return self.get('login')

from logilab.common.deprecation import class_renamed
Euser = class_renamed('Euser', EUser)
Euser.id = 'Euser'
