Quick start
===========

.. highlight:: console

From CubicWeb
-------------

-   Install everything (here with pip, possibly in a virtualenv)::

        pip install pyramid-cubicweb cubicweb-pyramid pyramid_debugtoolbar
        
-   Make sure CubicWeb is in user mode::

        export CW_MODE=user

-   Create a CubicWeb instance, and install the 'pyramid' cube on it (see
    :ref:`configenv` for more details on this step)::

        cubicweb-ctl create pyramid myinstance

-   Edit your ``~/etc/cubicweb.d/myinstance/all-in-one.conf`` and set values for
    :confval:`pyramid-auth-secret` and :confval:`pyramid-session-secret`.

-   Start the instance with the :ref:`'pyramid' command <cubicweb-ctl_pyramid>`
    instead of 'start'::

        cubicweb-ctl pyramid --debug myinstance

In a pyramid application
------------------------

Coming soon.
