"""twisted server for CubicWeb web instances

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
import os
import select
import errno
from time import mktime
from datetime import date, timedelta
from urlparse import urlsplit, urlunsplit

from twisted.internet import reactor, task, threads
from twisted.internet.defer import maybeDeferred
from twisted.web2 import channel, http, server, iweb
from twisted.web2 import static, resource, responsecode

from cubicweb import ConfigurationError, CW_EVENT_MANAGER
from cubicweb.web import (AuthenticationError, NotFound, Redirect,
                          RemoteCallFailed, DirectResponse, StatusResponse,
                          ExplicitLogin)
from cubicweb.web.application import CubicWebPublisher

from cubicweb.etwist.request import CubicWebTwistedRequestAdapter

def daemonize():
    # XXX unix specific
    # XXX factorize w/ code in cw.server.server and cw.server.serverctl
    # (start-repository command)
    # See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
    if os.fork():   # launch child and...
        return 1
    os.setsid()
    if os.fork():   # launch child again.
        return 1
    # move to the root to avoit mount pb
    os.chdir('/')
    # set paranoid umask
    os.umask(077)
    null = os.open('/dev/null', os.O_RDWR)
    for i in range(3):
        try:
            os.dup2(null, i)
        except OSError, e:
            if e.errno != errno.EBADF:
                raise
    os.close(null)
    return None

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


class LongTimeExpiringFile(static.File):
    """overrides static.File and sets a far futre ``Expires`` date
    on the resouce.

    versions handling is done by serving static files by different
    URLs for each version. For instance::

      http://localhost:8080/data-2.48.2/cubicweb.css
      http://localhost:8080/data-2.49.0/cubicweb.css
      etc.

    """
    def renderHTTP(self, request):
        def setExpireHeader(response):
            response = iweb.IResponse(response)
            # Don't provide additional resource information to error responses
            if response.code < 400:
                # the HTTP RFC recommands not going further than 1 year ahead
                expires = date.today() + timedelta(days=6*30)
                response.headers.setHeader('Expires', mktime(expires.timetuple()))
            return response
        d = maybeDeferred(super(LongTimeExpiringFile, self).renderHTTP, request)
        return d.addCallback(setExpireHeader)


class CubicWebRootResource(resource.PostableResource):
    addSlash = False

    def __init__(self, config, debug=None):
        self.debugmode = debug
        self.config = config
        # instantiate publisher here and not in init_publisher to get some
        # checks done before daemonization (eg versions consistency)
        self.appli = CubicWebPublisher(config, debug=self.debugmode)
        self.base_url = config['base-url']
        self.https_url = config['https-url']
        self.versioned_datadir = 'data%s' % config.instance_md5_version()

    def init_publisher(self):
        config = self.config
        # when we have an in-memory repository, clean unused sessions every XX
        # seconds and properly shutdown the server
        if config.repo_method == 'inmemory':
            reactor.addSystemEventTrigger('before', 'shutdown',
                                          self.shutdown_event)
            if config.pyro_enabled():
                # if pyro is enabled, we have to register to the pyro name
                # server, create a pyro daemon, and create a task to handle pyro
                # requests
                self.pyro_daemon = self.appli.repo.pyro_register()
                self.pyro_listen_timeout = 0.02
                self.appli.repo.looping_task(1, self.pyro_loop_event)
            self.appli.repo.start_looping_tasks()
        self.set_url_rewriter()
        CW_EVENT_MANAGER.bind('after-registry-reload', self.set_url_rewriter)

    def start_service(self):
        config = self.config
        interval = min(config['cleanup-session-time'] or 120,
                       config['cleanup-anonymous-session-time'] or 720) / 2.
        start_task(interval, self.appli.session_handler.clean_sessions)

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

    def locateChild(self, request, segments):
        """Indicate which resource to use to process down the URL's path"""
        if segments:
            if segments[0] == 'https':
                segments = segments[1:]
            if len(segments) >= 2:
                if segments[0] in (self.versioned_datadir, 'data', 'static'):
                    # Anything in data/, static/ is treated as static files
                    if segments[0] == 'static':
                        # instance static directory
                        datadir = self.config.static_directory
                    elif segments[1] == 'fckeditor':
                        fckeditordir = self.config.ext_resources['FCKEDITOR_PATH']
                        return static.File(fckeditordir), segments[2:]
                    else:
                        # cube static data file
                        datadir = self.config.locate_resource(segments[1])
                        if datadir is None:
                            return None, []
                    self.info('static file %s from %s', segments[-1], datadir)
                    if segments[0] == 'data':
                        return static.File(str(datadir)), segments[1:]
                    else:
                        return LongTimeExpiringFile(datadir), segments[1:]
                elif segments[0] == 'fckeditor':
                    fckeditordir = self.config.ext_resources['FCKEDITOR_PATH']
                    return static.File(fckeditordir), segments[1:]
        # Otherwise we use this single resource
        return self, ()

    def render(self, request):
        """Render a page from the root resource"""
        # reload modified files in debug mode
        if self.debugmode:
            self.appli.vreg.register_objects(self.config.vregistry_path())
        if self.config['profile']: # default profiler don't trace threads
            return self.render_request(request)
        else:
            return threads.deferToThread(self.render_request, request)

    def render_request(self, request):
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
        except AuthenticationError:
            return self.request_auth(req)
        except Redirect, ex:
            return self.redirect(req, ex.location)
        if https and req.cnx.anonymous_connection:
            # don't allow anonymous on https connection
            return self.request_auth(req)
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
            return http.Response(stream=ex.content, code=ex.status,
                                 headers=req.headers_out or None)
        except RemoteCallFailed, ex:
            req.set_header('content-type', 'application/json')
            return http.Response(stream=ex.dumps(),
                                 code=responsecode.INTERNAL_SERVER_ERROR)
        except NotFound:
            result = self.appli.notfound_content(req)
            return http.Response(stream=result, code=responsecode.NOT_FOUND,
                                 headers=req.headers_out or None)
        except ExplicitLogin:  # must be before AuthenticationError
            return self.request_auth(req)
        except AuthenticationError, ex:
            if self.config['auth-mode'] == 'cookie' and getattr(ex, 'url', None):
                return self.redirect(req, ex.url)
            # in http we have to request auth to flush current http auth
            # information
            return self.request_auth(req, loggedout=True)
        except Redirect, ex:
            return self.redirect(req, ex.location)
        # request may be referenced by "onetime callback", so clear its entity
        # cache to avoid memory usage
        req.drop_entity_cache()
        return http.Response(stream=result, code=responsecode.OK,
                             headers=req.headers_out or None)

    def redirect(self, req, location):
        req.headers_out.setHeader('location', str(location))
        self.debug('redirecting to %s', location)
        # 303 See other
        return http.Response(code=303, headers=req.headers_out)

    def request_auth(self, req, loggedout=False):
        if self.https_url and req.base_url() != self.https_url:
            req.headers_out.setHeader('location', self.https_url + 'login')
            return http.Response(code=303, headers=req.headers_out)
        if self.config['auth-mode'] == 'http':
            code = responsecode.UNAUTHORIZED
        else:
            code = responsecode.FORBIDDEN
        if loggedout:
            if req.https:
                req._base_url =  self.base_url
                req.https = False
            content = self.appli.loggedout_content(req)
        else:
            content = self.appli.need_login_content(req)
        return http.Response(code, req.headers_out, content)

