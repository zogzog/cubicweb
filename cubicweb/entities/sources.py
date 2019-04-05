# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
        if not self.config:
            return {}
        return text_to_dict(self.config)


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

    @property
    def repo_source(self):
        """repository only property, not available from the web side (eg
        self._cw is expected to be a server session)
        """
        return self._cw.repo.source_by_eid(self.eid)


class CWSourceHostConfig(_CWSourceCfgMixIn, AnyEntity):
    __regid__ = 'CWSourceHostConfig'
    fetch_attrs, cw_fetch_order = fetch_config(['match_host', 'config'])

    @property
    def cwsource(self):
        return self.cw_host_config_of[0]

    def match(self, hostname):
        return re.match(self.match_host, hostname)


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
