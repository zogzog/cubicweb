# copyright 2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""cubicweb-forum views/forms/actions/components for web ui"""

from cubicweb import view
from cubicweb.predicates import is_instance
from cubicweb.web.views import primary, baseviews, uicfg
from cubicweb.web.views.uicfg import autoform_section as afs

class MyAFS(uicfg.AutoformSectionRelationTags):
    __select__ = is_instance('ForumThread')

_myafs = MyAFS()

_myafs.tag_object_of(('*', 'in_forum', 'Forum'), 'main', 'inlined')

afs.tag_object_of(('*', 'in_forum', 'Forum'), 'main', 'inlined')


class ForumSameETypeListView(baseviews.SameETypeListView):
    __select__ = baseviews.SameETypeListView.__select__ & is_instance('Forum')

    def call(self, **kwargs):
        _ = self._cw._
        _('Topic'), _('Description')
        _('Number of threads'), _('Last activity')
        _('''a long
tranlated line
hop.''')


class ForumLastActivity(view.EntityView):
    __regid__ = 'forum_last_activity'
    __select__ = view.EntityView.__select__ & is_instance('Forum')


class ForumPrimaryView(primary.PrimaryView):
    __select__ = primary.PrimaryView.__select__ & is_instance('Forum')

    def render_entity_attributes(self, entity):
        _ = self._cw._
        _('Subject'), _('Created'), _('Answers'),
        _('Last answered')
        _('This forum does not have any thread yet.')

class ForumThreadPrimaryView(primary.PrimaryView):
    __select__ = primary.PrimaryView.__select__ & is_instance('ForumThread')
