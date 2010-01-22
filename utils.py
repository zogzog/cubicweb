"""Some utilities for CubicWeb server/clients.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

import locale
import sys
import decimal
import datetime as pydatetime
from md5 import md5
from datetime import datetime, timedelta, date
from time import time, mktime
from random import randint, seed
from calendar import monthrange
import decimal

# initialize random seed from current time
seed()
try:
    strptime = datetime.strptime
except AttributeError: # py < 2.5
    from time import strptime as time_strptime
    def strptime(value, format):
        return datetime(*time_strptime(value, format)[:6])

def todate(somedate):
    """return a date from a date (leaving unchanged) or a datetime"""
    if isinstance(somedate, datetime):
        return date(somedate.year, somedate.month, somedate.day)
    assert isinstance(somedate, date), repr(somedate)
    return somedate

def todatetime(somedate):
    """return a date from a date (leaving unchanged) or a datetime"""
    # take care, datetime is a subclass of date
    if isinstance(somedate, datetime):
        return somedate
    assert isinstance(somedate, date), repr(somedate)
    return datetime(somedate.year, somedate.month, somedate.day)

def datetime2ticks(date):
    return mktime(date.timetuple()) * 1000

ONEDAY = timedelta(days=1)
ONEWEEK = timedelta(days=7)

def days_in_month(date_):
    return monthrange(date_.year, date_.month)[1]

def days_in_year(date_):
    feb = pydatetime.date(date_.year, 2, 1)
    if days_in_month(feb) == 29:
        return 366
    else:
        return 365

def previous_month(date_, nbmonth=1):
    while nbmonth:
        date_ = first_day(date_) - ONEDAY
        nbmonth -= 1
    return date_

def next_month(date_, nbmonth=1):
    while nbmonth:
        date_ = last_day(date_) + ONEDAY
        nbmonth -= 1
    return date_

def first_day(date_):
    return date(date_.year, date_.month, 1)

def last_day(date_):
    return date(date_.year, date_.month, days_in_month(date_))

def date_range(begin, end, incday=None, incmonth=None):
    """yields each date between begin and end
    :param begin: the start date
    :param end: the end date
    :param incr: the step to use to iterate over dates. Default is
                 one day.
    :param include: None (means no exclusion) or a function taking a
                    date as parameter, and returning True if the date
                    should be included.
    """
    assert not (incday and incmonth)
    begin = todate(begin)
    end = todate(end)
    if incmonth:
        while begin < end:
            begin = next_month(begin, incmonth)
            yield begin
    else:
        if not incday:
            incr = ONEDAY
        else:
            incr = timedelta(incday)
        while begin <= end:
           yield begin
           begin += incr

def ustrftime(date, fmt='%Y-%m-%d'):
    """like strftime, but returns a unicode string instead of an encoded
    string which' may be problematic with localized date.

    encoding is guessed by locale.getpreferredencoding()
    """
    # date format may depend on the locale
    encoding = locale.getpreferredencoding(do_setlocale=False) or 'UTF-8'
    return unicode(date.strftime(str(fmt)), encoding)


if sys.version_info[:2] < (2, 5):
    def make_uid(key):
        """forge a unique identifier
        not that unique on win32"""
        msg = str(key) + "%.10f" % time() + str(randint(0, 1000000))
        return md5(msg).hexdigest()
else:
    from uuid import uuid4
    def make_uid(key):
        # remove dash, generated uid are used as identifier sometimes (sql table
        # names at least)
        return str(key) + str(uuid4()).replace('-', '')


def dump_class(cls, clsname):
    """create copy of a class by creating an empty class inheriting
    from the given cls.

    Those class will be used as place holder for attribute and relation
    description
    """
    # type doesn't accept unicode name
    # return type.__new__(type, str(clsname), (cls,), {})
    # __autogenerated__ attribute is just a marker
    return type(str(clsname), (cls,), {'__autogenerated__': True})


def merge_dicts(dict1, dict2):
    """update a copy of `dict1` with `dict2`"""
    dict1 = dict(dict1)
    dict1.update(dict2)
    return dict1


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

    def add_onload(self, jscode, jsoncall=False):
        if jsoncall:
            self.add_post_inline_script(u"""jQuery(CubicWeb).bind('ajax-loaded', function(event) {
%s
});""" % jscode)
        else:
            self.add_post_inline_script(u"""jQuery(document).ready(function () {
 %s
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

    def add_ie_css(self, cssfile, media='all'):
        """registers some IE specific CSS"""
        if (cssfile, media) not in self.ie_cssfiles:
            self.ie_cssfiles.append( (cssfile, media) )

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
            w(u'<!--[if lt IE 8]>\n')
            for cssfile, media in self.ie_cssfiles:
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
            if isinstance(obj, pydatetime.datetime):
                return obj.strftime('%Y/%m/%d %H:%M:%S')
            elif isinstance(obj, pydatetime.date):
                return obj.strftime('%Y/%m/%d')
            elif isinstance(obj, pydatetime.time):
                return obj.strftime('%H:%M:%S')
            elif isinstance(obj, pydatetime.timedelta):
                return (obj.days * 24 * 60 * 60) + obj.seconds
            elif isinstance(obj, decimal.Decimal):
                return float(obj)
            try:
                return JSONEncoder.default(self, obj)
            except TypeError:
                # we never ever want to fail because of an unknown type,
                # just return None in those cases.
                return None
