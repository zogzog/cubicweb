from contextlib import contextmanager
from warnings import warn
from cgi import FieldStorage

import rql

from cubicweb.web.request import CubicWebRequestBase
from cubicweb import repoapi

import cubicweb
import cubicweb.web
from cubicweb.server.session import Session

from pyramid import httpexceptions

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

        vreg = request.registry['cubicweb.registry']
        https = request.scheme == 'https'

        post = request.params.mixed()
        headers_in = request.headers

        super(CubicWebPyramidRequest, self).__init__(vreg, https, post,
                                                     headers=headers_in)

        self.content = request.body_file_seekable

    def setup_params(self, params):
        self.form = {}
        for param, val in params.iteritems():
            if param in self.no_script_form_params and val:
                val = self.no_script_form_param(param, val)
            if isinstance(val, FieldStorage) and val.file:
                val = (val.filename, val.file)
            if param == '_cwmsgid':
                self.set_message_id(val)
            elif param == '__message':
                warn('[3.13] __message in request parameter is deprecated '
                     '(may only be given to .build_url). Seeing this message '
                     'usualy means your application hold some <form> where '
                     'you should replace use of __message hidden input by '
                     'form.set_message, so new _cwmsgid mechanism is properly '
                     'used',
                     DeprecationWarning)
                self.set_message(val)
            else:
                self.form[param] = val

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


def _cw_cnx(request):
    cnx = repoapi.ClientConnection(request.cw_session)

    def cleanup(request):
        if (request.exception is not None and not isinstance(
            request.exception, (
                httpexceptions.HTTPSuccessful,
                httpexceptions.HTTPRedirection))):
            cnx.rollback()
        else:
            cnx.commit()
        cnx.__exit__(None, None, None)

    request.add_finished_callback(cleanup)
    cnx.__enter__()
    return cnx


def repo_connect(repo, eid):
    """A lightweight version of repo.connect that does not keep track of opened
    sessions, removing the need of closing them"""
    with repo.internal_cnx() as cnx:
        user = repo._build_user(cnx, eid=eid)
    session = Session(user, repo, None)
    user._cw = user.cw_rset.req = session
    user.cw_clear_relation_cache()
    # Calling the hooks should be done only once, disabling it completely for
    # now
    #with session.new_cnx() as cnx:
        #repo.hm.call_hooks('session_open', cnx)
        #cnx.commit()
    # repo._sessions[session.sessionid] = session
    return session


def _cw_session(request):
    """Obtains a cw session from a pyramid request"""
    repo = request.registry['cubicweb.repository']

    if not request.authenticated_userid:
        session = repo_connect(
            repo, eid=request.registry['cubicweb.anonymous_eid'])
    else:
        session = request._cw_cached_session

    # XXX Ideally we store the cw session data in the pyramid session.
    # BUT some data in the cw session data dictionnary makes pyramid fail.
    session.data = request.session

    return session


def _cw_request(request):
    req = CubicWebPyramidRequest(request)
    req.set_cnx(request.cw_cnx)
    return req


def get_principals(login, request):
    repo = request.registry['cubicweb.repository']

    try:
        session = repo_connect(repo, eid=login)
        request._cw_cached_session = session
    except:
        log.exception("Failed")
        raise

    return session.user.groups


def hello_world(request):
    request.response.text = \
        u"<html><body>Hello %s</body></html>" % request.cw_cnx.user.login
    return request.response


def includeme(config):
    repo = config.registry['cubicweb.repository']

    with repo.internal_cnx() as cnx:
        login = config.registry['cubicweb.config'].anonymous_user()[0]
        config.registry['cubicweb.anonymous_eid'] = cnx.find(
            'CWUser', login=login).one().eid

    repo.system_source.add_authentifier(authplugin.DirectAuthentifier())

    config.add_request_method(
        _cw_session, name='cw_session', property=True, reify=True)
    config.add_request_method(
        _cw_cnx, name='cw_cnx', property=True, reify=True)
    config.add_request_method(
        _cw_request, name='cw_request', property=True, reify=True)

    cwcfg = config.registry['cubicweb.config']
    for cube in cwcfg.cubes():
        pkgname = 'cubes.' + cube
        mod = __import__(pkgname)
        mod = getattr(mod, cube)
        if hasattr(mod, 'includeme'):
            config.include('cubes.' + cube)
