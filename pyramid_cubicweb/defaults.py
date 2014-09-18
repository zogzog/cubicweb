import warnings

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from pyramid_cubicweb.core import get_principals


def includeme(config):
    config.include('pyramid_cubicweb.session')

    secret = config.registry['cubicweb.config']['pyramid-auth-secret']

    if not secret:
        secret = 'notsosecret'
        warnings.warn('''

            !! WARNING !! !! WARNING !!

            The authentication cookies are signed with a static secret key.
            To put your own secret key, edit your all-in-one.conf file
            and set the 'pyramid-session-secret' key.

            YOU SHOULD STOP THIS INSTANCE unless your really know what you
            are doing !!

        ''')

    config.set_authentication_policy(
        AuthTktAuthenticationPolicy(
            secret, callback=get_principals, hashalg='sha512',
            reissue_time=3600))
    config.set_authorization_policy(ACLAuthorizationPolicy())

    config.include('pyramid_cubicweb.login')
