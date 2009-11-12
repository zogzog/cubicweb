"""cubicweb-clt handlers for twisted

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import sys

from cubicweb import underline_title
from cubicweb.toolsutils import CommandHandler
from cubicweb.web.webctl import WebCreateHandler

# trigger configuration registration
import cubicweb.etwist.twconfig # pylint: disable-msg=W0611

class TWCreateHandler(WebCreateHandler):
    cfgname = 'twisted'

class TWStartHandler(CommandHandler):
    cmdname = 'start'
    cfgname = 'twisted'

    def start_server(self, config, debug):
        from cubicweb.etwist import server
        server.run(config, debug)

class TWStopHandler(CommandHandler):
    cmdname = 'stop'
    cfgname = 'twisted'


try:
    from cubicweb.server import serverctl
    from cubicweb.server import serverctl
    WebCreateHandler
    class AllInOneCreateHandler(serverctl.RepositoryCreateHandler,
                                TWCreateHandler):
        """configuration to get an instance running in a twisted web server
        integrating a repository server in the same process
        """
        cfgname = 'all-in-one'

        def bootstrap(self, cubes, inputlevel=0):
            """bootstrap this configuration"""
            serverctl.RepositoryCreateHandler.bootstrap(self, cubes, inputlevel)
            TWCreateHandler.bootstrap(self, cubes, inputlevel)

    class AllInOneStartHandler(TWStartHandler):
        cmdname = 'start'
        cfgname = 'all-in-one'
        subcommand = 'cubicweb-twisted'

    class AllInOneStopHandler(serverctl.RepositoryStopHandler):
        cmdname = 'stop'
        cfgname = 'all-in-one'
        subcommand = 'cubicweb-twisted'

except ImportError:
    pass
