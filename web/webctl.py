"""cubicweb-ctl commands and command handlers common to twisted/modpython
web configuration

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.toolsutils import CommandHandler, confirm


class WebCreateHandler(CommandHandler):
    cmdname = 'create'

    def bootstrap(self, cubes, inputlevel=0):
        """bootstrap this configuration"""
        print '** generic web configuration'
        config = self.config
        if config.repo_method == 'pyro':
            print
            print '** repository server configuration'
            print '-' * 72
            config.input_config('pyro-client', inputlevel)
        if confirm('allow anonymous access', False):
            config.global_set_option('anonymous-user', 'anon')
            config.global_set_option('anonymous-password', 'anon')

    def postcreate(self):
        """hooks called once application's initialization has been completed"""
