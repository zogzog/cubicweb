# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""web ui configuration for cubicweb instances"""


from cubicweb import _

import os
import hmac
from uuid import uuid4
from os.path import dirname, join, exists, split, isdir

from logilab.common.decorators import cached, cachedproperty
from logilab.common.configuration import Method, merge_options

from cubicweb import ConfigurationError
from cubicweb.cwconfig import CubicWebConfiguration, register_persistent_options


_DATA_DIR = join(dirname(__file__), 'data')


register_persistent_options((
    # site-wide only web ui configuration
    ('site-title',
     {'type': 'string', 'default': 'unset title',
      'help': _('site title'),
      'sitewide': True, 'group': 'ui',
      }),
    ('main-template',
     {'type': 'string', 'default': 'main-template',
      'help': _('id of main template used to render pages'),
      'sitewide': True, 'group': 'ui',
      }),
    # user web ui configuration
    ('fckeditor',
     {'type': 'yn', 'default': False,
      'help': _('should html fields being edited using fckeditor (a HTML '
                'WYSIWYG editor).  You should also select text/html as default '
                'text format to actually get fckeditor.'),
      'group': 'ui',
      }),
    # navigation configuration
    ('page-size',
     {'type': 'int', 'default': 40,
      'help': _('maximum number of objects displayed by page of results'),
      'group': 'navigation',
      }),
    ('related-limit',
     {'type': 'int', 'default': 8,
      'help': _('maximum number of related entities to display in the primary '
                'view'),
      'group': 'navigation',
      }),
    ('combobox-limit',
     {'type': 'int', 'default': 20,
      'help': _('maximum number of entities to display in related combo box'),
      'group': 'navigation',
      }),

))


class BaseWebConfiguration(CubicWebConfiguration):
    """Base class for web configurations"""
    cubicweb_appobject_path = CubicWebConfiguration.cubicweb_appobject_path | set(['web.views'])
    cube_appobject_path = CubicWebConfiguration.cube_appobject_path | set(['views'])

    options = merge_options(CubicWebConfiguration.options + (
        ('repository-uri',
         {'type': 'string',
          'default': 'inmemory://',
          'help': 'see `cubicweb.dbapi.connect` documentation for possible value',
          'group': 'web', 'level': 2,
          }),
        ('use-uicache',
         {'type': 'yn', 'default': True,
          'help': _('should css be compiled and store in uicache'),
          'group': 'ui', 'level': 2,
          }),
        ('anonymous-user',
         {'type': 'string',
          'default': None,
          'help': ('login of the CubicWeb user account to use for anonymous '
                   'user (if you want to allow anonymous)'),
          'group': 'web', 'level': 1,
          }),
        ('anonymous-password',
         {'type': 'string',
          'default': None,
          'help': 'password of the CubicWeb user account to use for anonymous user, '
          'if anonymous-user is set',
          'group': 'web', 'level': 1,
          }),
        ('query-log-file',
         {'type': 'string',
          'default': None,
          'help': 'web instance query log file',
          'group': 'web', 'level': 3,
          }),
        ('cleanup-anonymous-session-time',
         {'type': 'time',
          'default': '5min',
          'help': 'Same as cleanup-session-time but specific to anonymous '
          'sessions. You can have a much smaller timeout here since it will be '
          'transparent to the user. Default to 5min.',
          'group': 'web', 'level': 3,
          }),
    ))

    def anonymous_user(self):
        """return a login and password to use for anonymous users.

        None may be returned for both if anonymous connection is not
        allowed or if an empty login is used in configuration
        """
        try:
            user = self['anonymous-user'] or None
            passwd = self['anonymous-password']
        except KeyError:
            user, passwd = None, None
        except UnicodeDecodeError:
            raise ConfigurationError("anonymous information should only contains ascii")
        return user, passwd


