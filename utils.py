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
"""Some utilities for CubicWeb server/clients."""

__docformat__ = "restructuredtext en"

import os
import sys
import decimal
import datetime
import random
from inspect import getargspec
from itertools import repeat
from uuid import uuid4
from warnings import warn

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

_MARKER = object()

# initialize random seed from current time
random.seed()

def make_uid(key=None):
    """Return a unique identifier string.

    if specified, `key` is used to prefix the generated uid so it can be used
    for instance as a DOM id or as sql table names.

    See uuid.uuid4 documentation for the shape of the generated identifier, but
    this is basicallly a 32 bits hexadecimal string.
    """
    if key is None:
        return uuid4().hex
    return str(key) + uuid4().hex


def support_args(callable, *argnames):
    """return true if the callable support given argument names"""
    if isinstance(callable, type):
        callable = callable.__init__
    argspec = getargspec(callable)
    if argspec[2]:
        return True
    for argname in argnames:
        if argname not in argspec[0]:
            return False
    return True


class wrap_on_write(object):
    """ Sometimes it is convenient to NOT write some container element
    if it happens that there is nothing to be written within,
    but this cannot be known beforehand.
    Hence one can do this:

    .. sourcecode:: python

       with wrap_on_write(w, '<div class="foo">', '</div>') as wow:
           component.render_stuff(wow)
    """
    def __init__(self, w, tag, closetag=None):
        self.written = False
        self.tag = unicode(tag)
        self.closetag = closetag
        self.w = w

    def __enter__(self):
        return self

    def __call__(self, data):
        if self.written is False:
            self.w(self.tag)
            self.written = True
        self.w(data)

    def __exit__(self, exctype, value, traceback):
        if self.written is True:
            if self.closetag:
                self.w(unicode(self.closetag))
            else:
                self.w(self.tag.replace('<', '</', 1))


# use networkX instead ?
# http://networkx.lanl.gov/reference/algorithms.traversal.html#module-networkx.algorithms.traversal.astar
def transitive_closure_of(entity, rtype, _seen=None):
    """return transitive closure *for the subgraph starting from the given
    entity* (eg 'parent' entities are not included in the results)
    """
    if _seen is None:
        _seen = set()
    _seen.add(entity.eid)
    yield entity
    for child in getattr(entity, rtype):
        if child.eid in _seen:
            continue
        for subchild in transitive_closure_of(child, rtype, _seen):
            yield subchild


class SizeConstrainedList(list):
    """simple list that makes sure the list does not get bigger than a given
    size.

    when the list is full and a new element is added, the first element of the
    list is removed before appending the new one

    >>> l = SizeConstrainedList(2)
    >>> l.append(1)
    >>> l.append(2)
    >>> l
    [1, 2]
    >>> l.append(3)
    >>> l
    [2, 3]
    """
    def __init__(self, maxsize):
        self.maxsize = maxsize

    def append(self, element):
        if len(self) == self.maxsize:
            del self[0]
        super(SizeConstrainedList, self).append(element)

    def extend(self, sequence):
        super(SizeConstrainedList, self).extend(sequence)
        keepafter = len(self) - self.maxsize
        if keepafter > 0:
            del self[:keepafter]

    __iadd__ = extend


class RepeatList(object):
    """fake a list with the same element in each row"""
    __slots__ = ('_size', '_item')
    def __init__(self, size, item):
        self._size = size
        self._item = item
    def __repr__(self):
        return '<cubicweb.utils.RepeatList at %s item=%s size=%s>' % (
            id(self), self._item, self._size)
    def __len__(self):
        return self._size
    def __nonzero__(self):
        return self._size
    def __iter__(self):
        return repeat(self._item, self._size)
    def __getitem__(self, index):
        return self._item
    def __delitem__(self, idc):
        assert self._size > 0
        self._size -= 1
    def __getslice__(self, i, j):
        # XXX could be more efficient, but do we bother?
        return ([self._item] * self._size)[i:j]
    def __add__(self, other):
        if isinstance(other, RepeatList):
            if other._item == self._item:
                return RepeatList(self._size + other._size, self._item)
            return ([self._item] * self._size) + other[:]
        return ([self._item] * self._size) + other
    def __radd__(self, other):
        if isinstance(other, RepeatList):
            if other._item == self._item:
                return RepeatList(self._size + other._size, self._item)
            return other[:] + ([self._item] * self._size)
        return other[:] + ([self._item] * self._size)
    def __eq__(self, other):
        if isinstance(other, RepeatList):
            return other._size == self._size and other._item == self._item
        return self[:] == other
    def pop(self, i):
        self._size -= 1


