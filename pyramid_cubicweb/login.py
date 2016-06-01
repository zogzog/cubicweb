""" Provide login views that reproduce a classical CubicWeb behavior"""
from pyramid import security
from pyramid.httpexceptions import HTTPSeeOther
from pyramid.view import view_config
from pyramid.settings import asbool

import cubicweb

from pyramid_cubicweb.core import render_view


@view_config(route_name='login')
def login_form(request):
    """ Default view for the 'login' route.

    Display the 'login' CubicWeb view, which is should be a login form"""
    request.response.text = render_view(request, 'login')
    return request.response


@view_config(route_name='login', request_param=('__login', '__password'))
def login_password_login(request):
    """ Handle GET/POST of __login/__password on the 'login' route.

    The authentication itself is delegated to the CubicWeb repository.

    Request parameters:

    :param __login: The user login (or email if :confval:`allow-email-login` is
                    on.
    :param __password: The user password
    :param __setauthcookie: (optional) If defined and equal to '1', set the
                            authentication cookie maxage to 1 week.

                            If not, the authentication cookie is a session
                            cookie.
    """
    repo = request.registry['cubicweb.repository']

    user_eid = None

    login = request.params['__login']
    password = request.params['__password']

    try:
        with repo.internal_cnx() as cnx:
            user = repo.authenticate_user(cnx, login, password=password)
            user_eid = user.eid
    except cubicweb.AuthenticationError:
        request.cw_request.set_message(request.cw_request._(
            "Authentication failed. Please check your credentials."))
        request.cw_request.post = dict(request.params)
        del request.cw_request.post['__password']
        request.response.status_code = 403
        return login_form(request)

    headers = security.remember(
        request, user_eid,
        persistent=asbool(request.params.get('__setauthcookie', False)))

    new_path = request.params.get('postlogin_path', '')

    if new_path == 'login':
        new_path = ''

    url = request.cw_request.build_url(new_path)
    raise HTTPSeeOther(url, headers=headers)


@view_config(route_name='login', effective_principals=security.Authenticated)
def login_already_loggedin(request):
    """ 'login' route view for Authenticated users.

    Simply redirect the user to '/'."""
    raise HTTPSeeOther('/')


def includeme(config):
    """ Create the 'login' route ('/login') and load this module views"""
    config.add_route('login', '/login')
    config.scan('pyramid_cubicweb.login')
