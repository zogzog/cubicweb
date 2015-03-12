# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""additional cubicweb-ctl commands and command handlers for cubicweb and
cubicweb's cubes development
"""

__docformat__ = "restructuredtext en"

# *ctl module should limit the number of import to be imported as quickly as
# possible (for cubicweb-ctl reactivity, necessary for instance for usable bash
# completion). So import locally in command helpers.
import sys
from datetime import datetime
from os import mkdir, chdir, path as osp
from warnings import warn

from logilab.common import STD_BLACKLIST

from cubicweb.__pkginfo__ import version as cubicwebversion
from cubicweb import CW_SOFTWARE_ROOT as BASEDIR, BadCommandUsage, ExecutionError
from cubicweb.cwctl import CWCTL
from cubicweb.cwconfig import CubicWebNoAppConfiguration
from cubicweb.toolsutils import (SKEL_EXCLUDE, Command, copy_skeleton,
                                 underline_title)
from cubicweb.web.webconfig import WebConfiguration
from cubicweb.server.serverconfig import ServerConfiguration


class DevConfiguration(ServerConfiguration, WebConfiguration):
    """dummy config to get full library schema and appobjects for
    a cube or for cubicweb (without a home)
    """
    creating = True
    cleanup_unused_appobjects = False

    cubicweb_appobject_path = (ServerConfiguration.cubicweb_appobject_path
                               | WebConfiguration.cubicweb_appobject_path)
    cube_appobject_path = (ServerConfiguration.cube_appobject_path
                           | WebConfiguration.cube_appobject_path)

    def __init__(self, *cubes):
        super(DevConfiguration, self).__init__(cubes and cubes[0] or None)
        if cubes:
            self._cubes = self.reorder_cubes(
                self.expand_cubes(cubes, with_recommends=True))
            self.load_site_cubicweb()
        else:
            self._cubes = ()

    @property
    def apphome(self):
        return None

    def available_languages(self):
        return self.cw_languages()

    def main_config_file(self):
        return None
    def init_log(self):
        pass
    def load_configuration(self):
        pass
    def default_log_file(self):
        return None


def cleanup_sys_modules(config):
    # cleanup sys.modules, required when we're updating multiple cubes
    for name, mod in sys.modules.items():
        if mod is None:
            # duh ? logilab.common.os for instance
            del sys.modules[name]
            continue
        if not hasattr(mod, '__file__'):
            continue
        if mod.__file__ is None:
            # odd/rare but real
            continue
        for path in config.appobjects_path():
            if mod.__file__.startswith(path):
                del sys.modules[name]
                break

def generate_schema_pot(w, cubedir=None):
    """generate a pot file with schema specific i18n messages

    notice that relation definitions description and static vocabulary
    should be marked using '_' and extracted using xgettext
    """
    from cubicweb.cwvreg import CWRegistryStore
    if cubedir:
        cube = osp.split(cubedir)[-1]
        config = DevConfiguration(cube)
        depcubes = list(config._cubes)
        depcubes.remove(cube)
        libconfig = DevConfiguration(*depcubes)
    else:
        config = DevConfiguration()
        cube = libconfig = None
    cleanup_sys_modules(config)
    schema = config.load_schema(remove_unused_rtypes=False)
    vreg = CWRegistryStore(config)
    # set_schema triggers objects registrations
    vreg.set_schema(schema)
    w(DEFAULT_POT_HEAD)
    _generate_schema_pot(w, vreg, schema, libconfig=libconfig)


def _generate_schema_pot(w, vreg, schema, libconfig=None):
    from cubicweb.i18n import add_msg
    from cubicweb.schema import NO_I18NCONTEXT, CONSTRAINTS
    w('# schema pot file, generated on %s\n'
      % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    w('# \n')
    w('# singular and plural forms for each entity type\n')
    w('\n')
    vregdone = set()
    afss = vreg['uicfg']['autoform_section']
    aiams = vreg['uicfg']['actionbox_appearsin_addmenu']
    if libconfig is not None:
        # processing a cube, libconfig being a config with all its dependencies
        # (cubicweb incl.)
        from cubicweb.cwvreg import CWRegistryStore
        libschema = libconfig.load_schema(remove_unused_rtypes=False)
        cleanup_sys_modules(libconfig)
        libvreg = CWRegistryStore(libconfig)
        libvreg.set_schema(libschema) # trigger objects registration
        libafss = libvreg['uicfg']['autoform_section']
        libaiams = libvreg['uicfg']['actionbox_appearsin_addmenu']
        # prefill vregdone set
        list(_iter_vreg_objids(libvreg, vregdone))

        def is_in_lib(rtags, eschema, rschema, role, tschema, predicate=bool):
            return any(predicate(rtag.etype_get(eschema, rschema, role, tschema))
                       for rtag in rtags)
    else:
        # processing cubicweb itself
        libschema = {}
        for cstrtype in CONSTRAINTS:
            add_msg(w, cstrtype)
        libafss = libaiams = None
        is_in_lib = lambda *args: False
    done = set()
    for eschema in sorted(schema.entities()):
        if eschema.type in libschema:
            done.add(eschema.description)
    for eschema in sorted(schema.entities()):
        etype = eschema.type
        if etype not in libschema:
            add_msg(w, etype)
            add_msg(w, '%s_plural' % etype)
            if not eschema.final:
                add_msg(w, 'This %s:' % etype)
                add_msg(w, 'New %s' % etype)
                add_msg(w, 'add a %s' % etype) # AddNewAction
                if libconfig is not None:  # processing a cube
                    # As of 3.20.3 we no longer use it, but keeping this string
                    # allows developers to run i18ncube with new cubicweb and still
                    # have the right translations at runtime for older versions
                    add_msg(w, 'This %s' % etype)
            if eschema.description and not eschema.description in done:
                done.add(eschema.description)
                add_msg(w, eschema.description)
        if eschema.final:
            continue
        for rschema, targetschemas, role in eschema.relation_definitions(True):
            if rschema.final:
                continue
            for tschema in targetschemas:

                for afs in afss:
                    fsections = afs.etype_get(eschema, rschema, role, tschema)
                    if 'main_inlined' in fsections and not \
                            is_in_lib(libafss, eschema, rschema, role, tschema,
                                      lambda x: 'main_inlined' in x):
                        add_msg(w, 'add a %s' % tschema,
                                'inlined:%s.%s.%s' % (etype, rschema, role))
                        add_msg(w, str(tschema),
                                'inlined:%s.%s.%s' % (etype, rschema, role))
                        break

                for aiam in aiams:
                    if aiam.etype_get(eschema, rschema, role, tschema) and not \
                            is_in_lib(libaiams, eschema, rschema, role, tschema):
                        if role == 'subject':
                            label = 'add %s %s %s %s' % (eschema, rschema,
                                                         tschema, role)
                            label2 = "creating %s (%s %%(linkto)s %s %s)" % (
                                tschema, eschema, rschema, tschema)
                        else:
                            label = 'add %s %s %s %s' % (tschema, rschema,
                                                         eschema, role)
                            label2 = "creating %s (%s %s %s %%(linkto)s)" % (
                                tschema, tschema, rschema, eschema)
                        add_msg(w, label)
                        add_msg(w, label2)
                        break
            # XXX also generate "creating ...' messages for actions in the
            # addrelated submenu
    w('# subject and object forms for each relation type\n')
    w('# (no object form for final or symmetric relation types)\n')
    w('\n')
    for rschema in sorted(schema.relations()):
        if rschema.type in libschema:
            done.add(rschema.type)
            done.add(rschema.description)
    for rschema in sorted(schema.relations()):
        rtype = rschema.type
        if rtype not in libschema:
            # bw compat, necessary until all translation of relation are done
            # properly...
            add_msg(w, rtype)
            done.add(rtype)
            if rschema.description and rschema.description not in done:
                add_msg(w, rschema.description)
            done.add(rschema.description)
            librschema = None
        else:
            librschema = libschema.rschema(rtype)
        # add context information only for non-metadata rtypes
        if rschema not in NO_I18NCONTEXT:
            libsubjects = librschema and librschema.subjects() or ()
            for subjschema in rschema.subjects():
                if not subjschema in libsubjects:
                    add_msg(w, rtype, subjschema.type)
        if not (rschema.final or rschema.symmetric):
            if rschema not in NO_I18NCONTEXT:
                libobjects = librschema and librschema.objects() or ()
                for objschema in rschema.objects():
                    if not objschema in libobjects:
                        add_msg(w, '%s_object' % rtype, objschema.type)
            if rtype not in libschema:
                # bw compat, necessary until all translation of relation are
                # done properly...
                add_msg(w, '%s_object' % rtype)
        for rdef in rschema.rdefs.itervalues():
            if not rdef.description or rdef.description in done:
                continue
            if (librschema is None or
                (rdef.subject, rdef.object) not in librschema.rdefs or
                librschema.rdefs[(rdef.subject, rdef.object)].description != rdef.description):
                add_msg(w, rdef.description)
            done.add(rdef.description)
    for objid in _iter_vreg_objids(vreg, vregdone):
        add_msg(w, '%s_description' % objid)
        add_msg(w, objid)


def _iter_vreg_objids(vreg, done):
    for reg, objdict in vreg.items():
        if reg in ('boxes', 'contentnavigation'):
            continue
        for objects in objdict.itervalues():
            for obj in objects:
                objid = '%s_%s' % (reg, obj.__regid__)
                if objid in done:
                    break
                pdefs = getattr(obj, 'cw_property_defs', {})
                if pdefs:
                    yield objid
                    done.add(objid)
                    break


DEFAULT_POT_HEAD = r'''msgid ""
msgstr ""
"Project-Id-Version: cubicweb %s\n"
"PO-Revision-Date: 2008-03-28 18:14+0100\n"
"Last-Translator: Logilab Team <contact@logilab.fr>\n"
"Language-Team: fr <contact@logilab.fr>\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Generated-By: cubicweb-devtools\n"
"Plural-Forms: nplurals=2; plural=(n > 1);\n"

''' % cubicwebversion


class UpdateCubicWebCatalogCommand(Command):
    """Update i18n catalogs for cubicweb library.

    It will regenerate cubicweb/i18n/xx.po files. You'll have then to edit those
    files to add translations of newly added messages.
    """
    name = 'i18ncubicweb'
    min_args = max_args = 0

    def run(self, args):
        """run the command with its specific arguments"""
        import shutil
        import tempfile
        import yams
        from logilab.common.fileutils import ensure_fs_mode
        from logilab.common.shellutils import globfind, find, rm
        from logilab.common.modutils import get_module_files
        from cubicweb.i18n import extract_from_tal, execute2
        tempdir = tempfile.mkdtemp(prefix='cw-')
        cwi18ndir = WebConfiguration.i18n_lib_dir()
        print '-> extract messages:',
        print 'schema',
        schemapot = osp.join(tempdir, 'schema.pot')
        potfiles = [schemapot]
        potfiles.append(schemapot)
        # explicit close necessary else the file may not be yet flushed when
        # we'll using it below
        schemapotstream = file(schemapot, 'w')
        generate_schema_pot(schemapotstream.write, cubedir=None)
        schemapotstream.close()
        print 'TAL',
        tali18nfile = osp.join(tempdir, 'tali18n.py')
        extract_from_tal(find(osp.join(BASEDIR, 'web'), ('.py', '.pt')),
                         tali18nfile)
        print '-> generate .pot files.'
        pyfiles = get_module_files(BASEDIR)
        pyfiles += globfind(osp.join(BASEDIR, 'misc', 'migration'), '*.py')
        schemafiles = globfind(osp.join(BASEDIR, 'schemas'), '*.py')
        jsfiles = globfind(osp.join(BASEDIR, 'web'), 'cub*.js')
        for id, files, lang in [('pycubicweb', pyfiles, None),
                                ('schemadescr', schemafiles, None),
                                ('yams', get_module_files(yams.__path__[0]), None),
                                ('tal', [tali18nfile], None),
                                ('js', jsfiles, 'java'),
                                ]:
            potfile = osp.join(tempdir, '%s.pot' % id)
            cmd = ['xgettext', '--no-location', '--omit-header', '-k_']
            if lang is not None:
                cmd.extend(['-L', lang])
            cmd.extend(['-o', potfile])
            cmd.extend(files)
            execute2(cmd)
            if osp.exists(potfile):
                potfiles.append(potfile)
            else:
                print '-> WARNING: %s file was not generated' % potfile
        print '-> merging %i .pot files' % len(potfiles)
        cubicwebpot = osp.join(tempdir, 'cubicweb.pot')
        cmd = ['msgcat', '-o', cubicwebpot] + potfiles
        execute2(cmd)
        print '-> merging main pot file with existing translations.'
        chdir(cwi18ndir)
        toedit = []
        for lang in CubicWebNoAppConfiguration.cw_languages():
            target = '%s.po' % lang
            cmd = ['msgmerge', '-N', '--sort-output', '-o',
                   target+'new', target, cubicwebpot]
            execute2(cmd)
            ensure_fs_mode(target)
            shutil.move('%snew' % target, target)
            toedit.append(osp.abspath(target))
        # cleanup
        rm(tempdir)
        # instructions pour la suite
        print '-> regenerated CubicWeb\'s .po catalogs.'
        print '\nYou can now edit the following files:'
        print '* ' + '\n* '.join(toedit)
        print 'when you are done, run "cubicweb-ctl i18ncube yourcube".'


class UpdateCubeCatalogCommand(Command):
    """Update i18n catalogs for cubes. If no cube is specified, update
    catalogs of all registered cubes.
    """
    name = 'i18ncube'
    arguments = '[<cube>...]'

    def run(self, args):
        """run the command with its specific arguments"""
        if args:
            cubes = [DevConfiguration.cube_dir(cube) for cube in args]
        else:
            cubes = [DevConfiguration.cube_dir(cube)
                     for cube in DevConfiguration.available_cubes()]
            cubes = [cubepath for cubepath in cubes
                     if osp.exists(osp.join(cubepath, 'i18n'))]
        if not update_cubes_catalogs(cubes):
            raise ExecutionError("update cubes i18n catalog failed")


def update_cubes_catalogs(cubes):
    from subprocess import CalledProcessError
    for cubedir in cubes:
        if not osp.isdir(cubedir):
            print '-> ignoring %s that is not a directory.' % cubedir
            continue
        try:
            toedit = update_cube_catalogs(cubedir)
        except CalledProcessError as exc:
            print '\n*** error while updating catalogs for cube', cubedir
            print 'cmd:\n%s' % exc.cmd
            print 'stdout:\n%s\nstderr:\n%s' % exc.data
        except Exception:
            import traceback
            traceback.print_exc()
            print '*** error while updating catalogs for cube', cubedir
            return False
        else:
            # instructions pour la suite
            if toedit:
                print '-> regenerated .po catalogs for cube %s.' % cubedir
                print '\nYou can now edit the following files:'
                print '* ' + '\n* '.join(toedit)
                print ('When you are done, run "cubicweb-ctl i18ninstance '
                       '<yourinstance>" to see changes in your instances.')
            return True

def update_cube_catalogs(cubedir):
    import shutil
    import tempfile
    from logilab.common.fileutils import ensure_fs_mode
    from logilab.common.shellutils import find, rm
    from cubicweb.i18n import extract_from_tal, execute2
    cube = osp.basename(osp.normpath(cubedir))
    tempdir = tempfile.mkdtemp()
    print underline_title('Updating i18n catalogs for cube %s' % cube)
    chdir(cubedir)
    if osp.exists(osp.join('i18n', 'entities.pot')):
        warn('entities.pot is deprecated, rename file to static-messages.pot (%s)'
             % osp.join('i18n', 'entities.pot'), DeprecationWarning)
        potfiles = [osp.join('i18n', 'entities.pot')]
    elif osp.exists(osp.join('i18n', 'static-messages.pot')):
        potfiles = [osp.join('i18n', 'static-messages.pot')]
    else:
        potfiles = []
    print '-> extracting messages:',
    print 'schema',
    schemapot = osp.join(tempdir, 'schema.pot')
    potfiles.append(schemapot)
    # explicit close necessary else the file may not be yet flushed when
    # we'll using it below
    schemapotstream = file(schemapot, 'w')
    generate_schema_pot(schemapotstream.write, cubedir)
    schemapotstream.close()
    print 'TAL',
    tali18nfile = osp.join(tempdir, 'tali18n.py')
    ptfiles = find('.', ('.py', '.pt'), blacklist=STD_BLACKLIST+('test',))
    extract_from_tal(ptfiles, tali18nfile)
    print 'Javascript'
    jsfiles =  [jsfile for jsfile in find('.', '.js')
                if osp.basename(jsfile).startswith('cub')]
    if jsfiles:
        tmppotfile = osp.join(tempdir, 'js.pot')
        cmd = ['xgettext', '--no-location', '--omit-header', '-k_', '-L', 'java',
               '--from-code=utf-8', '-o', tmppotfile] + jsfiles
        execute2(cmd)
        # no pot file created if there are no string to translate
        if osp.exists(tmppotfile):
            potfiles.append(tmppotfile)
    print '-> creating cube-specific catalog'
    tmppotfile = osp.join(tempdir, 'generated.pot')
    cubefiles = find('.', '.py', blacklist=STD_BLACKLIST+('test',))
    cubefiles.append(tali18nfile)
    cmd = ['xgettext', '--no-location', '--omit-header', '-k_', '-o', tmppotfile]
    cmd.extend(cubefiles)
    execute2(cmd)
    if osp.exists(tmppotfile): # doesn't exists of no translation string found
        potfiles.append(tmppotfile)
    potfile = osp.join(tempdir, 'cube.pot')
    print '-> merging %i .pot files' % len(potfiles)
    cmd = ['msgcat', '-o', potfile]
    cmd.extend(potfiles)
    execute2(cmd)
    if not osp.exists(potfile):
        print 'no message catalog for cube', cube, 'nothing to translate'
        # cleanup
        rm(tempdir)
        return ()
    print '-> merging main pot file with existing translations:',
    chdir('i18n')
    toedit = []
    for lang in CubicWebNoAppConfiguration.cw_languages():
        print lang,
        cubepo = '%s.po' % lang
        if not osp.exists(cubepo):
            shutil.copy(potfile, cubepo)
        else:
            cmd = ['msgmerge','-N','-s','-o', cubepo+'new', cubepo, potfile]
            execute2(cmd)
            ensure_fs_mode(cubepo)
            shutil.move('%snew' % cubepo, cubepo)
        toedit.append(osp.abspath(cubepo))
    print
    # cleanup
    rm(tempdir)
    return toedit


# XXX totally broken, fix it
# class LiveServerCommand(Command):
#     """Run a server from within a cube directory.
#     """
#     name = 'live-server'
#     arguments = ''
#     options = ()

