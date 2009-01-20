#!/usr/bin/env python
"""This script is just a thin wrapper around ``msgcat`` and ``msgfmt``
to generate ``.mo`` files
"""

import sys
import os
import os.path as osp
import shutil
from tempfile import mktemp
from glob import glob
from mx.DateTime import now

from logilab.common.fileutils import ensure_fs_mode
from logilab.common.shellutils import find, rm

from yams import BASE_TYPES

from cubicweb import CW_SOFTWARE_ROOT
# from cubicweb.__pkginfo__ import version as cubicwebversion
cubicwebversion = '2.48.2'

DEFAULT_POT_HEAD = r'''# LAX application po file

msgid ""
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


STDLIB_ERTYPES = BASE_TYPES | set( ('EUser', 'EProperty', 'Card', 'identity', 'for_user') )

def create_dir(directory):
    """create a directory if it doesn't exist yet"""
    try:
        os.makedirs(directory)
        print 'created directory', directory
    except OSError, ex:
        import errno
        if ex.errno != errno.EEXIST:
            raise
        print 'directory %s already exists' % directory

def execute(cmd):
    """display the command, execute it and raise an Exception if returned
    status != 0
    """
    print cmd.replace(os.getcwd() + os.sep, '')
    status = os.system(cmd)
    if status != 0:
        raise Exception()

def add_msg(w, msgid):
    """write an empty pot msgid definition"""
    if isinstance(msgid, unicode):
        msgid = msgid.encode('utf-8')
    msgid = msgid.replace('"', r'\"').splitlines()
    if len(msgid) > 1:
        w('msgid ""\n')
        for line in msgid:
            w('"%s"' % line.replace('"', r'\"'))
    else:
        w('msgid "%s"\n' % msgid[0])
    w('msgstr ""\n\n')


def generate_schema_pot(w, vreg, tmpldir):
    """generate a pot file with schema specific i18n messages

    notice that relation definitions description and static vocabulary
    should be marked using '_' and extracted using xgettext
    """
    cube = tmpldir and osp.split(tmpldir)[-1]
    config = vreg.config
    vreg.register_objects(config.vregistry_path())
    w(DEFAULT_POT_HEAD)
    _generate_schema_pot(w, vreg, vreg.schema, libschema=None, # no libschema for now
                         cube=cube)


def _generate_schema_pot(w, vreg, schema, libschema=None, cube=None):
    w('# schema pot file, generated on %s\n' % now().strftime('%Y-%m-%d %H:%M:%S'))
    w('# \n')
    w('# singular and plural forms for each entity type\n')
    w('\n')
    # XXX hard-coded list of stdlib's entity schemas
    libschema = libschema or STDLIB_ERTYPES
    entities = [e for e in schema.entities() if not e in libschema]
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
    cube = (cube or 'cubicweb') + '.'
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
    except (KeyError, AttributeError):
        # if libschema is a simple list of entity types (lax specific)
        # or if the relation could not be found
        return False



# XXX check if this is a pure duplication of the original
# `cubicweb.common.i18n` function
def compile_i18n_catalogs(sourcedirs, destdir, langs):
    """generate .mo files for a set of languages into the `destdir` i18n directory
    """
    print 'compiling %s catalogs...' % destdir
    errors = []
    for lang in langs:
        langdir = osp.join(destdir, lang, 'LC_MESSAGES')
        if not osp.exists(langdir):
            create_dir(langdir)
        pofiles = [osp.join(path, '%s.po' % lang) for path in sourcedirs]
        pofiles = [pof for pof in pofiles if osp.exists(pof)]
        mergedpo = osp.join(destdir, '%s_merged.po' % lang)
        try:
            # merge application messages' catalog with the stdlib's one
            execute('msgcat --use-first --sort-output --strict %s > %s'
                    % (' '.join(pofiles), mergedpo))
            # make sure the .mo file is writeable and compile with *msgfmt*
            applmo = osp.join(destdir, lang, 'LC_MESSAGES', 'cubicweb.mo')
            try:
                ensure_fs_mode(applmo)
            except OSError:
                pass # suppose not osp.exists
            execute('msgfmt %s -o %s' % (mergedpo, applmo))
        except Exception, ex:
            errors.append('while handling language %s: %s' % (lang, ex))
        try:
            # clean everything
            os.unlink(mergedpo)
        except Exception:
            continue
    return errors


def update_cubes_catalog(vreg, appdirectory, langs):
    toedit = []
    tmpl = osp.basename(osp.normpath(appdirectory))
    tempdir = mktemp()
    os.mkdir(tempdir)
    print '*' * 72
    print 'updating %s cube...' % tmpl
    os.chdir(appdirectory)
    potfiles = []
    if osp.exists(osp.join('i18n', 'entities.pot')):
        potfiles = potfiles.append( osp.join('i18n', 'entities.pot') )
    print '******** extract schema messages'
    schemapot = osp.join(tempdir, 'schema.pot')
    potfiles.append(schemapot)
    # XXX
    generate_schema_pot(open(schemapot, 'w').write, vreg, appdirectory)
    print '******** extract Javascript messages'
    jsfiles =  find('.', '.js')
    if jsfiles:
        tmppotfile = osp.join(tempdir, 'js.pot')
        execute('xgettext --no-location --omit-header -k_ -L java --from-code=utf-8 -o %s %s'
                % (tmppotfile, ' '.join(jsfiles)))
        # no pot file created if there are no string to translate
        if osp.exists(tmppotfile): 
            potfiles.append(tmppotfile)
    print '******** create cube specific catalog'
    tmppotfile = osp.join(tempdir, 'generated.pot')
    execute('xgettext --no-location --omit-header -k_ -o %s %s'
            % (tmppotfile, ' '.join(glob('*.py'))))
    if osp.exists(tmppotfile): # doesn't exists of no translation string found
        potfiles.append(tmppotfile)
    potfile = osp.join(tempdir, 'cube.pot')
    print '******** merging .pot files'
    execute('msgcat %s > %s' % (' '.join(potfiles), potfile))
    print '******** merging main pot file with existing translations'
    os.chdir('i18n')
    for lang in langs:
        print '****', lang
        tmplpo = '%s.po' % lang
        if not osp.exists(tmplpo):
            shutil.copy(potfile, tmplpo)
        else:
            execute('msgmerge -N -s %s %s > %snew' % (tmplpo, potfile, tmplpo))
            ensure_fs_mode(tmplpo)
            shutil.move('%snew' % tmplpo, tmplpo)
        toedit.append(osp.abspath(tmplpo))
    # cleanup
    rm(tempdir)
    # instructions pour la suite
    print '*' * 72
    print 'you can now edit the following files:'
    print '* ' + '\n* '.join(toedit)
             

def getlangs(i18ndir):
    return [fname[:-3] for fname in os.listdir(i18ndir)
            if fname.endswith('.po')]


def get_i18n_directory(appdirectory):
    if not osp.isdir(appdirectory):
        print '%s is not an application directory' % appdirectory
        sys.exit(2)
    i18ndir = osp.join(appdirectory, 'i18n')
    if not osp.isdir(i18ndir):
        print '%s is not an application directory ' \
            '(i18n subdirectory missing)' % appdirectory
        sys.exit(2)
    return i18ndir
