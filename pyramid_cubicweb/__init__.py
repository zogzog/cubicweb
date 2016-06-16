import os
from warnings import warn
import wsgicors

from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from pyramid.config import Configurator
from pyramid.settings import asbool, aslist

try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser


def make_cubicweb_application(cwconfig, settings=None):
    """
    Create a pyramid-based CubicWeb instance from a cubicweb configuration.

    It is initialy meant to be used by the 'pyramid' command of cubicweb-ctl.

    :param cwconfig: A CubicWeb configuration
    :returns: A Pyramid config object
    """
    settings = dict(settings) if settings else {}
    settings.update(settings_from_cwconfig(cwconfig))
    config = Configurator(settings=settings)
    config.registry['cubicweb.config'] = cwconfig
    config.include('pyramid_cubicweb')
    return config

def settings_from_cwconfig(cwconfig):
    '''
    Extract settings from pyramid.ini and pyramid-debug.ini (if in debug)

    Can be used to configure middleware WSGI with settings from pyramid.ini files

    :param cwconfig: A CubicWeb configuration
    :returns: A settings dictionnary
    '''
    settings_filenames = [os.path.join(cwconfig.apphome, 'pyramid.ini')]
    settings = {}
    if cwconfig.debugmode:
        settings_filenames.insert(
            0, os.path.join(cwconfig.apphome, 'pyramid-debug.ini'))
    
        settings.update({
            'pyramid.debug_authorization': True,
            'pyramid.debug_notfound': True,
            'pyramid.debug_routematch': True,
            'pyramid.reload_templates': True,
        })
    
    for fname in settings_filenames:
        if os.path.exists(fname):
            cp = SafeConfigParser()
            cp.read(fname)
            settings.update(cp.items('main'))
            break
    
    return settings


def wsgi_application_from_cwconfig(
        cwconfig,
        profile=False, profile_output=None, profile_dump_every=None):
    """ Build a WSGI application from a cubicweb configuration

    :param cwconfig: A CubicWeb configuration
    :param profile: Enable profiling. See :ref:`profiling`.
    :param profile_output: Profiling output filename. See :ref:`profiling`.
    :param profile_dump_every: Profiling number of requests before dumping the
                               stats. See :ref:`profiling`.

    :returns: A fully operationnal WSGI application
    """
    config = make_cubicweb_application(cwconfig)
    profile = profile or asbool(config.registry.settings.get(
        'cubicweb.profile.enable', False))
    if profile:
        config.add_route('profile_ping', '_profile/ping')
        config.add_route('profile_cnx', '_profile/cnx')
        config.scan('pyramid_cubicweb.profile')
    app = config.make_wsgi_app()
    # This replaces completely web/cors.py, which is not used by
    # pyramid_cubicweb anymore
    app = wsgicors.CORS(
        app,
        origin=' '.join(cwconfig['access-control-allow-origin']),
        headers=', '.join(cwconfig['access-control-allow-headers']),
        methods=', '.join(cwconfig['access-control-allow-methods']),
        credentials='true')

    if profile:
        from pyramid_cubicweb.profile import wsgi_profile
        filename = profile_output or config.registry.settings.get(
            'cubicweb.profile.output', 'program.prof')
        dump_every = profile_dump_every or config.registry.settings.get(
            'cubicweb.profile.dump_every', 100)
        app = wsgi_profile(app, filename=filename, dump_every=dump_every)
    return app


def wsgi_application(instance_name=None, debug=None):
    """ Build a WSGI application from a cubicweb instance name

    :param instance_name: Name of the cubicweb instance (optional). If not
                          provided, :envvar:`CW_INSTANCE` must exists.
    :param debug: Enable/disable the debug mode. If defined to True or False,
                  overrides :envvar:`CW_DEBUG`.

    The following environment variables are used if they exist:

    .. envvar:: CW_INSTANCE

        A CubicWeb instance name.

    .. envvar:: CW_DEBUG

        If defined, the debugmode is enabled.

    The function can be used as an entry-point for third-party wsgi containers.
    Below is a sample uswgi configuration file:

    .. code-block:: ini

        [uwsgi]
        http = 127.0.1.1:8080
        env = CW_INSTANCE=myinstance
        env = CW_DEBUG=1
        module = pyramid_cubicweb:wsgi_application()
        virtualenv = /home/user/.virtualenvs/myvirtualenv
        processes = 1
        threads = 8
        stats = 127.0.0.1:9191
        plugins = http,python

    """
    if instance_name is None:
        instance_name = os.environ['CW_INSTANCE']
    if debug is None:
        debug = 'CW_DEBUG' in os.environ

    cwconfig = cwcfg.config_for(instance_name, debugmode=debug)

    return wsgi_application_from_cwconfig(cwconfig)


def includeme(config):
    """Set-up a CubicWeb instance.

    The CubicWeb instance can be set in several ways:

    -   Provide an already loaded CubicWeb config instance in the registry:

        .. code-block:: python

            config.registry['cubicweb.config'] = your_config_instance

    -   Provide an instance name in the pyramid settings with
        :confval:`cubicweb.instance`.

    """
    cwconfig = config.registry.get('cubicweb.config')

    if cwconfig is None:
        debugmode = asbool(
            config.registry.settings.get('cubicweb.debug', False))
        cwconfig = cwcfg.config_for(
            config.registry.settings['cubicweb.instance'], debugmode=debugmode)
        config.registry['cubicweb.config'] = cwconfig

    if cwconfig.debugmode:
        try:
            config.include('pyramid_debugtoolbar')
        except ImportError:
            warn('pyramid_debugtoolbar package not available, install it to '
                 'get UI debug features', RuntimeWarning)

    config.registry['cubicweb.repository'] = repo = cwconfig.repository()
    config.registry['cubicweb.registry'] = repo.vreg

    if asbool(config.registry.settings.get('cubicweb.defaults', True)):
        config.include('pyramid_cubicweb.defaults')

    for name in aslist(config.registry.settings.get('cubicweb.includes', [])):
        config.include(name)

    config.include('pyramid_cubicweb.tools')
    config.include('pyramid_cubicweb.predicates')
    config.include('pyramid_cubicweb.core')

    if asbool(config.registry.settings.get('cubicweb.bwcompat', True)):
        config.include('pyramid_cubicweb.bwcompat')
