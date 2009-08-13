"""Base class for request/session

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: Library General Public License version 2 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from urllib import quote as urlquote, unquote as urlunquote
from datetime import time, datetime, timedelta

from logilab.common.decorators import cached

from cubicweb import Unauthorized, typed_eid
from cubicweb.rset import ResultSet
from cubicweb.utils import ustrftime, strptime, todate, todatetime

ONESECOND = timedelta(0, 1, 0)
CACHE_REGISTRY = {}


class Cache(dict):
    def __init__(self):
        super(Cache, self).__init__()
        _now = datetime.now()
        self.cache_creation_date = _now
        self.latest_cache_lookup = _now


class RequestSessionBase(object):
    """base class containing stuff shared by server session and web request
    """
    def __init__(self, vreg):
        self.vreg = vreg
        try:
            encoding = vreg.property_value('ui.encoding')
        except: # no vreg or property not registered
            encoding = 'utf-8'
        self.encoding = encoding
        # cache result of execution for (rql expr / eids),
        # should be emptied on commit/rollback of the server session / web
        # connection
        self.local_perm_cache = {}
        self._ = unicode

    def property_value(self, key):
        """return value of the property with the given key, giving priority to
        user specific value if any, else using site value
        """
        if self.user:
            return self.user.property_value(key)
        return self.vreg.property_value(key)

    def etype_rset(self, etype, size=1):
        """return a fake result set for a particular entity type"""
        rset = ResultSet([('A',)]*size, '%s X' % etype,
                         description=[(etype,)]*size)
        def get_entity(row, col=0, etype=etype, req=self, rset=rset):
            return req.vreg.etype_class(etype)(req, rset, row, col)
        rset.get_entity = get_entity
        return self.decorate_rset(rset)

    def eid_rset(self, eid, etype=None):
        """return a result set for the given eid without doing actual query
        (we have the eid, we can suppose it exists and user has access to the
        entity)
        """
        eid = typed_eid(eid)
        if etype is None:
            etype = self.describe(eid)[0]
        rset = ResultSet([(eid,)], 'Any X WHERE X eid %(x)s', {'x': eid},
                         [(etype,)])
        return self.decorate_rset(rset)

    def empty_rset(self):
        """return a result set for the given eid without doing actual query
        (we have the eid, we can suppose it exists and user has access to the
        entity)
        """
        return self.decorate_rset(ResultSet([], 'Any X WHERE X eid -1'))

    def entity_from_eid(self, eid, etype=None):
        """return an entity instance for the given eid. No query is done"""
        try:
            return self.entity_cache(eid)
        except KeyError:
            rset = self.eid_rset(eid, etype)
            entity = rset.get_entity(0, 0)
            self.set_entity_cache(entity)
            return entity

    def entity_cache(self, eid):
        raise KeyError

    def set_entity_cache(self, entity):
        pass

    def ensure_ro_rql(self, rql):
        """raise an exception if the given rql is not a select query"""
        first = rql.split(' ', 1)[0].lower()
        if first in ('insert', 'set', 'delete'):
            raise Unauthorized(self._('only select queries are authorized'))

    def get_cache(self, cachename):
        """
        NOTE: cachename should be dotted names as in :
        - cubicweb.mycache
        - cubes.blog.mycache
        - etc.
        """
        if cachename in CACHE_REGISTRY:
            cache = CACHE_REGISTRY[cachename]
        else:
            cache = CACHE_REGISTRY[cachename] = Cache()
        _now = datetime.now()
        if _now > cache.latest_cache_lookup + ONESECOND:
            ecache = self.execute(
                'Any C,T WHERE C is CWCache, C name %(name)s, C timestamp T',
                {'name':cachename}).get_entity(0,0)
            cache.latest_cache_lookup = _now
            if not ecache.valid(cache.cache_creation_date):
                cache.clear()
                cache.cache_creation_date = _now
        return cache

    # url generation methods ##################################################

    def build_url(self, *args, **kwargs):
        """return an absolute URL using params dictionary key/values as URL
        parameters. Values are automatically URL quoted, and the
        publishing method to use may be specified or will be guessed.
        """
        # use *args since we don't want first argument to be "anonymous" to
        # avoid potential clash with kwargs
        if args:
            assert len(args) == 1, 'only 0 or 1 non-named-argument expected'
            method = args[0]
        else:
            method = None
        # XXX I (adim) think that if method is passed explicitly, we should
        #     not try to process it and directly call req.build_url()
        if method is None:
            if self.from_controller() == 'view' and not '_restpath' in kwargs:
                method = self.relative_path(includeparams=False) or 'view'
            else:
                method = 'view'
        base_url = kwargs.pop('base_url', None)
        if base_url is None:
            base_url = self.base_url()
        if '_restpath' in kwargs:
            assert method == 'view', method
            path = kwargs.pop('_restpath')
        else:
            path = method
        if not kwargs:
            return u'%s%s' % (base_url, path)
        return u'%s%s?%s' % (base_url, path, self.build_url_params(**kwargs))


    def build_url_params(self, **kwargs):
        """return encoded params to incorporate them in an URL"""
        args = []
        for param, values in kwargs.items():
            if not isinstance(values, (list, tuple)):
                values = (values,)
            for value in values:
                args.append(u'%s=%s' % (param, self.url_quote(value)))
        return '&'.join(args)

    def url_quote(self, value, safe=''):
        """urllib.quote is not unicode safe, use this method to do the
        necessary encoding / decoding. Also it's designed to quote each
        part of a url path and so the '/' character will be encoded as well.
        """
        if isinstance(value, unicode):
            quoted = urlquote(value.encode(self.encoding), safe=safe)
            return unicode(quoted, self.encoding)
        return urlquote(str(value), safe=safe)

    def url_unquote(self, quoted):
        """returns a unicode unquoted string

        decoding is based on `self.encoding` which is the encoding
        used in `url_quote`
        """
        if isinstance(quoted, unicode):
            quoted = quoted.encode(self.encoding)
        try:
            return unicode(urlunquote(quoted), self.encoding)
        except UnicodeDecodeError: # might occurs on manually typed URLs
            return unicode(urlunquote(quoted), 'iso-8859-1')

    # bound user related methods ###############################################

    @cached
    def user_data(self):
        """returns a dictionnary with this user's information"""
        userinfo = {}
        if self.is_internal_session:
            userinfo['login'] = "cubicweb"
            userinfo['name'] = "cubicweb"
            userinfo['email'] = ""
            return userinfo
        user = self.actual_session().user
        rql = "Any F,S,A where U eid %(x)s, U firstname F, U surname S, U primary_email E, E address A"
        try:
            firstname, lastname, email = self.execute(rql, {'x': user.eid}, 'x')[0]
            if firstname is None and lastname is None:
                userinfo['name'] = ''
            else:
                userinfo['name'] = ("%s %s" % (firstname, lastname))
            userinfo['email'] = email
        except IndexError:
            userinfo['name'] = None
            userinfo['email'] = None
        userinfo['login'] = user.login
        return userinfo

    def is_internal_session(self):
        """overrided on the server-side"""
        return False

    # formating methods #######################################################

    def format_date(self, date, date_format=None, time=False):
        """return a string for a date time according to instance's
        configuration
        """
        if date:
            if date_format is None:
                if time:
                    date_format = self.property_value('ui.datetime-format')
                else:
                    date_format = self.property_value('ui.date-format')
            return ustrftime(date, date_format)
        return u''

    def format_time(self, time):
        """return a string for a time according to instance's
        configuration
        """
        if time:
            return ustrftime(time, self.property_value('ui.time-format'))
        return u''

    def format_float(self, num):
        """return a string for floating point number according to instance's
        configuration
        """
        if num:
            return self.property_value('ui.float-format') % num
        return u''

    def parse_datetime(self, value, etype='Datetime'):
        """get a datetime or time from a string (according to etype)
        Datetime formatted as Date are accepted
        """
        assert etype in ('Datetime', 'Date', 'Time'), etype
        # XXX raise proper validation error
        if etype == 'Datetime':
            format = self.property_value('ui.datetime-format')
            try:
                return todatetime(strptime(value, format))
            except ValueError:
                pass
        elif etype == 'Time':
            format = self.property_value('ui.time-format')
            try:
                # (adim) I can't find a way to parse a Time with a custom format
                date = strptime(value, format) # this returns a DateTime
                return time(date.hour, date.minute, date.second)
            except ValueError:
                raise ValueError('can\'t parse %r (expected %s)' % (value, format))
        try:
            format = self.property_value('ui.date-format')
            dt = strptime(value, format)
            if etype == 'Datetime':
                return todatetime(dt)
            return todate(dt)
        except ValueError:
            raise ValueError('can\'t parse %r (expected %s)' % (value, format))

    # abstract methods to override according to the web front-end #############

    def base_url(self):
        """return the root url of the instance"""
        raise NotImplementedError

    def decorate_rset(self, rset):
        """add vreg/req (at least) attributes to the given result set """
        raise NotImplementedError

    def describe(self, eid):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        raise NotImplementedError
