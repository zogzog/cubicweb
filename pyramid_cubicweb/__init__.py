import os

from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
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


def wsgi_application(instance_name=None, debug=None):
    if instance_name is None:
        instance_name = os.environ.get('CW_INSTANCE')
    if debug is None:
        debug = 'CW_DEBUG' in os.environ

    cwconfig = cwcfg.config_for(instance_name, debugmode=debug)
    config = make_cubicweb_application(cwconfig)
    return config.make_wsgi_app()
