"""provide utilies for web (live) unit testing"""

import socket
import logging
from os.path import join, dirname, exists
from StringIO import StringIO

#from twisted.application import service, strports
# from twisted.internet import reactor, task
from twisted.web2 import channel
from twisted.web2 import server
from twisted.web2 import static
from twisted.internet import reactor
from twisted.internet.error import CannotListenError

from logilab.common.testlib import TestCase

import cubicweb.web
from cubicweb.dbapi import in_memory_cnx
from cubicweb.etwist.server import CubicWebRootResource
from cubicweb.devtools import LivetestConfiguration, init_test_database



def get_starturl(port=7777, login=None, passwd=None):
    if login:
        return 'http://%s:%s/view?login=%s&password=%s' % (socket.gethostname(), port, login, passwd)
    else:
        return 'http://%s:%s/' % (socket.gethostname(), port)


class LivetestResource(CubicWebRootResource):
    """redefines main resource to search for data files in several directories"""

    def locateChild(self, request, segments):
        """Indicate which resource to use to process down the URL's path"""
        if len(segments) and segments[0] == 'data':
            # Anything in data/ is treated as static files
            datadir = self.config.locate_resource(segments[1])
            if datadir:
                return static.File(str(datadir), segments[1:])
        # Otherwise we use this single resource
        return self, ()
    
    
    
def make_site(cube, options=None):
    from cubicweb.etwist import twconfig # trigger configuration registration
    sourcefile = options.sourcefile
    config = LivetestConfiguration(cube, sourcefile,
                                   pyro_name=options.pyro_name,
                                   log_threshold=logging.DEBUG)
    source = config.sources()['system']
    init_test_database(driver=source['db-driver'], config=config)
    # if '-n' in sys.argv: # debug mode
    cubicweb = LivetestResource(config, debug=True)
    toplevel = cubicweb
    website = server.Site(toplevel)
    cube_dir = config.cube_dir(cube)
    for port in xrange(7777, 7798):
        try:
            reactor.listenTCP(port, channel.HTTPFactory(website))
            saveconf(cube_dir, port, source['db-user'], source['db-password'])
            break
        except CannotListenError, exc:
            print "port %s already in use, I will try another one" % port
    else:
        raise
    cubicweb.base_url = get_starturl(port=port)
    print "you can go here : %s" % cubicweb.base_url

def runserver():
    reactor.run()

def saveconf(templhome, port, user, passwd):
    import pickle
    conffile = file(join(templhome, 'test', 'livetest.conf'), 'w')
    
    pickle.dump((port, user, passwd, get_starturl(port, user, passwd)),
                conffile)
    conffile.close()


def loadconf(filename='livetest.conf'):
    import pickle
    return pickle.load(file(filename))


def execute_scenario(filename, **kwargs):
    """based on twill.parse.execute_file, but inserts cubicweb extensions"""
    from twill.parse import _execute_script
    stream = StringIO('extend_with cubicweb.devtools.cubicwebtwill\n' + file(filename).read())
    kwargs['source'] = filename
    _execute_script(stream, **kwargs)


def hijack_twill_output(new_output):
    from twill import commands as twc
    from twill import browser as twb
    twc.OUT = new_output
    twb.OUT = new_output
    
    
class LiveTestCase(TestCase):

    sourcefile = None
    cube = ''
    def setUp(self):
        assert self.cube, "You must specify a cube in your testcase"
        # twill can be quite verbose ...
        self.twill_output = StringIO()
        hijack_twill_output(self.twill_output)
        # build a config, and get a connection
        self.config = LivetestConfiguration(self.cube, self.sourcefile)
        _, user, passwd, _ = loadconf()
        self.repo, self.cnx = in_memory_cnx(self.config, user, passwd)
        self.setup_db(self.cnx)

    def tearDown(self):
        self.teardown_db(self.cnx)
    

    def setup_db(self, cnx):
        """override setup_db() to setup your environment"""

    def teardown_db(self, cnx):
        """override teardown_db() to clean up your environment"""

    def get_loggedurl(self):
        port, user, passwd, logged_url = loadconf()
        return logged_url

    def get_anonurl(self):
        port, _, _, _ = loadconf()
        return 'http://%s:%s/view?login=anon&password=anon' % (
            socket.gethostname(), port)

    # convenience
    execute_scenario = staticmethod(execute_scenario)


if __name__ == '__main__':
    runserver()