#     def run(self, args):
#         """run the command with its specific arguments"""
#         from cubicweb.devtools.livetest import runserver
#         runserver()


class NewCubeCommand(Command):
    """Create a new cube.

    <cubename>
      the name of the new cube. It should be a valid python module name.
    """
    name = 'newcube'
    arguments = '<cubename>'
    min_args = max_args = 1
    options = (
        ("layout",
         {'short': 'L', 'type' : 'choice', 'metavar': '<cube layout>',
          'default': 'simple', 'choices': ('simple', 'full'),
          'help': 'cube layout. You\'ll get a minimal cube with the "simple" \
layout, and a full featured cube with "full" layout.',
          }
         ),
        ("directory",
         {'short': 'd', 'type' : 'string', 'metavar': '<cubes directory>',
          'help': 'directory where the new cube should be created',
          }
         ),
        ("verbose",
         {'short': 'v', 'type' : 'yn', 'metavar': '<verbose>',
          'default': 'n',
          'help': 'verbose mode: will ask all possible configuration questions',
          }
         ),
        ("author",
         {'short': 'a', 'type' : 'string', 'metavar': '<author>',
          'default': 'LOGILAB S.A. (Paris, FRANCE)',
          'help': 'cube author',
          }
         ),
        ("author-email",
         {'short': 'e', 'type' : 'string', 'metavar': '<email>',
          'default': 'contact@logilab.fr',
          'help': 'cube author\'s email',
          }
         ),
        ("author-web-site",
         {'short': 'w', 'type' : 'string', 'metavar': '<web site>',
          'default': 'http://www.logilab.fr',
          'help': 'cube author\'s web site',
          }
         ),
        ("license",
         {'short': 'l', 'type' : 'choice', 'metavar': '<license>',
          'default': 'LGPL', 'choices': ('GPL', 'LGPL', ''),
          'help': 'cube license',
          }
         ),
        )

    LICENSES = {
        'LGPL': '''\
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
''',

        'GPL': '''\
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2.1 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
''',
        '': '# INSERT LICENSE HERE'
        }

    def run(self, args):
        import re
        from logilab.common.shellutils import ASK
        cubename = args[0]
        if not re.match('[_A-Za-z][_A-Za-z0-9]*$', cubename):
            raise BadCommandUsage(
                'cube name must be a valid python module name')
        verbose = self.get('verbose')
        cubesdir = self.get('directory')
        if not cubesdir:
            cubespath = ServerConfiguration.cubes_search_path()
            if len(cubespath) > 1:
                raise BadCommandUsage(
                    "can't guess directory where to put the new cube."
                    " Please specify it using the --directory option")
            cubesdir = cubespath[0]
        if not osp.isdir(cubesdir):
            print "-> creating cubes directory", cubesdir
            try:
                mkdir(cubesdir)
            except OSError as err:
                self.fail("failed to create directory %r\n(%s)"
                          % (cubesdir, err))
        cubedir = osp.join(cubesdir, cubename)
        if osp.exists(cubedir):
            self.fail("%s already exists!" % cubedir)
        skeldir = osp.join(BASEDIR, 'skeleton')
        default_name = 'cubicweb-%s' % cubename.lower().replace('_', '-')
        if verbose:
            distname = raw_input('Debian name for your cube ? [%s]): '
                                 % default_name).strip()
            if not distname:
                distname = default_name
            elif not distname.startswith('cubicweb-'):
                if ASK.confirm('Do you mean cubicweb-%s ?' % distname):
                    distname = 'cubicweb-' + distname
        else:
            distname = default_name
        if not re.match('[a-z][-a-z0-9]*$', distname):
            raise BadCommandUsage(
                'cube distname should be a valid debian package name')
        longdesc = shortdesc = raw_input(
            'Enter a short description for your cube: ')
        if verbose:
            longdesc = raw_input(
                'Enter a long description (leave empty to reuse the short one): ')
        dependencies = {'cubicweb': '>= %s' % cubicwebversion}
        if verbose:
            dependencies.update(self._ask_for_dependencies())
        context = {'cubename' : cubename,
                   'distname' : distname,
                   'shortdesc' : shortdesc,
                   'longdesc' : longdesc or shortdesc,
                   'dependencies' : dependencies,
                   'version'  : cubicwebversion,
                   'year'  : str(datetime.now().year),
                   'author': self['author'],
                   'author-email': self['author-email'],
                   'author-web-site': self['author-web-site'],
                   'license': self['license'],
                   'long-license': self.LICENSES[self['license']],
                   }
        exclude = SKEL_EXCLUDE
        if self['layout'] == 'simple':
            exclude += ('sobjects.py*', 'precreate.py*', 'realdb_test*',
                        'cubes.*', 'uiprops.py*')
        copy_skeleton(skeldir, cubedir, context, exclude=exclude)

    def _ask_for_dependencies(self):
        from logilab.common.shellutils import ASK
        from logilab.common.textutils import splitstrip
        depcubes = []
        for cube in ServerConfiguration.available_cubes():
            answer = ASK.ask("Depends on cube %s? " % cube,
                             ('N','y','skip','type'), 'N')
            if answer == 'y':
                depcubes.append(cube)
            if answer == 'type':
                depcubes = splitstrip(raw_input('type dependencies: '))
                break
            elif answer == 'skip':
                break
        return dict(('cubicweb-' + cube, ServerConfiguration.cube_version(cube))
                    for cube in depcubes)


