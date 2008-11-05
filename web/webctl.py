"""cubicweb-ctl commands and command handlers common to twisted/modpython
web configuration

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.toolsutils import CommandHandler


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
    
    def postcreate(self):
        """hooks called once application's initialization has been completed"""
        
