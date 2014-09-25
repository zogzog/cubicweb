# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""twisted server for CubicWeb web instances"""
__docformat__ = "restructuredtext en"

import sys
import select
import traceback
import threading
from urlparse import urlsplit, urlunsplit
from cgi import FieldStorage, parse_header

from twisted.internet import reactor, task, threads
from twisted.web import http, server
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET


from logilab.mtconverter import xml_escape
from logilab.common.decorators import monkeypatch

from cubicweb import ConfigurationError, CW_EVENT_MANAGER
from cubicweb.utils import json_dumps
from cubicweb.web import DirectResponse
from cubicweb.web.application import CubicWebPublisher
from cubicweb.etwist.request import CubicWebTwistedRequestAdapter
from cubicweb.etwist.http import HTTPResponse

def start_task(interval, func):
    lc = task.LoopingCall(func)
    # wait until interval has expired to actually start the task, else we have
    # to wait all tasks to be finished for the server to be actually started
    lc.start(interval, now=False)


class CubicWebRootResource(resource.Resource):
    def __init__(self, config, repo):
        resource.Resource.__init__(self)
        self.config = config
        # instantiate publisher here and not in init_publisher to get some
        # checks done before daemonization (eg versions consistency)
        self.appli = CubicWebPublisher(repo, config)
        self.base_url = config['base-url']
        self.https_url = config['https-url']
        global MAX_POST_LENGTH
        MAX_POST_LENGTH = config['max-post-length']

    def init_publisher(self):
        config = self.config
        # when we have an in-memory repository, clean unused sessions every XX
        # seconds and properly shutdown the server
        if config['repository-uri'] == 'inmemory://':
            if config.pyro_enabled():
                # if pyro is enabled, we have to register to the pyro name
                # server, create a pyro daemon, and create a task to handle pyro
                # requests
                self.appli.repo.warning('remote repository access through pyro is deprecated')
                self.pyro_daemon = self.appli.repo.pyro_register()
                self.pyro_listen_timeout = 0.02
                self.appli.repo.looping_task(1, self.pyro_loop_event)
            if config.mode != 'test':
                reactor.addSystemEventTrigger('before', 'shutdown',
                                              self.shutdown_event)
                self.appli.repo.start_looping_tasks()
        self.set_url_rewriter()
        CW_EVENT_MANAGER.bind('after-registry-reload', self.set_url_rewriter)

    def start_service(self):
        start_task(self.appli.session_handler.clean_sessions_interval,
                   self.appli.session_handler.clean_sessions)

    def set_url_rewriter(self):
        self.url_rewriter = self.appli.vreg['components'].select_or_none('urlrewriter')

    def shutdown_event(self):
        """callback fired when the server is shutting down to properly
        clean opened sessions
        """
        self.appli.repo.shutdown()

    def pyro_loop_event(self):
        """listen for pyro events"""
        try:
            self.pyro_daemon.handleRequests(self.pyro_listen_timeout)
        except select.error:
            return

    def getChild(self, path, request):
        """Indicate which resource to use to process down the URL's path"""
        return self

    def render(self, request):
        """Render a page from the root resource"""
        # reload modified files in debug mode
        if self.config.debugmode:
            self.config.uiprops.reload_if_needed()
            if self.https_url:
                self.config.https_uiprops.reload_if_needed()
            self.appli.vreg.reload_if_needed()
        if self.config['profile']: # default profiler don't trace threads
            return self.render_request(request)
        else:
            deferred = threads.deferToThread(self.render_request, request)
            return NOT_DONE_YET

    def render_request(self, request):
        try:
            # processing HUGE files (hundred of megabytes) in http.processReceived
            # blocks other HTTP requests processing
            # due to the clumsy & slow parsing algorithm of cgi.FieldStorage
            # so we deferred that part to the cubicweb thread
            request.process_multipart()
            return self._render_request(request)
        except Exception:
            trace = traceback.format_exc()
            return HTTPResponse(stream='<pre>%s</pre>' % xml_escape(trace),
                                code=500, twisted_request=request)

    def _render_request(self, request):
        origpath = request.path
        host = request.host
        # dual http/https access handling: expect a rewrite rule to prepend
        # 'https' to the path to detect https access
        https = False
        if origpath.split('/', 2)[1] == 'https':
            origpath = origpath[6:]
            request.uri = request.uri[6:]
            https = True
        if self.url_rewriter is not None:
            # XXX should occur before authentication?
            path = self.url_rewriter.rewrite(host, origpath, request)
            request.uri.replace(origpath, path, 1)
        else:
            path = origpath
        req = CubicWebTwistedRequestAdapter(request, self.appli.vreg, https)
        try:
            ### Try to generate the actual request content
            content = self.appli.handle_request(req, path)
        except DirectResponse as ex:
            return ex.response
        # at last: create twisted object
        return HTTPResponse(code    = req.status_out,
                            headers = req.headers_out,
                            stream  = content,
                            twisted_request=req._twreq)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    @classmethod
    def debug(cls, msg, *a, **kw):
        pass
    info = warning = error = critical = exception = debug


JSON_PATHS = set(('json',))
FRAME_POST_PATHS = set(('validateform',))

