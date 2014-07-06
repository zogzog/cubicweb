from cubicweb.web.request import CubicWebRequestBase
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.web.application import CubicWebPublisher
from cubicweb import repoapi

import cubicweb
import cubicweb.web

from pyramid import security
from pyramid.httpexceptions import HTTPSeeOther

from pyramid_cubicweb import authplugin

import weakref

import logging

log = logging.getLogger(__name__)


class CubicWebPyramidRequest(CubicWebRequestBase):
    def __init__(self, request):
        self._request = request

        self.path = request.upath_info

        vreg = request.registry['cubicweb.appli'].vreg
        https = request.scheme == 'https'

        post = request.params
        headers_in = request.headers

        super(CubicWebPyramidRequest, self).__init__(vreg, https, post,
                                                     headers=headers_in)

    def is_secure(self):
        return self._request.scheme == 'https'

    def relative_path(self, includeparams=True):
        path = self._request.path[1:]
        if includeparams and self._request.query_string:
            return '%s?%s' % (path, self._request.query_string)
        return path

    def instance_uri(self):
        return self._request.application_url

    def get_full_path(self):
        path = self._request.path
        if self._request.query_string:
            return '%s?%s' % (path, self._request.query_string)
        return path

    def http_method(self):
        return self._request.method

    def _set_status_out(self, value):
        self._request.response.status_int = value

    def _get_status_out(self):
        return self._request.response.status_int

    status_out = property(_get_status_out, _set_status_out)


class PyramidSessionHandler(object):
    """A CW Session handler that rely on the pyramid API to fetch the needed
    informations"""

    def __init__(self, appli):
        self.appli = appli

    def get_session(self, req):
        return req._request.cw_session

    def logout(self, req, goto_url):
        del req._request.session['cubicweb.sessionid']
        if not req.session.closed:
            req.session.repo.close(req.session.sessionid)
        for name, value in security.forget(req._request):
            req.headers_out.setHeader(name, value)
        raise cubicweb.web.LogOut(url=goto_url)


def render_view(request, vid, **kwargs):
    vreg = request.registry['cubicweb.registry']
    # XXX The select() function could, know how to handle a pyramid
    # request, and feed it directly to the views that supports it.
    # On the other hand, we could refine the View concept and decide it works
    # with a cnx, and never with a WebRequest

    view = vreg['views'].select(vid, request.cw_request(), **kwargs)

    view.set_stream()
    view.render()
    return view._stream.getvalue()


def login(request):
    repo = request.registry['cubicweb.repository']

    response = request.response
    userid = None

    if '__login' in request.params:
        login = request.params['__login']
        password = request.params['__password']

        try:
            sessionid = repo.connect(login, password=password)
            request.session['cubicweb.sessionid'] = sessionid
            session = repo._sessions[sessionid]
            userid = session.user.eid
        except cubicweb.AuthenticationError:
            raise

    if userid is not None:
        headers = security.remember(request, userid)

        if 'postlogin_path' in request.params:
            raise HTTPSeeOther(
                request.params['postlogin_path'],
                headers=headers)

        response.headerlist.extend(headers)

    response.text = render_view(request, 'login')
    return response


class CubicWebPyramidHandler(object):
    def __init__(self, appli):
        self.appli = appli

    def __call__(self, request):
        req = request.cw_request()
        result = self.appli.handle_request(req, req.path)
        if result is not None:
            request.response.body = result
        request.response.headers.clear()
        for k, v in req.headers_out.getAllRawHeaders():
            for item in v:
                request.response.headers.add(k, item)
        return request.response


def _cw_cnx(request):
    # XXX We should not need to use the session. A temporary one should be
    # enough. (by using repoapi.connect())
    cnx = repoapi.ClientConnection(request.cw_session)

    def cleanup(request):
        if request.exception is not None:
            cnx.rollback()
        else:
            cnx.commit()
        cnx.__exit__(None, None, None)

    request.add_finished_callback(cleanup)
    cnx.__enter__()
    return cnx


def _cw_session(request):
    repo = request.registry['cubicweb.repository']
    config = request.registry['cubicweb.config']

    sessionid = request.session.get('cubicweb.sessionid')

    if sessionid not in repo._sessions:
        if not request.authenticated_userid:
            login, password = config.anonymous_user()
            sessionid = repo.connect(login, password=password)
            request.session['cubicweb.sessionid'] = sessionid
        else:
            sessionid = request.session.get('cubicweb.sessionid')

    return repo._sessions[sessionid]


def _cw_request(request):
    return weakref.ref(CubicWebPyramidRequest(request))


def get_principals(userid, request):
    repo = request.registry['cubicweb.repository']

    sessionid = request.session.get('cubicweb.sessionid')

    if sessionid is None or sessionid not in repo._sessions:
        try:
            sessionid = repo.connect(
                str(userid), __pyramid_directauth=authplugin.EXT_TOKEN)
        except:
            log.exception("Failed")
            raise
        request.session['cubicweb.sessionid'] = sessionid

    #session = repo._session[sessionid]

    with repo.internal_cnx() as cnx:
        groupnames = [r[1] for r in cnx.execute(
            'Any X, N WHERE X is CWGroup, X name N, '
            'U in_group X, U eid %(userid)s',
            {'userid': userid})]

    return groupnames


from pyramid.authentication import SessionAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.session import SignedCookieSessionFactory


def hello_world(request):
    request.response.text = \
        u"<html><body>Hello %s</body></html>" % request.cw_cnx.user.login
    return request.response


def includeme(config):
    appid = config.registry.settings['cubicweb.instance']
    cwconfig = CubicWebConfiguration.config_for(appid)

    config.set_session_factory(
        SignedCookieSessionFactory(
            secret=config.registry.settings['session.secret']
        ))

    config.set_authentication_policy(
        SessionAuthenticationPolicy(callback=get_principals))
    config.set_authorization_policy(ACLAuthorizationPolicy())

    config.registry['cubicweb.config'] = cwconfig
    config.registry['cubicweb.repository'] = repo = cwconfig.repository()
    config.registry['cubicweb.registry'] = repo.vreg

    repo.system_source.add_authentifier(authplugin.DirectAuthentifier())

    config.add_request_method(
        _cw_session, name='cw_session', property=True, reify=True)
    config.add_request_method(
        _cw_cnx, name='cw_cnx', property=True, reify=True)
    config.add_request_method(
        _cw_request, name='cw_request', property=True, reify=True)

    config.add_route('login', '/login')
    config.add_view(login, route_name='login')

    config.add_route('hello', '/hello')
    config.add_view(hello_world, route_name='hello')

    # Set up a defaut route to handle non-catched urls.
    # This is to keep legacy compatibility for cubes that makes use of the
    # cubicweb controllers.
    cwappli = CubicWebPublisher(
        cwconfig.repository(), cwconfig,
        session_handler_fact=PyramidSessionHandler)
    handler = CubicWebPyramidHandler(cwappli)

    config.registry['cubicweb.appli'] = cwappli
    config.registry['cubicweb.handler'] = handler

    config.add_notfound_view(handler)
