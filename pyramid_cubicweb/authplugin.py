"""
Special authentifiers.

:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses

"""
__docformat__ = "restructuredtext en"

from cubicweb import AuthenticationError
from cubicweb.server.sources import native


class Token(object):
    pass

EXT_TOKEN = Token()


class DirectAuthentifier(native.BaseAuthentifier):
    """return CWUser eid for the given login.

    Before doing so, it makes sure the authentication request is not coming
    from ouside by checking the special '__externalauth_directauth' kwarg.

    """

    auth_rql = (
        'Any U WHERE U is CWUser, '
        'U eid %(eid)s'
    )

    def authenticate(self, session, login, **kwargs):
        """Return the CWUser eid for the given login.

        Make sure the request comes from inside pyramid by
        checking the special '__pyramid_directauth' kwarg.

        """
        session.debug('authentication by %s', self.__class__.__name__)
        directauth = kwargs.get('__pyramid_directauth', None)
        try:
            if directauth == EXT_TOKEN:
                rset = session.execute(self.auth_rql, {'eid': int(login)})
                if rset:
                    session.debug('Successfully identified %s', login)
                    return rset[0][0]
        except Exception, exc:
            session.debug('authentication failure (%s)', exc)

        raise AuthenticationError('user is not registered')
