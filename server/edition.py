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
"""helper classes to handle server-side edition of entities"""
__docformat__ = "restructuredtext en"

from copy import copy
from yams import ValidationError


_MARKER = object()

class dict_protocol_catcher(object):
    def __init__(self, entity):
        self.__entity = entity
    def __getitem__(self, attr):
        return self.__entity.cw_edited[attr]
    def __setitem__(self, attr, value):
        self.__entity.cw_edited[attr] = value
    def __getattr__(self, attr):
        return getattr(self.__entity, attr)


class EditedEntity(dict):
    """encapsulate entities attributes being written by an RQL query"""
    def __init__(self, entity, **kwargs):
        dict.__init__(self, **kwargs)
        self.entity = entity
        self.skip_security = set()
        self.querier_pending_relations = {}
        self.saved = False

    def __hash__(self):
        # dict|set keyable
        return hash(id(self))

    def __lt__(self, other):
        # we don't want comparison by value inherited from dict
        return id(self) < id(other)

    def __eq__(self, other):
        return id(self) == id(other)

    def __setitem__(self, attr, value):
        assert attr != 'eid'
        # don't add attribute into skip_security if already in edited
        # attributes, else we may accidentaly skip a desired security check
        if attr not in self:
            self.skip_security.add(attr)
        self.edited_attribute(attr, value)

    def __delitem__(self, attr):
        assert not self.saved, 'too late to modify edited attributes'
        super(EditedEntity, self).__delitem__(attr)
        self.entity.cw_attr_cache.pop(attr, None)

    def __copy__(self):
        # default copy protocol fails in EditedEntity.__setitem__ because
        # copied entity has no skip_security attribute at this point
        return EditedEntity(self.entity, **self)

    def pop(self, attr, *args):
        # don't update skip_security by design (think to storage api)
        assert not self.saved, 'too late to modify edited attributes'
        value = super(EditedEntity, self).pop(attr, *args)
        self.entity.cw_attr_cache.pop(attr, *args)
        return value

    def setdefault(self, attr, default):
        assert attr != 'eid'
        # don't add attribute into skip_security if already in edited
        # attributes, else we may accidentaly skip a desired security check
        if attr not in self:
            self[attr] = default
        return self[attr]

    def update(self, values, skipsec=True):
        if skipsec:
            setitem = self.__setitem__
        else:
            setitem = self.edited_attribute
        for attr, value in values.iteritems():
            setitem(attr, value)

    def edited_attribute(self, attr, value):
        """attribute being edited by a rql query: should'nt be added to
        skip_security
        """
        assert not self.saved, 'too late to modify edited attributes'
        super(EditedEntity, self).__setitem__(attr, value)
        self.entity.cw_attr_cache[attr] = value
        # mark attribute as needing purge by the client
        self.entity._cw_dont_cache_attribute(attr)

    def oldnewvalue(self, attr):
        """returns the couple (old attr value, new attr value)

        NOTE: will only work in a before_update_entity hook
        """
        assert not self.saved, 'too late to get the old value'
        # get new value and remove from local dict to force a db query to
        # fetch old value
        newvalue = self.entity.cw_attr_cache.pop(attr, _MARKER)
        oldvalue = getattr(self.entity, attr)
        if newvalue is not _MARKER:
            self.entity.cw_attr_cache[attr] = newvalue
        else:
            newvalue = oldvalue
        return oldvalue, newvalue

    def set_defaults(self):
        """set default values according to the schema"""
        for attr, value in self.entity.e_schema.defaults():
            if not attr in self:
                self[str(attr)] = value

    def check(self, creation=False):
        """check the entity edition against its schema. Only final relation
        are checked here, constraint on actual relations are checked in hooks
        """
        entity = self.entity
        if creation:
            # on creations, we want to check all relations, especially
            # required attributes
            relations = [rschema for rschema in entity.e_schema.subject_relations()
                         if rschema.final and rschema.type != 'eid']
        else:
            relations = [entity._cw.vreg.schema.rschema(rtype)
                         for rtype in self]
        try:
            entity.e_schema.check(dict_protocol_catcher(entity),
                                  creation=creation, relations=relations)
        except ValidationError as ex:
            ex.entity = self.entity.eid
            raise

    def clone(self):
        thecopy = EditedEntity(copy(self.entity))
        thecopy.entity.cw_attr_cache = copy(self.entity.cw_attr_cache)
        thecopy.entity._cw_related_cache = {}
        thecopy.update(self, skipsec=False)
        return thecopy
