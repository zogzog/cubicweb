"""various library content hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.uilib import soup2xhtml
from cubicweb.server.hooksmanager import Hook
from cubicweb.server.pool import PreCommitOperation


class AddUpdateCWUserHook(Hook):
    """ensure user logins are stripped"""
    events = ('before_add_entity', 'before_update_entity',)
    accepts = ('CWUser',)

    def call(self, session, entity):
        if 'login' in entity and entity['login']:
            entity['login'] = entity['login'].strip()


class AutoDeleteBookmark(PreCommitOperation):
    beid = None # make pylint happy
    def precommit_event(self):
        session = self.session
        if not self.beid in session.transaction_data.get('pendingeids', ()):
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
        metaattrs = entity.e_schema.meta_attributes()
        for metaattr, (metadata, attr) in metaattrs.iteritems():
            if metadata == 'format':
                try:
                    value = entity[attr]
                except KeyError:
                    continue # no text to tidy
                if isinstance(value, unicode): # filter out None and Binary
                    if self.event == 'before_add_entity':
                        fmt = entity.get(metaattr)
                    else:
                        fmt = entity.get_value(metaattr)
                    if fmt == 'text/html':
                        entity[attr] = soup2xhtml(value, session.encoding)
