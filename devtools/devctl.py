"""additional cubicweb-ctl commands and command handlers for cubicweb and cubicweb's
cubes development

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
from os import walk, mkdir, chdir, listdir, getcwd
from os.path import join, exists, abspath, basename, normpath, split, isdir


from logilab.common import STD_BLACKLIST
from logilab.common.modutils import get_module_files
from logilab.common.textutils import get_csv

from cubicweb import CW_SOFTWARE_ROOT as BASEDIR
from cubicweb.__pkginfo__ import version as cubicwebversion
from cubicweb import BadCommandUsage
from cubicweb.toolsutils import Command, register_commands, confirm, copy_skeleton
from cubicweb.web.webconfig import WebConfiguration
from cubicweb.server.serverconfig import ServerConfiguration


class DevCubeConfiguration(ServerConfiguration, WebConfiguration):
    """dummy config to get full library schema and entities"""
    creating = True
    cubicweb_vobject_path = ServerConfiguration.cubicweb_vobject_path | WebConfiguration.cubicweb_vobject_path
    cube_vobject_path = ServerConfiguration.cube_vobject_path | WebConfiguration.cube_vobject_path

    def __init__(self, cube):
        super(DevCubeConfiguration, self).__init__(cube)
        if cube is None:
            self._cubes = ()
        else:
            self._cubes = self.expand_cubes(self.my_cubes(cube))

    def my_cubes(self, cube):
        return (cube,) + self.cube_dependencies(cube) + self.cube_recommends(cube)
    
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

    def my_cubes(self, cube):
        return self.cube_dependencies(cube) + self.cube_recommends(cube)

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
    
def generate_schema_pot(w, cubedir=None):
    """generate a pot file with schema specific i18n messages

    notice that relation definitions description and static vocabulary
    should be marked using '_' and extracted using xgettext
    """
    from cubicweb.cwvreg import CubicWebRegistry
    cube = cubedir and split(cubedir)[-1]
    config = DevDepConfiguration(cube)
    cleanup_sys_modules(config)
    if cubedir:
        libschema = config.load_schema()
        config = DevCubeConfiguration(cube)
        schema = config.load_schema()
    else:
        schema = config.load_schema()
        libschema = None
        config.cleanup_interface_sobjects = False
    vreg = CubicWebRegistry(config)
    # set_schema triggers objects registrations
    vreg.set_schema(schema)
    w(DEFAULT_POT_HEAD)
    _generate_schema_pot(w, vreg, schema, libschema=libschema, cube=cube)
                
def _generate_schema_pot(w, vreg, schema, libschema=None, cube=None):
    from mx.DateTime import now
    from cubicweb.common.i18n import add_msg
    w('# schema pot file, generated on %s\n' % now().strftime('%Y-%m-%d %H:%M:%S'))
    w('# \n')
    w('# singular and plural forms for each entity type\n')
    w('\n')
    if libschema is not None:
        entities = [e for e in schema.entities() if not e in libschema]
    else:
        entities = schema.entities()
    done = set()
    for eschema in sorted(entities):
        etype = eschema.type
        add_msg(w, etype)
        add_msg(w, '%s_plural' % etype)
        if not eschema.is_final():
            add_msg(w, 'This %s' % etype)
            add_msg(w, 'New %s' % etype)
            add_msg(w, 'add a %s' % etype)
            add_msg(w, 'remove this %s' % etype)
        if eschema.description and not eschema.description in done:
            done.add(eschema.description)
            add_msg(w, eschema.description)
    w('# subject and object forms for each relation type\n')
    w('# (no object form for final relation types)\n')
    w('\n')
    if libschema is not None:
        relations = [r for r in schema.relations() if not r in libschema]
    else:
        relations = schema.relations()
    for rschema in sorted(set(relations)):
        rtype = rschema.type
        add_msg(w, rtype)
        done.add(rtype)
        if not (schema.rschema(rtype).is_final() or rschema.symetric):
            add_msg(w, '%s_object' % rtype)
        if rschema.description and rschema.description not in done:
            done.add(rschema.description)
            add_msg(w, rschema.description)
    w('# add related box generated message\n')
    w('\n')
    for eschema in schema.entities():
        if eschema.is_final():
            continue
        entity = vreg.etype_class(eschema)(None, None)
        for x, rschemas in (('subject', eschema.subject_relations()),
                            ('object', eschema.object_relations())):
            for rschema in rschemas:
                if rschema.is_final():
                    continue
                for teschema in rschema.targets(eschema, x):
                    if defined_in_library(libschema, eschema, rschema, teschema, x):
                        continue
                    if entity.relation_mode(rschema.type, teschema.type, x) == 'create':
                        if x == 'subject':
                            label = 'add %s %s %s %s' % (eschema, rschema, teschema, x)
                            label2 = "creating %s (%s %%(linkto)s %s %s)" % (teschema, eschema, rschema, teschema)
                        else:
                            label = 'add %s %s %s %s' % (teschema, rschema, eschema, x)
                            label2 = "creating %s (%s %s %s %%(linkto)s)" % (teschema, teschema, rschema, eschema)
                        add_msg(w, label)
                        add_msg(w, label2)
    cube = (cube and 'cubes.%s.' % cube or 'cubicweb.')
    done = set()
    for reg, objdict in vreg.items():
        for objects in objdict.values():
            for obj in objects:
                objid = '%s_%s' % (reg, obj.id)
                if objid in done:
                    continue
                if obj.__module__.startswith(cube) and obj.property_defs:
                    add_msg(w, '%s_description' % objid)
                    add_msg(w, objid)
                    done.add(objid)

                    
def defined_in_library(libschema, etype, rtype, tetype, x):
    """return true if the given relation definition exists in cubicweb's library"""
    if libschema is None:
        return False
    if x == 'subject':
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
    name = 'i18nlibupdate'

    def run(self, args):
        """run the command with its specific arguments"""
        if args:
            raise BadCommandUsage('Too much arguments')
        import shutil
        from tempfile import mktemp
        import yams
        from logilab.common.fileutils import ensure_fs_mode
        from logilab.common.shellutils import globfind, find, rm
        from cubicweb.common.i18n import extract_from_tal, execute
        tempdir = mktemp()
        mkdir(tempdir)
        potfiles = [join(I18NDIR, 'entities.pot')]
        print '******** extract schema messages'
        schemapot = join(tempdir, 'schema.pot')
        potfiles.append(schemapot)
        # explicit close necessary else the file may not be yet flushed when
        # we'll using it below
        schemapotstream = file(schemapot, 'w')
        generate_schema_pot(schemapotstream.write, cubedir=None)
        schemapotstream.close()
        print '******** extract TAL messages'
        tali18nfile = join(tempdir, 'tali18n.py')
        extract_from_tal(find(join(BASEDIR, 'web'), ('.py', '.pt')), tali18nfile)
        print '******** .pot files generation'
        for id, files, lang in [('pycubicweb', get_module_files(BASEDIR) + list(globfind(join(BASEDIR, 'misc', 'migration'), '*.py')), None),
                                ('schemadescr', globfind(join(BASEDIR, 'schemas'), '*.py'), None),
                                ('yams', get_module_files(yams.__path__[0]), None),
                                ('tal', [tali18nfile], None),
                                ('js', globfind(join(BASEDIR, 'web'), 'cub*.js'), 'java'),
                                ]:
            cmd = 'xgettext --no-location --omit-header -k_ -o %s %s'
            if lang is not None:
                cmd += ' -L %s' % lang
            potfiles.append(join(tempdir, '%s.pot' % id))
            execute(cmd % (potfiles[-1], ' '.join(files)))
        print '******** merging .pot files'
        cubicwebpot = join(tempdir, 'cubicweb.pot')
        execute('msgcat %s > %s' % (' '.join(potfiles), cubicwebpot))
        print '******** merging main pot file with existing translations'
        chdir(I18NDIR)
        toedit = []
        for lang in LANGS:
            target = '%s.po' % lang
            execute('msgmerge -N --sort-output  %s %s > %snew' % (target, cubicwebpot, target))
            ensure_fs_mode(target)
            shutil.move('%snew' % target, target)
            toedit.append(abspath(target))
        # cleanup
        rm(tempdir)
        # instructions pour la suite
        print '*' * 72
        print 'you can now edit the following files:'
        print '* ' + '\n* '.join(toedit)
        print
        print "then you'll have to update cubes catalogs using the i18nupdate command"


