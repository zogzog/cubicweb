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
"""cubicweb-clt handlers for twisted"""

from os.path import join

from logilab.common.shellutils import rm

from cubicweb.toolsutils import CommandHandler
from cubicweb.web.webctl import WebCreateHandler

# trigger configuration registration
import cubicweb.etwist.twconfig # pylint: disable=W0611

class TWCreateHandler(WebCreateHandler):
    cfgname = 'twisted'

class TWStartHandler(CommandHandler):
    cmdname = 'start'
    cfgname = 'twisted'

    def start_server(self, config):
        from cubicweb.etwist import server
        config.info('clear ui caches')
        for cachedir in ('uicache', 'uicachehttps'):
            rm(join(config.appdatahome, cachedir, '*'))
        return server.run(config)

class TWStopHandler(CommandHandler):
    cmdname = 'stop'
    cfgname = 'twisted'

    def poststop(self):
        pass


try:
    from cubicweb.server import serverctl
    class AllInOneCreateHandler(serverctl.RepositoryCreateHandler,
                                TWCreateHandler):
        """configuration to get an instance running in a twisted web server
        integrating a repository server in the same process
        """
        cfgname = 'all-in-one'

        def bootstrap(self, cubes, automatic=False, inputlevel=0):
            """bootstrap this configuration"""
            serverctl.RepositoryCreateHandler.bootstrap(self, cubes, automatic, inputlevel)
            TWCreateHandler.bootstrap(self, cubes, automatic, inputlevel)

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
