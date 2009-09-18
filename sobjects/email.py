"""hooks to ensure use_email / primary_email relations consistency

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.server.hooksmanager import Hook
from cubicweb.server.pool import PreCommitOperation
from cubicweb.server.repository import ensure_card_respected

class SetUseEmailRelationOp(PreCommitOperation):
    """delay this operation to commit to avoid conflict with a late rql query
    already setting the relation
    """
    rtype = 'use_email'
    fromeid = toeid = None # make pylint happy

    def condition(self):
        """check entity has use_email set for the email address"""
        return not self.session.unsafe_execute(
            'Any X WHERE X eid %(x)s, X use_email Y, Y eid %(y)s',
            {'x': self.fromeid, 'y': self.toeid}, 'x')

    def precommit_event(self):
        session = self.session
        if self.condition():
            # we've to handle cardinaly by ourselves since we're using unsafe_execute
            # but use session.execute and not session.unsafe_execute to check we
            # can change the relation
            ensure_card_respected(session.execute, session,
                                  self.fromeid, self.rtype, self.toeid)
            session.unsafe_execute(
                'SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % self.rtype,
                {'x': self.fromeid, 'y': self.toeid}, 'x')

class SetPrimaryEmailRelationOp(SetUseEmailRelationOp):
    rtype = 'primary_email'

    def condition(self):
        """check entity has no primary_email set"""
        return not self.session.unsafe_execute(
            'Any X WHERE X eid %(x)s, X primary_email Y',
            {'x': self.fromeid}, 'x')


class SetPrimaryEmailHook(Hook):
    """notify when a bug or story or version has its state modified"""
    events = ('after_add_relation',)
    accepts = ('use_email',)

    def call(self, session, fromeid, rtype, toeid):
        subjtype = session.describe(fromeid)[0]
        eschema = self.vreg.schema[subjtype]
        if 'primary_email' in eschema.subject_relations():
            SetPrimaryEmailRelationOp(session, vreg=self.vreg,
                                      fromeid=fromeid, toeid=toeid)

class SetUseEmailHook(Hook):
    """notify when a bug or story or version has its state modified"""
    events = ('after_add_relation',)
    accepts = ('primary_email',)

    def call(self, session, fromeid, rtype, toeid):
        subjtype = session.describe(fromeid)[0]
        eschema = self.vreg.schema[subjtype]
        if 'use_email' in eschema.subject_relations():
            SetUseEmailRelationOp(session, vreg=self.vreg,
                                  fromeid=fromeid, toeid=toeid)
