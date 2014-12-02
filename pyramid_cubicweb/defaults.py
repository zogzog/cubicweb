import datetime
import logging
import warnings

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from pyramid_cubicweb.core import get_principals

log = logging.getLogger(__name__)


class CubicWebAuthTktAuthenticationPolicy(AuthTktAuthenticationPolicy):
    """An authentication policy that update the user last_login_time.

    The update is done in the 'remember' method, which is called on login,
    and each time the authentication ticket is reissued.

    Meaning, the last_login_time is updated reissue_time seconds (maximum)
    before the last request by the user.
    """

    def remember(self, request, principal, **kw):
        headers = super(CubicWebAuthTktAuthenticationPolicy, self).remember(
            request, principal, **kw)
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
        return headers


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
        CubicWebAuthTktAuthenticationPolicy(
            secret, callback=get_principals, hashalg='sha512',
            reissue_time=3600))
    config.set_authorization_policy(ACLAuthorizationPolicy())

    config.include('pyramid_cubicweb.login')
