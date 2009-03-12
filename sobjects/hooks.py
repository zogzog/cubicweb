"""various library content hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.uilib import soup2xhtml
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


class TidyHtmlFields(Hook):
    """tidy HTML in rich text strings"""
    events = ('before_add_entity', 'before_update_entity')
    accepts = ('Any',)

    def call(self, session, entity):
        for formatattr, attr in entity.e_schema.format_fields.iteritems():
            try:
                value = entity[attr]
            except KeyError:
                continue # no text to tidy
            if isinstance(value, unicode): # filter out None and Binary
                if self.event == 'before_add_entity':
                    fmt = entity.get(formatattr)
                else:
                    fmt = entity.get_value(formatattr)
                if fmt == 'text/html':
                    entity[attr] = soup2xhtml(value, session.encoding)

