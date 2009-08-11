"""provide utilies for web (live) unit testing

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import os
import socket
import logging
from os.path import join, dirname, normpath, abspath
from StringIO import StringIO

#from twisted.application import service, strports
# from twisted.internet import reactor, task
from twisted.web2 import channel
from twisted.web2 import server
from twisted.web2 import static
from twisted.internet import reactor
from twisted.internet.error import CannotListenError

from logilab.common.testlib import TestCase

from cubicweb.dbapi import in_memory_cnx
from cubicweb.etwist.server import CubicWebRootResource
from cubicweb.devtools import BaseApptestConfiguration, init_test_database



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



class LivetestConfiguration(BaseApptestConfiguration):
    init_repository = False

    def __init__(self, cube=None, sourcefile=None, pyro_name=None,
                 log_threshold=logging.CRITICAL):
        BaseApptestConfiguration.__init__(self, cube, log_threshold=log_threshold)
        self.appid = pyro_name or cube
        # don't change this, else some symlink problems may arise in some
        # environment (e.g. mine (syt) ;o)
        # XXX I'm afraid this test will prevent to run test from a production
        # environment
        self._sources = None
        # instance cube test
        if cube is not None:
            self.apphome = self.cube_dir(cube)
        elif 'web' in os.getcwd().split(os.sep):
            # web test
            self.apphome = join(normpath(join(dirname(__file__), '..')), 'web')
        else:
            # cube test
            self.apphome = abspath('..')
        self.sourcefile = sourcefile
        self.global_set_option('realm', '')
        self.use_pyro = pyro_name is not None

    def pyro_enabled(self):
        if self.use_pyro:
            return True
        else:
            return False



def make_site(cube, options=None):
    from cubicweb.etwist import twconfig # trigger configuration registration
    config = LivetestConfiguration(cube, options.sourcefile,
                                   pyro_name=options.pyro_name,
                                   log_threshold=logging.DEBUG)
    init_test_database(config=config)
    # if '-n' in sys.argv: # debug mode
    cubicweb = LivetestResource(config, debug=True)
    toplevel = cubicweb
    website = server.Site(toplevel)
    cube_dir = config.cube_dir(cube)
    source = config.sources()['system']
    for port in xrange(7777, 7798):
        try:
            reactor.listenTCP(port, channel.HTTPFactory(website))
            saveconf(cube_dir, port, source['db-user'], source['db-password'])
            break
        except CannotListenError:
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
