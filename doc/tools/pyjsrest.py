#!/usr/bin/env python
"""
Parser for Javascript comments.
"""
import os.path as osp
import sys, os, getopt, re

def clean_comment(match):
    comment = match.group()
    comment = strip_stars(comment)
    return comment

# Rest utilities
def rest_title(title, level, level_markups=['=', '=', '-', '~', '+', '`']):
    size = len(title)
    if level == 0:
        return '\n'.join((level_markups[level] * size, title, level_markups[0] * size)) + '\n'
    return '\n'.join(('\n' + title, level_markups[level] * size)) + '\n'

def get_doc_comments(text):
    """
    Return a list of all documentation comments in the file text.  Each
    comment is a pair, with the first element being the comment text and
    the second element being the line after it, which may be needed to
    guess function & arguments.

    >>> get_doc_comments(read_file('examples/module.js'))[0][0][:40]
    '/**\n * This is the module documentation.'
    >>> get_doc_comments(read_file('examples/module.js'))[1][0][7:50]
    'This is documentation for the first method.'
    >>> get_doc_comments(read_file('examples/module.js'))[1][1]
    'function the_first_function(arg1, arg2) '
    >>> get_doc_comments(read_file('examples/module.js'))[2][0]
    '/** This is the documentation for the second function. */'

    """
    return [clean_comment(match) for match in re.finditer('/\*\*.*?\*/',
            text, re.DOTALL|re.MULTILINE)]

RE_STARS = re.compile('^\s*?\* ?', re.MULTILINE)


def strip_stars(doc_comment):
    """
    Strip leading stars from a doc comment.

    >>> strip_stars('/** This is a comment. */')
    'This is a comment.'
    >>> strip_stars('/**\n * This is a\n * multiline comment. */')
    'This is a\n multiline comment.'
    >>> strip_stars('/** \n\t * This is a\n\t * multiline comment. \n*/')
    'This is a\n multiline comment.'

    """
    return RE_STARS.sub('', doc_comment[3:-2]).strip()

def parse_js_files(args=sys.argv):
    """
    Main command-line invocation.
    """
    try:
        opts, args = getopt.gnu_getopt(args[1:], 'p:o:h', [
            'jspath=', 'output=', 'help'])
        opts = dict(opts)
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    rst_dir = opts.get('--output') or opts.get('-o')
    if rst_dir is None and len(args) != 1:
        rst_dir = 'apidocs'
    js_dir = opts.get('--jspath') or opts.get('-p')
    if not osp.exists(osp.join(rst_dir)):
        os.makedirs(osp.join(rst_dir))

    index = set()
    for js_path, js_dirs, js_files in os.walk(js_dir):
        rst_path = re.sub('%s%s*' % (js_dir, osp.sep), '', js_path)
        for js_file in js_files:
            if not js_file.endswith('.js'):
                continue
            if js_file in FILES_TO_IGNORE:
                continue
            if not osp.exists(osp.join(rst_dir, rst_path)):
                os.makedirs(osp.join(rst_dir, rst_path))
            rst_content =  extract_rest(js_path, js_file)
            filename = osp.join(rst_path, js_file[:-3])
            # add to index
            index.add(filename)
            # save rst file
            with open(osp.join(rst_dir, filename) + '.rst', 'wb') as f_rst:
                f_rst.write(rst_content.encode())
    stream = open(osp.join(rst_dir, 'index.rst'), 'w')
    stream.write('''
Javascript API
==============

.. toctree::
    :maxdepth: 1

''')
    # first write expected files in order
    for fileid in INDEX_IN_ORDER:
        try:
            index.remove(fileid)
        except Exception:
            raise Exception(
        'Bad file id %s referenced in INDEX_IN_ORDER in %s, '
        'fix this please' % (fileid, __file__))
        stream.write('    %s\n' % fileid)
    # append remaining, by alphabetical order
    for fileid in sorted(index):
        stream.write('    %s\n' % fileid)
    stream.close()

def extract_rest(js_dir, js_file):
    js_filepath = osp.join(js_dir, js_file)
    filecontent = open(js_filepath, 'U').read()
    comments = get_doc_comments(filecontent)
    rst = rest_title(js_file, 0)
    rst += '.. module:: %s\n\n' % js_file
    rst += '\n\n'.join(comments)
    return rst

INDEX_IN_ORDER = [
    'cubicweb',
    'cubicweb.python',
    'cubicweb.htmlhelpers',
    'cubicweb.ajax',

    'cubicweb.ajax.box',
    'cubicweb.facets',
    'cubicweb.widgets',
    'cubicweb.image',
    'cubicweb.flot',
    'cubicweb.calendar',
    'cubicweb.preferences',
    'cubicweb.edition',
    'cubicweb.reledit',
]

FILES_TO_IGNORE = set([
    'jquery.js',
    'jquery.treeview.js',
    'jquery.tablesorter.js',
    'jquery.timePicker.js',
    'jquery.flot.js',
    'jquery.corner.js',
    'jquery.ui.js',
    'excanvas.js',
    'gmap.utility.labeledmarker.js',

    'cubicweb.fckcwconfig.js',
    'cubicweb.fckcwconfig-full.js',
    'cubicweb.compat.js',
    ])

if __name__ == '__main__':
    parse_js_files()
