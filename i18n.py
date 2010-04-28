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
"""Some i18n/gettext utilities.

"""
__docformat__ = "restructuredtext en"

import re
import os
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
    from subprocess import call
    print cmd.replace(os.getcwd() + os.sep, '')
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