class ExamineLogCommand(Command):
    """Examine a rql log file.

    Will print out the following table

      Percentage; Cumulative Time (clock); Cumulative Time (CPU); Occurences; Query

    sorted by descending cumulative time (clock). Time are expressed in seconds.

    Chances are the lines at the top are the ones that will bring the higher
    benefit after optimisation. Start there.
    """
    arguments = 'rql.log'
    name = 'exlog'
    options = ()

    def run(self, args):
        import re
        requests = {}
        for filepath in args:
            try:
                stream = file(filepath)
            except OSError as ex:
                raise BadCommandUsage("can't open rql log file %s: %s"
                                      % (filepath, ex))
            for lineno, line in enumerate(stream):
                if not ' WHERE ' in line:
                    continue
                try:
                    rql, time = line.split('--')
                    rql = re.sub("(\'\w+': \d*)", '', rql)
                    if '{' in rql:
                        rql = rql[:rql.index('{')]
                    req = requests.setdefault(rql, [])
                    time.strip()
                    chunks = time.split()
                    clocktime = float(chunks[0][1:])
                    cputime = float(chunks[-3])
                    req.append( (clocktime, cputime) )
                except Exception as exc:
                    sys.stderr.write('Line %s: %s (%s)\n' % (lineno, exc, line))
        stat = []
        for rql, times in requests.iteritems():
            stat.append( (sum(time[0] for time in times),
                          sum(time[1] for time in times),
                          len(times), rql) )
        stat.sort()
        stat.reverse()
        total_time = sum(clocktime for clocktime, cputime, occ, rql in stat) * 0.01
        print 'Percentage;Cumulative Time (clock);Cumulative Time (CPU);Occurences;Query'
        for clocktime, cputime, occ, rql in stat:
            print '%.2f;%.2f;%.2f;%s;%s' % (clocktime/total_time, clocktime,
                                            cputime, occ, rql)


