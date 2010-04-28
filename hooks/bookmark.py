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
"""bookmark related hooks

"""
__docformat__ = "restructuredtext en"

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
    __select__ = hook.Hook.__select__ & hook.match_rtype('bookmarked_by',)
    category = 'bookmark'
    events = ('after_delete_relation',)

    def __call__(self):
        AutoDeleteBookmarkOp(self._cw,
                             bookmark=self._cw.entity_from_eid(self.eidfrom))
