Quick start
===========

.. highlight:: bash

Prerequites
-----------

-   Install everything (here with pip, possibly in a virtualenv)::

        pip install pyramid-cubicweb cubicweb-pyramid pyramid_debugtoolbar

-   Have a working Cubicweb instance, for example:


    -   Make sure CubicWeb is in user mode::

            export CW_MODE=user

    -   Create a CubicWeb instance, and install the 'pyramid' cube on it (see
        :ref:`configenv` for more details on this step)::

            cubicweb-ctl create pyramid myinstance

-   Edit your ``~/etc/cubicweb.d/myinstance/all-in-one.conf`` and set values for
    :confval:`pyramid-auth-secret` and :confval:`pyramid-session-secret`.
    *required if cubicweb.pyramid.auth and pyramid_cubiweb.session get
    included, which is the default*

From CubicWeb
-------------

-   Start the instance with the :ref:`'pyramid' command <cubicweb-ctl_pyramid>`
    instead of 'start'::

        cubicweb-ctl pyramid --debug myinstance

In a pyramid application
------------------------

-   Create a pyramid application

-   Include cubicweb.pyramid:

    .. code-block:: python

        def includeme(config):
            # ...
            config.include('cubicweb.pyramid')
            # ...

-   Configure the instance name (in the .ini file):

    .. code-block:: ini

        cubicweb.instance = myinstance

-   Configure the base-url and https-url in all-in-one.conf to match the ones
    of the pyramid configuration (this is a temporary limitation).


Usage with pserve
-----------------

To run a Pyramid application using pserve_:

::

    pserve /path/to/development.ini instance=<appid>


.. _pserve: \
    http://docs.pylonsproject.org/projects/pyramid/en/latest/pscripts/pserve.html
