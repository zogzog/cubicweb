"""additional cubicweb-ctl commands and command handlers for cubicweb and cubicweb's
cubes development

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
from datetime import datetime
from os import mkdir, chdir, getcwd
from os.path import join, exists, abspath, basename, normpath, split, isdir
from copy import deepcopy
from warnings import warn
from tempfile import NamedTemporaryFile
from subprocess import Popen

from logilab.common import STD_BLACKLIST
from logilab.common.modutils import get_module_files
from logilab.common.textutils import splitstrip
from logilab.common.shellutils import ASK
from logilab.common.clcommands import register_commands, pop_arg

from yams import schema2dot

from cubicweb.__pkginfo__ import version as cubicwebversion
from cubicweb import CW_SOFTWARE_ROOT as BASEDIR, BadCommandUsage
from cubicweb.toolsutils import Command, copy_skeleton, underline_title
from cubicweb.schema import CONSTRAINTS
from cubicweb.web.webconfig import WebConfiguration
from cubicweb.server.serverconfig import ServerConfiguration
from yams import BASE_TYPES
from cubicweb.schema import (META_RTYPES, SCHEMA_TYPES, SYSTEM_RTYPES,
                             WORKFLOW_TYPES, INTERNAL_TYPES)


class DevCubeConfiguration(ServerConfiguration, WebConfiguration):
    """dummy config to get full library schema and entities"""
    creating = True
    cubicweb_appobject_path = ServerConfiguration.cubicweb_appobject_path | WebConfiguration.cubicweb_appobject_path
    cube_appobject_path = ServerConfiguration.cube_appobject_path | WebConfiguration.cube_appobject_path

    def __init__(self, *cubes):
        super(DevCubeConfiguration, self).__init__(cubes[0])
        self._cubes = self.reorder_cubes(self.expand_cubes(cubes,
                                         with_recommends=True))

    @property
    def apphome(self):
        return None
    def main_config_file(self):
        return None
    def init_log(self, debug=None):
        pass
    def load_configuration(self):
        pass


class DevDepConfiguration(DevCubeConfiguration):
    """configuration to use to generate cubicweb po files or to use as "library" configuration
    to filter out message ids from cubicweb and dependencies of a cube
    """

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
        for path in config.vregistry_path():
            if mod.__file__.startswith(path):
                del sys.modules[name]
                break
    # fresh rtags
    from cubicweb import rtags
    from cubicweb.web import uicfg
    rtags.RTAGS[:] = []
    reload(uicfg)

def generate_schema_pot(w, cubedir=None):
    """generate a pot file with schema specific i18n messages

    notice that relation definitions description and static vocabulary
    should be marked using '_' and extracted using xgettext
    """
    from cubicweb.cwvreg import CubicWebVRegistry
    cube = cubedir and split(cubedir)[-1]
    libconfig = DevDepConfiguration(cube)
    libconfig.cleanup_interface_sobjects = False
    cleanup_sys_modules(libconfig)
    if cubedir:
        config = DevCubeConfiguration(cube)
        config.cleanup_interface_sobjects = False
    else:
        config = libconfig
        libconfig = None
    schema = config.load_schema(remove_unused_rtypes=False)
    vreg = CubicWebVRegistry(config)
    # set_schema triggers objects registrations
    vreg.set_schema(schema)
    w(DEFAULT_POT_HEAD)
    _generate_schema_pot(w, vreg, schema, libconfig=libconfig, cube=cube)


def _generate_schema_pot(w, vreg, schema, libconfig=None, cube=None):
    from cubicweb.i18n import add_msg
    from cubicweb.web import uicfg
    from cubicweb.schema import META_RTYPES, SYSTEM_RTYPES
    no_context_rtypes = META_RTYPES | SYSTEM_RTYPES
    w('# schema pot file, generated on %s\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    w('# \n')
    w('# singular and plural forms for each entity type\n')
    w('\n')
    vregdone = set()
    if libconfig is not None:
        from cubicweb.cwvreg import CubicWebVRegistry, clear_rtag_objects
        libschema = libconfig.load_schema(remove_unused_rtypes=False)
        afs = deepcopy(uicfg.autoform_section)
        appearsin_addmenu = deepcopy(uicfg.actionbox_appearsin_addmenu)
        clear_rtag_objects()
        cleanup_sys_modules(libconfig)
        libvreg = CubicWebVRegistry(libconfig)
        libvreg.set_schema(libschema) # trigger objects registration
        libafs = uicfg.autoform_section
        libappearsin_addmenu = uicfg.actionbox_appearsin_addmenu
        # prefill vregdone set
        list(_iter_vreg_objids(libvreg, vregdone))
    else:
        libschema = {}
        afs = uicfg.autoform_section
        appearsin_addmenu = uicfg.actionbox_appearsin_addmenu
        for cstrtype in CONSTRAINTS:
            add_msg(w, cstrtype)
    done = set()
    for eschema in sorted(schema.entities()):
        etype = eschema.type
        if etype not in libschema:
            add_msg(w, etype)
            add_msg(w, '%s_plural' % etype)
            if not eschema.final:
                add_msg(w, 'This %s' % etype)
                add_msg(w, 'New %s' % etype)
            if eschema.description and not eschema.description in done:
                done.add(eschema.description)
                add_msg(w, eschema.description)
        if eschema.final:
            continue
        for rschema, targetschemas, role in eschema.relation_definitions(True):
            if rschema.final:
                continue
            for tschema in targetschemas:
                fsections = afs.etype_get(eschema, rschema, role, tschema)
                if 'main_inlined' in fsections and \
                       (libconfig is None or not
                        'main_inlined' in libafs.etype_get(
                            eschema, rschema, role, tschema)):
                    add_msg(w, 'add a %s' % tschema,
                            'inlined:%s.%s.%s' % (etype, rschema, role))
                    add_msg(w, str(tschema),
                            'inlined:%s.%s.%s' % (etype, rschema, role))
                if appearsin_addmenu.etype_get(eschema, rschema, role, tschema) and \
                       (libconfig is None or not
                        libappearsin_addmenu.etype_get(eschema, rschema, role, tschema)):
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
            # XXX also generate "creating ...' messages for actions in the
            # addrelated submenu
    w('# subject and object forms for each relation type\n')
    w('# (no object form for final or symmetric relation types)\n')
    w('\n')
    for rschema in sorted(schema.relations()):
        rtype = rschema.type
        if rtype not in libschema:
            # bw compat, necessary until all translation of relation are done properly...
            add_msg(w, rtype)
            if rschema.description and rschema.description not in done:
                done.add(rschema.description)
                add_msg(w, rschema.description)
            done.add(rtype)
            librschema = None
        else:
            librschema = libschema.rschema(rtype)
        # add context information only for non-metadata rtypes
        if rschema not in no_context_rtypes:
            libsubjects = librschema and librschema.subjects() or ()
            for subjschema in rschema.subjects():
                if not subjschema in libsubjects:
                    add_msg(w, rtype, subjschema.type)
        if not (schema.rschema(rtype).final or rschema.symmetric):
            if rschema not in no_context_rtypes:
                libobjects = librschema and librschema.objects() or ()
                for objschema in rschema.objects():
                    if not objschema in libobjects:
                        add_msg(w, '%s_object' % rtype, objschema.type)
            if rtype not in libschema:
                # bw compat, necessary until all translation of relation are done properly...
                add_msg(w, '%s_object' % rtype)
    for objid in _iter_vreg_objids(vreg, vregdone):
        add_msg(w, '%s_description' % objid)
        add_msg(w, objid)


def _iter_vreg_objids(vreg, done, prefix=None):
    for reg, objdict in vreg.items():
        for objects in objdict.values():
            for obj in objects:
                objid = '%s_%s' % (reg, obj.__regid__)
                if objid in done:
                    break
                try: # XXX < 3.6 bw compat
                    pdefs = obj.property_defs
                except AttributeError:
                    pdefs = getattr(obj, 'cw_property_defs', {})
                if pdefs:
                    yield objid
                    done.add(objid)
                    break


def defined_in_library(etype, rtype, tetype, role):
    """return true if the given relation definition exists in cubicweb's library
    """
    if libschema is None:
        return False
    if role == 'subject':
        subjtype, objtype = etype, tetype
    else:
        subjtype, objtype = tetype, etype
    try:
        return libschema.rschema(rtype).has_rdef(subjtype, objtype)
    except KeyError:
        return False


LANGS = ('en', 'fr', 'es')
I18NDIR = join(BASEDIR, 'i18n')
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

    def run(self, args):
        """run the command with its specific arguments"""
        if args:
            raise BadCommandUsage('Too much arguments')
        import shutil
        import tempfile
        import yams
        from logilab.common.fileutils import ensure_fs_mode
        from logilab.common.shellutils import globfind, find, rm
        from cubicweb.i18n import extract_from_tal, execute
        tempdir = tempfile.mkdtemp()
        potfiles = [join(I18NDIR, 'static-messages.pot')]
        print '-> extract schema messages.'
        schemapot = join(tempdir, 'schema.pot')
        potfiles.append(schemapot)
        # explicit close necessary else the file may not be yet flushed when
        # we'll using it below
        schemapotstream = file(schemapot, 'w')
        generate_schema_pot(schemapotstream.write, cubedir=None)
        schemapotstream.close()
        print '-> extract TAL messages.'
        tali18nfile = join(tempdir, 'tali18n.py')
        extract_from_tal(find(join(BASEDIR, 'web'), ('.py', '.pt')), tali18nfile)
        print '-> generate .pot files.'
        for id, files, lang in [('pycubicweb', get_module_files(BASEDIR) + list(globfind(join(BASEDIR, 'misc', 'migration'), '*.py')), None),
                                ('schemadescr', globfind(join(BASEDIR, 'schemas'), '*.py'), None),
                                ('yams', get_module_files(yams.__path__[0]), None),
                                ('tal', [tali18nfile], None),
                                ('js', globfind(join(BASEDIR, 'web'), 'cub*.js'), 'java'),
                                ]:
            cmd = 'xgettext --no-location --omit-header -k_ -o %s %s'
            if lang is not None:
                cmd += ' -L %s' % lang
            potfile = join(tempdir, '%s.pot' % id)
            execute(cmd % (potfile, ' '.join('"%s"' % f for f in files)))
            if exists(potfile):
                potfiles.append(potfile)
            else:
                print '-> WARNING: %s file was not generated' % potfile
        print '-> merging %i .pot files' % len(potfiles)
        cubicwebpot = join(tempdir, 'cubicweb.pot')
        execute('msgcat -o %s %s' % (cubicwebpot, ' '.join('"%s"' % f for f in potfiles)))
        print '-> merging main pot file with existing translations.'
        chdir(I18NDIR)
        toedit = []
        for lang in LANGS:
            target = '%s.po' % lang
            execute('msgmerge -N --sort-output -o "%snew" "%s" "%s"' % (target, target, cubicwebpot))
            ensure_fs_mode(target)
            shutil.move('%snew' % target, target)
            toedit.append(abspath(target))
        # cleanup
        rm(tempdir)
        # instructions pour la suite
        print '-> regenerated CubicWeb\'s .po catalogs.'
        print '\nYou can now edit the following files:'
        print '* ' + '\n* '.join(toedit)
        print 'when you are done, run "cubicweb-ctl i18ncube yourcube".'


class UpdateTemplateCatalogCommand(Command):
    """Update i18n catalogs for cubes. If no cube is specified, update
    catalogs of all registered cubes.
    """
    name = 'i18ncube'
    arguments = '[<cube>...]'

    def run(self, args):
        """run the command with its specific arguments"""
        if args:
            cubes = [DevCubeConfiguration.cube_dir(cube) for cube in args]
        else:
            cubes = [DevCubeConfiguration.cube_dir(cube) for cube in DevCubeConfiguration.available_cubes()]
            cubes = [cubepath for cubepath in cubes if exists(join(cubepath, 'i18n'))]
        update_cubes_catalogs(cubes)


def update_cubes_catalogs(cubes):
    for cubedir in cubes:
        toedit = []
        if not isdir(cubedir):
            print '-> ignoring %s that is not a directory.' % cubedir
            continue
        try:
            toedit += update_cube_catalogs(cubedir)
        except Exception:
            import traceback
            traceback.print_exc()
            print '-> error while updating catalogs for cube', cubedir
        else:
            # instructions pour la suite
            print '-> regenerated .po catalogs for cube %s.' % cubedir
            print '\nYou can now edit the following files:'
            print '* ' + '\n* '.join(toedit)
            print ('When you are done, run "cubicweb-ctl i18ninstance '
                   '<yourinstance>" to see changes in your instances.')

def update_cube_catalogs(cubedir):
    import shutil
    import tempfile
    from logilab.common.fileutils import ensure_fs_mode
    from logilab.common.shellutils import find, rm
    from cubicweb.i18n import extract_from_tal, execute
    toedit = []
    cube = basename(normpath(cubedir))
    tempdir = tempfile.mkdtemp()
    print underline_title('Updating i18n catalogs for cube %s' % cube)
    chdir(cubedir)
    if exists(join('i18n', 'entities.pot')):
        warn('entities.pot is deprecated, rename file to static-messages.pot (%s)'
             % join('i18n', 'entities.pot'), DeprecationWarning)
        potfiles = [join('i18n', 'entities.pot')]
    elif exists(join('i18n', 'static-messages.pot')):
        potfiles = [join('i18n', 'static-messages.pot')]
    else:
        potfiles = []
    print '-> extract schema messages'
    schemapot = join(tempdir, 'schema.pot')
    potfiles.append(schemapot)
    # explicit close necessary else the file may not be yet flushed when
    # we'll using it below
    schemapotstream = file(schemapot, 'w')
    generate_schema_pot(schemapotstream.write, cubedir)
    schemapotstream.close()
    print '-> extract TAL messages'
    tali18nfile = join(tempdir, 'tali18n.py')
    extract_from_tal(find('.', ('.py', '.pt'), blacklist=STD_BLACKLIST+('test',)), tali18nfile)
    print '-> extract Javascript messages'
    jsfiles =  [jsfile for jsfile in find('.', '.js') if basename(jsfile).startswith('cub')]
    if jsfiles:
        tmppotfile = join(tempdir, 'js.pot')
        execute('xgettext --no-location --omit-header -k_ -L java --from-code=utf-8 -o %s %s'
                % (tmppotfile, ' '.join(jsfiles)))
        # no pot file created if there are no string to translate
        if exists(tmppotfile):
            potfiles.append(tmppotfile)
    print '-> create cube-specific catalog'
    tmppotfile = join(tempdir, 'generated.pot')
    cubefiles = find('.', '.py', blacklist=STD_BLACKLIST+('test',))
    cubefiles.append(tali18nfile)
    execute('xgettext --no-location --omit-header -k_ -o %s %s'
            % (tmppotfile, ' '.join('"%s"' % f for f in cubefiles)))
    if exists(tmppotfile): # doesn't exists of no translation string found
        potfiles.append(tmppotfile)
    potfile = join(tempdir, 'cube.pot')
    print '-> merging %i .pot files:' % len(potfiles)
    execute('msgcat -o %s %s' % (potfile,
                                 ' '.join('"%s"' % f for f in potfiles)))
    print '-> merging main pot file with existing translations:'
    chdir('i18n')
    for lang in LANGS:
        print '-> language', lang
        cubepo = '%s.po' % lang
        if not exists(cubepo):
            shutil.copy(potfile, cubepo)
        else:
            execute('msgmerge -N -s -o %snew %s %s' % (cubepo, cubepo, potfile))
            ensure_fs_mode(cubepo)
            shutil.move('%snew' % cubepo, cubepo)
        toedit.append(abspath(cubepo))
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
      the name of the new cube
    """
    name = 'newcube'
    arguments = '<cubename>'

    options = (
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
        )


    def run(self, args):
        if len(args) != 1:
            raise BadCommandUsage("exactly one argument (cube name) is expected")
        cubename, = args
        verbose = self.get('verbose')
        cubesdir = self.get('directory')
        if not cubesdir:
            cubespath = ServerConfiguration.cubes_search_path()
            if len(cubespath) > 1:
                raise BadCommandUsage("can't guess directory where to put the new cube."
                                      " Please specify it using the --directory option")
            cubesdir = cubespath[0]
        if not isdir(cubesdir):
            print "-> creating cubes directory", cubesdir
            try:
                mkdir(cubesdir)
            except OSError, err:
                self.fail("failed to create directory %r\n(%s)" % (cubesdir, err))
        cubedir = join(cubesdir, cubename)
        if exists(cubedir):
            self.fail("%s already exists !" % (cubedir))
        skeldir = join(BASEDIR, 'skeleton')
        default_name = 'cubicweb-%s' % cubename.lower()
        if verbose:
            distname = raw_input('Debian name for your cube ? [%s]): ' % default_name).strip()
            if not distname:
                distname = default_name
            elif not distname.startswith('cubicweb-'):
                if ASK.confirm('Do you mean cubicweb-%s ?' % distname):
                    distname = 'cubicweb-' + distname
        else:
            distname = default_name

        longdesc = shortdesc = raw_input('Enter a short description for your cube: ')
        if verbose:
            longdesc = raw_input('Enter a long description (leave empty to reuse the short one): ')
        if verbose:
            includes = self._ask_for_dependancies()
            if len(includes) == 1:
                dependancies = '%r,' % includes[0]
            else:
                dependancies = ', '.join(repr(cube) for cube in includes)
        else:
            dependancies = ''
        context = {'cubename' : cubename,
                   'distname' : distname,
                   'shortdesc' : shortdesc,
                   'longdesc' : longdesc or shortdesc,
                   'dependancies' : dependancies,
                   'version'  : cubicwebversion,
                   'year'  : str(datetime.now().year),
                   'author': self['author'],
                   'author-email': self['author-email'],
                   'author-web-site': self['author-web-site'],
                   }
        copy_skeleton(skeldir, cubedir, context)

    def _ask_for_dependancies(self):
        includes = []
        for stdtype in ServerConfiguration.available_cubes():
            answer = ASK.ask("Depends on cube %s? " % stdtype,
                             ('N','y','skip','type'), 'N')
            if answer == 'y':
                includes.append(stdtype)
            if answer == 'type':
                includes = splitstrip(raw_input('type dependancies: '))
                break
            elif answer == 'skip':
                break
        return includes


