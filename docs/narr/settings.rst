Settings
========

.. _cubicweb_settings:

Cubicweb Settings
-----------------

Pyramid CubicWeb will make use of the following configuration entries if found
in the cubicweb configuration (a.k.a. `all-in-one.conf`):

.. warning::

    These settings requires the `pyramid` cube to be enabled on the instance.

.. confval:: pyramid-session-secret

    Secret phrase to sign the session cookie
    
    Used by :func:`pyramid_cubicweb.session.includeme` to configure the default session factory.

    .. code-block:: ini

        pyramid-session-secret = <some very secret passphrase>

.. confval:: pyramid-auth-secret

    Secret phrase to sign the authentication cookie
    
    Used by :func:`pyramid_cubicweb.auth.includeme` to configure the default authentication policy.

    .. code-block:: ini

        pyramid-auth-secret = <some other very secret passphrase>


.. _pyramid_settings:

Pyramid Settings
----------------

If a ``pyramid.ini`` file is found in the instance home directory (where the
``all-in-one.conf`` file is), its ``[main]`` section will be read and used as the
``settings`` of the pyramid Configurator.

This configuration file is almost the same as the one read by ``pserve``, which
allow to easily add any pyramid extension and configure it.

A typical ``pyramid.ini`` file is:

.. code-block:: ini

    [main]
    pyramid.includes =
        pyramid_redis_sessions

    cubicweb.defaults = no
    cubicweb.includes =
        pyramid_cubicweb.auth
        pyramid_cubicweb.login

    cubicweb.profile = no

    redis.sessions.secret = your_cookie_signing_secret
    redis.sessions.timeout = 1200

    redis.sessions.host = mywheezy

The Pyramid CubicWeb specific configuration entries are:

.. confval:: cubicweb.includes (list)

    Same as ``pyramid.includes``, but the includes are done after the cubicweb
    specific registry entries are initialized.

    Useful to include extensions that requires these entries.

.. confval:: cubicweb.bwcompat (bool)

    (True) Enable/disable backward compatibility. See :ref:`bwcompat_module`.

.. confval:: cubicweb.defaults (bool)

    (True) Enable/disable defaults. See :ref:`defaults_module`.

.. confval:: cubicweb.profile (bool)

    (False) Enable/disable profiling. See :ref:`profiling`.
