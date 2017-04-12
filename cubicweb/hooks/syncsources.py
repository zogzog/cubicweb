# copyright 2010-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""hooks for repository sources synchronization"""

from cubicweb import _

from cubicweb import validation_error
from cubicweb.predicates import is_instance
from cubicweb.server import SOURCE_TYPES, hook


class SourceHook(hook.Hook):
    __abstract__ = True
    category = 'cw.sources'

    def get_source(self, source_entity):
        if source_entity.name == 'system':
            return self._cw.repo.system_source
        return self._cw.repo.get_source(source_entity.type, source_entity.name,
                                        {}, source_entity.eid)


class SourceAddedHook(SourceHook):
    __regid__ = 'cw.sources.added'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('after_add_entity',)

    def __call__(self):
        if self.entity.type not in SOURCE_TYPES:
            msg = _('Unknown source type')
            raise validation_error(self.entity, {('type', 'subject'): msg})

        source = self.get_source(self.entity)
        source.check_urls(self.entity)
        source.check_config(self.entity)


class SourceRemovedHook(SourceHook):
    __regid__ = 'cw.sources.removed'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('before_delete_entity',)

    def __call__(self):
        if self.entity.name == 'system':
            msg = _("You cannot remove the system source")
            raise validation_error(self.entity, {None: msg})


class SourceUpdatedHook(SourceHook):
    __regid__ = 'cw.sources.configupdate'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('before_update_entity',)

    def __call__(self):
        if 'name' in self.entity.cw_edited:
            oldname, newname = self.entity.cw_edited.oldnewvalue('name')
            if oldname == 'system':
                msg = _("You cannot rename the system source")
                raise validation_error(self.entity, {('name', 'subject'): msg})

        source = self.get_source(self.entity)
        if 'url' in self.entity.cw_edited:
            source.check_urls(self.entity)
        if 'config' in self.entity.cw_edited:
            source.check_config(self.entity)
