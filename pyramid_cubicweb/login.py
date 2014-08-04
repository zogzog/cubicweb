from pyramid import security
from pyramid.httpexceptions import HTTPSeeOther

import cubicweb

from pyramid_cubicweb.core import render_view


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

        new_path = request.params.get('postlogin_path', '/')

        if new_path == 'login':
            new_path = '/'

        raise HTTPSeeOther(new_path, headers=headers)

    response.text = render_view(request, 'login')
    return response


def includeme(config):
    config.add_route('login', '/login')
    config.add_view(login, route_name='login')
