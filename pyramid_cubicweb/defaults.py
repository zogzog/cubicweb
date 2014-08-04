from pyramid.authentication import SessionAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.session import SignedCookieSessionFactory

from pyramid_cubicweb.core import get_principals


def includeme(config):
    config.set_session_factory(
        SignedCookieSessionFactory(
            secret=config.registry.settings['session.secret']
        ))

    config.set_authentication_policy(
        SessionAuthenticationPolicy(callback=get_principals))
    config.set_authorization_policy(ACLAuthorizationPolicy())

    config.include('pyramid_cubicweb.login')
