from contextlib import contextmanager
from warnings import warn

import rql

from cubicweb.web.request import CubicWebRequestBase
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb import repoapi

import cubicweb
import cubicweb.web

from pyramid import security, httpexceptions
from pyramid.httpexceptions import HTTPSeeOther

from pyramid_cubicweb import authplugin

import logging

log = logging.getLogger(__name__)


@contextmanager
def cw_to_pyramid(request):
    """Wrap a call to the cubicweb API.

    All CW exceptions will be transformed into their pyramid equivalent.
    When needed, some CW reponse bits may be converted too (mainly headers)"""
    try:
        yield
    except cubicweb.web.Redirect as ex:
        assert 300 <= ex.status < 400
        raise httpexceptions.status_map[ex.status](ex.location)
    except cubicweb.web.StatusResponse as ex:
        warn('[3.16] StatusResponse is deprecated use req.status_out',
             DeprecationWarning, stacklevel=2)
        request.body = ex.content
        request.status_int = ex.status
    except cubicweb.web.Unauthorized as ex:
        raise httpexceptions.HTTPForbidden(
            request.cw_request._(
                'You\'re not authorized to access this page. '
                'If you think you should, please contact the site '
                'administrator.'))
    except cubicweb.web.Forbidden:
        raise httpexceptions.HTTPForbidden(
            request.cw_request._(
                'This action is forbidden. '
                'If you think it should be allowed, please contact the site '
                'administrator.'))
    except (rql.BadRQLQuery, cubicweb.web.RequestError) as ex:
        raise


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


def render_view(request, vid, **kwargs):
    vreg = request.registry['cubicweb.registry']
    # XXX The select() function could, know how to handle a pyramid
    # request, and feed it directly to the views that supports it.
    # On the other hand, we could refine the View concept and decide it works
    # with a cnx, and never with a WebRequest

    with cw_to_pyramid(request):
        view = vreg['views'].select(vid, request.cw_request, **kwargs)
        view.set_stream()
        view.render()
        return view._stream.getvalue()


def login(request):
    repo = request.registry['cubicweb.repository']

    response = request.response
    user_eid = None

    if '__login' in request.params:
        login = request.params['__login']
        password = request.params['__password']

        try:
            with repo.internal_cnx() as cnx:
                user = repo.authenticate_user(cnx, login, password=password)
                user_eid = user.eid
        except cubicweb.AuthenticationError:
            raise

    if user_eid is not None:
        headers = security.remember(request, user_eid)

        raise HTTPSeeOther(
            request.params.get('postlogin_path', '/'),
            headers=headers)

        response.headerlist.extend(headers)

    response.text = render_view(request, 'login')
    return response


def _cw_cnx(request):
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


def _cw_close_session(request):
    request.cw_session.close()


def _cw_session(request):
    """Obtains a cw session from a pyramid request"""
    repo = request.registry['cubicweb.repository']
    config = request.registry['cubicweb.config']

    if not request.authenticated_userid:
        login, password = config.anonymous_user()
        sessionid = repo.connect(login, password=password)
        session = repo._sessions[sessionid]
        request.add_finished_callback(_cw_close_session)
    else:
        session = request._cw_cached_session

    # XXX Ideally we store the cw session data in the pyramid session.
    # BUT some data in the cw session data dictionnary makes pyramid fail.
    #session.data = request.session

    return session


def _cw_request(request):
    req = CubicWebPyramidRequest(request)
    req.set_cnx(request.cw_cnx)
    return req


def get_principals(login, request):
    repo = request.registry['cubicweb.repository']

    try:
        sessionid = repo.connect(
            str(login), __pyramid_directauth=authplugin.EXT_TOKEN)
        session = repo._sessions[sessionid]
        request._cw_cached_session = session
        request.add_finished_callback(_cw_close_session)
    except:
        log.exception("Failed")
        raise

    return session.user.groups


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

    config.include('pyramid_cubicweb.handler')
