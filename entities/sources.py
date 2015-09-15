# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""data source related entities"""

__docformat__ = "restructuredtext en"

import re
from socket import gethostname
import logging

from logilab.common.textutils import text_to_dict
from logilab.common.configuration import OptionError
from logilab.mtconverter import xml_escape

from cubicweb.entities import AnyEntity, fetch_config

class _CWSourceCfgMixIn(object):
    @property
    def dictconfig(self):
        return self.config and text_to_dict(self.config) or {}

    def update_config(self, skip_unknown=False, **config):
        from cubicweb.server import SOURCE_TYPES
        from cubicweb.server.serverconfig import (SourceConfiguration,
                                                  generate_source_config)
        cfg = self.dictconfig
        cfg.update(config)
        options = SOURCE_TYPES[self.type].options
        sconfig = SourceConfiguration(self._cw.vreg.config, options=options)
        for opt, val in cfg.items():
            try:
                sconfig.set_option(opt, val)
            except OptionError:
                if skip_unknown:
                    continue
                raise
        cfgstr = unicode(generate_source_config(sconfig), self._cw.encoding)
        self.cw_set(config=cfgstr)


class CWSource(_CWSourceCfgMixIn, AnyEntity):
    __regid__ = 'CWSource'
    fetch_attrs, cw_fetch_order = fetch_config(['name', 'type'])

    @property
    def host_config(self):
        dictconfig = self.dictconfig
        host = gethostname()
        for hostcfg in self.host_configs:
            if hostcfg.match(host):
                self.info('matching host config %s for source %s',
                          hostcfg.match_host, self.name)
                dictconfig.update(hostcfg.dictconfig)
        return dictconfig

    @property
    def host_configs(self):
        return self.reverse_cw_host_config_of

    def init_mapping(self, mapping):
        for key, options in mapping:
            if isinstance(key, tuple): # relation definition
                assert len(key) == 3
                restrictions = ['X relation_type RT, RT name %(rt)s']
                kwargs = {'rt': key[1]}
                if key[0] != '*':
                    restrictions.append('X from_entity FT, FT name %(ft)s')
                    kwargs['ft'] = key[0]
                if key[2] != '*':
                    restrictions.append('X to_entity TT, TT name %(tt)s')
                    kwargs['tt'] = key[2]
                rql = 'Any X WHERE %s' % ','.join(restrictions)
                schemarset = self._cw.execute(rql, kwargs)
            elif key[0].isupper(): # entity type
                schemarset = self._cw.execute('CWEType X WHERE X name %(et)s',
                                              {'et': key})
            else: # relation type
                schemarset = self._cw.execute('CWRType X WHERE X name %(rt)s',
                                              {'rt': key})
            for schemaentity in schemarset.entities():
                self._cw.create_entity('CWSourceSchemaConfig',
                                       cw_for_source=self,
                                       cw_schema=schemaentity,
                                       options=options)

    @property
    def repo_source(self):
        """repository only property, not available from the web side (eg
        self._cw is expected to be a server session)
        """
        return self._cw.repo.sources_by_eid[self.eid]


class CWSourceHostConfig(_CWSourceCfgMixIn, AnyEntity):
    __regid__ = 'CWSourceHostConfig'
    fetch_attrs, cw_fetch_order = fetch_config(['match_host', 'config'])

    @property
    def cwsource(self):
        return self.cw_host_config_of[0]

    def match(self, hostname):
        return re.match(self.match_host, hostname)


class CWSourceSchemaConfig(AnyEntity):
    __regid__ = 'CWSourceSchemaConfig'
    fetch_attrs, cw_fetch_order = fetch_config(['cw_for_source', 'cw_schema', 'options'])

    def dc_title(self):
        return self._cw._(self.cw_etype) + ' #%s' % self.eid

    @property
    def schema(self):
        return self.cw_schema[0]

    @property
    def cwsource(self):
        return self.cw_for_source[0]


class CWDataImport(AnyEntity):
    __regid__ = 'CWDataImport'
    repo_source = _logs = None # please pylint

    def init(self):
        self._logs = []
        self.repo_source = self.cwsource.repo_source

    def dc_title(self):
        return '%s [%s]' % (self.printable_value('start_timestamp'),
                            self.printable_value('status'))

    @property
    def cwsource(self):
        return self.cw_import_of[0]

    def record_debug(self, msg, path=None, line=None):
        self._log(logging.DEBUG, msg, path, line)
        self.repo_source.debug(msg)

    def record_info(self, msg, path=None, line=None):
        self._log(logging.INFO, msg, path, line)
        self.repo_source.info(msg)

    def record_warning(self, msg, path=None, line=None):
        self._log(logging.WARNING, msg, path, line)
        self.repo_source.warning(msg)

    def record_error(self, msg, path=None, line=None):
        self._status = u'failed'
        self._log(logging.ERROR, msg, path, line)
        self.repo_source.error(msg)

    def record_fatal(self, msg, path=None, line=None):
        self._status = u'failed'
        self._log(logging.FATAL, msg, path, line)
        self.repo_source.fatal(msg)

    def _log(self, severity, msg, path=None, line=None):
        encodedmsg =  u'%s\t%s\t%s\t%s<br/>' % (severity, path or u'',
                                                line or u'', xml_escape(msg))
        self._logs.append(encodedmsg)

    def write_log(self, session, **kwargs):
        if 'status' not in kwargs:
            kwargs['status'] = getattr(self, '_status', u'success')
        self.cw_set(log=u'<br/>'.join(self._logs), **kwargs)
        self._logs = []
