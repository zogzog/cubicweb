.. _profiling:

Profiling
=========

Profiling of requests by the pyramid debug toolbar can be a little restrictive
when a specific url needs thin profiling that includes the whole pyramid
dispatch.

Pyramid CubicWeb provides facilities to profile requests as a
:func:`wsgi middleware <cubicweb.pyramid.profile.wsgi_profile>`, and a few
views that facilitate profiling of basic features.

The views and the wsgi middleware are activated when the 'profile' option is
given. This can be done on the command line
(:option:`cubicweb-ctl pyramid --profile`) or in the :ref:`pyramid_settings`.

Views
-----

The following routes and corresponding views are provided when profiling is on:

-   ``/_profile/ping``: Reply 'ping' without doing anything else. See also
    :func:`cubicweb.pyramid.profile.ping`.

-   ``/_profile/cnx``: Reply 'ping' after getting a cnx. See also
    :func:`cubicweb.pyramid.profile.cnx`.

Typical Usage
-------------

Let's say we want to measure the cost of having a ``cnx``.

-   Start the application with profile enabled:

    .. code-block:: console

        $ cubicweb-ctl pyramid --no-daemon --profile --profile-dump-every 100

-   Use 'ab' or any other http benchmark tool to throw a lot of requests:

    .. code-block:: console

        $ ab -c 1 -n 100 http://localhost:8080/_profile/cnx

-   Analyse the results. I personnaly fancy SnakeViz_:

    .. code-block:: console

        $ snakeviz program.prof

.. _SnakeViz: http://jiffyclub.github.io/snakeviz/
