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

class SourceAddedOp(hook.Operation):
    entity = None # make pylint happy
    def postcommit_event(self):
        self.cnx.repo.add_source(self.entity)

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
            sourcecls.check_conf_dict(self.entity.eid, self.entity.host_config,
                                      fail_if_unknown=not self._cw.vreg.config.repairing)
            SourceAddedOp(self._cw, entity=self.entity)


class SourceRemovedOp(hook.Operation):
    uri = None # make pylint happy
    def postcommit_event(self):
        self.cnx.repo.remove_source(self.uri)

class SourceRemovedHook(SourceHook):
    __regid__ = 'cw.sources.removed'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('before_delete_entity',)
    def __call__(self):
        if self.entity.name == 'system':
            msg = _("You cannot remove the system source")
            raise validation_error(self.entity, {None: msg})
        SourceRemovedOp(self._cw, uri=self.entity.name)


class SourceConfigUpdatedOp(hook.DataOperationMixIn, hook.Operation):

    def precommit_event(self):
        self.__processed = []
        for source in self.get_data():
            if not self.cnx.deleted_in_transaction(source.eid):
                conf = source.repo_source.check_config(source)
                self.__processed.append( (source, conf) )

    def postcommit_event(self):
        for source, conf in self.__processed:
            source.repo_source.update_config(source, conf)


class SourceRenamedOp(hook.LateOperation):
    oldname = newname = None # make pylint happy

    def postcommit_event(self):
        repo = self.cnx.repo
        # XXX race condition
        source = repo.sources_by_uri.pop(self.oldname)
        source.uri = self.newname
        source.public_config['uri'] = self.newname
        repo.sources_by_uri[self.newname] = source
        clear_cache(repo, 'source_defs')


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
            SourceRenamedOp(self._cw, oldname=oldname, newname=newname)
        if 'config' in self.entity.cw_edited or 'url' in self.entity.cw_edited:
            if self.entity.name == 'system' and self.entity.config:
                msg = _("Configuration of the system source goes to "
                        "the 'sources' file, not in the database")
                raise validation_error(self.entity, {('config', 'subject'): msg})
            SourceConfigUpdatedOp.get_instance(self._cw).add_data(self.entity)


class SourceHostConfigUpdatedHook(SourceHook):
    __regid__ = 'cw.sources.hostconfigupdate'
    __select__ = SourceHook.__select__ & is_instance('CWSourceHostConfig')
    events = ('after_add_entity', 'after_update_entity', 'before_delete_entity',)
    def __call__(self):
        if self.entity.match(gethostname()):
            if self.event == 'after_update_entity' and \
                   not 'config' in self.entity.cw_edited:
                return
            try:
                SourceConfigUpdatedOp.get_instance(self._cw).add_data(self.entity.cwsource)
            except IndexError:
                # XXX no source linked to the host config yet
                pass
