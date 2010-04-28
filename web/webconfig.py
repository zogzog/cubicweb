# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""common web configuration for twisted/modpython instances

"""
__docformat__ = "restructuredtext en"
_ = unicode

import os
from os.path import join, exists, split

from logilab.common.decorators import cached

from cubicweb.toolsutils import read_config
from cubicweb.cwconfig import CubicWebConfiguration, register_persistent_options, merge_options


register_persistent_options( (
    # site-wide only web ui configuration
    ('site-title',
     {'type' : 'string', 'default': 'unset title',
      'help': _('site title'),
      'sitewide': True, 'group': 'ui',
      }),
    ('main-template',
     {'type' : 'string', 'default': 'main-template',
      'help': _('id of main template used to render pages'),
      'sitewide': True, 'group': 'ui',
      }),
    # user web ui configuration
    ('fckeditor',
     {'type' : 'yn', 'default': True,
      'help': _('should html fields being edited using fckeditor (a HTML '
                'WYSIWYG editor).  You should also select text/html as default '
                'text format to actually get fckeditor.'),
      'group': 'ui',
      }),
    # navigation configuration
    ('page-size',
     {'type' : 'int', 'default': 40,
      'help': _('maximum number of objects displayed by page of results'),
      'group': 'navigation',
      }),
    ('related-limit',
     {'type' : 'int', 'default': 8,
      'help': _('maximum number of related entities to display in the primary '
                'view'),
      'group': 'navigation',
      }),
    ('combobox-limit',
     {'type' : 'int', 'default': 20,
      'help': _('maximum number of entities to display in related combo box'),
      'group': 'navigation',
      }),

    ))


class WebConfiguration(CubicWebConfiguration):
    """the WebConfiguration is a singleton object handling instance's
    configuration and preferences
    """
    cubicweb_appobject_path = CubicWebConfiguration.cubicweb_appobject_path | set(['web/views'])
    cube_appobject_path = CubicWebConfiguration.cube_appobject_path | set(['views'])

    options = merge_options(CubicWebConfiguration.options + (
        ('anonymous-user',
         {'type' : 'string',
          'default': None,
          'help': 'login of the CubicWeb user account to use for anonymous user (if you want to allow anonymous)',
          'group': 'main', 'level': 1,
          }),
        ('anonymous-password',
         {'type' : 'string',
          'default': None,
          'help': 'password of the CubicWeb user account to use for anonymous user, '
          'if anonymous-user is set',
          'group': 'main', 'level': 1,
          }),
        ('query-log-file',
         {'type' : 'string',
          'default': None,
          'help': 'web instance query log file',
          'group': 'main', 'level': 2,
          }),
        # web configuration
        ('https-url',
         {'type' : 'string',
          'default': None,
          'help': 'web server root url on https. By specifying this option your '\
          'site can be available as an http and https site. Authenticated users '\
          'will in this case be authenticated and once done navigate through the '\
          'https site. IMPORTANTE NOTE: to do this work, you should have your '\
          'apache redirection include "https" as base url path so cubicweb can '\
          'differentiate between http vs https access. For instance: \n'\
          'RewriteRule ^/demo/(.*) http://127.0.0.1:8080/https/$1 [L,P]\n'\
          'where the cubicweb web server is listening on port 8080.',
          'group': 'main', 'level': 2,
          }),
        ('auth-mode',
         {'type' : 'choice',
          'choices' : ('cookie', 'http'),
          'default': 'cookie',
          'help': 'authentication mode (cookie / http)',
          'group': 'web', 'level': 1,
          }),
        ('realm',
         {'type' : 'string',
          'default': 'cubicweb',
          'help': 'realm to use on HTTP authentication mode',
          'group': 'web', 'level': 2,
          }),
        ('http-session-time',
         {'type' : 'time',
          'default': 0,
          'help': "duration of the cookie used to store session identifier. "
          "If 0, the cookie will expire when the user exist its browser. "
          "Should be 0 or greater than repository\'s session-time.",
          'group': 'web', 'inputlevel': 2,
          }),
        ('cleanup-session-time',
         {'type' : 'time',
          'default': '24h',
          'help': 'duration of inactivity after which a connection '
          'will be closed, to limit memory consumption (avoid sessions that '
          'never expire and cause memory leak when http-session-time is 0). '
          'So even if http-session-time is 0 and the user don\'t close his '
          'browser, he will have to reauthenticate after this time of '
          'inactivity. Default to 24h.',
          'group': 'web', 'level': 2,
          }),
        ('cleanup-anonymous-session-time',
         {'type' : 'time',
          'default': '5min',
          'help': 'Same as cleanup-session-time but specific to anonymous '
          'sessions. You can have a much smaller timeout here since it will be '
          'transparent to the user. Default to 5min.',
          'group': 'web', 'level': 2,
          }),
        ('force-html-content-type',
         {'type' : 'yn',
          'default': False,
          'help': 'force text/html content type for your html pages instead of cubicweb user-agent based'\
          'deduction of an appropriate content type',
          'group': 'web', 'level': 2,
          }),
        ('embed-allowed',
         {'type' : 'regexp',
          'default': None,
          'help': 'regular expression matching URLs that may be embeded. \
leave it blank if you don\'t want the embedding feature, or set it to ".*" \
if you want to allow everything',
          'group': 'web', 'level': 1,
          }),
        ('submit-mail',
         {'type' : 'string',
          'default': None,
          'help': ('Mail used as recipient to report bug in this instance, '
                   'if you want this feature on'),
          'group': 'web', 'level': 2,
          }),

        ('language-negociation',
         {'type' : 'yn',
          'default': True,
          'help': 'use Accept-Language http header to try to set user '\
          'interface\'s language according to browser defined preferences',
          'group': 'web', 'level': 2,
          }),

        ('print-traceback',
         {'type' : 'yn',
          'default': CubicWebConfiguration.mode != 'system',
          'help': 'print the traceback on the error page when an error occured',
          'group': 'web', 'level': 2,
          }),

        ('captcha-font-file',
         {'type' : 'string',
          'default': join(CubicWebConfiguration.shared_dir(), 'data', 'porkys.ttf'),
          'help': 'True type font to use for captcha image generation (you \
must have the python imaging library installed to use captcha)',
          'group': 'web', 'level': 2,
          }),
        ('captcha-font-size',
         {'type' : 'int',
          'default': 25,
          'help': 'Font size to use for captcha image generation (you must \
have the python imaging library installed to use captcha)',
          'group': 'web', 'level': 2,
          }),

        ))

    def fckeditor_installed(self):
        return exists(self.ext_resources['FCKEDITOR_PATH'])

    def eproperty_definitions(self):
        for key, pdef in super(WebConfiguration, self).eproperty_definitions():
            if key == 'ui.fckeditor' and not self.fckeditor_installed():
                continue
            yield key, pdef

    # method used to connect to the repository: 'inmemory' / 'pyro'
    # Pyro repository by default
    repo_method = 'pyro'

    # don't use @cached: we want to be able to disable it while this must still
    # be cached
    def repository(self, vreg=None):
        """return the instance's repository object"""
        try:
            return self.__repo
        except AttributeError:
            from cubicweb.dbapi import get_repository
            if self.repo_method == 'inmemory':
                repo = get_repository('inmemory', vreg=vreg, config=self)
            else:
                repo = get_repository('pyro', self['pyro-instance-id'],
                                      config=self)
            self.__repo = repo
            return repo

    def vc_config(self):
        return self.repository().get_versions()

    # mapping to external resources (id -> path) (`external_resources` file) ##
    ext_resources = {
        'FAVICON':  'DATADIR/favicon.ico',
        'LOGO':     'DATADIR/logo.png',
        'RSS_LOGO': 'DATADIR/rss.png',
        'HELP':     'DATADIR/help.png',
        'CALENDAR_ICON': 'DATADIR/calendar.gif',
        'SEARCH_GO':'DATADIR/go.png',

        'FCKEDITOR_PATH':  '/usr/share/fckeditor/',

        'IE_STYLESHEETS':    ['DATADIR/cubicweb.ie.css'],
        'STYLESHEETS':       ['DATADIR/cubicweb.css'],
        'STYLESHEETS_PRINT': ['DATADIR/cubicweb.print.css'],

        'JAVASCRIPTS':       ['DATADIR/jquery.js',
                              'DATADIR/jquery.corner.js',
                              'DATADIR/jquery.json.js',
                              'DATADIR/cubicweb.compat.js',
                              'DATADIR/cubicweb.python.js',
                              'DATADIR/cubicweb.htmlhelpers.js'],
        }


    def anonymous_user(self):
        """return a login and password to use for anonymous users. None
        may be returned for both if anonymous connections are not allowed
        """
        try:
            user = self['anonymous-user']
            passwd = self['anonymous-password']
        except KeyError:
            user, passwd = None, None
        if user is not None:
            user = unicode(user)
        return user, passwd

    def has_resource(self, rid):
        """return true if an external resource is defined"""
        return bool(self.ext_resources.get(rid))

    @cached
    def locate_resource(self, rid):
        """return the directory where the given resource may be found"""
        return self._fs_locate(rid, 'data')

    @cached
    def locate_doc_file(self, fname):
        """return the directory where the given resource may be found"""
        return self._fs_locate(fname, 'wdoc')

    def _fs_locate(self, rid, rdirectory):
        """return the directory where the given resource may be found"""
        path = [self.apphome] + self.cubes_path() + [join(self.shared_dir())]
        for directory in path:
            if exists(join(directory, rdirectory, rid)):
                return join(directory, rdirectory)

    def locate_all_files(self, rid, rdirectory='wdoc'):
        """return all files corresponding to the given resource"""
        path = [self.apphome] + self.cubes_path() + [join(self.shared_dir())]
        for directory in path:
            fpath = join(directory, rdirectory, rid)
            if exists(fpath):
                yield join(fpath)

    def load_configuration(self):
        """load instance's configuration files"""
        super(WebConfiguration, self).load_configuration()
        # load external resources definition
        self._build_ext_resources()
        self._init_base_url()

    def _init_base_url(self):
        # normalize base url(s)
        baseurl = self['base-url'] or self.default_base_url()
        if baseurl and baseurl[-1] != '/':
            baseurl += '/'
        if not self.repairing:
            self.global_set_option('base-url', baseurl)
        httpsurl = self['https-url']
        if httpsurl and httpsurl[-1] != '/':
            httpsurl += '/'
            if not self.repairing:
                self.global_set_option('https-url', httpsurl)

    def _build_ext_resources(self):
        libresourcesfile = join(self.shared_dir(), 'data', 'external_resources')
        self.ext_resources.update(read_config(libresourcesfile))
        for path in reversed([self.apphome] + self.cubes_path()):
            resourcesfile = join(path, 'data', 'external_resources')
            if exists(resourcesfile):
                self.debug('loading %s', resourcesfile)
                self.ext_resources.update(read_config(resourcesfile))
        resourcesfile = join(self.apphome, 'external_resources')
        if exists(resourcesfile):
            self.debug('loading %s', resourcesfile)
            self.ext_resources.update(read_config(resourcesfile))
        for resource in ('STYLESHEETS', 'STYLESHEETS_PRINT',
                         'IE_STYLESHEETS', 'JAVASCRIPTS'):
            val = self.ext_resources[resource]
            if isinstance(val, str):
                files = [w.strip() for w in val.split(',') if w.strip()]
                self.ext_resources[resource] = files

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
            os.makedirs(staticdir)
        return file(join(staticdir, filename), mode)

    def static_file_add(self, rpath, data):
        stream = self.static_file_open(rpath)
        stream.write(data)
        stream.close()

    def static_file_del(self, rpath):
        if self.static_file_exists(rpath):
            os.remove(join(self.static_directory, rpath))