class GenerateSchema(Command):
    """Generate schema image for the given cube"""
    name = "schema"
    arguments = '<cube>'
    min_args = max_args = 1
    options = [
        ('output-file',
         {'type':'string', 'default': None,
          'metavar': '<file>', 'short':'o', 'help':'output image file',
          'input':False,
          }),
        ('viewer',
         {'type': 'string', 'default':None,
          'short': "d", 'metavar':'<cmd>',
          'help':'command use to view the generated file (empty for none)',
          }),
        ('show-meta',
         {'action': 'store_true', 'default':False,
          'short': "m", 'metavar': "<yN>",
          'help':'include meta and internal entities in schema',
          }),
        ('show-workflow',
         {'action': 'store_true', 'default':False,
          'short': "w", 'metavar': "<yN>",
          'help':'include workflow entities in schema',
          }),
        ('show-cw-user',
         {'action': 'store_true', 'default':False,
          'metavar': "<yN>",
          'help':'include cubicweb user entities in schema',
          }),
        ('exclude-type',
         {'type':'string', 'default':'',
          'short': "x", 'metavar': "<types>",
          'help':'coma separated list of entity types to remove from view',
          }),
        ('include-type',
         {'type':'string', 'default':'',
          'short': "i", 'metavar': "<types>",
          'help':'coma separated list of entity types to include in view',
          }),
        ('show-etype',
         {'type':'string', 'default':'',
          'metavar': '<etype>',
          'help':'show graph of this etype and its neighbours'
          }),
        ]

    def run(self, args):
        from subprocess import Popen
        from tempfile import NamedTemporaryFile
        from logilab.common.textutils import splitstrip
        from logilab.common.graph import GraphGenerator, DotBackend
        from yams import schema2dot as s2d, BASE_TYPES
        from cubicweb.schema import (META_RTYPES, SCHEMA_TYPES, SYSTEM_RTYPES,
                                     WORKFLOW_TYPES, INTERNAL_TYPES)
        cubes = splitstrip(args[0])
        dev_conf = DevConfiguration(*cubes)
        schema = dev_conf.load_schema()
        out, viewer = self['output-file'], self['viewer']
        if out is None:
            tmp_file = NamedTemporaryFile(suffix=".svg")
            out = tmp_file.name
        skiptypes = BASE_TYPES | SCHEMA_TYPES
        if not self['show-meta']:
            skiptypes |=  META_RTYPES | SYSTEM_RTYPES | INTERNAL_TYPES
        if not self['show-workflow']:
            skiptypes |= WORKFLOW_TYPES
        if not self['show-cw-user']:
            skiptypes |= set(('CWUser', 'CWGroup', 'EmailAddress'))
        skiptypes |= set(self['exclude-type'].split(','))
        skiptypes -= set(self['include-type'].split(','))

        if not self['show-etype']:
            s2d.schema2dot(schema, out, skiptypes=skiptypes)
        else:
            etype = self['show-etype']
            visitor = s2d.OneHopESchemaVisitor(schema[etype], skiptypes=skiptypes)
            propshdlr = s2d.SchemaDotPropsHandler(visitor)
            backend = DotBackend('schema', 'BT',
                                 ratio='compress',size=None,
                                 renderer='dot',
                                 additionnal_param={'overlap' : 'false',
                                                    'splines' : 'true',
                                                    'sep' : '0.2'})
            generator = s2d.GraphGenerator(backend)
            generator.generate(visitor, propshdlr, out)

        if viewer:
            p = Popen((viewer, out))
            p.wait()


class GenerateQUnitHTML(Command):
    """Generate a QUnit html file to see test in your browser"""
    name = "qunit-html"
    arguments = '<test file> [<dependancy js file>...]'

    def run(self, args):
        from cubicweb.devtools.qunit import make_qunit_html
        print make_qunit_html(args[0], args[1:])

for cmdcls in (UpdateCubicWebCatalogCommand,
               UpdateCubeCatalogCommand,
               #LiveServerCommand,
               NewCubeCommand,
               ExamineLogCommand,
               GenerateSchema,
               GenerateQUnitHTML,
               ):
    CWCTL.register(cmdcls)
