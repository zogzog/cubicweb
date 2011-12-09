# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
import os
import os.path as osp
import select
import traceback
import threading
import re
from hashlib import md5 # pylint: disable=E0611
from os.path import join
from time import mktime
from datetime import date, timedelta
from urlparse import urlsplit, urlunsplit
from cgi import FieldStorage, parse_header
from cStringIO import StringIO

from twisted.internet import reactor, task, threads
from twisted.internet.defer import maybeDeferred
from twisted.web import http, server
from twisted.web import static, resource
from twisted.web.server import NOT_DONE_YET


from logilab.common.decorators import monkeypatch

from cubicweb import (AuthenticationError, ConfigurationError,
                      CW_EVENT_MANAGER, CubicWebException)
from cubicweb.utils import json_dumps
from cubicweb.web import Redirect, DirectResponse, StatusResponse, LogOut
from cubicweb.web.application import CubicWebPublisher
from cubicweb.web.http_headers import generateDateTime
from cubicweb.etwist.request import CubicWebTwistedRequestAdapter
from cubicweb.etwist.http import HTTPResponse

def start_task(interval, func):
    lc = task.LoopingCall(func)
    # wait until interval has expired to actually start the task, else we have
    # to wait all task to be finished for the server to be actually started
    lc.start(interval, now=False)

def host_prefixed_baseurl(baseurl, host):
    scheme, netloc, url, query, fragment = urlsplit(baseurl)
    netloc_domain = '.' + '.'.join(netloc.split('.')[-2:])
    if host.endswith(netloc_domain):
        netloc = host
    baseurl = urlunsplit((scheme, netloc, url, query, fragment))
    return baseurl


class ForbiddenDirectoryLister(resource.Resource):
    def render(self, request):
        return HTTPResponse(twisted_request=request,
                            code=http.FORBIDDEN,
                            stream='Access forbidden')


class NoListingFile(static.File):
    def __init__(self, config, path=None):
        if path is None:
            path = config.static_directory
        static.File.__init__(self, path)
        self.config = config

    def set_expires(self, request):
        if not self.config.debugmode:
            # XXX: Don't provide additional resource information to error responses
            #
            # the HTTP RFC recommands not going further than 1 year ahead
            expires = date.today() + timedelta(days=6*30)
            request.setHeader('Expires', generateDateTime(mktime(expires.timetuple())))

    def directoryListing(self):
        return ForbiddenDirectoryLister()


class DataLookupDirectory(NoListingFile):
    def __init__(self, config, path):
        self.md5_version = config.instance_md5_version()
        NoListingFile.__init__(self, config, path)
        self.here = path
        self._defineChildResources()
        if self.config.debugmode:
            self.data_modconcat_basepath = '/data/??'
        else:
            self.data_modconcat_basepath = '/data/%s/??' % self.md5_version

    def _defineChildResources(self):
        self.putChild(self.md5_version, self)

    def getChild(self, path, request):
        if not path:
            uri = request.uri
            if uri.startswith('/https/'):
                uri = uri[6:]
            if uri.startswith(self.data_modconcat_basepath):
                resource_relpath = uri[len(self.data_modconcat_basepath):]
                if resource_relpath:
                    paths = resource_relpath.split(',')
                    try:
                        self.set_expires(request)
                        return ConcatFiles(self.config, paths)
                    except ConcatFileNotFoundError:
                        return self.childNotFound
            return self.directoryListing()
        childpath = join(self.here, path)
        dirpath, rid = self.config.locate_resource(childpath)
        if dirpath is None:
            # resource not found
            return self.childNotFound
        filepath = os.path.join(dirpath, rid)
        if os.path.isdir(filepath):
            resource = DataLookupDirectory(self.config, childpath)
            # cache resource for this segment path to avoid recomputing
            # directory lookup
            self.putChild(path, resource)
            return resource
        else:
            self.set_expires(request)
            return NoListingFile(self.config, filepath)


