""" Defaults for a classical CubicWeb instance. """


def includeme(config):
    """ Enable the defaults that make the application behave like a classical
    CubicWeb instance.

    The following modules get included:

    -   :func:`cubicweb.pyramid.session <cubicweb.pyramid.session.includeme>`
    -   :func:`cubicweb.pyramid.auth <cubicweb.pyramid.auth.includeme>`
    -   :func:`cubicweb.pyramid.login <cubicweb.pyramid.login.includeme>`

    It is automatically included by the configuration system, unless the
    following entry is added to the :ref:`pyramid_settings`:

    .. code-block:: ini

        cubicweb.defaults = no

    """
    config.include('cubicweb.pyramid.session')
    config.include('cubicweb.pyramid.auth')
    config.include('cubicweb.pyramid.login')
