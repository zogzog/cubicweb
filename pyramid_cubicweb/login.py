from pyramid import security
from pyramid.httpexceptions import HTTPSeeOther
from pyramid.view import view_config

import cubicweb

from pyramid_cubicweb.core import render_view


@view_config(route_name='login')
def login_form(request):
    request.response.text = render_view(request, 'login')
    return request.response


@view_config(route_name='login', request_param=('__login', '__password'))
def login_password_login(request):
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
        return login_form(request)

    max_age = None
    if request.params.get('__setauthcookie') == '1':
        max_age = 604800
    headers = security.remember(request, user_eid, max_age=max_age)

    new_path = request.params.get('postlogin_path', '/')

    if new_path == 'login':
        new_path = '/'

    raise HTTPSeeOther(new_path, headers=headers)


@view_config(route_name='login', effective_principals=security.Authenticated)
def login_already_loggedin(request):
    raise HTTPSeeOther('/')


def includeme(config):
    config.add_route('login', '/login')
    config.scan('pyramid_cubicweb.login')