class FCKEditorResource(NoListingFile):

    def getChild(self, path, request):
        pre_path = request.path.split('/')[1:]
        if pre_path[0] == 'https':
            pre_path.pop(0)
            uiprops = self.config.https_uiprops
        else:
            uiprops = self.config.uiprops
        return static.File(osp.join(uiprops['FCKEDITOR_PATH'], path))


class LongTimeExpiringFile(DataLookupDirectory):
    """overrides static.File and sets a far future ``Expires`` date
    on the resouce.

    versions handling is done by serving static files by different
    URLs for each version. For instance::

      http://localhost:8080/data-2.48.2/cubicweb.css
      http://localhost:8080/data-2.49.0/cubicweb.css
      etc.

    """
    def _defineChildResources(self):
        pass


class ConcatFileNotFoundError(CubicWebException):
    pass


class ConcatFiles(LongTimeExpiringFile):
    def __init__(self, config, paths):
        _, ext = osp.splitext(paths[0])
        self._resources = {}
        # create a unique / predictable filename. We don't consider cubes
        # version since uicache is cleared at server startup, and file's dates
        # are checked in debug mode
        fname = 'cache_concat_' + md5(';'.join(paths)).hexdigest() + ext
        filepath = osp.join(config.appdatahome, 'uicache', fname)
        LongTimeExpiringFile.__init__(self, config, filepath)
        self._concat_cached_filepath(filepath, paths)

    def _resource(self, path):
        try:
            return self._resources[path]
        except KeyError:
            self._resources[path] = self.config.locate_resource(path)
            return self._resources[path]

    def _concat_cached_filepath(self, filepath, paths):
        if not self._up_to_date(filepath, paths):
            with open(filepath, 'wb') as f:
                for path in paths:
                    dirpath, rid = self._resource(path)
                    if rid is None:
                        # In production mode log an error, do not return a 404
                        # XXX the erroneous content is cached anyway
                        LOGGER.error('concatenated data url error: %r file '
                                     'does not exist', path)
                        if self.config.debugmode:
                            raise ConcatFileNotFoundError(path)
                    else:
                        for line in open(osp.join(dirpath, rid)):
                            f.write(line)
                        f.write('\n')

    def _up_to_date(self, filepath, paths):
        """
        The concat-file is considered up-to-date if it exists.
        In debug mode, an additional check is performed to make sure that
        concat-file is more recent than all concatenated files
        """
        if not osp.isfile(filepath):
            return False
        if self.config.debugmode:
            concat_lastmod = os.stat(filepath).st_mtime
            for path in paths:
                dirpath, rid = self._resource(path)
                if rid is None:
                    raise ConcatFileNotFoundError(path)
                path = osp.join(dirpath, rid)
                if os.stat(path).st_mtime > concat_lastmod:
                    return False
        return True


