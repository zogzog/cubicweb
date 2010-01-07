"""Some i18n/gettext utilities.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import re
import os
import sys
from os.path import join, basename, splitext, exists
from glob import glob

from cubicweb.toolsutils import create_dir

def extract_from_tal(files, output_file):
    """extract i18n strings from tal and write them into the given output file
    using standard python gettext marker (_)
    """
    output = open(output_file, 'w')
    for filepath in files:
        for match in re.finditer('i18n:(content|replace)="([^"]+)"', open(filepath).read()):
            print >> output, '_("%s")' % match.group(2)
    output.close()


def add_msg(w, msgid, msgctx=None):
    """write an empty pot msgid definition"""
    if isinstance(msgid, unicode):
        msgid = msgid.encode('utf-8')
    if msgctx:
        if isinstance(msgctx, unicode):
            msgctx = msgctx.encode('utf-8')
        w('msgctxt "%s"\n' % msgctx)
    msgid = msgid.replace('"', r'\"').splitlines()
    if len(msgid) > 1:
        w('msgid ""\n')
        for line in msgid:
            w('"%s"' % line.replace('"', r'\"'))
    else:
        w('msgid "%s"\n' % msgid[0])
    w('msgstr ""\n\n')


def execute(cmd):
    """display the command, execute it and raise an Exception if returned
    status != 0
    """
    print cmd.replace(os.getcwd() + os.sep, '')
    from subprocess import call
    status = call(cmd, shell=True)
    if status != 0:
        raise Exception('status = %s' % status)


def available_catalogs(i18ndir=None):
    if i18ndir is None:
        wildcard = '*.po'
    else:
        wildcard = join(i18ndir, '*.po')
    for popath in glob(wildcard):
        lang = splitext(basename(popath))[0]
        yield lang, popath


def compile_i18n_catalogs(sourcedirs, destdir, langs):
    """generate .mo files for a set of languages into the `destdir` i18n directory
    """
    from logilab.common.fileutils import ensure_fs_mode
    print '-> compiling %s catalogs...' % destdir
    errors = []
    for lang in langs:
        langdir = join(destdir, lang, 'LC_MESSAGES')
        if not exists(langdir):
            create_dir(langdir)
        pofiles = [join(path, '%s.po' % lang) for path in sourcedirs]
        pofiles = [pof for pof in pofiles if exists(pof)]
        mergedpo = join(destdir, '%s_merged.po' % lang)
        try:
            # merge instance/cubes messages catalogs with the stdlib's one
            execute('msgcat --use-first --sort-output --strict -o "%s" %s'
                    % (mergedpo, ' '.join('"%s"' % f for f in pofiles)))
            # make sure the .mo file is writeable and compiles with *msgfmt*
            applmo = join(destdir, lang, 'LC_MESSAGES', 'cubicweb.mo')
            try:
                ensure_fs_mode(applmo)
            except OSError:
                pass # suppose not exists
            execute('msgfmt "%s" -o "%s"' % (mergedpo, applmo))
        except Exception, ex:
            errors.append('while handling language %s: %s' % (lang, ex))
        try:
            # clean everything
            os.unlink(mergedpo)
        except Exception:
            continue
    return errors
