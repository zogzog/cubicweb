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
"""hooks to ensure use_email / primary_email relations consistency

"""
__docformat__ = "restructuredtext en"

from cubicweb.server import hook

from logilab.common.compat import any


class SetUseEmailRelationOp(hook.Operation):
    """delay this operation to commit to avoid conflict with a late rql query
    already setting the relation
    """
    rtype = 'use_email'
    entity = email = None # make pylint happy

    def condition(self):
        """check entity has use_email set for the email address"""
        return not any(e for e in self.entity.use_email
                       if self.email.eid == e.eid)

    def precommit_event(self):
        if self.condition():
            self.session.execute(
                'SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % self.rtype,
                {'x': self.entity.eid, 'y': self.email.eid})


class SetPrimaryEmailRelationOp(SetUseEmailRelationOp):
    rtype = 'primary_email'

    def condition(self):
        """check entity has no primary_email set"""
        return not self.entity.primary_email


class SetPrimaryEmailHook(hook.Hook):
    """notify when a bug or story or version has its state modified"""
    __regid__ = 'setprimaryemail'
    __select__ = hook.Hook.__select__ & hook.match_rtype('use_email')
    category = 'email'
    events = ('after_add_relation',)

    def __call__(self):
        entity = self._cw.entity_from_eid(self.eidfrom)
        if 'primary_email' in entity.e_schema.subject_relations():
            SetPrimaryEmailRelationOp(self._cw, entity=entity,
                                      email=self._cw.entity_from_eid(self.eidto))

class SetUseEmailHook(hook.Hook):
    """notify when a bug or story or version has its state modified"""
    __regid__ = 'setprimaryemail'
    __select__ = hook.Hook.__select__ & hook.match_rtype('primary_email')
    category = 'email'
    events = ('after_add_relation',)

    def __call__(self):
        entity = self._cw.entity_from_eid(self.eidfrom)
        if 'use_email' in entity.e_schema.subject_relations():
            SetUseEmailRelationOp(self._cw, entity=entity,
                                  email=self._cw.entity_from_eid(self.eidto))
