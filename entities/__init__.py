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
"""base application's entities class implementation: `AnyEntity`"""

__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.deprecation import deprecated
from logilab.common.decorators import cached

from cubicweb import Unauthorized, typed_eid
from cubicweb.entity import Entity


class AnyEntity(Entity):
    """an entity instance has e_schema automagically set on the class and
    instances have access to their issuing cursor
    """
    __regid__ = 'Any'
    __implements__ = ()

    @classmethod
    def cw_create_url(cls, req, **kwargs):
        """ return the url of the entity creation form for this entity type"""
        return req.build_url('add/%s' % cls.__regid__, **kwargs)

    # meta data api ###########################################################

    def dc_title(self):
        """return a suitable *unicode* title for this entity"""
        for rschema, attrschema in self.e_schema.attribute_definitions():
            if rschema.meta:
                continue
            value = self.cw_attr_value(rschema.type)
            if value:
                # make the value printable (dates, floats, bytes, etc.)
                return self.printable_value(rschema.type, value, attrschema.type,
                                            format='text/plain')
        return u'%s #%s' % (self.dc_type(), self.eid)

    def dc_long_title(self):
        """return a more detailled title for this entity"""
        return self.dc_title()

    def dc_description(self, format='text/plain'):
        """return a suitable description for this entity"""
        if 'description' in self.e_schema.subjrels:
            return self.printable_value('description', format=format)
        return u''

    def dc_authors(self):
        """return a suitable description for the author(s) of the entity"""
        try:
            return ', '.join(u.name() for u in self.owned_by)
        except Unauthorized:
            return u''

    def dc_creator(self):
        """return a suitable description for the creator of the entity"""
        if self.creator:
            return self.creator.name()
        return u''

    def dc_date(self, date_format=None):# XXX default to ISO 8601 ?
        """return latest modification date of this entity"""
        return self._cw.format_date(self.modification_date, date_format=date_format)

    def dc_type(self, form=''):
        """return the display name for the type of this entity (translated)"""
        return self.e_schema.display_name(self._cw, form)

    def dc_language(self):
        """return language used by this entity (translated)"""
        # check if entities has internationalizable attributes
        # XXX one is enough or check if all String attributes are internationalizable?
        for rschema, attrschema in self.e_schema.attribute_definitions():
            if rschema.rdef(self.e_schema, attrschema).internationalizable:
                return self._cw._(self._cw.user.property_value('ui.language'))
        return self._cw._(self._cw.vreg.property_value('ui.language'))

    @property
    def creator(self):
        """return the CWUser entity which has created this entity, or None if
        unknown or if the curent user doesn't has access to this euser
        """
        try:
            return self.created_by[0]
        except (Unauthorized, IndexError):
            return None

    # abstractions making the whole things (well, some at least) working ######

    def sortvalue(self, rtype=None):
        """return a value which can be used to sort this entity or given
        entity's attribute
        """
        if rtype is None:
            return self.dc_title().lower()
        value = self.cw_attr_value(rtype)
        # do not restrict to `unicode` because Bytes will return a `str` value
        if isinstance(value, basestring):
            return self.printable_value(rtype, format='text/plain').lower()
        return value

    # edition helper functions ################################################

    def linked_to(self, rtype, role, remove=True):
        """if entity should be linked to another using __linkto form param for
        the given relation/role, return eids of related entities

        This method is consuming matching link-to information from form params
        if `remove` is True (by default).
        """
        try:
            return self.__linkto[(rtype, role)]
        except AttributeError:
            self.__linkto = {}
        except KeyError:
            pass
        linktos = list(self._cw.list_form_param('__linkto'))
        linkedto = []
        for linkto in linktos[:]:
            ltrtype, eid, ltrole = linkto.split(':')
            if rtype == ltrtype and role == ltrole:
                # delete __linkto from form param to avoid it being added as
                # hidden input
                if remove:
                    linktos.remove(linkto)
                    self._cw.form['__linkto'] = linktos
                linkedto.append(typed_eid(eid))
        self.__linkto[(rtype, role)] = linkedto
        return linkedto

    # server side helpers #####################################################

# XXX:  store a reference to the AnyEntity class since it is hijacked in goa
#       configuration and we need the actual reference to avoid infinite loops
#       in mro
ANYENTITY = AnyEntity

def fetch_config(fetchattrs, mainattr=None, pclass=AnyEntity, order='ASC'):
    if pclass is ANYENTITY:
        pclass = AnyEntity # AnyEntity and ANYENTITY may be different classes
    if pclass is not None:
        fetchattrs += pclass.fetch_attrs
    if mainattr is None:
        mainattr = fetchattrs[0]
    @classmethod
    def fetch_order(cls, attr, var):
        if attr == mainattr:
            return '%s %s' % (var, order)
        return None
    return fetchattrs, fetch_order