class UStringIO(list):
    """a file wrapper which automatically encode unicode string to an encoding
    specifed in the constructor
    """

    def __nonzero__(self):
        return True

    def write(self, value):
        assert isinstance(value, unicode), u"unicode required not %s : %s"\
                                     % (type(value).__name__, repr(value))
        self.append(value)

    def getvalue(self):
        return u''.join(self)

    def __repr__(self):
        return '<%s at %#x>' % (self.__class__.__name__, id(self))


class HTMLHead(UStringIO):
    """wraps HTML header's stream

    Request objects use a HTMLHead instance to ease adding of
    javascripts and stylesheets
    """
    js_unload_code = u'''if (typeof(pageDataUnloaded) == 'undefined') {
    jQuery(window).unload(unloadPageData);
    pageDataUnloaded = true;
}'''
    # Making <script> tag content work properly with all possible
    # content-types (xml/html) and all possible browsers is very
    # tricky, see http://www.hixie.ch/advocacy/xhtml for an in-depth discussion
    xhtml_safe_script_opening = u'<script type="text/javascript"><!--//--><![CDATA[//><!--\n'
    xhtml_safe_script_closing = u'\n//--><!]]></script>'

    def __init__(self, datadir_url=None):
        super(HTMLHead, self).__init__()
        self.jsvars = []
        self.jsfiles = []
        self.cssfiles = []
        self.ie_cssfiles = []
        self.post_inlined_scripts = []
        self.pagedata_unload = False
        self.datadir_url = datadir_url


    def add_raw(self, rawheader):
        self.write(rawheader)

    def define_var(self, var, value, override=True):
        """adds a javascript var declaration / assginment in the header

        :param var: the variable name
        :param value: the variable value (as a raw python value,
                      it will be jsonized later)
        :param override: if False, don't set the variable value if the variable
                         is already defined. Default is True.
        """
        self.jsvars.append( (var, value, override) )

    def add_post_inline_script(self, content):
        self.post_inlined_scripts.append(content)

    def add_onload(self, jscode, jsoncall=_MARKER):
        if jsoncall is not _MARKER:
            warn('[3.7] specifying jsoncall is not needed anymore',
                 DeprecationWarning, stacklevel=2)
        self.add_post_inline_script(u"""$(cw).one('server-response', function(event) {
%s});""" % jscode)


    def add_js(self, jsfile):
        """adds `jsfile` to the list of javascripts used in the webpage

        This function checks if the file has already been added
        :param jsfile: the script's URL
        """
        if jsfile not in self.jsfiles:
            self.jsfiles.append(jsfile)

    def add_css(self, cssfile, media='all'):
        """adds `cssfile` to the list of javascripts used in the webpage

        This function checks if the file has already been added
        :param cssfile: the stylesheet's URL
        """
        if (cssfile, media) not in self.cssfiles:
            self.cssfiles.append( (cssfile, media) )

    def add_ie_css(self, cssfile, media='all', iespec=u'[if lt IE 8]'):
        """registers some IE specific CSS"""
        if (cssfile, media, iespec) not in self.ie_cssfiles:
            self.ie_cssfiles.append( (cssfile, media, iespec) )

    def add_unload_pagedata(self):
        """registers onunload callback to clean page data on server"""
        if not self.pagedata_unload:
            self.post_inlined_scripts.append(self.js_unload_code)
            self.pagedata_unload = True

    def concat_urls(self, urls):
        """concatenates urls into one url usable by Apache mod_concat

        This method returns the url without modifying it if there is only
        one element in the list
        :param urls: list of local urls/filenames to concatenate
        """
        if len(urls) == 1:
            return urls[0]
        len_prefix = len(self.datadir_url)
        concated = u','.join(url[len_prefix:] for url in urls)
        return (u'%s??%s' % (self.datadir_url, concated))

    def group_urls(self, urls_spec):
        """parses urls_spec in order to generate concatenated urls
        for js and css includes

        This method checks if the file is local and if it shares options
        with direct neighbors
        :param urls_spec: entire list of urls/filenames to inspect
        """
        concatable = []
        prev_islocal = False
        prev_key = None
        for url, key in urls_spec:
            islocal = url.startswith(self.datadir_url)
            if concatable and (islocal != prev_islocal or key != prev_key):
                yield (self.concat_urls(concatable), prev_key)
                del concatable[:]
            if not islocal:
                yield (url, key)
            else:
                concatable.append(url)
            prev_islocal = islocal
            prev_key = key
        if concatable:
            yield (self.concat_urls(concatable), prev_key)


    def getvalue(self, skiphead=False):
        """reimplement getvalue to provide a consistent (and somewhat browser
        optimzed cf. http://stevesouders.com/cuzillion) order in external
        resources declaration
        """
        w = self.write
        # 1/ variable declaration if any
        if self.jsvars:
            w(self.xhtml_safe_script_opening)
            for var, value, override in self.jsvars:
                vardecl = u'%s = %s;' % (var, json.dumps(value))
                if not override:
                    vardecl = (u'if (typeof %s == "undefined") {%s}' %
                               (var, vardecl))
                w(vardecl + u'\n')
            w(self.xhtml_safe_script_closing)
        # 2/ css files
        for cssfile, media in (self.group_urls(self.cssfiles) if self.datadir_url else self.cssfiles):
            w(u'<link rel="stylesheet" type="text/css" media="%s" href="%s"/>\n' %
              (media, xml_escape(cssfile)))
        # 3/ ie css if necessary
        if self.ie_cssfiles:
            ie_cssfiles = ((x, (y, z)) for x, y, z in self.ie_cssfiles)
            for cssfile, (media, iespec) in (self.group_urls(ie_cssfiles) if self.datadir_url else ie_cssfiles):
                w(u'<!--%s>\n' % iespec)
                w(u'<link rel="stylesheet" type="text/css" media="%s" href="%s"/>\n' %
                  (media, xml_escape(cssfile)))
            w(u'<![endif]--> \n')
        # 4/ js files
        jsfiles = ((x, None) for x in self.jsfiles)
        for jsfile, media in self.group_urls(jsfiles) if self.datadir_url else jsfiles:
            if skiphead:
                # Don't insert <script> tags directly as they would be
                # interpreted directly by some browsers (e.g. IE).
                # Use <pre class="script"> tags instead and let
                # `loadAjaxHtmlHead` handle the script insertion / execution.
                w(u'<pre class="script" src="%s"></pre>\n' %
                  xml_escape(jsfile))
                # FIXME: a probably better implementation might be to add
                #        JS or CSS urls in a JS list that loadAjaxHtmlHead
                #        would iterate on and postprocess:
                #            cw._ajax_js_scripts.push('myscript.js')
                #        Then, in loadAjaxHtmlHead, do something like:
                #            jQuery.each(cw._ajax_js_script, jQuery.getScript)
            else:
                w(u'<script type="text/javascript" src="%s"></script>\n' %
                  xml_escape(jsfile))
        # 5/ post inlined scripts (i.e. scripts depending on other JS files)
        if self.post_inlined_scripts:
            if skiphead:
                for script in self.post_inlined_scripts:
                    w(u'<pre class="script">')
                    w(script)
                    w(u'</pre>')
            else:
                w(self.xhtml_safe_script_opening)
                w(u'\n\n'.join(self.post_inlined_scripts))
                w(self.xhtml_safe_script_closing)
        header = super(HTMLHead, self).getvalue()
        if skiphead:
            return header
        return u'<head>\n%s</head>\n' % header


