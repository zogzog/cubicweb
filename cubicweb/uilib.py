# -*- coding: utf-8 -*-
# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""user interface libraries

contains some functions designed to help implementation of cubicweb user
interface.
"""



import csv
import re
from io import StringIO

from logilab.mtconverter import xml_escape, html_unescape
from logilab.common.date import ustrftime

from cubicweb import _
from cubicweb.utils import js_dumps


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

def eid_param(name, eid):
    assert name is not None
    assert eid is not None
    return '%s:%s' % (name, eid)

def print_bytes(value, req, props, displaytime=True):
    return u''

def print_string(value, req, props, displaytime=True):
    # don't translate empty value if you don't want strange results
    if props is not None and value and props.get('internationalizable'):
        return req._(value)
    return value

def print_int(value, req, props, displaytime=True):
    return str(value)

def print_date(value, req, props, displaytime=True):
    return ustrftime(value, req.property_value('ui.date-format'))

def print_time(value, req, props, displaytime=True):
    return ustrftime(value, req.property_value('ui.time-format'))

def print_tztime(value, req, props, displaytime=True):
    return ustrftime(value, req.property_value('ui.time-format')) + u' UTC'

def print_datetime(value, req, props, displaytime=True):
    if displaytime:
        return ustrftime(value, req.property_value('ui.datetime-format'))
    return ustrftime(value, req.property_value('ui.date-format'))

def print_tzdatetime(value, req, props, displaytime=True):
    if displaytime:
        return ustrftime(value, req.property_value('ui.datetime-format')) + u' UTC'
    return ustrftime(value, req.property_value('ui.date-format'))

_('%d years')
_('%d months')
_('%d weeks')
_('%d days')
_('%d hours')
_('%d minutes')
_('%d seconds')

def print_timedelta(value, req, props, displaytime=True):
    if isinstance(value, int):
        # `date - date`, unlike `datetime - datetime` gives an int
        # (number of days), not a timedelta
        # XXX should rql be fixed to return Int instead of Interval in
        #     that case? that would be probably the proper fix but we
        #     loose information on the way...
        value = timedelta(days=value)
    if value.days > 730 or value.days < -730: # 2 years
        return req._('%d years') % (value.days // 365)
    elif value.days > 60 or value.days < -60: # 2 months
        return req._('%d months') % (value.days // 30)
    elif value.days > 14 or value.days < -14: # 2 weeks
        return req._('%d weeks') % (value.days // 7)
    elif value.days > 2 or value.days < -2:
        return req._('%d days') % int(value.days)
    else:
        minus = 1 if value.days >= 0 else -1
        if value.seconds > 3600:
            return req._('%d hours') % (int(value.seconds // 3600) * minus)
        elif value.seconds >= 120:
            return req._('%d minutes') % (int(value.seconds // 60) * minus)
        else:
            return req._('%d seconds') % (int(value.seconds) * minus)

def print_boolean(value, req, props, displaytime=True):
    if value:
        return req._('yes')
    return req._('no')

def print_float(value, req, props, displaytime=True):
    return str(req.property_value('ui.float-format') % value) # XXX cast needed ?

PRINTERS = {
    'Bytes': print_bytes,
    'String': print_string,
    'Int': print_int,
    'BigInt': print_int,
    'Date': print_date,
    'Time': print_time,
    'TZTime': print_tztime,
    'Datetime': print_datetime,
    'TZDatetime': print_tzdatetime,
    'Boolean': print_boolean,
    'Float': print_float,
    'Decimal': print_float,
    'Interval': print_timedelta,
    }

def css_em_num_value(vreg, propname, default):
    """ we try to read an 'em' css property
    if we get another unit we're out of luck and resort to the given default
    (hence, it is strongly advised not to specify but ems for this css prop)
    """
    propvalue = vreg.config.uiprops[propname].lower().strip()
    if propvalue.endswith('em'):
        try:
            return float(propvalue[:-2])
        except Exception:
            vreg.warning('css property %s looks malformed (%r)',
                         propname, propvalue)
    else:
        vreg.warning('css property %s should use em (currently is %r)',
                     propname, propvalue)
    return default

# text publishing #############################################################

from cubicweb.ext.markdown import markdown_publish # pylint: disable=W0611

try:
    from cubicweb.ext.rest import rest_publish # pylint: disable=W0611
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
    return u'<a href="%s">%s</a>' % (view._cw.build_url(rql=rql), descr)

def html_publish(view, text):
    """replace <ref rql=''> links by <a href="...">"""
    if not text:
        return u''
    return REF_PROG.sub(lambda obj, view=view:_subst_rql(view, obj), text)

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

REM_ROOT_HTML_TAGS = re.compile('</(body|html)>', re.U)

from lxml import etree, html
from lxml.html import clean, defs

ALLOWED_TAGS = (defs.general_block_tags | defs.list_tags | defs.table_tags |
                defs.phrase_tags | defs.font_style_tags |
                set(('span', 'a', 'br', 'img', 'map', 'area', 'sub', 'sup', 'canvas'))
                )

CLEANER = clean.Cleaner(allow_tags=ALLOWED_TAGS, remove_unknown_tags=False,
                        style=True, safe_attrs_only=True,
                        add_nofollow=False,
                        )

def soup2xhtml(data, encoding):
    """tidy html soup by allowing some element tags and return the result
    """
    # remove spurious </body> and </html> tags, then normalize line break
    # (see http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1)
    data = REM_ROOT_HTML_TAGS.sub('', u'\n'.join(data.splitlines()))
    xmltree = etree.HTML(CLEANER.clean_html('<div>%s</div>' % data))
    # NOTE: lxml 2.0 does support encoding='unicode', but last time I (syt)
    # tried I got weird results (lxml 2.2.8)
    body = etree.tostring(xmltree[0], encoding=encoding)
    # remove <body> and </body> and decode to unicode
    snippet = body[6:-7].decode(encoding)
    # take care to bad xhtml (for instance starting with </div>) which
    # may mess with the <div> we added below. Only remove it if it's
    # still there...
    if snippet.startswith('<div>') and snippet.endswith('</div>'):
        snippet = snippet[5:-6]
    return snippet

    # lxml.Cleaner envelops text elements by internal logic (not accessible)
    # see http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1
    # TODO drop attributes in elements
    # TODO add policy configuration (content only, embedded content, ...)
    # XXX this is buggy for "<p>text1</p><p>text2</p>"...
    # XXX drop these two snippets action and follow the lxml behaviour
    # XXX (tests need to be updated)
    # if snippet.startswith('<div>') and snippet.endswith('</div>'):
    #     snippet = snippet[5:-6]
    # if snippet.startswith('<p>') and snippet.endswith('</p>'):
    #     snippet = snippet[3:-4]
    return snippet.decode(encoding)

if hasattr(etree.HTML('<div>test</div>'), 'iter'): # XXX still necessary?
    # pylint: disable=E0102
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

class _JSId(object):
    def __init__(self, id, parent=None):
        self.id = id
        self.parent = parent
    def __str__(self):
        if self.parent:
            return u'%s.%s' % (self.parent, self.id)
        return str(self.id)
    def __getattr__(self, attr):
        return _JSId(attr, self)
    def __call__(self, *args):
        return _JSCallArgs(args, self)

class _JSCallArgs(_JSId):
    def __init__(self, args, parent=None):
        assert isinstance(args, tuple)
        self.args = args
        self.parent = parent
    def __str__(self):
        args = []
        for arg in self.args:
            args.append(js_dumps(arg))
        if self.parent:
            return u'%s(%s)' % (self.parent, ','.join(args))
        return ','.join(args)

class _JS(object):
    def __getattr__(self, attr):
        return _JSId(attr)

js = _JS()
js.__doc__ = """\
magic object to return strings suitable to call some javascript function with
the given arguments (which should be correctly typed).

