# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""twisted server configurations:

* the "twisted" configuration to get a web instance running in a standalone
  twisted web server which talk to a repository server using Pyro

* the "all-in-one" configuration to get a web instance running in a twisted
  web server integrating a repository server in the same process (only available
  if the repository part of the software is installed
"""
__docformat__ = "restructuredtext en"

from os.path import join

from logilab.common.configuration import Method, merge_options

from cubicweb.cwconfig import CONFIGURATIONS
from cubicweb.web.webconfig import WebConfiguration


class WebConfigurationBase(WebConfiguration):
    """web instance (in a twisted web server) client of a RQL server"""

    options = merge_options((
        # ctl configuration
        ('port',
         {'type' : 'int',
          'default': None,
          'help': 'http server port number (default to 8080)',
          'group': 'web', 'level': 0,
          }),
        ('interface',
         {'type' : 'string',
          'default': "",
          'help': 'http server address on which to listen (default to everywhere)',
          'group': 'web', 'level': 1,
          }),
        ('max-post-length',
         {'type' : 'bytes',
          'default': '100MB',
          'help': 'maximum length of HTTP request. Default to 100 MB.',
          'group': 'web', 'level': 1,
          }),
        ('profile',
         {'type' : 'string',
          'default': None,
          'help': 'profile code and use the specified file to store stats if this option is set',
          'group': 'web', 'level': 3,
          }),
        ('host',
         {'type' : 'string',
          'default': None,
          'help': 'host name if not correctly detectable through gethostname',
          'group': 'main', 'level': 1,
          }),
        ('pid-file',
         {'type' : 'string',
          'default': Method('default_pid_file'),
          'help': 'repository\'s pid file',
          'group': 'main', 'level': 2,
          }),
        ('uid',
         {'type' : 'string',
          'default': None,
          'help': 'if this option is set, use the specified user to start \
the repository rather than the user running the command',
          'group': 'main', 'level': WebConfiguration.mode == 'system'
          }),
        ('pyro-server',
         {'type' : 'yn',
          # pyro is only a recommends by default, so don't activate it here
          'default': False,
          'help': 'run a pyro server',
          'group': 'main', 'level': 1,
          }),
        ('webserver-threadpool-size',
         {'type': 'int',
          'default': 4,
          'help': "size of twisted's reactor threadpool. It should probably be not too \
much greater than connection-poolsize",
          'group': 'web', 'level': 3,
          }),
        ) + WebConfiguration.options)

    def server_file(self):
        return join(self.apphome, '%s-%s.py' % (self.appid, self.name))

    def default_base_url(self):
        from socket import getfqdn
        return 'http://%s:%s/' % (self['host'] or getfqdn().lower(), self['port'] or 8080)


try:
    from cubicweb.server.serverconfig import ServerConfiguration

    class AllInOneConfiguration(WebConfigurationBase, ServerConfiguration):
        """repository and web instance in the same twisted process"""
        name = 'all-in-one'
        options = merge_options(WebConfigurationBase.options
                                + ServerConfiguration.options)

        cubicweb_appobject_path = WebConfigurationBase.cubicweb_appobject_path | ServerConfiguration.cubicweb_appobject_path
        cube_appobject_path = WebConfigurationBase.cube_appobject_path | ServerConfiguration.cube_appobject_path
        def pyro_enabled(self):
            """tell if pyro is activated for the in memory repository"""
            return self['pyro-server']


    CONFIGURATIONS.append(AllInOneConfiguration)

except ImportError:
    pass