from twisted.internet import defer
from twisted.web2 import fileupload

# XXX set max file size to 100Mo: put max upload size in the configuration
# line below for twisted >= 8.0, default param value for earlier version
resource.PostableResource.maxSize = 100*1024*1024
def parsePOSTData(request, maxMem=100*1024, maxFields=1024,
                  maxSize=100*1024*1024):
    if request.stream.length == 0:
        return defer.succeed(None)

    ctype = request.headers.getHeader('content-type')

    if ctype is None:
        return defer.succeed(None)

    def updateArgs(data):
        args = data
        request.args.update(args)

    def updateArgsAndFiles(data):
        args, files = data
        request.args.update(args)
        request.files.update(files)

    def error(f):
        f.trap(fileupload.MimeFormatError)
        raise http.HTTPError(responsecode.BAD_REQUEST)

    if ctype.mediaType == 'application' and ctype.mediaSubtype == 'x-www-form-urlencoded':
        d = fileupload.parse_urlencoded(request.stream, keep_blank_values=True)
        d.addCallbacks(updateArgs, error)
        return d
    elif ctype.mediaType == 'multipart' and ctype.mediaSubtype == 'form-data':
        boundary = ctype.params.get('boundary')
        if boundary is None:
            return defer.fail(http.HTTPError(
                http.StatusResponse(responsecode.BAD_REQUEST,
                                    "Boundary not specified in Content-Type.")))
        d = fileupload.parseMultipartFormData(request.stream, boundary,
                                              maxMem, maxFields, maxSize)
        d.addCallbacks(updateArgsAndFiles, error)
        return d
    else:
        raise http.HTTPError(responsecode.BAD_REQUEST)

server.parsePOSTData = parsePOSTData


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(CubicWebRootResource, getLogger('cubicweb.twisted'))


listiterator = type(iter([]))

