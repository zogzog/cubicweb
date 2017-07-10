Settings
========

.. _cubicweb_settings:

Cubicweb Settings
-----------------

Pyramid CubicWeb will **not** make use of the configuration entries
found in the cubicweb configuration (a.k.a. `all-in-one.conf`) for any
pyramid related configuration value.


.. _pyramid_settings:

Pyramid Settings file
---------------------

In *backwards compatibility* mode, Pyramid settings will be looked for in a
``pyramid.ini`` file in the instance home directory (where the
``all-in-one.conf`` file is), its ``[main]`` section will be read and used as
the ``settings`` of the pyramid Configurator.

This configuration file is almost the same as the one read by ``pserve``, which
allow to easily add any pyramid extension and configure it.

A typical ``pyramid.ini`` file is:

.. code-block:: ini

    [main]
    pyramid.includes =
        pyramid_redis_sessions

    cubicweb.defaults = no
    cubicweb.includes =
        cubicweb.pyramid.auth
        cubicweb.pyramid.login

    cubicweb.profile = no

    redis.sessions.secret = your_cookie_signing_secret
    redis.sessions.timeout = 1200

    redis.sessions.host = mywheezy


Without *backwards compatibility* a standard ``development.ini`` file can be
used with any useful CubicWeb-specific settings added.


Pyramid CubicWeb configuration entries
--------------------------------------

The Pyramid CubicWeb specific configuration entries are:

.. confval:: cubicweb.instance (string)

    A CubicWeb instance name. Useful when the application is not run by
    :ref:`cubicweb-ctl_pyramid`.

.. confval:: cubicweb.debug (bool)

    Enables the cubicweb debugmode. Works only if the instance is setup by
    :confval:`cubicweb.instance`.

    Unlike when the debugmode is set by the :option:`cubicweb-ctl pyramid --debug-mode`
    command, the pyramid debug options are untouched.

.. confval:: cubicweb.includes (list)

    Same as ``pyramid.includes``, but the includes are done after the cubicweb
    specific registry entries are initialized.

    Useful to include extensions that requires these entries.

.. confval:: cubicweb.bwcompat (bool)

    (True) Enable/disable backward compatibility. This only applies to
    "all-in-one" configuration type.

    See :ref:`bwcompat_module`.

.. confval:: cubicweb.bwcompat.errorhandler (bool)

    (True) Enable/disable the backward compatibility error handler.
    Set to 'no' if you need to define your own error handlers.

.. confval:: cubicweb.defaults (bool)

    (True) Enable/disable defaults. See :ref:`defaults_module`.

.. confval:: cubicweb.profile (bool)

    (False) Enable/disable profiling. See :ref:`profiling`.

.. confval:: cubicweb.auth.update_login_time (bool)

    (True) Add a :class:`cubicweb.pyramid.auth.UpdateLoginTimeAuthenticationPolicy`
    policy, that update the CWUser.login_time attribute when a user login.
    
.. confval:: cubicweb.auth.authtkt (bool)

    (True) Enables the 2 cookie-base auth policies, which activate/deactivate
    depending on the `persistent` argument passed to `remember`.

    The default login views set persistent to True if a `__setauthcookie`
    parameters is passed to them, and evals to True in
    :func:`pyramid.settings.asbool`.

    The configuration values of the policies are arguments for
    :class:`pyramid.authentication.AuthTktAuthenticationPolicy`.

    The first policy handles session authentication. It doesn't get
    activated if `remember()` is called with `persistent=False`:

    .. confval:: cubicweb.auth.authtkt.session.cookie_name (str)

        ('auth_tkt') The cookie name. Must be different from the persistent
        authentication cookie name.

    .. confval:: cubicweb.auth.authtkt.session.timeout (int)

        (1200) Cookie timeout.

    .. confval:: cubicweb.auth.authtkt.session.reissue_time (int)

        (120) Reissue time.

    The second policy handles persistent authentication. It doesn't get
    activated if `remember()` is called with `persistent=True`:

    .. confval:: cubicweb.auth.authtkt.persistent.cookie_name (str)

        ('auth_tkt') The cookie name. Must be different from the session
        authentication cookie name.

    .. confval:: cubicweb.auth.authtkt.persistent.max_age (int)

        (30 days) Max age in seconds.

    .. confval:: cubicweb.auth.authtkt.persistent.reissue_time (int)

        (1 day) Reissue time in seconds.

    Both policies set the ``secure`` flag to ``True`` by default, meaning that
    cookies will only be sent back over a secure connection (see
    `Authentication Policies documentation`_ for details). This can be
    configured through :confval:`cubicweb.auth.authtkt.persistent.secure` and
    :confval:`cubicweb.auth.authtkt.session.secure` configuration options.

    .. _`Authentication Policies documentation`: \
        http://docs.pylonsproject.org/projects/pyramid/en/latest/api/authentication.html

.. confval:: cubicweb.auth.groups_principals (bool)

    (True) Setup a callback on the authentication stack that inject the user
    groups in the principals.
