from pyramid.config import Configurator


def make_cubicweb_application(cwconfig):
    """
    Create a pyramid-based CubicWeb instance from a cubicweb configuration.

    It is initialy meant to be used by the 'pyramid' command of cubicweb-ctl.
    """
    settings = {
        'session.secret': '11',  # XXX
    }
    if cwconfig.debugmode:
        settings.update({
            'pyramid.debug_authorization': True,
            'pyramid.debug_notfound': True,
            'pyramid.debug_routematch': True,
        })
    config = Configurator(settings=settings)
    if cwconfig.debugmode:
        config.include('pyramid_debugtoolbar')
    config.registry['cubicweb.config'] = cwconfig
    config.registry['cubicweb.repository'] = repo = cwconfig.repository()
    config.registry['cubicweb.registry'] = repo.vreg
    config.include('pyramid_cubicweb.defaults')
    config.include('pyramid_cubicweb.core')
    config.include('pyramid_cubicweb.bwcompat')
    return config
