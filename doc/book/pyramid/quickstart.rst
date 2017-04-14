Quick start
===========

.. highlight:: bash

Prerequites
-----------

Install the *pyramid* flavour of CubicWeb (here with pip, possibly in a
virtualenv):

::

        pip install cubicweb[pyramid]


Instance creation and running
-----------------------------

In *backwards compatible* mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this mode, you can simply create an instance of kind ``all-in-one`` with
the ``cubicweb-ctl create`` command. You'll then need to add a ``pyramid.ini``
file in your instance directory, see :ref:`pyramid_settings` for details about the
content of this file.

Start the instance with the :ref:`'pyramid' command <cubicweb-ctl_pyramid>`
instead of 'start':

::

    cubicweb-ctl pyramid --debug myinstance


Without *backwards compatibility*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this mode, you can create an instance of kind ``pyramid`` as follow:

::

    cubicweb-ctl create -c pyramid <cube_name> <instance_name>

This will bootstrap a ``development.ini`` file typical of a Pyramid
application in the instance's directory. The new instance may then be launched
by any WSGI server, for instance with pserve_:

::

    pserve etc/cubicweb.d/<instance_name>/development.ini


In a pyramid application
~~~~~~~~~~~~~~~~~~~~~~~~

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

-   Configure the base-url in all-in-one.conf to match the ones of the pyramid
    configuration (this is a temporary limitation).


.. _pserve: \
    http://docs.pylonsproject.org/projects/pyramid/en/latest/pscripts/pserve.html
