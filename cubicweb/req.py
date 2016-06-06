# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Base class for request/session"""

__docformat__ = "restructuredtext en"

from warnings import warn
from datetime import time, datetime, timedelta

from six import PY2, PY3, text_type
from six.moves.urllib.parse import (parse_qs, parse_qsl,
                                    quote as urlquote, unquote as urlunquote,
                                    urlsplit, urlunsplit)

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated
from logilab.common.date import ustrftime, strptime, todate, todatetime

from rql.utils import rqlvar_maker

from cubicweb import (Unauthorized, NoSelectableObject, NoResultError,
                      MultipleResultsError, uilib)
from cubicweb.rset import ResultSet

ONESECOND = timedelta(0, 1, 0)
CACHE_REGISTRY = {}


class FindEntityError(Exception):
    """raised when find_one_entity() can not return one and only one entity"""


class Cache(dict):
    def __init__(self):
        super(Cache, self).__init__()
        _now = datetime.now()
        self.cache_creation_date = _now
        self.latest_cache_lookup = _now


class RequestSessionBase(object):
    """base class containing stuff shared by server session and web request

    request/session is the main resources accessor, mainly through it's vreg
    attribute:

    :attribute vreg: the instance's registry
    :attribute vreg.schema: the instance's schema
    :attribute vreg.config: the instance's configuration
    """
    is_request = True  # False for repository session

    def __init__(self, vreg):
        self.vreg = vreg
        try:
            encoding = vreg.property_value('ui.encoding')
        except Exception:  # no vreg or property not registered
            encoding = 'utf-8'
        self.encoding = encoding
        # cache result of execution for (rql expr / eids),
        # should be emptied on commit/rollback of the server session / web
        # connection
        self.user = None
        self.local_perm_cache = {}
        self._ = text_type

    def _set_user(self, orig_user):
        """set the user for this req_session_base

        A special method is needed to ensure the linked user is linked to the
        connection too.
        """
        rset = self.eid_rset(orig_user.eid, 'CWUser')
        user_cls = self.vreg['etypes'].etype_class('CWUser')
        user = user_cls(self, rset, row=0, groups=orig_user.groups,
                        properties=orig_user.properties)
        user.cw_attr_cache['login'] = orig_user.login # cache login
        self.user = user
        self.set_entity_cache(user)
        self.set_language(user.prefered_language())


    def set_language(self, lang):
        """install i18n configuration for `lang` translation.

        Raises :exc:`KeyError` if translation doesn't exist.
        """
        self.lang = lang
        gettext, pgettext = self.vreg.config.translations[lang]
        # use _cw.__ to translate a message without registering it to the catalog
        self._ = self.__ = gettext
        self.pgettext = pgettext

    def get_option_value(self, option):
        raise NotImplementedError

    def property_value(self, key):
        """return value of the property with the given key, giving priority to
        user specific value if any, else using site value
        """
        if self.user:
            val = self.user.property_value(key)
            if val is not None:
                return val
        return self.vreg.property_value(key)

    def etype_rset(self, etype, size=1):
        """return a fake result set for a particular entity type"""
        rset = ResultSet([('A',)] * size, '%s X' % etype,
                         description=[(etype,)] * size)

        def get_entity(row, col=0, etype=etype, req=self, rset=rset):
            return req.vreg['etypes'].etype_class(etype)(req, rset, row, col)

        rset.get_entity = get_entity
        rset.req = self
        return rset

    def eid_rset(self, eid, etype=None):
        """return a result set for the given eid without doing actual query
        (we have the eid, we can suppose it exists and user has access to the
        entity)
        """
        eid = int(eid)
        if etype is None:
            etype = self.entity_metas(eid)['type']
        rset = ResultSet([(eid,)], 'Any X WHERE X eid %(x)s', {'x': eid},
                         [(etype,)])
        rset.req = self
        return rset

    def empty_rset(self):
        """ return a guaranteed empty result """
        rset = ResultSet([], 'Any X WHERE X eid -1')
        rset.req = self
        return rset

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

    def create_entity(self, etype, **kwargs):
        """add a new entity of the given type

        Example (in a shell session):

        >>> c = create_entity('Company', name=u'Logilab')
        >>> create_entity('Person', firstname=u'John', surname=u'Doe',
        ...               works_for=c)

        """
        cls = self.vreg['etypes'].etype_class(etype)
        return cls.cw_instantiate(self.execute, **kwargs)

    @deprecated('[3.18] use find(etype, **kwargs).entities()')
    def find_entities(self, etype, **kwargs):
        """find entities of the given type and attribute values.

        >>> users = find_entities('CWGroup', name=u'users')
        >>> groups = find_entities('CWGroup')
        """
        return self.find(etype, **kwargs).entities()

    @deprecated('[3.18] use find(etype, **kwargs).one()')
    def find_one_entity(self, etype, **kwargs):
        """find one entity of the given type and attribute values.
        raise :exc:`FindEntityError` if can not return one and only one entity.

        >>> users = find_one_entity('CWGroup', name=u'users')
        >>> groups = find_one_entity('CWGroup')
        Exception()
        """
        try:
            return self.find(etype, **kwargs).one()
        except (NoResultError, MultipleResultsError) as e:
            raise FindEntityError("%s: (%s, %s)" % (str(e), etype, kwargs))

    def find(self, etype, **kwargs):
        """find entities of the given type and attribute values.

        :returns: A :class:`ResultSet`

        >>> users = find('CWGroup', name=u"users").one()
        >>> groups = find('CWGroup').entities()
        """
        parts = ['Any X WHERE X is %s' % etype]
        varmaker = rqlvar_maker(defined='X')
        eschema = self.vreg.schema.eschema(etype)
        for attr, value in kwargs.items():
            if isinstance(value, list) or isinstance(value, tuple):
                raise NotImplementedError("List of values are not supported")
            if hasattr(value, 'eid'):
                kwargs[attr] = value.eid
            if attr.startswith('reverse_'):
                attr = attr[8:]
                assert attr in eschema.objrels, \
                    '%s not in %s object relations' % (attr, eschema)
                parts.append(
                    '%(varname)s %(attr)s X, '
                    '%(varname)s eid %%(reverse_%(attr)s)s'
                    % {'attr': attr, 'varname': next(varmaker)})
            else:
                assert attr in eschema.subjrels, \
                    '%s not in %s subject relations' % (attr, eschema)
                parts.append('X %(attr)s %%(%(attr)s)s' % {'attr': attr})

        rql = ', '.join(parts)

        return self.execute(rql, kwargs)

    def ensure_ro_rql(self, rql):
        """raise an exception if the given rql is not a select query"""
        first = rql.split(None, 1)[0].lower()
        if first in ('insert', 'set', 'delete'):
            raise Unauthorized(self._('only select queries are authorized'))

    def get_cache(self, cachename):
        """cachename should be dotted names as in :

        - cubicweb.mycache
        - cubes.blog.mycache
        - etc.
        """
        warn.warning('[3.19] .get_cache will disappear soon. '
                     'Distributed caching mechanisms are being introduced instead.'
                     'Other caching mechanism can be used more reliably '
                     'to the same effect.',
                     DeprecationWarning)
        if cachename in CACHE_REGISTRY:
            cache = CACHE_REGISTRY[cachename]
        else:
            cache = CACHE_REGISTRY[cachename] = Cache()
        _now = datetime.now()
        if _now > cache.latest_cache_lookup + ONESECOND:
            ecache = self.execute(
                'Any C,T WHERE C is CWCache, C name %(name)s, C timestamp T',
                {'name': cachename}).get_entity(0, 0)
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

        if ``__secure__`` argument is True, the request will try to build a
        https url.

        raises :exc:`ValueError` if None is found in arguments
        """
        # use *args since we don't want first argument to be "anonymous" to
        # avoid potential clash with kwargs
        method = None
        if args:
            assert len(args) == 1, 'only 0 or 1 non-named-argument expected'
            method = args[0]
        if method is None:
            method = 'view'
        # XXX I (adim) think that if method is passed explicitly, we should
        #     not try to process it and directly call req.build_url()
        base_url = kwargs.pop('base_url', None)
        if base_url is None:
            secure = kwargs.pop('__secure__', None)
            base_url = self.base_url(secure=secure)
        if '_restpath' in kwargs:
            assert method == 'view', repr(method)
            path = kwargs.pop('_restpath')
        else:
            path = method
        if not kwargs:
            return u'%s%s' % (base_url, path)
        return u'%s%s?%s' % (base_url, path, self.build_url_params(**kwargs))

    def build_url_params(self, **kwargs):
        """return encoded params to incorporate them in a URL"""
        args = []
        for param, values in kwargs.items():
            if not isinstance(values, (list, tuple)):
                values = (values,)
            for value in values:
                assert value is not None
                args.append(u'%s=%s' % (param, self.url_quote(value)))
        return '&'.join(args)

    def url_quote(self, value, safe=''):
        """urllib.quote is not unicode safe, use this method to do the
        necessary encoding / decoding. Also it's designed to quote each
        part of a url path and so the '/' character will be encoded as well.
        """
        if PY2 and isinstance(value, unicode):
            quoted = urlquote(value.encode(self.encoding), safe=safe)
            return unicode(quoted, self.encoding)
        return urlquote(str(value), safe=safe)

    def url_unquote(self, quoted):
        """returns a unicode unquoted string

        decoding is based on `self.encoding` which is the encoding
        used in `url_quote`
        """
        if PY3:
            return urlunquote(quoted)
        if isinstance(quoted, unicode):
            quoted = quoted.encode(self.encoding)
        try:
            return unicode(urlunquote(quoted), self.encoding)
        except UnicodeDecodeError:  # might occurs on manually typed URLs
            return unicode(urlunquote(quoted), 'iso-8859-1')

    def url_parse_qsl(self, querystring):
        """return a list of (key, val) found in the url quoted query string"""
        if PY3:
            for key, val in parse_qsl(querystring):
                yield key, val
            return
        if isinstance(querystring, unicode):
            querystring = querystring.encode(self.encoding)
        for key, val in parse_qsl(querystring):
            try:
                yield unicode(key, self.encoding), unicode(val, self.encoding)
            except UnicodeDecodeError:  # might occurs on manually typed URLs
                yield unicode(key, 'iso-8859-1'), unicode(val, 'iso-8859-1')

    def rebuild_url(self, url, **newparams):
        """return the given url with newparams inserted. If any new params
        is already specified in the url, it's overriden by the new value

        newparams may only be mono-valued.
        """
        if PY2 and isinstance(url, unicode):
            url = url.encode(self.encoding)
        schema, netloc, path, query, fragment = urlsplit(url)
        query = parse_qs(query)
        # sort for testing predictability
        for key, val in sorted(newparams.items()):
            query[key] = (self.url_quote(val),)
        query = '&'.join(u'%s=%s' % (param, value)
                         for param, values in sorted(query.items())
                         for value in values)
        return urlunsplit((schema, netloc, path, query, fragment))

    # bound user related methods ###############################################

    @cached
    def user_data(self):
        """returns a dictionary with this user's information.

        The keys are :

        login
            The user login

        name
            The user name, returned by user.name()

        email
            The user principal email

        """
        userinfo = {}
        user = self.user
        userinfo['login'] = user.login
        userinfo['name'] = user.name()
        userinfo['email'] = user.cw_adapt_to('IEmailable').get_email()
        return userinfo

    # formating methods #######################################################

    def view(self, __vid, rset=None, __fallback_oid=None, __registry='views',
             initargs=None, w=None, **kwargs):
        """Select object with the given id (`__oid`) then render it.  If the
        object isn't selectable, try to select fallback object if
        `__fallback_oid` is specified.

        If specified `initargs` is expected to be a dictionary containing
        arguments that should be given to selection (hence to object's __init__
        as well), but not to render(). Other arbitrary keyword arguments will be
        given to selection *and* to render(), and so should be handled by
        object's call or cell_call method..
        """
        if initargs is None:
            initargs = kwargs
        else:
            initargs.update(kwargs)
        try:
            view = self.vreg[__registry].select(__vid, self, rset=rset, **initargs)
        except NoSelectableObject:
            if __fallback_oid is None:
                raise
            view = self.vreg[__registry].select(__fallback_oid, self, rset=rset, **initargs)
        return view.render(w=w, **kwargs)

    def printable_value(self, attrtype, value, props=None, displaytime=True,
                        formatters=uilib.PRINTERS):
        """return a displayablye value (i.e. unicode string)"""
        if value is None:
            return u''
        try:
            as_string = formatters[attrtype]
        except KeyError:
            self.error('given bad attrtype %s', attrtype)
            return unicode(value)
        return as_string(value, self, props, displaytime)

    def format_date(self, date, date_format=None, time=False):
        """return a string for a date time according to instance's
        configuration
        """
        if date is not None:
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
        if time is not None:
            return ustrftime(time, self.property_value('ui.time-format'))
        return u''

    def format_float(self, num):
        """return a string for floating point number according to instance's
        configuration
        """
        if num is not None:
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
                # (adim) I can't find a way to parse a time with a custom format
                date = strptime(value, format)  # this returns a datetime
                return time(date.hour, date.minute, date.second)
            except ValueError:
                raise ValueError(self._('can\'t parse %(value)r (expected %(format)s)')
                                 % {'value': value, 'format': format})
        try:
            format = self.property_value('ui.date-format')
            dt = strptime(value, format)
            if etype == 'Datetime':
                return todatetime(dt)
            return todate(dt)
        except ValueError:
            raise ValueError(self._('can\'t parse %(value)r (expected %(format)s)')
                             % {'value': value, 'format': format})

    def _base_url(self, secure=None):
        if secure:
            return self.vreg.config.get('https-url') or self.vreg.config['base-url']
        return self.vreg.config['base-url']

    def base_url(self, secure=None):
        """return the root url of the instance
        """
        url = self._base_url(secure=secure)
        return url if url is None else url.rstrip('/') + '/'

    # abstract methods to override according to the web front-end #############

    def describe(self, eid, asdict=False):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        raise NotImplementedError
