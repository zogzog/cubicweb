import os
import os.path as osp
import sys

import win32serviceutil
import win32service
import win32event

from cubicweb.etwist.server import (CubicWebRootResource, reactor, server,
                                    parsePOSTData, channel)

from logging import getLogger, handlers
from cubicweb import set_log_methods
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg

logger = getLogger('cubicweb.twisted')
logger.handlers = [handlers.NTEventLogHandler('cubicweb')]

os.environ['CW_INSTANCES_DIR'] = r'C:\etc\cubicweb.d'
os.environ['USERNAME'] = 'cubicweb'


class CWService(object, win32serviceutil.ServiceFramework):
    _svc_name_ = None
    _svc_display_name_ = None
    instance = None

    def __init__(self, *args, **kwargs):
        win32serviceutil.ServiceFramework.__init__(self, *args, **kwargs)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        cwcfg.load_cwctl_plugins()
        set_log_methods(CubicWebRootResource, logger)
        server.parsePOSTData = parsePOSTData

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logger.info('stopping %s service' % self.instance)
        win32event.SetEvent(self._stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        logger = getLogger('cubicweb.twisted')
        logger.info('starting %s service' % instance)
        try:
            # create the site
            config = cwcfg.config_for(self.instance)
            root_resource = CubicWebRootResource(config, False)
            website = server.Site(root_resource)
            # serve it via standard HTTP on port set in the configuration
            port = config['port'] or 8080
            logger.info('listening on port %s' % port)
            reactor.listenTCP(port, channel.HTTPFactory(website))
            root_resource.init_publisher()
            root_resource.start_service()
            logger.info('instance started on %s', root_resource.base_url)
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            reactor.run()
        except Exception, e:
            logger.error('service %s stopped (cause: %s)' % (self.instance, e))
            logger.exception('what happened ...')
            self.SvcStop()

