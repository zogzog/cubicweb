import datetime
import logging
import warnings

from zope.interface import implementer

from pyramid.settings import asbool
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid_cubicweb.core import get_principals
from pyramid_multiauth import MultiAuthenticationPolicy

from pyramid.authentication import AuthTktAuthenticationPolicy

from pyramid.interfaces import IAuthenticationPolicy

log = logging.getLogger(__name__)


@implementer(IAuthenticationPolicy)
class UpdateLoginTimeAuthenticationPolicy(object):
    """An authentication policy that update the user last_login_time.

    The update is done in the 'remember' method, which is called by the login
    views login,

    Usually used via :func:`includeme`.
    """

    def authenticated_userid(self, request):
        pass

    def effective_principals(self, request):
        return ()

    def remember(self, request, principal, **kw):
        try:
            repo = request.registry['cubicweb.repository']
            with repo.internal_cnx() as cnx:
                cnx.execute(
                    "SET U last_login_time %(now)s WHERE U eid %(user)s", {
                        'now': datetime.datetime.now(),
                        'user': principal})
                cnx.commit()
        except:
            log.exception("Failed to update last_login_time")
        return ()

    def forget(self, request):
        return ()


class CWAuthTktAuthenticationPolicy(AuthTktAuthenticationPolicy):
    """
    An authentication policy that inhibate the call the 'remember' if a
    'persistent' argument is passed to it, and is equal to the value that
    was passed to the constructor.

    This allow to combine two policies with different settings and select them
    by just setting this argument.
    """
    def __init__(self, secret, persistent, defaults={}, prefix='', **settings):
        self.persistent = persistent
        unset = object()
        kw = {}
        # load string settings
        for name in ('cookie_name', 'path', 'domain', 'hashalg'):
            value = settings.get(prefix + name, defaults.get(name, unset))
            if value is not unset:
                kw[name] = value
        # load boolean settings
        for name in ('secure', 'include_ip', 'http_only', 'wild_domain',
                     'parent_domain', 'debug'):
            value = settings.get(prefix + name, defaults.get(name, unset))
            if value is not unset:
                kw[name] = asbool(value)
        # load int settings
        for name in ('timeout', 'reissue_time', 'max_age'):
            value = settings.get(prefix + name, defaults.get(name, unset))
            if value is not unset:
                kw[name] = int(value)
        super(CWAuthTktAuthenticationPolicy, self).__init__(secret, **kw)

    def remember(self, request, principals, **kw):
        if 'persistent' not in kw or kw.pop('persistent') == self.persistent:
            return super(CWAuthTktAuthenticationPolicy, self).remember(
                request, principals, **kw)
        else:
            return ()


def includeme(config):
    """ Activate the CubicWeb AuthTkt authentication policy.

    Usually called via ``config.include('pyramid_cubicweb.auth')``.

    See also :ref:`defaults_module`
    """
    settings = config.registry.settings

    policies = []

    if asbool(settings.get('cubicweb.auth.update_login_time', True)):
        policies.append(UpdateLoginTimeAuthenticationPolicy())

    if asbool(settings.get('cubicweb.auth.authtkt', True)):
        session_prefix = 'cubicweb.auth.authtkt.session.'
        persistent_prefix = 'cubicweb.auth.authtkt.persistent.'

        try:
            secret = config.registry['cubicweb.config']['pyramid-auth-secret']
            warnings.warn(
                "pyramid-auth-secret from all-in-one is now "
                "cubicweb.auth.authtkt.[session|persistent].secret",
                DeprecationWarning)
        except:
            secret = 'notsosecret'

        session_secret = settings.get(
            session_prefix + 'secret', secret)
        persistent_secret = settings.get(
            persistent_prefix + 'secret', secret)

        if 'notsosecret' in (session_secret, persistent_secret):
            warnings.warn('''

                !! SECURITY WARNING !!

                The authentication cookies are signed with a static secret key.

                Configure the following options in your pyramid.ini file:

                - cubicweb.auth.authtkt.session.secret
                - cubicweb.auth.authtkt.persistent.secret

                YOU SHOULD STOP THIS INSTANCE unless your really know what you
                are doing !!

            ''')

        policies.append(
            CWAuthTktAuthenticationPolicy(
                session_secret, False,
                defaults={
                    'hashalg': 'sha512',
                    'cookie_name': 'auth_tkt',
                    'timeout': 1200,
                    'reissue_time': 120,
                    'http_only': True,
                    'secure': True
                },
                prefix=session_prefix,
                **settings
            )
        )

        policies.append(
            CWAuthTktAuthenticationPolicy(
                persistent_secret, True,
                defaults={
                    'hashalg': 'sha512',
                    'cookie_name': 'pauth_tkt',
                    'max_age': 3600*24*30,
                    'reissue_time': 3600*24,
                    'http_only': True,
                    'secure': True
                },
                prefix=persistent_prefix,
                **settings
            )
        )

    kw = {}
    if asbool(settings.get('cubicweb.auth.groups_principals', True)):
        kw['callback'] = get_principals

    authpolicy = MultiAuthenticationPolicy(policies, **kw)
    config.registry['cubicweb.authpolicy'] = authpolicy

    config.set_authentication_policy(authpolicy)
    config.set_authorization_policy(ACLAuthorizationPolicy())
