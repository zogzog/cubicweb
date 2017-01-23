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
from __future__ import print_function

import os
import sys

try:
    import win32serviceutil
    import win32service
except ImportError:
    print('Win32 extensions for Python are likely not installed.')
    sys.exit(3)

from os.path import join

from cubicweb.etwist.server import (CubicWebRootResource, reactor, server)

from logilab.common.shellutils import rm

import logging
from logging import getLogger, handlers
from cubicweb import set_log_methods
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg


def _check_env(env):
    env_vars = ('CW_INSTANCES_DIR', 'CW_INSTANCES_DATA_DIR', 'CW_RUNTIME_DIR')
    for var in env_vars:
        if var not in env:
            raise Exception('The environment variables %s must be set.' %
                            ', '.join(env_vars))
    if not env.get('USERNAME'):
        env['USERNAME'] = 'cubicweb'


class CWService(object, win32serviceutil.ServiceFramework):
    _svc_name_ = None
    _svc_display_name_ = None
    instance = None

    def __init__(self, *args, **kwargs):
        win32serviceutil.ServiceFramework.__init__(self, *args, **kwargs)
        cwcfg.load_cwctl_plugins()
        logger = getLogger('cubicweb')
        set_log_methods(CubicWebRootResource, logger)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logger = getLogger('cubicweb.twisted')
        logger.info('stopping %s service' % self.instance)
        reactor.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        logger = getLogger('cubicweb.twisted')
        handler = handlers.NTEventLogHandler('cubicweb')
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.info('starting %s service' % self.instance)
        try:
            _check_env(os.environ)
            # create the site
            config = cwcfg.config_for(self.instance)
            config.init_log(force=True)
            config.debugmode = False
            logger.info('starting cubicweb instance %s ', self.instance)
            config.info('clear ui caches')
            rm(join(config.appdatahome, 'uicache', '*'))
            root_resource = CubicWebRootResource(config, config.repository())
            website = server.Site(root_resource)
            # serve it via standard HTTP on port set in the configuration
            port = config['port'] or 8080
            logger.info('listening on port %s' % port)
            reactor.listenTCP(port, website)
            root_resource.init_publisher()
            root_resource.start_service()
            logger.info('instance started on %s', root_resource.base_url)
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            reactor.run()
        except Exception as e:
            logger.error('service %s stopped (cause: %s)' % (self.instance, e))
            logger.exception('what happened ...')
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