class HTMLStream(object):
    """represents a HTML page.

    This is used my main templates so that HTML headers can be added
    at any time during the page generation.

    HTMLStream uses the (U)StringIO interface to be compliant with
    existing code.
    """

    def __init__(self, req):
        # stream for <head>
        self.head = req.html_headers
        # main stream
        self.body = UStringIO()
        self.doctype = u''
        # xmldecl and html opening tag
        self.xmldecl = u'<?xml version="1.0" encoding="%s"?>\n' % req.encoding
        self._namespaces = [('xmlns', 'http://www.w3.org/1999/xhtml'),
                            ('xmlns:cubicweb','http://www.logilab.org/2008/cubicweb')]
        self._htmlattrs = [('xml:lang', req.lang),
                           ('lang', req.lang)]
        # keep main_stream's reference on req for easier text/html demoting
        req.main_stream = self

    def add_namespace(self, prefix, uri):
        self._namespaces.append( (prefix, uri) )

    def set_namespaces(self, namespaces):
        self._namespaces = namespaces

    def add_htmlattr(self, attrname, attrvalue):
        self._htmlattrs.append( (attrname, attrvalue) )

    def set_htmlattrs(self, attrs):
        self._htmlattrs = attrs

    def set_doctype(self, doctype, reset_xmldecl=True):
        self.doctype = doctype
        if reset_xmldecl:
            self.xmldecl = u''

    def write(self, data):
        """StringIO interface: this method will be assigned to self.w
        """
        self.body.write(data)

    @property
    def htmltag(self):
        attrs = ' '.join('%s="%s"' % (attr, xml_escape(value))
                         for attr, value in (self._namespaces + self._htmlattrs))
        if attrs:
            return '<html %s>' % attrs
        return '<html>'

    def getvalue(self):
        """writes HTML headers, closes </head> tag and writes HTML body"""
        return u'%s\n%s\n%s\n%s\n%s\n</html>' % (self.xmldecl, self.doctype,
                                                 self.htmltag,
                                                 self.head.getvalue(),
                                                 self.body.getvalue())

