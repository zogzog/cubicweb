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

from socket import gethostname

from logilab.common.decorators import clear_cache

from cubicweb import validation_error
from cubicweb.predicates import is_instance
from cubicweb.server import SOURCE_TYPES, hook


class SourceHook(hook.Hook):
    __abstract__ = True
    category = 'cw.sources'


# repo sources synchronization #################################################

class SourceAddedHook(SourceHook):
    __regid__ = 'cw.sources.added'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('after_add_entity',)
    def __call__(self):
        try:
            sourcecls = SOURCE_TYPES[self.entity.type]
        except KeyError:
            msg = _('Unknown source type')
            raise validation_error(self.entity, {('type', 'subject'): msg})
        # ignore creation of the system source done during database
        # initialisation, as config for this source is in a file and handling
        # is done separatly (no need for the operation either)
        if self.entity.name != 'system':
            sourcecls._check_config_dict(self.entity.eid, self.entity.host_config,
                                         raise_on_error=not self._cw.vreg.config.repairing)


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
        if 'config' in self.entity.cw_edited or 'url' in self.entity.cw_edited:
            if self.entity.name == 'system' and self.entity.config:
                msg = _("Configuration of the system source goes to "
                        "the 'sources' file, not in the database")
                raise validation_error(self.entity, {('config', 'subject'): msg})
