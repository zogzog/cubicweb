"""cubicweb-ctl commands and command handlers common to twisted/modpython
web configuration

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import underline_title
from cubicweb.toolsutils import CommandHandler
from logilab.common.shellutils import ASK

class WebCreateHandler(CommandHandler):
    cmdname = 'create'

    def bootstrap(self, cubes, inputlevel=0):
        """bootstrap this configuration"""
        print '\n' + underline_title('Generic web configuration')
        config = self.config
        if config.repo_method == 'pyro':
            print '\n' + underline_title('Pyro configuration')
            config.input_config('pyro', inputlevel)
        if ASK.confirm('Allow anonymous access ?', False):
            config.global_set_option('anonymous-user', 'anon')
            config.global_set_option('anonymous-password', 'anon')

    def postcreate(self):
        """hooks called once instance's initialization has been completed"""