class ExamineLogCommand(Command):
    """Examine a rql log file.

    usage: python exlog.py < rql.log

    will print out the following table

      total execution time || number of occurences || rql query

    sorted by descending total execution time

    chances are the lines at the top are the ones that will bring
    the higher benefit after optimisation. Start there.
    """
    name = 'exlog'
    options = (
        )

    def run(self, args):
        if args:
            raise BadCommandUsage("no argument expected")
        import re
        requests = {}
        for lineno, line in enumerate(sys.stdin):
            if not ' WHERE ' in line:
                continue
            #sys.stderr.write( line )
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
            except Exception, exc:
                sys.stderr.write('Line %s: %s (%s)\n' % (lineno, exc, line))

        stat = []
        for rql, times in requests.items():
            stat.append( (sum(time[0] for time in times),
                          sum(time[1] for time in times),
                          len(times), rql) )

        stat.sort()
        stat.reverse()

        total_time = sum(clocktime for clocktime, cputime, occ, rql in stat)*0.01
        print 'Percentage;Cumulative Time (clock);Cumulative Time (CPU);Occurences;Query'
        for clocktime, cputime, occ, rql in stat:
            print '%.2f;%.2f;%.2f;%s;%s' % (clocktime/total_time, clocktime, cputime, occ, rql)

