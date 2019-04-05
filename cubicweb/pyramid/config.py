# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Configuration for CubicWeb instances on top of a Pyramid application"""

from os import path
import random
import string

from logilab.common.configuration import merge_options

from cubicweb.cwconfig import CONFIGURATIONS
from cubicweb.server.serverconfig import ServerConfiguration
from cubicweb.toolsutils import fill_templated_file
from cubicweb.web.webconfig import BaseWebConfiguration, WebConfigurationBase


def get_random_secret_key():
    """Return 50-character secret string"""
    chars = string.ascii_letters + string.digits
    secure_random = random.SystemRandom()

    return "".join([secure_random.choice(chars) for i in range(50)])


class CubicWebPyramidConfiguration(BaseWebConfiguration, ServerConfiguration):
    """Pyramid application with a CubicWeb repository"""
    name = 'pyramid'

    cubicweb_appobject_path = (BaseWebConfiguration.cubicweb_appobject_path
                               | ServerConfiguration.cubicweb_appobject_path)
    cube_appobject_path = (BaseWebConfiguration.cube_appobject_path
                           | ServerConfiguration.cube_appobject_path)

    options = merge_options(ServerConfiguration.options
                            + BaseWebConfiguration.options)

    def init_log(self, *args, **kwargs):
        """Rely on logging configuration in Pyramid's .ini file, do nothing
        here.
        """

    def write_development_ini(self, cubes):
        """Write a 'development.ini' file into apphome."""
        template_fpath = path.join(path.dirname(__file__), 'development.ini.tmpl')
        target_fpath = path.join(self.apphome, 'development.ini')
        context = {
            'instance': self.appid,
            'cubename': cubes[0],
            'session-secret': get_random_secret_key(),
            'auth-authtkt-persistent-secret': get_random_secret_key(),
            'auth-authtkt-session-secret': get_random_secret_key(),
        }
        fill_templated_file(template_fpath, target_fpath, context)


CONFIGURATIONS.append(CubicWebPyramidConfiguration)


class AllInOneConfiguration(WebConfigurationBase, ServerConfiguration):
    """repository and web instance in the same Pyramid process"""
    name = 'all-in-one'
    options = merge_options((
        ('profile',
         {'type': 'string',
          'default': None,
          'help': 'profile code and use the specified file to store stats if this option is set',
          'group': 'web', 'level': 3,
          }),
    ) + WebConfigurationBase.options + ServerConfiguration.options
    )

    cubicweb_appobject_path = (
        WebConfigurationBase.cubicweb_appobject_path
        | ServerConfiguration.cubicweb_appobject_path
    )
    cube_appobject_path = (
        WebConfigurationBase.cube_appobject_path
        | ServerConfiguration.cube_appobject_path
    )


CONFIGURATIONS.append(AllInOneConfiguration)
