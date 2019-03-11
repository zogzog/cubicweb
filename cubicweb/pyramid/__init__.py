# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# copyright 2014-2016 UNLISH S.A.S. (Montpellier, FRANCE), all rights reserved.
#
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

"""Pyramid interface to CubicWeb"""

import atexit
import os
import warnings

from six.moves.configparser import SafeConfigParser
import wsgicors

from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool, aslist


def config_from_cwconfig(cwconfig, settings=None):
    """Return a Pyramid Configurator instance built from a CubicWeb config and
    Pyramid-specific configuration files (pyramid.ini).

    :param cwconfig: A CubicWeb configuration
    :returns: A Pyramid config object
    """
    settings = dict(settings) if settings else {}
    settings.update(settings_from_cwconfig(cwconfig))
    config = Configurator(settings=settings)
    config.registry['cubicweb.config'] = cwconfig
    config.include('cubicweb.pyramid')
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
    config = config_from_cwconfig(cwconfig)
    profile = profile or asbool(config.registry.settings.get(
        'cubicweb.profile.enable', False))
    if profile:
        config.add_route('profile_ping', '_profile/ping')
        config.add_route('profile_cnx', '_profile/cnx')
        config.scan('cubicweb.pyramid.profile')
    app = config.make_wsgi_app()
    # This replaces completely web/cors.py, which is not used by
    # cubicweb.pyramid anymore
    app = wsgicors.CORS(
        app,
        origin=' '.join(cwconfig['access-control-allow-origin']),
        headers=', '.join(cwconfig['access-control-allow-headers']),
        expose_headers=', '.join(cwconfig['access-control-expose-headers']),
        methods=', '.join(cwconfig['access-control-allow-methods']),
        maxage=cwconfig['access-control-max-age'],
        credentials='true')

    if profile:
        from cubicweb.pyramid.profile import wsgi_profile
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
        module = cubicweb.pyramid:wsgi_application()
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


def pyramid_app(global_config, **settings):
    """Return a Pyramid WSGI application bound to a CubicWeb repository."""
    config = Configurator(settings=settings)
    config.include('cubicweb.pyramid')
    return config.make_wsgi_app()


def includeme(config):
    """Set-up a CubicWeb instance.

    The CubicWeb instance can be set in several ways:

    -   Provide an already loaded CubicWeb repository in the registry:

        .. code-block:: python

            config.registry['cubicweb.repository'] = your_repo_instance

    -   Provide an already loaded CubicWeb config instance in the registry:

        .. code-block:: python

            config.registry['cubicweb.config'] = your_config_instance

    -   Provide an instance name in the pyramid settings with
        :confval:`cubicweb.instance`.

    A CubicWeb repository is instantiated and attached in
    'cubicweb.repository' registry key if not already present.

    The CubicWeb instance registry is attached in 'cubicweb.registry' registry
    key.
    """
    cwconfig = config.registry.get('cubicweb.config')
    repo = config.registry.get('cubicweb.repository')

    if repo is not None:
        if cwconfig is None:
            config.registry['cubicweb.config'] = cwconfig = repo.config
        elif cwconfig is not repo.config:
            raise ConfigurationError(
                'CubicWeb config instance (found in "cubicweb.config" '
                'registry key) mismatches with that of the repository '
                '(registry["cubicweb.repository"])'
            )

    if cwconfig is None:
        debugmode = asbool(
            config.registry.settings.get('cubicweb.debug', False))
        cwconfig = cwcfg.config_for(
            config.registry.settings['cubicweb.instance'], debugmode=debugmode)
        config.registry['cubicweb.config'] = cwconfig

    if repo is None:
        repo = config.registry['cubicweb.repository'] = cwconfig.repository()
    config.registry['cubicweb.registry'] = repo.vreg

    if cwconfig.mode != 'test':
        @atexit.register
        def shutdown_repo():
            if repo.shutting_down:
                return
            repo.shutdown

    if asbool(config.registry.settings.get('cubicweb.defaults', True)):
        config.include('cubicweb.pyramid.defaults')

    for name in aslist(config.registry.settings.get('cubicweb.includes', [])):
        config.include(name)

    config.include('cubicweb.pyramid.core')

    if asbool(config.registry.settings.get('cubicweb.bwcompat',
                                           cwconfig.name == 'all-in-one')):
        if cwconfig.name != 'all-in-one':
            warnings.warn('"cubicweb.bwcompat" setting only applies to '
                          '"all-in-one" instance configuration',
                          UserWarning)
        else:
            config.include('cubicweb.pyramid.bwcompat')