orig_gotLength = http.Request.gotLength
@monkeypatch(http.Request)
def gotLength(self, length):
    orig_gotLength(self, length)
    if length > MAX_POST_LENGTH: # length is 0 on GET
        path = self.channel._path.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1]
        self.clientproto = 'HTTP/1.1' # not yet initialized
        self.channel.persistent = 0   # force connection close on cleanup
        self.setResponseCode(http.REQUEST_ENTITY_TOO_LARGE)
        if path in JSON_PATHS: # XXX better json path detection
            self.setHeader('content-type',"application/json")
            body = json_dumps({'reason': 'request max size exceeded'})
        elif path in FRAME_POST_PATHS: # XXX better frame post path detection
            self.setHeader('content-type',"text/html")
            body = ('<script type="text/javascript">'
                    'window.parent.handleFormValidationResponse(null, null, null, %s, null);'
                    '</script>' % json_dumps( (False, 'request max size exceeded', None) ))
        else:
            self.setHeader('content-type',"text/html")
            body = ("<html><head><title>Processing Failed</title></head><body>"
                    "<b>request max size exceeded</b></body></html>")
        self.setHeader('content-length', str(len(body)))
        self.write(body)
        # see request.finish(). Done here since we get error due to not full
        # initialized request
        self.finished = 1
        if not self.queued:
            self._cleanup()
        for d in self.notifications:
            d.callback(None)
        self.notifications = []

@monkeypatch(http.Request)
def requestReceived(self, command, path, version):
    """Called by channel when all data has been received.

    This method is not intended for users.
    """
    self.content.seek(0, 0)
    self.args = {}
    self.files = {}
    self.stack = []
    self.method, self.uri = command, path
    self.clientproto = version
    x = self.uri.split('?', 1)
    if len(x) == 1:
        self.path = self.uri
    else:
        self.path, argstring = x
        self.args = http.parse_qs(argstring, 1)
    # cache the client and server information, we'll need this later to be
    # serialized and sent with the request so CGIs will work remotely
    self.client = self.channel.transport.getPeer()
    self.host = self.channel.transport.getHost()
    # Argument processing
    ctype = self.getHeader('content-type')
    self._do_process_multipart = False
    if self.method == "POST" and ctype:
        key, pdict = parse_header(ctype)
        if key == 'application/x-www-form-urlencoded':
            self.args.update(http.parse_qs(self.content.read(), 1))
            self.content.seek(0)
        elif key == 'multipart/form-data':
            # defer this as it can be extremely time consumming
            # with big files
            self._do_process_multipart = True
    self.process()

@monkeypatch(http.Request)
def process_multipart(self):
    if not self._do_process_multipart:
        return
    form = FieldStorage(self.content, self.received_headers,
                        environ={'REQUEST_METHOD': 'POST'},
                        keep_blank_values=1,
                        strict_parsing=1)
    for key in form:
        values = form[key]
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if value.filename:
                if value.done != -1: # -1 is transfer has been interrupted
                    self.files.setdefault(key, []).append((value.filename, value.file))
                else:
                    self.files.setdefault(key, []).append((None, None))
            else:
                self.args.setdefault(key, []).append(value.value)

from logging import getLogger
from cubicweb import set_log_methods
LOGGER = getLogger('cubicweb.twisted')
set_log_methods(CubicWebRootResource, LOGGER)

def run(config, debug=None, repo=None):
    # repo may by passed during test.
    #
    # Test has already created a repo object so we should not create a new one.
    # Explicitly passing the repo object avoid relying on the fragile
    # config.repository() cache. We could imagine making repo a mandatory
    # argument and receives it from the starting command directly.
    if debug is not None:
        config.debugmode = debug
    config.check_writeable_uid_directory(config.appdatahome)
    # create the site
    if repo is None:
        repo = config.repository()
    root_resource = CubicWebRootResource(config, repo)
    website = server.Site(root_resource)
    # serve it via standard HTTP on port set in the configuration
    port = config['port'] or 8080
    interface = config['interface']
    reactor.suggestThreadPoolSize(config['webserver-threadpool-size'])
    reactor.listenTCP(port, website, interface=interface)
    if not config.debugmode:
        if sys.platform == 'win32':
            raise ConfigurationError("Under windows, you must use the service management "
                                     "commands (e.g : 'net start my_instance)'")
        from logilab.common.daemon import daemonize
        LOGGER.info('instance started in the background on %s', root_resource.base_url)
        whichproc = daemonize(config['pid-file'], umask=config['umask'])
        if whichproc: # 1 = orig process, 2 = first fork, None = second fork (eg daemon process)
            return whichproc # parent process
    root_resource.init_publisher() # before changing uid
    if config['uid'] is not None:
        from logilab.common.daemon import setugid
        setugid(config['uid'])
    root_resource.start_service()
    LOGGER.info('instance started on %s', root_resource.base_url)
    # avoid annoying warnign if not in Main Thread
    signals = threading.currentThread().getName() == 'MainThread'
    if config['profile']:
        import cProfile
        cProfile.runctx('reactor.run(installSignalHandlers=%s)' % signals,
                        globals(), locals(), config['profile'])
    else:
        reactor.run(installSignalHandlers=signals)
