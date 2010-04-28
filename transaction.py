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
"""undoable transaction objects.


This module is in the cubicweb package and not in cubicweb.server because those
objects should be accessible to client through pyro, where the cubicweb.server
package may not be installed.

"""
__docformat__ = "restructuredtext en"
_ = unicode

from cubicweb import RepositoryError


ACTION_LABELS = {
    'C': _('entity creation'),
    'U': _('entity update'),
    'D': _('entity deletion'),
    'A': _('relation add'),
    'R': _('relation removal'),
    }


class NoSuchTransaction(RepositoryError):
    pass


class Transaction(object):
    """an undoable transaction"""

    def __init__(self, uuid, time, ueid):
        self.uuid = uuid
        self.datetime = time
        self.user_eid = ueid
        # should be set by the dbapi connection
        self.req = None

    def __repr__(self):
        return '<Transaction %s by %s on %s>' % (
            self.uuid, self.user_eid, self.datetime)

    def user(self):
        """return the user entity which has done the transaction,
        none if not found.
        """
        return self.req.execute('Any X WHERE X eid %(x)s',
                                {'x': self.user_eid}).get_entity(0, 0)

    def actions_list(self, public=True):
        """return an ordered list of action effectued during that transaction

        if public is true, return only 'public' action, eg not ones triggered
        under the cover by hooks.
        """
        return self.req.cnx.transaction_actions(self.uuid, public)


class AbstractAction(object):
    def __init__(self, action, public, order):
        self.action = action
        self.public = public
        self.order = order

    @property
    def label(self):
        return ACTION_LABELS[self.action]


class EntityAction(AbstractAction):
    def __init__(self, action, public, order, etype, eid, changes):
        AbstractAction.__init__(self, action, public, order)
        self.etype = etype
        self.eid = eid
        self.changes = changes

    def __repr__(self):
        return '<%s: %s %s (%s)>' % (
            self.label, self.eid, self.changes,
            self.public and 'dbapi' or 'hook')


class RelationAction(AbstractAction):
    def __init__(self, action, public, order, rtype, eidfrom, eidto):
        AbstractAction.__init__(self, action, public, order)
        self.rtype = rtype
        self.eid_from = eidfrom
        self.eid_to = eidto

    def __repr__(self):
        return '<%s: %s %s %s (%s)>' % (
            self.label, self.eid_from, self.rtype, self.eid_to,
            self.public and 'dbapi' or 'hook')
