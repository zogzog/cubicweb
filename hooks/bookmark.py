"""bookmark related hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.selectors import entity_implements
from cubicweb.server import hook


class AutoDeleteBookmarkOp(hook.Operation):
    bookmark = None # make pylint happy
    def precommit_event(self):
        if not self.session.deleted_in_transaction(self.bookmark.eid):
            if not self.bookmark.bookmarked_by:
                self.bookmark.delete()


class DelBookmarkedByHook(hook.Hook):
    """ensure user logins are stripped"""
    __regid__ = 'autodelbookmark'
    __select__ = hook.Hook.__select__ & entity_implements('bookmarked_by',)
    category = 'bookmark'
    events = ('after_delete_relation',)

    def __call__(self):
        AutoDeleteBookmarkOp(self._cw,
                             bookmark=self._cw.entity_from_eid(self.eidfrom))