def _gc_debug(all=True):
    import gc
    from pprint import pprint
    from cubicweb.appobject import AppObject
    gc.collect()
    count = 0
    acount = 0
    fcount = 0
    rcount = 0
    ccount = 0
    scount = 0
    ocount = {}
    from rql.stmts import Union
    from cubicweb.schema import CubicWebSchema
    from cubicweb.rset import ResultSet
    from cubicweb.dbapi import Connection, Cursor
    from cubicweb.req import RequestSessionBase
    from cubicweb.server.repository import Repository
    from cubicweb.server.sources.native import NativeSQLSource
    from cubicweb.server.session import Session
    from cubicweb.devtools.testlib import CubicWebTC
    from logilab.common.testlib import TestSuite
    from optparse import Values
    import types, weakref
    for obj in gc.get_objects():
        if isinstance(obj, RequestSessionBase):
            count += 1
            if isinstance(obj, Session):
                print '   session', obj, referrers(obj, True)
        elif isinstance(obj, AppObject):
            acount += 1
        elif isinstance(obj, ResultSet):
            rcount += 1
            #print '   rset', obj, referrers(obj)
        elif isinstance(obj, Repository):
            print '   REPO', obj, referrers(obj, True)
        #elif isinstance(obj, NativeSQLSource):
        #    print '   SOURCe', obj, referrers(obj)
        elif isinstance(obj, CubicWebTC):
            print '   TC', obj, referrers(obj)
        elif isinstance(obj, TestSuite):
            print '   SUITE', obj, referrers(obj)
        #elif isinstance(obj, Values):
        #    print '   values', '%#x' % id(obj), referrers(obj, True)
        elif isinstance(obj, Connection):
            ccount += 1
            #print '   cnx', obj, referrers(obj)
        #elif isinstance(obj, Cursor):
        #    ccount += 1
        #    print '   cursor', obj, referrers(obj)
        elif isinstance(obj, file):
            fcount += 1
        #    print '   open file', file.name, file.fileno
        elif isinstance(obj, CubicWebSchema):
            scount += 1
            print '   schema', obj, referrers(obj)
        elif not isinstance(obj, (type, tuple, dict, list, set, frozenset,
                                  weakref.ref, weakref.WeakKeyDictionary,
                                  listiterator,
                                  property, classmethod,
                                  types.ModuleType, types.MemberDescriptorType,
                                  types.FunctionType, types.MethodType)):
            try:
                ocount[obj.__class__] += 1
            except KeyError:
                ocount[obj.__class__] = 1
            except AttributeError:
                pass
    if count:
        print ' NB REQUESTS/SESSIONS', count
    if acount:
        print ' NB APPOBJECTS', acount
    if ccount:
        print ' NB CONNECTIONS', ccount
    if rcount:
        print ' NB RSETS', rcount
    if scount:
        print ' NB SCHEMAS', scount
    if fcount:
        print ' NB FILES', fcount
    if all:
        ocount = sorted(ocount.items(), key=lambda x: x[1], reverse=True)[:20]
        pprint(ocount)
    if gc.garbage:
        print 'UNREACHABLE', gc.garbage

def referrers(obj, showobj=False):
    try:
        return sorted(set((type(x), showobj and x or getattr(x, '__name__', '%#x' % id(x)))
                          for x in _referrers(obj)))
    except TypeError:
        s = set()
        unhashable = []
        for x in _referrers(obj):
            try:
                s.add(x)
            except TypeError:
                unhashable.append(x)
        return sorted(s) + unhashable

def _referrers(obj, seen=None, level=0):
    import gc, types
    from cubicweb.schema import CubicWebRelationSchema, CubicWebEntitySchema
    interesting = []
    if seen is None:
        seen = set()
    for x in gc.get_referrers(obj):
        if id(x) in seen:
            continue
        seen.add(id(x))
        if isinstance(x, types.FrameType):
            continue
        if isinstance(x, (CubicWebRelationSchema, CubicWebEntitySchema)):
            continue
        if isinstance(x, (list, tuple, set, dict, listiterator)):
            if level >= 5:
                pass
                #interesting.append(x)
            else:
                interesting += _referrers(x, seen, level+1)
        else:
            interesting.append(x)
    return interesting

def run(config, debug):
    # create the site
    root_resource = CubicWebRootResource(config, debug)
    website = server.Site(root_resource)
    # serve it via standard HTTP on port set in the configuration
    port = config['port'] or 8080
    reactor.listenTCP(port, channel.HTTPFactory(website))
    logger = getLogger('cubicweb.twisted')
    if not debug:
        if sys.platform == 'win32':
            raise ConfigurationError("Under windows, you must use the service management "
                                     "commands (e.g : 'net start my_instance)'")
        print 'instance starting in the background'
        if daemonize():
            return # child process
        if config['pid-file']:
            # ensure the directory where the pid-file should be set exists (for
            # instance /var/run/cubicweb may be deleted on computer restart)
            piddir = os.path.dirname(config['pid-file'])
            if not os.path.exists(piddir):
                os.makedirs(piddir)
            file(config['pid-file'], 'w').write(str(os.getpid()))
    root_resource.init_publisher() # before changing uid
    if config['uid'] is not None:
        try:
            uid = int(config['uid'])
        except ValueError:
            from pwd import getpwnam
            uid = getpwnam(config['uid']).pw_uid
        os.setuid(uid)
    root_resource.start_service()
    logger.info('instance started on %s', root_resource.base_url)
    if config['profile']:
        import cProfile
        cProfile.runctx('reactor.run()', globals(), locals(), config['profile'])
    else:
        reactor.run()
