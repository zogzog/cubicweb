
pyramid_cubicweb_ is one specific way of integrating CubicWeb_ with a
Pyramid_ web application.

Features
========

* provides a default route that let a cubicweb instance handle the request.

Usage
=====

To use, install ``pyramid_cubicweb`` in your python environment, and
then include_ the package::

    config.include('pyramid_cubicweb')

    
Configuration
=============

Requires the following `INI setting / environment variable`_:

* `cubicweb.instance` / `CW_INSTANCE`: the cubicweb instance name

Authentication cookies
----------------------

When using the `pyramid_cubicweb.auth` (CubicWeb AuthTkt
authentication policy), which is the default in most cases, you may
have to configure the behaviour of these authentication policies using
standard's Pyramid configuration. You may want to configure in your
``pyramid.ini``:

:Session Authentication:

    This is a `AuthTktAuthenticationPolicy`_ so you may overwrite default
    configuration values by adding configuration entries using the prefix
    ``cubicweb.auth.authtkt.session``. Default values are:

    ::

        cubicweb.auth.authtkt.session.hashalg = sha512
        cubicweb.auth.authtkt.session.cookie_name = auth_tkt
        cubicweb.auth.authtkt.session.timeout = 1200
        cubicweb.auth.authtkt.session.reissue_time = 120
        cubicweb.auth.authtkt.session.http_only = True
        cubicweb.auth.authtkt.session.secure = True


:Persistent Authentication:

    This is also a `AuthTktAuthenticationPolicy`_. It is used when persistent
    sessions are activated (typically when using the cubicweb-rememberme_
    cube). You may overwrite default configuration values by adding
    configuration entries using the prefix
    ``cubicweb.auth.authtkt.persistent``. Default values are:

    ::

        cubicweb.auth.authtkt.persistent.hashalg = sha512
        cubicweb.auth.authtkt.persistent.cookie_name = pauth_tkt
        cubicweb.auth.authtkt.persistent.max_age = 3600*24*30
        cubicweb.auth.authtkt.persistent.reissue_time = 3600*24
        cubicweb.auth.authtkt.persistent.http_only = True
        cubicweb.auth.authtkt.persistent.secure = True


.. Warning:: Legacy timeout values from the instance's
             ``all-in-one.conf`` are **not** used at all (``
             http-session-time`` and ``cleanup-session-time``)

Please refer to the documentation_ for more details (available in the
``docs`` directory of the source code).

.. _pyramid_cubicweb: https://www.cubicweb.org/project/pyramid-cubicweb
.. _CubicWeb: https://www.cubicweb.org/
.. _`cubicweb-rememberme`: \
    https://www.cubicweb.org/project/cubicweb-rememberme
.. _Pyramid: http://pypi.python.org/pypi/pyramid
.. _include: http://docs.pylonsproject.org/projects/pyramid/en/latest/api/config.html#pyramid.config.Configurator.include
.. _`INI setting / environment variable`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/environment.html#adding-a-custom-setting
.. _documentation: http://pyramid-cubicweb.readthedocs.org/
.. _AuthTktAuthenticationPolicy: \
    http://docs.pylonsproject.org/projects/pyramid/en/latest/api/authentication.html#pyramid.authentication.AuthTktAuthenticationPolicy

Command
=======

Summary
-------

Add the 'pyramid' command to cubicweb-ctl".

This cube also add a ``CWSession`` entity type so that sessions can be
stored in the database, which allows to run a Cubicweb instance
without having to set up a session storage (like redis or memcache)
solution.

However, for production systems, it is greatly advised to use such a
storage solution for the sessions.

The handling of the sessions is made by pyramid (see the
`pyramid's documentation on sessions`_ for more details).

For example, to set up a redis based session storage, you need the
`pyramid-redis-session`_ package, then you must configure pyramid to
use this backend, by configuring the ``pyramid.ini`` file in the instance's
config directory (near the ``all-in-one.conf`` file):


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
           pyramid_cubicweb.auth
           pyramid_cubicweb.login


See the documentation of `Pyramid Cubicweb`_ for more details.

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

For the record:

:cubicweb.session.secret: This secret is used to encrypt the session's
   data ID (data themselved are stored in the backend, database or
   redis) when using the integrated (``CWSession`` based) session data
   storage.

:redis.session.secret: This secret is used to encrypt the session's
   data ID (data themselved are stored in the backend, database or
   redis) when using redis as backend.

:cubicweb.auth.authtkt.session.secret: This secret is used to encrypt
   the authentication cookie.

:cubicweb.auth.authtkt.persistent.secret: This secret is used to
   encrypt the persistent authentication cookie.


.. _`Pyramid Cubicweb`: http://pyramid-cubicweb.readthedocs.org/
.. _`pyramid's documentation on sessions`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/sessions.html
.. _`pyramid-redis-session`: http://pyramid-redis-sessions.readthedocs.org/en/latest/index.html
.. _`Pyramid's documentation`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/security.html#admonishment-against-secret-sharing
