import warnings
import logging

from pyramid.compat import pickle
from pyramid.session import SignedCookieSessionFactory

from cubicweb import Binary


log = logging.getLogger(__name__)


def logerrors(logger):
    def wrap(fn):
        def newfn(*args, **kw):
            try:
                return fn(*args, **kw)
            except:
                logger.exception("Error in %s" % fn.__name__)
        return newfn
    return wrap


def CWSessionFactory(
        secret,
        cookie_name='session',
        max_age=None,
        path='/',
        domain=None,
        secure=False,
        httponly=False,
        set_on_exception=True,
        timeout=1200,
        reissue_time=120,
        hashalg='sha512',
        salt='pyramid.session.',
        serializer=None):
    """ A pyramid session factory that store session data in the CubicWeb
    database.

    Storage is done with the 'CWSession' entity, which is provided by the
    'pyramid' cube.

    .. warning::

        Although it provides a sane default behavior, this session storage has
        a serious overhead because it uses RQL to access the database.

        Using pure SQL would improve a bit (it is roughly twice faster), but it
        is still pretty slow and thus not an immediate priority.

        It is recommended to use faster session factory
        (pyramid_redis_sessions_ for example) if you need speed.

    .. _pyramid_redis_sessions: http://pyramid-redis-sessions.readthedocs.org/
                                en/latest/index.html
    """

    SignedCookieSession = SignedCookieSessionFactory(
        secret,
        cookie_name=cookie_name,
        max_age=max_age,
        path=path,
        domain=domain,
        secure=secure,
        httponly=httponly,
        set_on_exception=set_on_exception,
        timeout=timeout,
        reissue_time=reissue_time,
        hashalg=hashalg,
        salt=salt,
        serializer=serializer)

    class CWSession(SignedCookieSession):
        def __init__(self, request):
            # _set_accessed will be called by the super __init__.
            # Setting _loaded to True inhibates it.
            self._loaded = True

            # the super __init__ will load a single value in the dictionnary,
            # the session id.
            super(CWSession, self).__init__(request)

            # Remove the session id from the dict
            self.sessioneid = self.pop('sessioneid', None)
            self.repo = request.registry['cubicweb.repository']

            # We need to lazy-load only for existing sessions
            self._loaded = self.sessioneid is None

        @logerrors(log)
        def _set_accessed(self, value):
            self._accessed = value

            if self._loaded:
                return

            with self.repo.internal_cnx() as cnx:
                session = cnx.find('CWSession', eid=self.sessioneid).one()
                value = session.cwsessiondata
                if value:
                    # Use directly dict.update to avoir _set_accessed to be
                    # recursively called
                    dict.update(self, pickle.load(value))

            self._loaded = True

        def _get_accessed(self):
            return self._accessed

        accessed = property(_get_accessed, _set_accessed)

        @logerrors(log)
        def _set_cookie(self, response):
            # Save the value in the database
            data = Binary(pickle.dumps(dict(self)))
            sessioneid = self.sessioneid

            with self.repo.internal_cnx() as cnx:
                if not sessioneid:
                    session = cnx.create_entity(
                        'CWSession', cwsessiondata=data)
                    sessioneid = session.eid
                else:
                    session = cnx.entity_from_eid(sessioneid)
                    session.cw_set(cwsessiondata=data)
                cnx.commit()

            # Only if needed actually set the cookie
            if self.new or self.accessed - self.renewed > self._reissue_time:
                dict.clear(self)
                dict.__setitem__(self, 'sessioneid', sessioneid)
                return super(CWSession, self)._set_cookie(response)

            return True

    return CWSession


def includeme(config):
    """ Activate the CubicWeb session factory.

    Usually called via ``config.include('pyramid_cubicweb.auth')``.

    See also :ref:`defaults_module`
    """
    secret = config.registry['cubicweb.config']['pyramid-session-secret']
    if not secret:
        secret = 'notsosecret'
        warnings.warn('''

            !! WARNING !! !! WARNING !!

            The session cookies are signed with a static secret key.
            To put your own secret key, edit your all-in-one.conf file
            and set the 'pyramid-session-secret' key.

            YOU SHOULD STOP THIS INSTANCE unless your really know what you
            are doing !!

        ''')
    session_factory = CWSessionFactory(secret)
    config.set_session_factory(session_factory)