try:
    # may not be there if cubicweb-web not installed
    if sys.version_info < (2, 6):
        import simplejson as json
    else:
        import json
except ImportError:
    json_dumps = JSString = None

else:
    from logilab.common.date import ustrftime

    class CubicWebJsonEncoder(json.JSONEncoder):
        """define a json encoder to be able to encode yams std types"""

        def default(self, obj):
            if hasattr(obj, 'eid'):
                d = obj.cw_attr_cache.copy()
                d['eid'] = obj.eid
                return d
            if isinstance(obj, datetime.datetime):
                return ustrftime(obj, '%Y/%m/%d %H:%M:%S')
            elif isinstance(obj, datetime.date):
                return ustrftime(obj, '%Y/%m/%d')
            elif isinstance(obj, datetime.time):
                return obj.strftime('%H:%M:%S')
            elif isinstance(obj, datetime.timedelta):
                return (obj.days * 24 * 60 * 60) + obj.seconds
            elif isinstance(obj, decimal.Decimal):
                return float(obj)
            try:
                return json.JSONEncoder.default(self, obj)
            except TypeError:
                # we never ever want to fail because of an unknown type,
                # just return None in those cases.
                return None

    def json_dumps(value):
        return json.dumps(value, cls=CubicWebJsonEncoder)


    class JSString(str):
        """use this string sub class in values given to :func:`js_dumps` to
        insert raw javascript chain in some JSON string
        """

    def _dict2js(d, predictable=False):
        res = [key + ': ' + js_dumps(val, predictable)
               for key, val in d.iteritems()]
        return '{%s}' % ', '.join(res)

    def _list2js(l, predictable=False):
        return '[%s]' % ', '.join([js_dumps(val, predictable) for val in l])

    def js_dumps(something, predictable=False):
        """similar as :func:`json_dumps`, except values which are instances of
        :class:`JSString` are expected to be valid javascript and will be output
        as is

        >>> js_dumps({'hop': JSString('$.hop'), 'bar': None}, predictable=True)
        '{bar: null, hop: $.hop}'
        >>> js_dumps({'hop': '$.hop'})
        '{hop: "$.hop"}'
        >>> js_dumps({'hip': {'hop': JSString('momo')}})
        '{hip: {hop: momo}}'
        """
        if isinstance(something, dict):
            return _dict2js(something, predictable)
        if isinstance(something, list):
            return _list2js(something, predictable)
        if isinstance(something, JSString):
            return something
        return json_dumps(something)


@deprecated('[3.7] merge_dicts is deprecated')
def merge_dicts(dict1, dict2):
    """update a copy of `dict1` with `dict2`"""
    dict1 = dict(dict1)
    dict1.update(dict2)
    return dict1

from logilab.common import date
_THIS_MOD_NS = globals()
for funcname in ('date_range', 'todate', 'todatetime', 'datetime2ticks',
                 'days_in_month', 'days_in_year', 'previous_month',
                 'next_month', 'first_day', 'last_day',
                 'strptime'):
    msg = '[3.6] %s has been moved to logilab.common.date' % funcname
    _THIS_MOD_NS[funcname] = deprecated(msg)(getattr(date, funcname))
