"""Some utilities for CubicWeb server/clients.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
import decimal
import datetime
import random
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


def dump_class(cls, clsname):
    """create copy of a class by creating an empty class inheriting
    from the given cls.

    Those class will be used as place holder for attribute and relation
    description
    """
    # type doesn't accept unicode name
    # return type.__new__(type, str(clsname), (cls,), {})
    # __autogenerated__ attribute is just a marker
    return type(str(clsname), (cls,), {'__autogenerated__': True,
                                       '__doc__': cls.__doc__,
                                       '__module__': cls.__module__})


# use networkX instead ?
# http://networkx.lanl.gov/reference/algorithms.traversal.html#module-networkx.algorithms.traversal.astar
def transitive_closure_of(entity, relname, _seen=None):
    """return transitive closure *for the subgraph starting from the given
    entity* (eg 'parent' entities are not included in the results)
    """
    if _seen is None:
        _seen = set()
    _seen.add(entity.eid)
    yield entity
    for child in getattr(entity, relname):
        if child.eid in _seen:
            continue
        for subchild in transitive_closure_of(child, relname, _seen):
            yield subchild


class SizeConstrainedList(list):
    """simple list that makes sure the list does not get bigger
    than a given size.

    when the list is full and a new element is added, the first
    element of the list is removed before appending the new one

    >>> l = SizeConstrainedList(2)
    >>> l.append(1)
    >>> l.append(2)
    >>> l
    [1, 2]
    >>> l.append(3)
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
    js_unload_code = u'jQuery(window).unload(unloadPageData);'

    def __init__(self):
        super(HTMLHead, self).__init__()
        self.jsvars = []
        self.jsfiles = []
        self.cssfiles = []
        self.ie_cssfiles = []
        self.post_inlined_scripts = []
        self.pagedata_unload = False


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
        self.add_post_inline_script(u"""jQuery(CubicWeb).one('server-response', function(event) {
});""" % jscode)


    def add_js(self, jsfile):
        """adds `jsfile` to the list of javascripts used in the webpage

        This function checks if the file has already been added
        :param jsfile: the script's URL
        """
        if jsfile not in self.jsfiles:
            self.jsfiles.append(jsfile)

    def add_css(self, cssfile, media):
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

    def getvalue(self, skiphead=False):
        """reimplement getvalue to provide a consistent (and somewhat browser
        optimzed cf. http://stevesouders.com/cuzillion) order in external
        resources declaration
        """
        w = self.write
        # 1/ variable declaration if any
        if self.jsvars:
            w(u'<script type="text/javascript"><!--//--><![CDATA[//><!--\n')
            for var, value, override in self.jsvars:
                vardecl = u'%s = %s;' % (var, dumps(value))
                if not override:
                    vardecl = (u'if (typeof %s == "undefined") {%s}' %
                               (var, vardecl))
                w(vardecl + u'\n')
            w(u'//--><!]]></script>\n')
        # 2/ css files
        for cssfile, media in self.cssfiles:
            w(u'<link rel="stylesheet" type="text/css" media="%s" href="%s"/>\n' %
              (media, xml_escape(cssfile)))
        # 3/ ie css if necessary
        if self.ie_cssfiles:
            for cssfile, media, iespec in self.ie_cssfiles:
                w(u'<!--%s>\n' % iespec)
                w(u'<link rel="stylesheet" type="text/css" media="%s" href="%s"/>\n' %
                  (media, xml_escape(cssfile)))
            w(u'<![endif]--> \n')
        # 4/ js files
        for jsfile in self.jsfiles:
            w(u'<script type="text/javascript" src="%s"></script>\n' %
              xml_escape(jsfile))
        # 5/ post inlined scripts (i.e. scripts depending on other JS files)
        if self.post_inlined_scripts:
            w(u'<script type="text/javascript">\n')
            w(u'\n\n'.join(self.post_inlined_scripts))
            w(u'\n</script>\n')
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
        self.htmltag = u'<html xmlns="http://www.w3.org/1999/xhtml" ' \
                       'xmlns:cubicweb="http://www.logilab.org/2008/cubicweb" ' \
                       'xml:lang="%s" lang="%s">' % (req.lang, req.lang)
        # keep main_stream's reference on req for easier text/html demoting
        req.main_stream = self

    def write(self, data):
        """StringIO interface: this method will be assigned to self.w
        """
        self.body.write(data)

    def getvalue(self):
        """writes HTML headers, closes </head> tag and writes HTML body"""
        return u'%s\n%s\n%s\n%s\n%s\n</html>' % (self.xmldecl, self.doctype,
                                                 self.htmltag,
                                                 self.head.getvalue(),
                                                 self.body.getvalue())


def can_do_pdf_conversion(__answer=[None]):
    """pdf conversion depends on
    * pysixt (python package)
    * fop 0.9x
    """
    if __answer[0] is not None:
        return __answer[0]
    try:
        import pysixt
    except ImportError:
        __answer[0] = False
        return False
    from subprocess import Popen, STDOUT
    import os
    try:
        Popen(['/usr/bin/fop', '-q'],
              stdout=open(os.devnull, 'w'),
              stderr=STDOUT)
    except OSError, e:
        print e
        __answer[0] = False
        return False
    __answer[0] = True
    return True


try:
    # may not be there if cubicweb-web not installed
    from simplejson import dumps, JSONEncoder
except ImportError:
    pass
else:

    class CubicWebJsonEncoder(JSONEncoder):
        """define a simplejson encoder to be able to encode yams std types"""
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return obj.strftime('%Y/%m/%d %H:%M:%S')
            elif isinstance(obj, datetime.date):
                return obj.strftime('%Y/%m/%d')
            elif isinstance(obj, datetime.time):
                return obj.strftime('%H:%M:%S')
            elif isinstance(obj, datetime.timedelta):
                return (obj.days * 24 * 60 * 60) + obj.seconds
            elif isinstance(obj, decimal.Decimal):
                return float(obj)
            try:
                return JSONEncoder.default(self, obj)
            except TypeError:
                # we never ever want to fail because of an unknown type,
                # just return None in those cases.
                return None


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
                 'next_month', 'first_day', 'last_day', 'ustrftime',
                 'strptime'):
    msg = '[3.6] %s has been moved to logilab.common.date' % funcname
    _THIS_MOD_NS[funcname] = deprecated(msg)(getattr(date, funcname))
