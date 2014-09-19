from pyramid.authentication import SessionAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from pyramid_cubicweb.core import get_principals


def includeme(config):
    config.include('pyramid_cubicweb.session')

    config.set_authentication_policy(
        SessionAuthenticationPolicy(callback=get_principals))
    config.set_authorization_policy(ACLAuthorizationPolicy())

    config.include('pyramid_cubicweb.login')