class CubicWebRootResource(resource.Resource):
    def __init__(self, config, vreg=None):
        resource.Resource.__init__(self)
        self.config = config
        # instantiate publisher here and not in init_publisher to get some
        # checks done before daemonization (eg versions consistency)
        self.appli = CubicWebPublisher(config, vreg=vreg)
        self.base_url = config['base-url']
        self.https_url = config['https-url']
        global MAX_POST_LENGTH
        MAX_POST_LENGTH = config['max-post-length']
        self.putChild('static', NoListingFile(config))
        self.putChild('fckeditor', FCKEditorResource(self.config, ''))
        self.putChild('data', DataLookupDirectory(self.config, ''))

    def init_publisher(self):
        config = self.config
        # when we have an in-memory repository, clean unused sessions every XX
        # seconds and properly shutdown the server
        if config.repo_method == 'inmemory':
            if config.pyro_enabled():
                # if pyro is enabled, we have to register to the pyro name
                # server, create a pyro daemon, and create a task to handle pyro
                # requests
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
            errorstream = StringIO()
            traceback.print_exc(file=errorstream)
            return HTTPResponse(stream='<pre>%s</pre>' % errorstream.getvalue(),
                                code=500, twisted_request=request)

    def _render_request(self, request):
        origpath = request.path
        host = request.host
        # dual http/https access handling: expect a rewrite rule to prepend
        # 'https' to the path to detect https access
        if origpath.split('/', 2)[1] == 'https':
            origpath = origpath[6:]
            request.uri = request.uri[6:]
            https = True
            baseurl = self.https_url or self.base_url
        else:
            https = False
            baseurl = self.base_url
        if self.config['use-request-subdomain']:
            baseurl = host_prefixed_baseurl(baseurl, host)
            self.warning('used baseurl is %s for this request', baseurl)
        req = CubicWebTwistedRequestAdapter(request, self.appli.vreg, https, baseurl)
        if req.authmode == 'http':
            # activate realm-based auth
            realm = self.config['realm']
            req.set_header('WWW-Authenticate', [('Basic', {'realm' : realm })], raw=False)
        try:
            self.appli.connect(req)
        except Redirect, ex:
            return self.redirect(request=req, location=ex.location)
        if https and req.session.anonymous_session:
            # don't allow anonymous on https connection
            return self.request_auth(request=req)
        if self.url_rewriter is not None:
            # XXX should occur before authentication?
            try:
                path = self.url_rewriter.rewrite(host, origpath, req)
            except Redirect, ex:
                return self.redirect(req, ex.location)
            request.uri.replace(origpath, path, 1)
        else:
            path = origpath
        if not path or path == "/":
            path = 'view'
        try:
            result = self.appli.publish(path, req)
        except DirectResponse, ex:
            return ex.response
        except StatusResponse, ex:
            return HTTPResponse(stream=ex.content, code=ex.status,
                                twisted_request=req._twreq,
                                headers=req.headers_out)
        except AuthenticationError:
            return self.request_auth(request=req)
        except LogOut, ex:
            if self.config['auth-mode'] == 'cookie' and ex.url:
                return self.redirect(request=req, location=ex.url)
            # in http we have to request auth to flush current http auth
            # information
            return self.request_auth(request=req, loggedout=True)
        except Redirect, ex:
            return self.redirect(request=req, location=ex.location)
        # request may be referenced by "onetime callback", so clear its entity
        # cache to avoid memory usage
        req.drop_entity_cache()
        return HTTPResponse(twisted_request=req._twreq, code=http.OK,
                            stream=result, headers=req.headers_out)

    def redirect(self, request, location):
        self.debug('redirecting to %s', str(location))
        request.headers_out.setHeader('location', str(location))
        # 303 See other
        return HTTPResponse(twisted_request=request._twreq, code=303,
                            headers=request.headers_out)

    def request_auth(self, request, loggedout=False):
        if self.https_url and request.base_url() != self.https_url:
            return self.redirect(request, self.https_url + 'login')
        if self.config['auth-mode'] == 'http':
            code = http.UNAUTHORIZED
        else:
            code = http.FORBIDDEN
        if loggedout:
            if request.https:
                request._base_url =  self.base_url
                request.https = False
            content = self.appli.loggedout_content(request)
        else:
            content = self.appli.need_login_content(request)
        return HTTPResponse(twisted_request=request._twreq,
                            stream=content, code=code,
                            headers=request.headers_out)

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
        self.setResponseCode(http.BAD_REQUEST)
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
        value = form[key]
        if isinstance(value, list):
            self.args[key] = [v.value for v in value]
        elif value.filename:
            if value.done != -1: # -1 is transfer has been interrupted
                self.files[key] = (value.filename, value.file)
            else:
                self.files[key] = (None, None)
        else:
            self.args[key] = value.value

from logging import getLogger
from cubicweb import set_log_methods
LOGGER = getLogger('cubicweb.twisted')
set_log_methods(CubicWebRootResource, LOGGER)

def run(config, vreg=None, debug=None):
    if debug is not None:
        config.debugmode = debug
    config.check_writeable_uid_directory(config.appdatahome)
    # create the site
    root_resource = CubicWebRootResource(config, vreg=vreg)
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
