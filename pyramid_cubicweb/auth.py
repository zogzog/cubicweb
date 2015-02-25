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
    def __init__(self, secret, persistent, **kw):
        self.persistent = persistent
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
        secret = config.registry['cubicweb.config']['pyramid-auth-secret']

        if not secret:
            secret = 'notsosecret'
            warnings.warn('''

                !! WARNING !! !! WARNING !!

                The authentication cookies are signed with a static secret key.
                To put your own secret key, edit your all-in-one.conf file
                and set the 'pyramid-auth-secret' key.

                YOU SHOULD STOP THIS INSTANCE unless your really know what you
                are doing !!

            ''')

        policies.append(
            CWAuthTktAuthenticationPolicy(
                secret, False, hashalg='sha512',
                cookie_name=settings.get(
                    'cubicweb.auth.authtkt.session.cookie_name',
                    'auth_tkt'),
                timeout=int(settings.get(
                    'cubicweb.auth.authtkt.session.timeout',
                    1200)),
                reissue_time=int(settings.get(
                    'cubicweb.auth.authtkt.session.reissue_time',
                    120))
            )
        )

        policies.append(
            CWAuthTktAuthenticationPolicy(
                secret, True, hashalg='sha512',
                cookie_name=settings.get(
                    'cubicweb.auth.authtkt.persistent.cookie_name',
                    'pauth_tkt'),
                max_age=int(settings.get(
                    'cubicweb.auth.authtkt.persistent.max_age',
                    3600*24*30  # defaults to 1 month
                )),
                reissue_time=int(settings.get(
                    'cubicweb.auth.authtkt.persistent.reissue_time',
                    3600*24
                ))
            )
        )

    kw = {}
    if asbool(settings.get('cubicweb.auth.groups_principals', True)):
        kw['callback'] = get_principals

    authpolicy = MultiAuthenticationPolicy(policies, **kw)
    config.registry['cubicweb.authpolicy'] = authpolicy

    config.set_authentication_policy(authpolicy)
    config.set_authorization_policy(ACLAuthorizationPolicy())
