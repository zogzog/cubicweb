================
Pyramid Cubicweb
================

Pyramid Cubicweb is an attempt to rebase the CubicWeb framework on pyramid.

It can be used in two different ways:

-   Within CubicWeb, through the 'pyramid' cube and the
    :ref:`pyramid command <cubicweb-ctl_pyramid>`.
    In this mode, the Pyramid CubicWeb replaces some parts of
    CubicWeb and make the pyramid api available to the cubes.

-   Within a pyramid application, it provides easy access to a CubicWeb
    instance and registry.

Narrative Documentation
=======================

.. toctree::
    :maxdepth: 2
    
    quickstart
    ctl
    settings
    auth
    profiling

Api Documentation
=================

.. toctree::
    :maxdepth: 2
    :glob:

    ../../api/pyramid
