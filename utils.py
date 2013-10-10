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

from __future__ import division, with_statement

__docformat__ = "restructuredtext en"

import sys
import decimal
import datetime
import random
import re

from operator import itemgetter
from inspect import getargspec
from itertools import repeat
from uuid import uuid4
from warnings import warn
from threading import Lock
from urlparse import urlparse

from logging import getLogger

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

_MARKER = object()

# initialize random seed from current time
random.seed()

def make_uid(key=None):
    """Return a unique identifier string.

    if specified, `key` is used to prefix the generated uid so it can be used
    for instance as a DOM id or as sql table name.

    See uuid.uuid4 documentation for the shape of the generated identifier, but
    this is basically a 32 bits hexadecimal string.
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
    # py3k future warning "Overriding __eq__ blocks inheritance of __hash__ in 3.x"
    # is annoying but won't go away because we don't want to hash() the repeatlist
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
    script_opening = u'<script type="text/javascript">\n'
    script_closing = u'\n</script>'

    def __init__(self, req):
        super(HTMLHead, self).__init__()
        self.jsvars = []
        self.jsfiles = []
        self.cssfiles = []
        self.ie_cssfiles = []
        self.post_inlined_scripts = []
        self.pagedata_unload = False
        self._cw = req
        self.datadir_url = req.datadir_url

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

    def add_onload(self, jscode):
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
            w(self.script_opening)
            for var, value, override in self.jsvars:
                vardecl = u'%s = %s;' % (var, json.dumps(value))
                if not override:
                    vardecl = (u'if (typeof %s == "undefined") {%s}' %
                               (var, vardecl))
                w(vardecl + u'\n')
            w(self.script_closing)
        # 2/ css files
        ie_cssfiles = ((x, (y, z)) for x, y, z in self.ie_cssfiles)
        if self.datadir_url and self._cw.vreg.config['concat-resources']:
            cssfiles = self.group_urls(self.cssfiles)
            ie_cssfiles = self.group_urls(ie_cssfiles)
            jsfiles = (x for x, _ in self.group_urls((x, None) for x in self.jsfiles))
        else:
            cssfiles = self.cssfiles
            jsfiles = self.jsfiles
        for cssfile, media in cssfiles:
            w(u'<link rel="stylesheet" type="text/css" media="%s" href="%s"/>\n' %
              (media, xml_escape(cssfile)))
        # 3/ ie css if necessary
        if self.ie_cssfiles: # use self.ie_cssfiles because `ie_cssfiles` is a genexp
            for cssfile, (media, iespec) in ie_cssfiles:
                w(u'<!--%s>\n' % iespec)
                w(u'<link rel="stylesheet" type="text/css" media="%s" href="%s"/>\n' %
                  (media, xml_escape(cssfile)))
            w(u'<![endif]--> \n')
        # 4/ js files
        for jsfile in jsfiles:
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
                    w(xml_escape(script))
                    w(u'</pre>')
            else:
                w(self.script_opening)
                w(u'\n\n'.join(self.post_inlined_scripts))
                w(self.script_closing)
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
        self._htmlattrs = [('lang', req.lang)]
        # keep main_stream's reference on req for easier text/html demoting
        req.main_stream = self

    @deprecated('[3.17] there are no namespaces in html, xhtml is not served any longer')
    def add_namespace(self, prefix, uri):
        pass

    @deprecated('[3.17] there are no namespaces in html, xhtml is not served any longer')
    def set_namespaces(self, namespaces):
        pass

    def add_htmlattr(self, attrname, attrvalue):
        self._htmlattrs.append( (attrname, attrvalue) )

    def set_htmlattrs(self, attrs):
        self._htmlattrs = attrs

    def set_doctype(self, doctype, reset_xmldecl=None):
        self.doctype = doctype
        if reset_xmldecl is not None:
            warn('[3.17] xhtml is no more supported',
                 DeprecationWarning, stacklevel=2)

    def write(self, data):
        """StringIO interface: this method will be assigned to self.w
        """
        self.body.write(data)

    @property
    def htmltag(self):
        attrs = ' '.join('%s="%s"' % (attr, xml_escape(value))
                         for attr, value in self._htmlattrs)
        if attrs:
            return '<html %s>' % attrs
        return '<html>'

    def getvalue(self):
        """writes HTML headers, closes </head> tag and writes HTML body"""
        return u'%s\n%s\n%s\n%s\n</html>' % (self.doctype,
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
            if hasattr(obj, '__json_encode__'):
                return obj.__json_encode__()
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

    def json_dumps(value, **kwargs):
        return json.dumps(value, cls=CubicWebJsonEncoder, **kwargs)


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

PERCENT_IN_URLQUOTE_RE = re.compile(r'%(?=[0-9a-fA-F]{2})')
def js_href(javascript_code):
    """Generate a "javascript: ..." string for an href attribute.

    Some % which may be interpreted in a href context will be escaped.

    In an href attribute, url-quotes-looking fragments are interpreted before
    being given to the javascript engine. Valid url quotes are in the form
    ``%xx`` with xx being a byte in hexadecimal form. This means that ``%toto``
    will be unaltered but ``%babar`` will be mangled because ``ba`` is the
    hexadecimal representation of 186.

    >>> js_href('alert("babar");')
    'javascript: alert("babar");'
    >>> js_href('alert("%babar");')
    'javascript: alert("%25babar");'
    >>> js_href('alert("%toto %babar");')
    'javascript: alert("%toto %25babar");'
    >>> js_href('alert("%1337%");')
    'javascript: alert("%251337%");'
    """
    return 'javascript: ' + PERCENT_IN_URLQUOTE_RE.sub(r'%25', javascript_code)


def parse_repo_uri(uri):
    """ transform a command line uri into a (protocol, hostport, appid), e.g:
    <myapp>                      -> 'inmemory', None, '<myapp>'
    inmemory://<myapp>           -> 'inmemory', None, '<myapp>'
    pyro://[host][:port]         -> 'pyro', 'host:port', None
    zmqpickle://[host][:port]    -> 'zmqpickle', 'host:port', None
    """
    parseduri = urlparse(uri)
    scheme = parseduri.scheme
    if scheme == '':
        return ('inmemory', None, parseduri.path)
    if scheme == 'inmemory':
        return (scheme, None, parseduri.netloc)
    if scheme in ('pyro', 'pyroloc') or scheme.startswith('zmqpickle-'):
        return (scheme, parseduri.netloc, parseduri.path)
    raise NotImplementedError('URI protocol not implemented for `%s`' % uri)



logger = getLogger('cubicweb.utils')

class QueryCache(object):
    """ a minimalist dict-like object to be used by the querier
    and native source (replaces lgc.cache for this very usage)

    To be efficient it must be properly used. The usage patterns are
    quite specific to its current clients.

    The ceiling value should be sufficiently high, else it will be
    ruthlessly inefficient (there will be warnings when this happens).
    A good (high enough) value can only be set on a per-application
    value. A default, reasonnably high value is provided but tuning
    e.g `rql-cache-size` can certainly help.

    There are two kinds of elements to put in this cache:
    * frequently used elements
    * occasional elements

    The former should finish in the _permanent structure after some
    warmup.

    Occasional elements can be buggy requests (server-side) or
    end-user (web-ui provided) requests. These have to be cleaned up
    when they fill the cache, without evicting the usefull, frequently
    used entries.
    """
    # quite arbitrary, but we want to never
    # immortalize some use-a-little query
    _maxlevel = 15

    def __init__(self, ceiling=3000):
        self._max = ceiling
        # keys belonging forever to this cache
        self._permanent = set()
        # mapping of key (that can get wiped) to getitem count
        self._transient = {}
        self._data = {}
        self._lock = Lock()

    def __len__(self):
        with self._lock:
            return len(self._data)

    def __getitem__(self, k):
        with self._lock:
            if k in self._permanent:
                return self._data[k]
            v = self._transient.get(k, _MARKER)
            if v is _MARKER:
                self._transient[k] = 1
                return self._data[k]
            if v > self._maxlevel:
                self._permanent.add(k)
                self._transient.pop(k, None)
            else:
                self._transient[k] += 1
            return self._data[k]

    def __setitem__(self, k, v):
        with self._lock:
            if len(self._data) >= self._max:
                self._try_to_make_room()
            self._data[k] = v

    def pop(self, key, default=_MARKER):
        with self._lock:
            try:
                if default is _MARKER:
                    return self._data.pop(key)
                return self._data.pop(key, default)
            finally:
                if key in self._permanent:
                    self._permanent.remove(key)
                else:
                    self._transient.pop(key, None)

    def clear(self):
        with self._lock:
            self._clear()

    def _clear(self):
        self._permanent = set()
        self._transient = {}
        self._data = {}

    def _try_to_make_room(self):
        current_size = len(self._data)
        items = sorted(self._transient.items(), key=itemgetter(1))
        level = 0
        for k, v in items:
            self._data.pop(k, None)
            self._transient.pop(k, None)
            if v > level:
                datalen = len(self._data)
                if datalen == 0:
                    return
                if (current_size - datalen) / datalen > .1:
                    break
                level = v
        else:
            # we removed cruft but everything is permanent
            if len(self._data) >= self._max:
                logger.warning('Cache %s is full.' % id(self))
                self._clear()

    def _usage_report(self):
        with self._lock:
            return {'itemcount': len(self._data),
                    'transientcount': len(self._transient),
                    'permanentcount': len(self._permanent)}

    def popitem(self):
        raise NotImplementedError()

    def setdefault(self, key, default=None):
        raise NotImplementedError()

    def update(self, other):
        raise NotImplementedError()
