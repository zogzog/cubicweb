import os
import wsgicors

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


def wsgi_application_from_cwconfig(cwconfig):
    config = make_cubicweb_application(cwconfig)
    app = config.make_wsgi_app()
    # This replaces completely web/cors.py, which is not used by
    # pyramid_cubicweb anymore
    app = wsgicors.CORS(
        app,
        origin=' '.join(cwconfig['access-control-allow-origin']),
        headers=cwconfig['access-control-allow-headers'],
        methods=cwconfig['access-control-allow-methods'],
        credentials='true')
    return app


def wsgi_application(instance_name=None, debug=None):
    if instance_name is None:
        instance_name = os.environ.get('CW_INSTANCE')
    if debug is None:
        debug = 'CW_DEBUG' in os.environ

    cwconfig = cwcfg.config_for(instance_name, debugmode=debug)

    return wsgi_application_from_cwconfig(cwconfig)
