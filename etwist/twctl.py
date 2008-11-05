"""cubicweb-clt handlers for twisted
"""

import sys

from cubicweb.toolsutils import CommandHandler
from cubicweb.web.webctl import WebCreateHandler

# trigger configuration registration
import cubicweb.etwist.twconfig # pylint: disable-msg=W0611


class TWCreateHandler(WebCreateHandler):
    cfgname = 'twisted'

    def bootstrap(self, cubes, inputlevel=0):
        """bootstrap this configuration"""
        print '** twisted configuration'
        mainpyfile = self.config.server_file()
        mainpy = open(mainpyfile, 'w')
        mainpy.write('''
from cubicweb.etwist import server
application = server.main(%r, %r)
''' % (self.config.appid, self.config.name))
        mainpy.close()
        print 'application\'s twisted file %s generated' % mainpyfile
        super(TWCreateHandler, self).bootstrap(cubes, inputlevel)


class TWStartHandler(CommandHandler):
    cmdname = 'start'
    cfgname = 'twisted'

    def start_command(self, config, debug):
        command = ['%s `which twistd`' % sys.executable]
        for ctl_opt, server_opt in (('pid-file', 'pidfile'),
                                    ('uid', 'uid'),
                                    ('log-file', 'logfile',)):
            value = config[ctl_opt]
            if not value or (debug and ctl_opt == 'log-file'):
                continue
            command.append('--%s %s' % (server_opt, value))
        if debug:
            command.append('-n')
        if config['profile']:
            command.append('-p %s --savestats' % config['profile'])
        command.append('-oy')
        command.append(self.config.server_file())
        return ' '.join(command)


class TWStopHandler(CommandHandler):
    cmdname = 'stop'
    cfgname = 'twisted'
    
    
try:
    from cubicweb.server import serverctl

    class AllInOneCreateHandler(serverctl.RepositoryCreateHandler, TWCreateHandler):
        """configuration to get a web application running in a twisted web
        server integrating a repository server in the same process
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
    
