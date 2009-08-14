"""hooks to ensure use_email / primary_email relations consistency

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.server import hook

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
            self.session.unsafe_execute(
                'SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % self.rtype,
                {'x': self.entity.eid, 'y': self.email.eid}, 'x')

class SetPrimaryEmailRelationOp(SetUseEmailRelationOp):
    rtype = 'primary_email'

    def condition(self):
        """check entity has no primary_email set"""
        return not self.entity.primary_email


class SetPrimaryEmailHook(hook.Hook):
    """notify when a bug or story or version has its state modified"""
    __id__ = 'setprimaryemail'
    __select__ = hook.Hook.__select__ & hook.match_rtype('use_email')
    category = 'email'
    events = ('after_add_relation',)

    def __call__(self):
        entity = self.cw_req.entity_from_eid(self.eidfrom)
        if 'primary_email' in entity.e_schema.subject_relations():
            SetPrimaryEmailRelationOp(self.cw_req, entity=entity,
                                      email=self.cw_req.entity_from_eid(self.eidto))

class SetUseEmailHook(hook.Hook):
    """notify when a bug or story or version has its state modified"""
    __id__ = 'setprimaryemail'
    __select__ = hook.Hook.__select__ & hook.match_rtype('primary_email')
    category = 'email'
    events = ('after_add_relation',)

    def __call__(self):
        entity = self.cw_req.entity_from_eid(self.eidfrom)
        if 'use_email' in entity.e_schema.subject_relations():
            SetUseEmailRelationOp(self.cw_req, entity=entity,
                                  email=self.cw_req.entity_from_eid(self.eidto))
