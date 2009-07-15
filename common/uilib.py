# -*- coding: utf-8 -*-
"""user interface libraries

contains some functions designed to help implementation of cubicweb user interface

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import csv
import re
from urllib import quote as urlquote
from StringIO import StringIO

from logilab.mtconverter import xml_escape, html_unescape

from cubicweb.utils import ustrftime

def rql_for_eid(eid):
    """return the rql query necessary to fetch entity with the given eid.  This
    function should only be used to generate link with rql inside, not to give
    to cursor.execute (in which case you won't benefit from rql cache).

    :Parameters:
      - `eid`: the eid of the entity we should search
    :rtype: str
    :return: the rql query
    """
    return 'Any X WHERE X eid %s' % eid


def printable_value(req, attrtype, value, props=None, displaytime=True):
    """return a displayable value (i.e. unicode string)"""
    if value is None or attrtype == 'Bytes':
        return u''
    if attrtype == 'String':
        # don't translate empty value if you don't want strange results
        if props is not None and value and props.get('internationalizable'):
            return req._(value)

        return value
    if attrtype == 'Date':
        return ustrftime(value, req.property_value('ui.date-format'))
    if attrtype == 'Time':
        return ustrftime(value, req.property_value('ui.time-format'))
    if attrtype == 'Datetime':
        if not displaytime:
            return ustrftime(value, req.property_value('ui.date-format'))
        return ustrftime(value, req.property_value('ui.datetime-format'))
    if attrtype == 'Boolean':
        if value:
            return req._('yes')
        return req._('no')
    if attrtype == 'Float':
        value = req.property_value('ui.float-format') % value
    return unicode(value)


# text publishing #############################################################

try:
    from cubicweb.ext.rest import rest_publish # pylint: disable-msg=W0611
except ImportError:
    def rest_publish(entity, data):
        """default behaviour if docutils was not found"""
        return xml_escape(data)

TAG_PROG = re.compile(r'</?.*?>', re.U)
def remove_html_tags(text):
    """Removes HTML tags from text

    >>> remove_html_tags('<td>hi <a href="http://www.google.fr">world</a></td>')
    'hi world'
    >>>
    """
    return TAG_PROG.sub('', text)


REF_PROG = re.compile(r"<ref\s+rql=([\'\"])([^\1]*?)\1\s*>([^<]*)</ref>", re.U)
def _subst_rql(view, obj):
    delim, rql, descr = obj.groups()
    return u'<a href="%s">%s</a>' % (view.build_url(rql=rql), descr)

def html_publish(view, text):
    """replace <ref rql=''> links by <a href="...">"""
    if not text:
        return u''
    return REF_PROG.sub(lambda obj, view=view:_subst_rql(view, obj), text)

# fallback implementation, nicer one defined below if lxml is available
def soup2xhtml(data, encoding):
    # normalize line break
    # see http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1
    return u'\n'.join(data.splitlines())

# fallback implementation, nicer one defined below if lxml> 2.0 is available
def safe_cut(text, length):
    """returns a string of length <length> based on <text>, removing any html
    tags from given text if cut is necessary."""
    if text is None:
        return u''
    noenttext = html_unescape(text)
    text_nohtml = remove_html_tags(noenttext)
    # try to keep html tags if text is short enough
    if len(text_nohtml) <= length:
        return text
    # else if un-tagged text is too long, cut it
    return xml_escape(text_nohtml[:length] + u'...')

fallback_safe_cut = safe_cut


try:
    from lxml import etree
except (ImportError, AttributeError):
    # gae environment: lxml not availabel
    pass
else:

    def soup2xhtml(data, encoding):
        """tidy (at least try) html soup and return the result
        Note: the function considers a string with no surrounding tag as valid
              if <div>`data`</div> can be parsed by an XML parser
        """
        # normalize line break
        # see http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1
        data = u'\n'.join(data.splitlines())
        # XXX lxml 1.1 support still needed ?
        xmltree = etree.HTML('<div>%s</div>' % data)
        # NOTE: lxml 1.1 (etch platforms) doesn't recognize
        #       the encoding=unicode parameter (lxml 2.0 does), this is
        #       why we specify an encoding and re-decode to unicode later
        body = etree.tostring(xmltree[0], encoding=encoding)
        # remove <body> and </body> and decode to unicode
        return body[11:-13].decode(encoding)

    if hasattr(etree.HTML('<div>test</div>'), 'iter'):

        def safe_cut(text, length):
            """returns an html document of length <length> based on <text>,
            and cut is necessary.
            """
            if text is None:
                return u''
            dom = etree.HTML(text)
            curlength = 0
            add_ellipsis = False
            for element in dom.iter():
                if curlength >= length:
                    parent = element.getparent()
                    parent.remove(element)
                    if curlength == length and (element.text or element.tail):
                        add_ellipsis = True
                else:
                    if element.text is not None:
                        element.text = cut(element.text, length - curlength)
                        curlength += len(element.text)
                    if element.tail is not None:
                        if curlength < length:
                            element.tail = cut(element.tail, length - curlength)
                            curlength += len(element.tail)
                        elif curlength == length:
                            element.tail = '...'
                        else:
                            element.tail = ''
            text = etree.tounicode(dom[0])[6:-7] # remove wrapping <body></body>
            if add_ellipsis:
                return text + u'...'
            return text

def text_cut(text, nbwords=30, gotoperiod=True):
    """from the given plain text, return a text with at least <nbwords> words,
    trying to go to the end of the current sentence.

    :param nbwords: the minimum number of words required
    :param gotoperiod: specifies if the function should try to go to
                       the first period after the cut (i.e. finish
                       the sentence if possible)

    Note that spaces are normalized.
    """
    if text is None:
        return u''
    words = text.split()
    text = u' '.join(words) # normalize spaces
    textlength = minlength = len(' '.join(words[:nbwords]))
    if gotoperiod:
        textlength = text.find('.', minlength) + 1
        if textlength == 0: # no period found
            textlength = minlength
    return text[:textlength]

def cut(text, length):
    """returns a string of a maximum length <length> based on <text>
    (approximatively, since if text has been  cut, '...' is added to the end of the string,
    resulting in a string of len <length> + 3)
    """
    if text is None:
        return u''
    if len(text) <= length:
        return text
    # else if un-tagged text is too long, cut it
    return text[:length] + u'...'



# HTML generation helper functions ############################################

def simple_sgml_tag(tag, content=None, escapecontent=True, **attrs):
    """generation of a simple sgml tag (eg without children tags) easier

    content and attributes will be escaped
    """
    value = u'<%s' % tag
    if attrs:
        try:
            attrs['class'] = attrs.pop('klass')
        except KeyError:
            pass
        value += u' ' + u' '.join(u'%s="%s"' % (attr, xml_escape(unicode(value)))
                                  for attr, value in sorted(attrs.items())
                                  if value is not None)
    if content:
        if escapecontent:
            content = xml_escape(unicode(content))
        value += u'>%s</%s>' % (content, tag)
    else:
        value += u'></%s>' % tag
    return value

def tooltipize(text, tooltip, url=None):
    """make an HTML tooltip"""
    url = url or '#'
    return u'<a href="%s" title="%s">%s</a>' % (url, tooltip, text)

def toggle_action(nodeid):
    """builds a HTML link that uses the js toggleVisibility function"""
    return u"javascript: toggleVisibility('%s')" % nodeid

def toggle_link(nodeid, label):
    """builds a HTML link that uses the js toggleVisibility function"""
    return u'<a href="%s">%s</a>' % (toggle_action(nodeid), label)


def ureport_as_html(layout):
    from logilab.common.ureports import HTMLWriter
    formater = HTMLWriter(True)
    stream = StringIO() #UStringIO() don't want unicode assertion
    formater.format(layout, stream)
    res = stream.getvalue()
    if isinstance(res, str):
        res = unicode(res, 'UTF8')
    return res

def render_HTML_tree(tree, selected_node=None, render_node=None, caption=None):
    """
    Generate a pure HTML representation of a tree given as an instance
    of a logilab.common.tree.Node

    selected_node is the currently selected node (if any) which will
    have its surrounding <div> have id="selected" (which default
    to a bold border libe with the default CSS).

    render_node is a function that should take a Node content (Node.id)
    as parameter and should return a string (what will be displayed
    in the cell).

    Warning: proper rendering of the generated html code depends on html_tree.css
    """
    tree_depth = tree.depth_down()
    if render_node is None:
        render_node = str

    # helper function that build a matrix from the tree, like:
    # +------+-----------+-----------+
    # | root | child_1_1 | child_2_1 |
    # | root | child_1_1 | child_2_2 |
    # | root | child_1_2 |           |
    # | root | child_1_3 | child_2_3 |
    # | root | child_1_3 | child_2_4 |
    # +------+-----------+-----------+
    # from:
    # root -+- child_1_1 -+- child_2_1
    #       |             |
    #       |             +- child_2_2
    #       +- child_1_2
    #       |
    #       +- child1_3 -+- child_2_3
    #                    |
    #                    +- child_2_2
    def build_matrix(path, matrix):
        if path[-1].is_leaf():
            matrix.append(path[:])
        else:
            for child in path[-1].children:
                build_matrix(path[:] + [child], matrix)

    matrix = []
    build_matrix([tree], matrix)

    # make all lines in the matrix have the same number of columns
    for line in matrix:
        line.extend([None]*(tree_depth-len(line)))
    for i in range(len(matrix)-1, 0, -1):
        prev_line, line = matrix[i-1:i+1]
        for j in range(len(line)):
            if line[j] == prev_line[j]:
                line[j] = None

    # We build the matrix of link types (between 2 cells on a line of the matrix)
    # link types are :
    link_types = {(True,  True,  True ): 1, # T
                  (False, False, True ): 2, # |
                  (False, True,  True ): 3, # + (actually, vert. bar with horiz. bar on the right)
                  (False, True,  False): 4, # L
                  (True,  True,  False): 5, # -
                  }
    links = []
    for i, line in enumerate(matrix):
        links.append([])
        for j in range(tree_depth-1):
            cell_11 = line[j] is not None
            cell_12 = line[j+1] is not None
            cell_21 = line[j+1] is not None and line[j+1].next_sibling() is not None
            link_type = link_types.get((cell_11, cell_12, cell_21), 0)
            if link_type == 0 and i > 0 and links[i-1][j] in (1, 2, 3):
                link_type = 2
            links[-1].append(link_type)


    # We can now generate the HTML code for the <table>
    s = u'<table class="tree">\n'
    if caption:
        s += '<caption>%s</caption>\n' % caption

    for i, link_line in enumerate(links):
        line = matrix[i]

        s += '<tr>'
        for j, link_cell in enumerate(link_line):
            cell = line[j]
            if cell:
                if cell.id == selected_node:
                    s += '<td class="tree_cell" rowspan="2"><div id="selected" class="tree_cell">%s</div></td>' % (render_node(cell.id))
                else:
                    s += '<td class="tree_cell" rowspan="2"><div class="tree_cell">%s</div></td>' % (render_node(cell.id))
            else:
                s += '<td rowspan="2">&nbsp;</td>'
            s += '<td class="tree_cell_%d_1">&nbsp;</td>' % link_cell
            s += '<td class="tree_cell_%d_2">&nbsp;</td>' % link_cell

        cell = line[-1]
        if cell:
            if cell.id == selected_node:
                s += '<td class="tree_cell" rowspan="2"><div id="selected" class="tree_cell">%s</div></td>' % (render_node(cell.id))
            else:
                s += '<td class="tree_cell" rowspan="2"><div class="tree_cell">%s</div></td>' % (render_node(cell.id))
        else:
            s += '<td rowspan="2">&nbsp;</td>'

        s += '</tr>\n'
        if link_line:
            s += '<tr>'
            for j, link_cell in enumerate(link_line):
                s += '<td class="tree_cell_%d_3">&nbsp;</td>' % link_cell
                s += '<td class="tree_cell_%d_4">&nbsp;</td>' % link_cell
            s += '</tr>\n'

    s += '</table>'
    return s



# traceback formatting ########################################################

import traceback

def rest_traceback(info, exception):
    """return a ReST formated traceback"""
    res = [u'Traceback\n---------\n::\n']
    for stackentry in traceback.extract_tb(info[2]):
        res.append(u'\tFile %s, line %s, function %s' % tuple(stackentry[:3]))
        if stackentry[3]:
            res.append(u'\t  %s' % stackentry[3].decode('utf-8', 'replace'))
    res.append(u'\n')
    try:
        res.append(u'\t Error: %s\n' % exception)
    except:
        pass
    return u'\n'.join(res)


def html_traceback(info, exception, title='',
                   encoding='ISO-8859-1', body=''):
    """ return an html formatted traceback from python exception infos.
    """
    tcbk = info[2]
    stacktb = traceback.extract_tb(tcbk)
    strings = []
    if body:
        strings.append(u'<div class="error_body">')
        # FIXME
        strings.append(body)
        strings.append(u'</div>')
    if title:
        strings.append(u'<h1 class="error">%s</h1>'% xml_escape(title))
    try:
        strings.append(u'<p class="error">%s</p>' % xml_escape(str(exception)).replace("\n","<br />"))
    except UnicodeError:
        pass
    strings.append(u'<div class="error_traceback">')
    for index, stackentry in enumerate(stacktb):
        strings.append(u'<b>File</b> <b class="file">%s</b>, <b>line</b> '
                       u'<b class="line">%s</b>, <b>function</b> '
                       u'<b class="function">%s</b>:<br/>'%(
            xml_escape(stackentry[0]), stackentry[1], xml_escape(stackentry[2])))
        if stackentry[3]:
            string = xml_escape(stackentry[3]).decode('utf-8', 'replace')
            strings.append(u'&nbsp;&nbsp;%s<br/>\n' % (string))
        # add locals info for each entry
        try:
            local_context = tcbk.tb_frame.f_locals
            html_info = []
            chars = 0
            for name, value in local_context.iteritems():
                value = xml_escape(repr(value))
                info = u'<span class="name">%s</span>=%s, ' % (name, value)
                line_length = len(name) + len(value)
                chars += line_length
                # 150 is the result of *years* of research ;-) (CSS might be helpful here)
                if chars > 150:
                    info = u'<br/>' + info
                    chars = line_length
                html_info.append(info)
            boxid = 'ctxlevel%d' % index
            strings.append(u'[%s]' % toggle_link(boxid, '+'))
            strings.append(u'<div id="%s" class="pycontext hidden">%s</div>' %
                           (boxid, ''.join(html_info)))
            tcbk = tcbk.tb_next
        except Exception:
            pass # doesn't really matter if we have no context info
    strings.append(u'</div>')
    return '\n'.join(strings)

# csv files / unicode support #################################################

class UnicodeCSVWriter:
    """proxies calls to csv.writer.writerow to be able to deal with unicode"""

    def __init__(self, wfunc, encoding, **kwargs):
        self.writer = csv.writer(self, **kwargs)
        self.wfunc = wfunc
        self.encoding = encoding

    def write(self, data):
        self.wfunc(data)

    def writerow(self, row):
        csvrow = []
        for elt in row:
            if isinstance(elt, unicode):
                csvrow.append(elt.encode(self.encoding))
            else:
                csvrow.append(str(elt))
        self.writer.writerow(csvrow)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# some decorators #############################################################

class limitsize(object):
    def __init__(self, maxsize):
        self.maxsize = maxsize

    def __call__(self, function):
        def newfunc(*args, **kwargs):
            ret = function(*args, **kwargs)
            if isinstance(ret, basestring):
                return ret[:self.maxsize]
            return ret
        return newfunc


def htmlescape(function):
    def newfunc(*args, **kwargs):
        ret = function(*args, **kwargs)
        assert isinstance(ret, basestring)
        return xml_escape(ret)
    return newfunc