class GenerateSchema(Command):
    """Generate schema image for the given cube"""
    name = "schema"
    arguments = '<cube>'
    options = [('output-file', {'type':'file', 'default': None,
                 'metavar': '<file>', 'short':'o', 'help':'output image file',
                 'input':False}),
               ('viewer', {'type': 'string', 'default':None,
                'short': "d", 'metavar':'<cmd>',
                 'help':'command use to view the generated file (empty for none)'}
               ),
               ('show-meta', {'action': 'store_true', 'default':False,
                'short': "m", 'metavar': "<yN>",
                 'help':'include meta and internal entities in schema'}
               ),
               ('show-workflow', {'action': 'store_true', 'default':False,
                'short': "w", 'metavar': "<yN>",
                'help':'include workflow entities in schema'}
               ),
               ('show-cw-user', {'action': 'store_true', 'default':False,
                'metavar': "<yN>",
                'help':'include cubicweb user entities in schema'}
               ),
               ('exclude-type', {'type':'string', 'default':'',
                'short': "x", 'metavar': "<types>",
                 'help':'coma separated list of entity types to remove from view'}
               ),
               ('include-type', {'type':'string', 'default':'',
                'short': "i", 'metavar': "<types>",
                 'help':'coma separated list of entity types to include in view'}
               ),
              ]

    def run(self, args):
        from logilab.common.textutils import splitstrip
        cubes = splitstrip(pop_arg(args, 1))

        dev_conf = DevCubeConfiguration(*cubes)
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

        schema2dot.schema2dot(schema, out, skiptypes=skiptypes)

        if viewer:
            p = Popen((viewer, out))
            p.wait()

register_commands((UpdateCubicWebCatalogCommand,
                   UpdateTemplateCatalogCommand,
                   #LiveServerCommand,
                   NewCubeCommand,
                   ExamineLogCommand,
                   GenerateSchema,
                   ))
