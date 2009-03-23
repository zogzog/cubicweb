"""google appengine configuration

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import os
from os.path import join

from cubicweb import CW_SOFTWARE_ROOT
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.web.webconfig import WebConfiguration, merge_options
from cubicweb.server.serverconfig import ServerConfiguration
from cubicweb.goa.dbmyams import load_schema

UNSUPPORTED_OPTIONS = set(('connections-pool-size',
                           'pyro-port', 'pyro-id', 'pyro-application-id',
                           'pyro-ns-host', 'pyro-ns-port', 'pyro-ns-group',
                           'https-url', 'host', 'pid-file', 'uid', 'base-url', 'log-file',
                           'smtp-host', 'smtp-port',
                           'embed-allowed',
                           ))

# XXX fix:
# * default sender-name / sender-addr value
# * what about *session-time
# * check auth-mode=http + fix doc (eg require use-google-auth = False)

class GAEConfiguration(ServerConfiguration, WebConfiguration):
    """repository and web application in the same twisted process"""
    name = 'app'
    repo_method = 'inmemory'
    options = merge_options(( 
        ('included-cubes',
         {'type' : 'csv',
          'default': [],
          'help': 'list of db model based cubes used by the application.',
          'group': 'main', 'inputlevel': 1,
          }),
        ('included-yams-cubes',
         {'type' : 'csv',
          'default': [],
          'help': 'list of yams based cubes used by the application.',
          'group': 'main', 'inputlevel': 1,
          }),
        ('use-google-auth',
         {'type' : 'yn',
          'default': True,
          'help': 'does this application rely on google authentication service or not.',
          'group': 'main', 'inputlevel': 1,
          }),
        ('schema-type',
         {'type' : 'choice', 'choices': ('yams', 'dbmodel'),
          'default': 'yams',
          'help': 'does this application is defining its schema using yams or db model.',
          'group': 'main', 'inputlevel': 1,
          }),
        # overriden options
        ('query-log-file',
         {'type' : 'string',
          'default': None,
          'help': 'web application query log file: DON\'T SET A VALUE HERE WHEN '
          'UPLOADING YOUR APPLICATION. This should only be used to analyse '
          'queries issued by your application in the development environment.',
          'group': 'main', 'inputlevel': 2,
          }),
        ('anonymous-user',
         {'type' : 'string',
          'default': None,
          'help': 'login of the CubicWeb user account to use for anonymous user '
          '(if you want to allow anonymous). This option will be ignored if '
          'use-google-auth option is set (in which case you should control '
          'anonymous access using the app.yaml file)',
          'group': 'main', 'inputlevel': 1,
          }),
        
        ) + WebConfiguration.options + ServerConfiguration.options)
    options = [(optname, optdict) for optname, optdict in options
               if not optname in UNSUPPORTED_OPTIONS]

    cubicweb_vobject_path = WebConfiguration.cubicweb_vobject_path | ServerConfiguration.cubicweb_vobject_path
    cubicweb_vobject_path = list(cubicweb_vobject_path) + ['goa/appobjects']
    cube_vobject_path = WebConfiguration.cube_vobject_path | ServerConfiguration.cube_vobject_path

    # use file system schema
    bootstrap_schema = read_application_schema = False
    # schema is not persistent, don't load schema hooks (unavailable)
    schema_hooks = False
    # no user workflow for now
    consider_user_state = False

    # deactivate some hooks during [pre|post]create scripts execution
    # (unique values check, owned_by/created_by relations setup)
    free_wheel = True
    
    if not os.environ.get('APYCOT_ROOT'):
        CUBES_DIR = join(CW_SOFTWARE_ROOT, '../cubes')
    
    def __init__(self, appid, apphome=None):
        if apphome is None:
            apphome = 'data'
        self._apphome = apphome
        self._base_url = None
        CubicWebConfiguration.__init__(self, appid)

    def __getitem__(self, key):
        if key == 'connections-pool-size':
            return 4 # > 1 to allow multiple user sessions in tests
        if key == 'base-url':
            return self._base_url
        return super(GAEConfiguration, self).__getitem__(key)
    
    # overriden from cubicweb base configuration

    @property
    def apphome(self):
        return self._apphome

    def cubes(self):
        """return the list of top level cubes used by this instance (eg
        without dependencies)
        """
        if self._cubes is None:
            cubes = self['included-cubes'] + self['included-yams-cubes']
            cubes = self.expand_cubes(cubes)
            return self.reorder_cubes(cubes)
        return self._cubes

    def vc_config(self):
        """return CubicWeb's engine and application's cube versions number"""
        return {}

    # overriden from cubicweb web configuration

    def instance_md5_version(self):
        return ''
    
    def _init_base_url(self):
        pass
    
    # overriden from cubicweb server configuration
    
    def sources(self):
        return {'system': {'adapter': 'gae'}}
    
    def load_schema(self, schemaclasses=None, extrahook=None):
        try:
            return self._schema
        except AttributeError:
            self._schema = load_schema(self, schemaclasses, extrahook)
            return self._schema

    # goa specific
    def repo_session(self, sessionid):
        return self.repository()._sessions[sessionid]
    
    def is_anonymous_user(self, login):
        if self['use-google-auth']:
            from google.appengine.api import users
            return users.get_current_user() is None
        else:
            return login == self.anonymous_user()[0]