>>> str(js.pouet(1, "2"))
'pouet(1,"2")'
>>> str(js.cw.pouet(1, "2"))
'cw.pouet(1,"2")'
>>> str(js.cw.pouet(1, "2").pouet(None))
'cw.pouet(1,"2").pouet(null)'
>>> str(js.cw.pouet(1, JSString("$")).pouet(None))
'cw.pouet(1,$).pouet(null)'
>>> str(js.cw.pouet(1, {'callback': JSString("cw.cb")}).pouet(None))
'cw.pouet(1,{callback: cw.cb}).pouet(null)'
"""

def domid(string):
    """return a valid DOM id from a string (should also be usable in jQuery
    search expression...)
    """
    return string.replace('.', '_').replace('-', '_')

HTML4_EMPTY_TAGS = frozenset(('base', 'meta', 'link', 'hr', 'br', 'param',
                              'img', 'area', 'input', 'col'))

def sgml_attributes(attrs):
    return u' '.join(u'%s="%s"' % (attr, xml_escape(str(value)))
                     for attr, value in sorted(attrs.items())
                     if value is not None)

def simple_sgml_tag(tag, content=None, escapecontent=True, **attrs):
    """generation of a simple sgml tag (eg without children tags) easier

    content and attri butes will be escaped
    """
    value = u'<%s' % tag
    if attrs:
        try:
            attrs['class'] = attrs.pop('klass')
        except KeyError:
            pass
        value += u' ' + sgml_attributes(attrs)
    if content:
        if escapecontent:
            content = xml_escape(str(content))
        value += u'>%s</%s>' % (content, tag)
    else:
        if tag in HTML4_EMPTY_TAGS:
            value += u' />'
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
    if isinstance(res, bytes):
        res = res.decode('UTF8')
    return res

# traceback formatting ########################################################

import traceback

def exc_message(ex, encoding):
    excmsg = str(ex)
    exctype = ex.__class__.__name__
    return u'%s: %s' % (exctype, excmsg)


def rest_traceback(info, exception):
    """return a unicode ReST formated traceback"""
    res = [u'Traceback\n---------\n::\n']
    for stackentry in traceback.extract_tb(info[2]):
        res.append(u'\tFile %s, line %s, function %s' % tuple(stackentry[:3]))
        if stackentry[3]:
            data = xml_escape(stackentry[3])
            res.append(u'\t  %s' % data)
    res.append(u'\n')
    try:
        res.append(u'\t Error: %s\n' % exception)
    except Exception:
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
            string = xml_escape(stackentry[3])
            strings.append(u'&#160;&#160;%s<br/>\n' % (string))
        # add locals info for each entry
        try:
            local_context = tcbk.tb_frame.f_locals
            html_info = []
            chars = 0
            for name, value in local_context.items():
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
    """proxies calls to csv.writer.writerow to be able to deal with unicode

    Under Python 3, this code no longer encodes anything."""

    def __init__(self, wfunc, encoding, **kwargs):
        self.writer = csv.writer(self, **kwargs)
        self.wfunc = wfunc
        self.encoding = encoding

    def write(self, data):
        self.wfunc(data)

    def writerow(self, row):
        self.writer.writerow(row)
        return

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
            if isinstance(ret, str):
                return ret[:self.maxsize]
            return ret
        return newfunc


def htmlescape(function):
    def newfunc(*args, **kwargs):
        ret = function(*args, **kwargs)
        assert isinstance(ret, str)
        return xml_escape(ret)
    return newfunc
