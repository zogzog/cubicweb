Pyramid
=======

:mod:`cubicweb.pyramid` provides a way to bind a CubicWeb data repository to a
Pyramid WSGI web application.

It can be used in two different ways:

-   Through the :ref:`pyramid command <cubicweb-ctl_pyramid>` or through
    :func:`cubicweb.pyramid.wsgi_application` WSGI application factory, one can
    run an ``all-in-one`` CubicWeb instance with the web part served by a
    Pyramid application. This is referred to as the *backwards compatible
    mode*.

-   Through the ``pyramid`` configuration type, one can setup a CubicWeb
    instance which repository can be used from within a Pyramid application.
    Such an instance may be launched through ``pserve`` or any WSGI server as
    would any plain Pyramid application.


Narrative Documentation
=======================

.. toctree::
    :maxdepth: 2

    quickstart
    ctl
    settings
    auth
    profiling
    debug_toolbar

Api Documentation
=================

.. toctree::
    :maxdepth: 2
    :glob:

    ../../api/pyramid