class UpdateTemplateCatalogCommand(Command):
    """Update i18n catalogs for cubes. If no cube is specified, update
    catalogs of all registered cubes.
    """
    name = 'i18nupdate'
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
    import shutil
    from tempfile import mktemp
    from logilab.common.fileutils import ensure_fs_mode
    from logilab.common.shellutils import find, rm
    from cubicweb.common.i18n import extract_from_tal, execute
    toedit = []
    for cubedir in cubes:
        cube = basename(normpath(cubedir))
        if not isdir(cubedir):
            print 'unknown cube', cube
            continue
        tempdir = mktemp()
        mkdir(tempdir)
        print '*' * 72
        print 'updating %s cube...' % cube
        chdir(cubedir)
        potfiles = [join('i18n', scfile) for scfile in ('entities.pot',)
                    if exists(join('i18n', scfile))]
        print '******** extract schema messages'
        schemapot = join(tempdir, 'schema.pot')
        potfiles.append(schemapot)
        # explicit close necessary else the file may not be yet flushed when
        # we'll using it below
        schemapotstream = file(schemapot, 'w')
        generate_schema_pot(schemapotstream.write, cubedir)
        schemapotstream.close()
        print '******** extract TAL messages'
        tali18nfile = join(tempdir, 'tali18n.py')
        extract_from_tal(find('.', ('.py', '.pt'), blacklist=STD_BLACKLIST+('test',)), tali18nfile)
        print '******** extract Javascript messages'
        jsfiles =  [jsfile for jsfile in find('.', '.js') if basename(jsfile).startswith('cub')]
        if jsfiles:
            tmppotfile = join(tempdir, 'js.pot')
            execute('xgettext --no-location --omit-header -k_ -L java --from-code=utf-8 -o %s %s'
                    % (tmppotfile, ' '.join(jsfiles)))
            # no pot file created if there are no string to translate
            if exists(tmppotfile): 
                potfiles.append(tmppotfile)
        print '******** create cube specific catalog'
        tmppotfile = join(tempdir, 'generated.pot')
        cubefiles = find('.', '.py', blacklist=STD_BLACKLIST+('test',))
        cubefiles.append(tali18nfile)
        execute('xgettext --no-location --omit-header -k_ -o %s %s'
                % (tmppotfile, ' '.join(cubefiles)))
        if exists(tmppotfile): # doesn't exists of no translation string found
            potfiles.append(tmppotfile)
        potfile = join(tempdir, 'cube.pot')
        print '******** merging .pot files'
        execute('msgcat %s > %s' % (' '.join(potfiles), potfile))
        print '******** merging main pot file with existing translations'
        chdir('i18n')
        for lang in LANGS:
            print '****', lang
            cubepo = '%s.po' % lang
            if not exists(cubepo):
                shutil.copy(potfile, cubepo)
            else:
                execute('msgmerge -N -s %s %s > %snew' % (cubepo, potfile, cubepo))
                ensure_fs_mode(cubepo)
                shutil.move('%snew' % cubepo, cubepo)
            toedit.append(abspath(cubepo))
        # cleanup
        rm(tempdir)
    # instructions pour la suite
    print '*' * 72
    print 'you can now edit the following files:'
    print '* ' + '\n* '.join(toedit)


