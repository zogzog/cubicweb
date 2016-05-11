
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
