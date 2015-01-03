import os
import wsgicors

from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from pyramid.config import Configurator
from pyramid.settings import asbool, aslist

try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser


def make_cubicweb_application(cwconfig):
    """
    Create a pyramid-based CubicWeb instance from a cubicweb configuration.

    It is initialy meant to be used by the 'pyramid' command of cubicweb-ctl.
    """
    settings_filenames = [os.path.join(cwconfig.apphome, 'pyramid.ini')]

    settings = {}

    if cwconfig.debugmode:
        settings_filenames.insert(
            0, os.path.join(cwconfig.apphome, 'pyramid-debug.ini'))

        settings.update({
            'pyramid.debug_authorization': True,
            'pyramid.debug_notfound': True,
            'pyramid.debug_routematch': True,
        })

    for fname in settings_filenames:
        if os.path.exists(fname):
            cp = SafeConfigParser()
            cp.read(fname)
            settings.update(cp.items('main'))
            break

    config = Configurator(settings=settings)
    if cwconfig.debugmode:
        config.include('pyramid_debugtoolbar')
    config.registry['cubicweb.config'] = cwconfig
    config.registry['cubicweb.repository'] = repo = cwconfig.repository()
    config.registry['cubicweb.registry'] = repo.vreg

    if asbool(config.registry.settings.get('cubicweb.defaults', True)):
        config.include('pyramid_cubicweb.defaults')

    for name in aslist(config.registry.settings.get('cubicweb.includes')):
        config.include(name)

    config.include('pyramid_cubicweb.core')

    if asbool(config.registry.settings.get('cubicweb.bwcompat', True)):
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