class LiveServerCommand(Command):
    """Run a server from within a cube directory.
    """
    name = 'live-server'
    arguments = ''
    options = ()
    
    def run(self, args):
        """run the command with its specific arguments"""
        from cubicweb.devtools.livetest import runserver
        runserver()


class NewCubeCommand(Command):
    """Create a new cube.

    <cubename>
      the name of the new cube
    """
    name = 'newcube'
    arguments = '<cubename>'

    options = (
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
        #if ServerConfiguration.mode != "dev":
        #    self.fail("you can only create new cubes in development mode")
        verbose = self.get('verbose')
        cubedir = ServerConfiguration.CUBES_DIR
        if not isdir(cubedir):
            print "creating apps directory", cubedir
            try:
                mkdir(cubedir)
            except OSError, err:
                self.fail("failed to create directory %r\n(%s)" % (cubedir, err))
        cubedir = join(cubedir, cubename)
        if exists(cubedir):
            self.fail("%s already exists !" % (cubedir))
        skeldir = join(BASEDIR, 'skeleton')
        if verbose:
            distname = raw_input('Debian name for your cube (just type enter to use the cube name): ').strip()
            if not distname:
                distname = 'cubicweb-%s' % cubename.lower()
            elif not distname.startswith('cubicweb-'):
                if confirm('do you mean cubicweb-%s ?' % distname):
                    distname = 'cubicweb-' + distname
        else:
            distname = 'cubicweb-%s' % cubename.lower()
        
        longdesc = shortdesc = raw_input('Enter a short description for your cube: ')
        if verbose:
            longdesc = raw_input('Enter a long description (or nothing if you want to reuse the short one): ')
        if verbose:
            includes = self._ask_for_dependancies()
            if len(includes) == 1:
                dependancies = '%r,' % includes[0]
            else:
                dependancies = ', '.join(repr(cube) for cube in includes)
        else:
            dependancies = ''
        from mx.DateTime import now
        context = {'cubename' : cubename,
                   'distname' : distname,
                   'shortdesc' : shortdesc,
                   'longdesc' : longdesc or shortdesc,
                   'dependancies' : dependancies,
                   'version'  : cubicwebversion,
                   'year'  : str(now().year),
                   'author': self['author'],
                   'author-email': self['author-email'],
                   'author-web-site': self['author-web-site'],
                   }
        copy_skeleton(skeldir, cubedir, context)

    def _ask_for_dependancies(self):
        includes = []
        for stdtype in ServerConfiguration.available_cubes():
            ans = raw_input("Depends on cube %s? (N/y/s(kip)/t(ype)"
                            % stdtype).lower().strip()
            if ans == 'y':
                includes.append(stdtype)
            if ans == 't':
                includes = get_csv(raw_input('type dependancies: '))
                break
            elif ans == 's':
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
        for line in sys.stdin:
            if not ' WHERE ' in line:
                continue
            #sys.stderr.write( line )
            rql, time = line.split('--')
            rql = re.sub("(\'\w+': \d*)", '', rql)
            req = requests.setdefault(rql, [])
            time.strip()
            chunks = time.split()
            cputime = float(chunks[-3])
            req.append( cputime )

        stat = []
        for rql, times in requests.items():
            stat.append( (sum(times), len(times), rql) )

        stat.sort()
        stat.reverse()
        for time, occ, rql in stat:
            print time, occ, rql
        
register_commands((UpdateCubicWebCatalogCommand,
                   UpdateTemplateCatalogCommand,
                   LiveServerCommand,
                   NewCubeCommand,
                   ExamineLogCommand,
                   ))
