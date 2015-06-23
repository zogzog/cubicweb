.. _dataimport_module:

:mod:`cubicweb.dataimport`
==========================

.. automodule:: cubicweb.dataimport

    Utilities
    ---------

    .. autofunction:: count_lines

    .. autofunction:: ucsvreader_pb

    .. autofunction:: ucsvreader

    .. autofunction:: callfunc_every

    .. autofunction:: lazytable

    .. autofunction:: lazydbtable

    .. autofunction:: mk_entity

    Sanitizing/coercing functions
    -----------------------------

    .. autofunction:: optional
    .. autofunction:: required
    .. autofunction:: todatetime
    .. autofunction:: call_transform_method
    .. autofunction:: call_check_method

    Integrity functions
    -------------------

    .. autofunction:: check_doubles
    .. autofunction:: check_doubles_not_none

    Object Stores
    -------------

    .. autoclass:: ObjectStore
        :members:

    .. autoclass:: RQLObjectStore
        :show-inheritance:
        :members:

    .. autoclass:: NoHookRQLObjectStore
        :show-inheritance:
        :members:

    .. autoclass:: SQLGenObjectStore
        :show-inheritance:
        :members:

    Import Controller
    -----------------

    .. autoclass:: CWImportController
        :show-inheritance:
        :members:
