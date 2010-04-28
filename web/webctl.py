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
"""cubicweb-ctl commands and command handlers common to twisted/modpython
web configuration

"""
__docformat__ = "restructuredtext en"

from cubicweb.toolsutils import CommandHandler, underline_title
from logilab.common.shellutils import ASK

class WebCreateHandler(CommandHandler):
    cmdname = 'create'

    def bootstrap(self, cubes, inputlevel=0):
        """bootstrap this configuration"""
        print '\n' + underline_title('Generic web configuration')
        config = self.config
        if config.repo_method == 'pyro' or config.pyro_enabled():
            print '\n' + underline_title('Pyro configuration')
            config.input_config('pyro', inputlevel)
        if ASK.confirm('Allow anonymous access ?', False):
            config.global_set_option('anonymous-user', 'anon')
            config.global_set_option('anonymous-password', 'anon')

    def postcreate(self):
        """hooks called once instance's initialization has been completed"""