class WebConfiguration(BaseWebConfiguration):
    """the WebConfiguration is a singleton object handling instance's
    configuration and preferences
    """
    options = merge_options(BaseWebConfiguration.options + (
        # web configuration
        ('datadir-url',
         {'type': 'string', 'default': None,
          'help': ('base url for static data, if different from "${base-url}/data/".  '
                   'If served from a different domain, that domain should allow '
                   'cross-origin requests.'),
          'group': 'web',
          }),
        ('auth-mode',
         {'type': 'choice',
          'choices': ('cookie', 'http'),
          'default': 'cookie',
          'help': 'authentication mode (cookie / http)',
          'group': 'web', 'level': 3,
          }),
        ('realm',
         {'type': 'string',
          'default': 'cubicweb',
          'help': 'realm to use on HTTP authentication mode',
          'group': 'web', 'level': 3,
          }),
        ('http-session-time',
         {'type': 'time',
          'default': 0,
          'help': "duration of the cookie used to store session identifier. "
          "If 0, the cookie will expire when the user exist its browser. "
          "Should be 0 or greater than repository\'s session-time.",
          'group': 'web', 'level': 2,
          }),
        ('submit-mail',
         {'type': 'string',
          'default': None,
          'help': ('Mail used as recipient to report bug in this instance, '
                   'if you want this feature on'),
          'group': 'web', 'level': 2,
          }),

        ('language-mode',
         {'type': 'choice',
          'choices': ('http-negotiation', 'url-prefix', ''),
          'default': 'http-negotiation',
          'help': ('source for interface\'s language detection. '
                   'If set to "http-negotiation" the Accept-Language HTTP header will be used,'
                   ' if set to "url-prefix", the URL will be inspected for a'
                   ' short language prefix.'),
          'group': 'web', 'level': 2,
          }),

        ('print-traceback',
         {'type': 'yn',
          'default': CubicWebConfiguration.mode != 'system',
          'help': 'print the traceback on the error page when an error occurred',
          'group': 'web', 'level': 2,
          }),

        ('captcha-font-file',
         {'type': 'string',
          'default': join(_DATA_DIR, 'porkys.ttf'),
          'help': 'True type font to use for captcha image generation (you \
must have the python imaging library installed to use captcha)',
          'group': 'web', 'level': 3,
          }),
        ('captcha-font-size',
         {'type': 'int',
          'default': 25,
          'help': 'Font size to use for captcha image generation (you must \
have the python imaging library installed to use captcha)',
          'group': 'web', 'level': 3,
          }),

        ('concat-resources',
         {'type': 'yn',
          'default': False,
          'help': 'use modconcat-like URLS to concat and serve JS / CSS files',
          'group': 'web', 'level': 2,
          }),
        ('anonymize-jsonp-queries',
         {'type': 'yn',
          'default': True,
          'help': 'anonymize the connection before executing any jsonp query.',
          'group': 'web', 'level': 1
          }),
        ('generate-staticdir',
         {'type': 'yn',
          'default': False,
          'help': 'Generate the static data resource directory on upgrade.',
          'group': 'web', 'level': 2,
          }),
        ('staticdir-path',
         {'type': 'string',
          'default': None,
          'help': 'The static data resource directory path.',
          'group': 'web', 'level': 2,
          }),
        ('access-control-allow-origin',
         {'type': 'csv',
          'default': (),
          'help': ('comma-separated list of allowed origin domains or "*" for any domain'),
          'group': 'web', 'level': 2,
          }),
        ('access-control-allow-methods',
         {'type': 'csv',
          'default': (),
          'help': ('comma-separated list of allowed HTTP methods'),
          'group': 'web', 'level': 2,
          }),
        ('access-control-max-age',
         {'type': 'int',
          'default': None,
          'help': ('maximum age of cross-origin resource sharing (in seconds)'),
          'group': 'web', 'level': 2,
          }),
        ('access-control-expose-headers',
         {'type': 'csv',
          'default': (),
          'help': ('comma-separated list of HTTP headers the application '
                   'declare in response to a preflight request'),
          'group': 'web', 'level': 2,
          }),
        ('access-control-allow-headers',
         {'type': 'csv',
          'default': (),
          'help': ('comma-separated list of HTTP headers the application may set in the response'),
          'group': 'web', 'level': 2,
          }),
    ))

    def __init__(self, *args, **kwargs):
        super(WebConfiguration, self).__init__(*args, **kwargs)
        self.uiprops = None
        self.datadir_url = None

    def fckeditor_installed(self):
        if self.uiprops is None:
            return False
        return exists(self.uiprops.get('FCKEDITOR_PATH', ''))

    def cwproperty_definitions(self):
        for key, pdef in super(WebConfiguration, self).cwproperty_definitions():
            if key == 'ui.fckeditor' and not self.fckeditor_installed():
                continue
            yield key, pdef

    @cachedproperty
    def _instance_salt(self):
        """This random key/salt is used to sign content to be sent back by
        browsers, eg. in the error report form.
        """
        return str(uuid4()).encode('ascii')

    def sign_text(self, text):
        """sign some text for later checking"""
        # hmac.new expect bytes
        if isinstance(text, str):
            text = text.encode('utf-8')
        # replace \r\n so we do not depend on whether a browser "reencode"
        # original message using \r\n or not
        return hmac.new(self._instance_salt,
                        text.strip().replace(b'\r\n', b'\n'),
                        digestmod="sha3_512").hexdigest()

    def check_text_sign(self, text, signature):
        """check the text signature is equal to the given signature"""
        return self.sign_text(text) == signature

    def locate_resource(self, rid):
        """return the (directory, filename) where the given resource
        may be found
        """
        return self._fs_locate(rid, 'data')

    def locate_doc_file(self, fname):
        """return the directory where the given resource may be found"""
        return self._fs_locate(fname, 'wdoc')[0]

    @cached
    def _fs_path_locate(self, rid, rdirectory):
        """return the directory where the given resource may be found"""
        path = [self.apphome] + self.cubes_path() + [dirname(__file__)]
        for directory in path:
            if exists(join(directory, rdirectory, rid)):
                return directory

    def _fs_locate(self, rid, rdirectory):
        """return the (directory, filename) where the given resource
        may be found
        """
        directory = self._fs_path_locate(rid, rdirectory)
        if directory is None:
            return None, None
        if self['use-uicache'] and rdirectory == 'data' and rid.endswith('.css'):
            return self.ensure_uid_directory(
                self.uiprops.process_resource(
                    join(directory, rdirectory), rid)), rid
        return join(directory, rdirectory), rid

    def locate_all_files(self, rid, rdirectory='wdoc'):
        """return all files corresponding to the given resource"""
        path = [self.apphome] + self.cubes_path() + [dirname(__file__)]
        for directory in path:
            fpath = join(directory, rdirectory, rid)
            if exists(fpath):
                yield join(fpath)

    def load_configuration(self, **kw):
        """load instance's configuration files"""
        super(WebConfiguration, self).load_configuration(**kw)
        # load external resources definition
        self._init_base_url()
        self._build_ui_properties()

    def _init_base_url(self):
        # normalize base url(s)
        baseurl = self['base-url'] or self.default_base_url()
        if baseurl and baseurl[-1] != '/':
            baseurl += '/'
        if not (self.repairing or self.creating):
            self.global_set_option('base-url', baseurl)
        self.datadir_url = self['datadir-url']
        if self.datadir_url:
            if self.datadir_url[-1] != '/':
                self.datadir_url += '/'
            if self.mode != 'test':
                self.datadir_url += '%s/' % self.instance_md5_version()
            return
        data_relpath = self.data_relpath()
        self.datadir_url = baseurl + data_relpath

    def data_relpath(self):
        if self.mode == 'test':
            return 'data/'
        return 'data/%s/' % self.instance_md5_version()

    def _build_ui_properties(self):
        # self.datadir_url[:-1] to remove trailing /
        from cubicweb.web.propertysheet import PropertySheet
        cachedir = join(self.appdatahome, 'uicache')
        self.check_writeable_uid_directory(cachedir)
        self.uiprops = PropertySheet(
            cachedir,
            data=lambda x: self.datadir_url + x,
            datadir_url=self.datadir_url[:-1])
        self._init_uiprops(self.uiprops)

    def _init_uiprops(self, uiprops):
        libuiprops = join(_DATA_DIR, 'uiprops.py')
        uiprops.load(libuiprops)
        for path in reversed([self.apphome] + self.cubes_path()):
            self._load_ui_properties_file(uiprops, path)
        self._load_ui_properties_file(uiprops, self.apphome)
        datadir_url = uiprops.context['datadir_url']
        cubicweb_js_url = datadir_url + '/cubicweb.js'
        if cubicweb_js_url not in uiprops['JAVASCRIPTS']:
            uiprops['JAVASCRIPTS'].insert(0, cubicweb_js_url)

    def _load_ui_properties_file(self, uiprops, path):
        uipropsfile = join(path, 'uiprops.py')
        if exists(uipropsfile):
            self.debug('loading %s', uipropsfile)
            uiprops.load(uipropsfile)

    # static files handling ###################################################

    @property
    def static_directory(self):
        return join(self.appdatahome, 'static')

    def static_file_exists(self, rpath):
        return exists(join(self.static_directory, rpath))

    def static_file_open(self, rpath, mode='wb'):
        staticdir = self.static_directory
        rdir, filename = split(rpath)
        if rdir:
            staticdir = join(staticdir, rdir)
            if not isdir(staticdir) and 'w' in mode:
                self.check_writeable_uid_directory(staticdir)
        return open(join(staticdir, filename), mode)

    def static_file_add(self, rpath, data):
        stream = self.static_file_open(rpath)
        stream.write(data)
        stream.close()
        self.ensure_uid(rpath)

    def static_file_del(self, rpath):
        if self.static_file_exists(rpath):
            os.remove(join(self.static_directory, rpath))


class WebConfigurationBase(WebConfiguration):
    """web instance (in a web server) client of a RQL server"""

    options = merge_options((
        # ctl configuration
        ('port',
         {'type': 'int',
          'default': None,
          'help': 'http server port number (default to 8080)',
          'group': 'web', 'level': 0,
          }),
        ('interface',
         {'type': 'string',
          'default': '0.0.0.0',
          'help': 'http server address on which to listen (default to everywhere)',
          'group': 'web', 'level': 1,
          }),
        ('max-post-length',  # XXX specific to "wsgi" server
         {'type': 'bytes',
          'default': '100MB',
          'help': 'maximum length of HTTP request. Default to 100 MB.',
          'group': 'web', 'level': 1,
          }),
        ('pid-file',
         {'type': 'string',
          'default': Method('default_pid_file'),
          'help': 'repository\'s pid file',
          'group': 'main', 'level': 2,
          }),
    ) + WebConfiguration.options)

    def default_base_url(self):
        from socket import getfqdn
        return 'http://%s:%s/' % (self['host'] or getfqdn().lower(), self['port'] or 8080)
