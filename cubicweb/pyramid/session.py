# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# copyright 2014-2016 UNLISH S.A.S. (Montpellier, FRANCE), all rights reserved.
#
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""
Web session when using pyramid
------------------------------

CubicWeb ``CWSession`` entity type so that sessions can be
stored in the database, which allows to run a Cubicweb instance
without having to set up a session storage (like redis or memcache)
solution.

However, for production systems, it is greatly advised to use such a
storage solution for the sessions.

The handling of the sessions is made by pyramid (see the
`pyramid's documentation on sessions`_ for more details).

For example, to set up a redis based session storage, you need the
`pyramid-redis-session`_ package, then you must configure pyramid to
use this backend, by configuring the pyramid configuration file:


.. code-block:: ini

   [main]
   cubicweb.defaults = no # we do not want to load the default cw session handling

   cubicweb.auth.authtkt.session.secret = <secret1>
   cubicweb.auth.authtkt.persistent.secret = <secret2>
   cubicweb.auth.authtkt.session.secure = yes
   cubicweb.auth.authtkt.persistent.secure = yes

   redis.sessions.secret = <secret3>
   redis.sessions.prefix = <my-app>:

   redis.sessions.url = redis://localhost:6379/0

   pyramid.includes =
           pyramid_redis_sessions
           cubicweb.pyramid.auth
           cubicweb.pyramid.login


.. Warning:: If you want to be able to log in a CubicWeb application
             served by pyramid on a unsecured stream (typically when
             you start an instance in dev mode using a simple
             ``cubicweb-ctl pyramid -D -linfo myinstance``), you
             **must** set ``cubicweb.auth.authtkt.session.secure`` to
             ``no``.

Secrets
~~~~~~~

There are a number of secrets to configure in ``pyramid.ini``. They
should be different one from each other, as explained in `Pyramid's
documentation`_.

For the record, regarding session handling:

:cubicweb.session.secret: This secret is used to encrypt the session's
   data ID (data themselved are stored in the backend, database or
   redis) when using the integrated (``CWSession`` based) session data
   storage.

:redis.session.secret: This secret is used to encrypt the session's
   data ID (data themselved are stored in the backend, database or
   redis) when using redis as backend.
"""

import warnings
import logging
from contextlib import contextmanager

from pyramid.compat import pickle
from pyramid.session import SignedCookieSessionFactory

from cubicweb import (
    Binary,
    UnknownEid,
)


log = logging.getLogger(__name__)


def logerrors(logger):
    def wrap(fn):
        def newfn(*args, **kw):
            try:
                return fn(*args, **kw)
            except Exception:
                logger.exception("Error in %s" % fn.__name__)
        return newfn
    return wrap


@contextmanager
def unsafe_cnx_context_manager(request):
    """Return a connection for use as a context manager, with security disabled

    If request has an attached connection, its security will be deactived in the context manager's
    scope, else a new internal connection is returned.

    This should be used for read-only queries, not if you intend to commit/rollback some data.
    """
    cnx = request.cw_cnx
    if cnx is None:
        with request.registry['cubicweb.repository'].internal_cnx() as cnx:
            yield cnx
    else:
        with cnx.security_enabled(read=False, write=False):
            yield cnx


def CWSessionFactory(
        secret,
        cookie_name='session',
        max_age=None,
        path='/',
        domain=None,
        secure=False,
        httponly=True,
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

            with unsafe_cnx_context_manager(self.request) as cnx:
                value_rset = cnx.execute('Any D WHERE X eid %(x)s, X cwsessiondata D',
                                         {'x': self.sessioneid})
                value = value_rset[0][0]
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

            with self.request.registry['cubicweb.repository'].internal_cnx() as cnx:
                if not sessioneid:
                    session = cnx.create_entity(
                        'CWSession', cwsessiondata=data)
                    sessioneid = session.eid
                else:
                    try:
                        session = cnx.entity_from_eid(sessioneid)
                    except UnknownEid:
                        # Might occur if CWSession entity got dropped (e.g.
                        # the whole db got recreated) while user's cookie is
                        # still valid. We recreate the CWSession in this case.
                        sessioneid = cnx.create_entity(
                            'CWSession', cwsessiondata=data).eid
                    else:
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

    Usually called via ``config.include('cubicweb.pyramid.auth')``.

    See also :ref:`defaults_module`
    """
    settings = config.registry.settings
    try:
        secret = settings['cubicweb.session.secret']
    except KeyError:
        secret = 'notsosecret'
        if config.registry['cubicweb.config'].mode != 'test':
            warnings.warn('''

                !! WARNING !! !! WARNING !!

                The session cookies are signed with a static secret key.
                To put your own secret key, edit your pyramid.ini file
                and set the 'cubicweb.session.secret' key.

                YOU SHOULD STOP THIS INSTANCE unless your really know what you
                are doing !!

            ''')
    session_factory = CWSessionFactory(secret)
    config.set_session_factory(session_factory)
