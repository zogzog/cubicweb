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
"""entity classes user and group entities

"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import cached

from cubicweb import Unauthorized
from cubicweb.entities import AnyEntity, fetch_config

class CWGroup(AnyEntity):
    __regid__ = 'CWGroup'
    fetch_attrs, fetch_order = fetch_config(['name'])
    fetch_unrelated_order = fetch_order

    def db_key_name(self):
        """XXX goa specific"""
        return self.get('name')


class CWUser(AnyEntity):
    __regid__ = 'CWUser'
    fetch_attrs, fetch_order = fetch_config(['login', 'firstname', 'surname'])
    fetch_unrelated_order = fetch_order

    # used by repository to check if  the user can log in or not
    AUTHENTICABLE_STATES = ('activated',)

    # low level utilities #####################################################
    def __init__(self, *args, **kwargs):
        groups = kwargs.pop('groups', None)
        properties = kwargs.pop('properties', None)
        super(CWUser, self).__init__(*args, **kwargs)
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
            return self._cw.vreg.typed_value(key, self.properties[key])
        except KeyError:
            pass
        except ValueError:
            self.warning('incorrect value for eproperty %s of user %s',
                         key, self.login)
        return self._cw.vreg.property_value(key)

    def matching_groups(self, groups):
        """return the number of the given group(s) in which the user is

        :type groups: str or iterable(str)
        :param groups: a group name or an iterable on group names
        """
        if isinstance(groups, basestring):
            groups = frozenset((groups,))
        elif isinstance(groups, (tuple, list)):
            groups = frozenset(groups)
        return len(groups & self.groups) # XXX return the resulting set instead of its size

    def is_in_group(self, group):
        """convience / shortcut method to test if the user belongs to `group`
        """
        return group in self.groups

    def is_anonymous(self):
        """ checks if user is an anonymous user"""
        #FIXME on the web-side anonymous user is detected according
        # to config['anonymous-user'], we don't have this info on
        # the server side.
        return self.groups == frozenset(('guests', ))

    def owns(self, eid):
        try:
            return self._cw.execute(
                'Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                {'x': eid, 'u': self.eid})
        except Unauthorized:
            return False
    owns = cached(owns, keyarg=1)

    def has_permission(self, pname, contexteid=None):
        rql = 'Any P WHERE P is CWPermission, U eid %(u)s, U in_group G, '\
              'P name %(pname)s, P require_group G'
        kwargs = {'pname': pname, 'u': self.eid}
        if contexteid is not None:
            rql += ', X require_permission P, X eid %(x)s'
            kwargs['x'] = contexteid
        try:
            return self._cw.execute(rql, kwargs)
        except Unauthorized:
            return False

    # presentation utilities ##################################################

    def name(self):
        """construct a name using firstname / surname or login if not defined"""

        if self.firstname and self.surname:
            return self._cw._('%(firstname)s %(surname)s') % {
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
EUser = class_renamed('EUser', CWUser)
EGroup = class_renamed('EGroup', CWGroup)
