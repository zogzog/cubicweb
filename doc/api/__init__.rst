.. _index_module:

:mod:`cubicweb`
===============

.. automodule:: cubicweb

    Exceptions
    ----------

    Base exceptions
    ~~~~~~~~~~~~~~~

    .. autoexception:: ProgrammingError
        :show-inheritance:

    .. autoexception:: CubicWebException
        :show-inheritance:

    .. autoexception:: InternalError
        :show-inheritance:

    .. autoexception:: SecurityError
        :show-inheritance:

    .. autoexception:: RepositoryError
        :show-inheritance:

    .. autoexception:: SourceException
        :show-inheritance:

    .. autoexception:: CubicWebRuntimeError
        :show-inheritance:

    Repository exceptions
    ~~~~~~~~~~~~~~~~~~~~~

    .. autoexception:: ConnectionError
        :show-inheritance:

    .. autoexception:: AuthenticationError
        :show-inheritance:

    .. autoexception:: BadConnectionId
        :show-inheritance:

    .. autoexception:: UnknownEid
        :show-inheritance:

    .. autoexception:: UniqueTogetherError
        :show-inheritance:

    Security Exceptions
    ~~~~~~~~~~~~~~~~~~~

    .. autoexception:: Unauthorized
        :show-inheritance:

    .. autoexception:: Forbidden
        :show-inheritance:

    Source exceptions
    ~~~~~~~~~~~~~~~~~

    .. autoexception:: EidNotInSource
        :show-inheritance:

    Registry exceptions
    ~~~~~~~~~~~~~~~~~~~

    .. autoexception:: UnknownProperty
        :show-inheritance:

    Query exceptions
    ~~~~~~~~~~~~~~~~

    .. autoexception:: QueryError
        :show-inheritance:

    .. autoexception:: NotAnEntity
        :show-inheritance:

    .. autoexception:: MultipleResultsError
        :show-inheritance:

    .. autoexception:: NoResultError
        :show-inheritance:

    .. autoexception:: UndoTransactionException
        :show-inheritance:


    Misc
    ~~~~

    .. autoexception:: ConfigurationError
        :show-inheritance:

    .. autoexception:: ExecutionError
        :show-inheritance:

    .. autoexception:: BadCommandUsage
        :show-inheritance:

    .. autoexception:: ValidationError
        :show-inheritance:


    Utilities
    ---------

    .. autoclass:: Binary
    .. autoclass:: CubicWebEventManager
    .. autofunction:: onevent
    .. autofunction:: validation_error
