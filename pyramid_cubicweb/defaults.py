""" Defaults for a classical CubicWeb instance. """


def includeme(config):
    """ Enable the defaults that make the application behave like a classical
    CubicWeb instance.

    The following modules get included:

    -   :func:`pyramid_cubicweb.session <pyramid_cubicweb.session.includeme>`
    -   :func:`pyramid_cubicweb.auth <pyramid_cubicweb.auth.includeme>`
    -   :func:`pyramid_cubicweb.login <pyramid_cubicweb.login.includeme>`

    It is automatically included by the configuration system, unless the
    following entry is added to the :ref:`pyramid_settings`:

    .. code-block:: ini

        cubicweb.defaults = no

    """
    config.include('pyramid_cubicweb.session')
    config.include('pyramid_cubicweb.auth')
    config.include('pyramid_cubicweb.login')
