"""various library content hooks

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.server.hooksmanager import Hook
from cubicweb.server.pool import PreCommitOperation

class AddUpdateEUserHook(Hook):
    """ensure user logins are stripped"""
    events = ('before_add_entity', 'before_update_entity',)
    accepts = ('EUser',)
    
    def call(self, session, entity):
        if 'login' in entity and entity['login']:
            entity['login'] = entity['login'].strip()


class AutoDeleteBookmark(PreCommitOperation):
    def precommit_event(self):
        session = self.session
        if not self.beid in session.query_data('pendingeids', ()):
            if not session.unsafe_execute('Any X WHERE X bookmarked_by U, X eid %(x)s',
                                          {'x': self.beid}, 'x'):
                session.unsafe_execute('DELETE Bookmark X WHERE X eid %(x)s',
                                       {'x': self.beid}, 'x')
        
class DelBookmarkedByHook(Hook):
    """ensure user logins are stripped"""
    events = ('after_delete_relation',)
    accepts = ('bookmarked_by',)
    
    def call(self, session, subj, rtype, obj):
        AutoDeleteBookmark(session, beid=subj)
