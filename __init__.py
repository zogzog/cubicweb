"""CubicWeb is a generic framework to quickly build applications which describes
relations between entitites.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: Library General Public License version 2 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
from cubicweb.__pkginfo__ import version as __version__

import __builtin__
# '_' is available in builtins to mark internationalized string but should
# not be used to do the actual translation
if not hasattr(__builtin__, '_'):
    __builtin__._ = unicode

CW_SOFTWARE_ROOT = __path__[0]

import sys, os, logging
from StringIO import StringIO
from urllib import quote as urlquote, unquote as urlunquote

from logilab.common.decorators import cached
from logilab.common.logging_ext import set_log_methods

if os.environ.get('APYCOT_ROOT'):
    logging.basicConfig(level=logging.CRITICAL)
else:
    logging.basicConfig()


set_log_methods(sys.modules[__name__], logging.getLogger('cubicweb'))

# make all exceptions accessible from the package
from cubicweb._exceptions import *

# convert eid to the right type, raise ValueError if it's not a valid eid
typed_eid = int


#def log_thread(f, w, a):
#    print f.f_code.co_filename, f.f_code.co_name
#import threading
#threading.settrace(log_thread)

class Binary(StringIO):
    """customize StringIO to make sure we don't use unicode"""
    def __init__(self, buf=''):
        assert isinstance(buf, (str, buffer)), \
               "Binary objects must use raw strings, not %s" % buf.__class__
        StringIO.__init__(self, buf)

    def write(self, data):
        assert isinstance(data, (str, buffer)), \
               "Binary objects must use raw strings, not %s" % data.__class__
        StringIO.write(self, data)


class RequestSessionMixIn(object):
    """mixin class containing stuff shared by server session and web request
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

    def property_value(self, key):
        if self.user:
            return self.user.property_value(key)
        return self.vreg.property_value(key)

    def etype_rset(self, etype, size=1):
        """return a fake result set for a particular entity type"""
        from cubicweb.rset import ResultSet
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
        from cubicweb.rset import ResultSet
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
        from cubicweb.rset import ResultSet
        return self.decorate_rset(ResultSet([], 'Any X WHERE X eid -1'))

    def entity_from_eid(self, eid, etype=None):
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
    # url generation methods ##################################################

    def build_url(self, *args, **kwargs):
        """return an absolute URL using params dictionary key/values as URL
        parameters. Values are automatically URL quoted, and the
        publishing method to use may be specified or will be guessed.
        """
        # use *args since we don't want first argument to be "anonymous" to
        # avoid potential clash with kwargs
        assert len(args) == 1, 'only 0 or 1 non-named-argument expected'
        method = args[0]
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


    # session's user related methods #####################################

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


# XXX 2.45 is allowing nicer entity type names, use this map for bw compat
ETYPE_NAME_MAP = {# 3.2 migration
                  'ECache': 'CWCache',
                  'EUser': 'CWUser',
                  'EGroup': 'CWGroup',
                  'EProperty': 'CWProperty',
                  'EFRDef': 'CWAttribute',
                  'ENFRDef': 'CWRelation',
                  'ERType': 'CWRType',
                  'EEType': 'CWEType',
                  'EConstraintType': 'CWConstraintType',
                  'EConstraint': 'CWConstraint',
                  'EPermission': 'CWPermission',
                   # 2.45 migration
                  'Eetype': 'CWEType',
                  'Ertype': 'CWRType',
                  'Efrdef': 'CWAttribute',
                  'Enfrdef': 'CWRelation',
                  'Econstraint': 'CWConstraint',
                  'Econstrainttype': 'CWConstraintType',
                  'Epermission': 'CWPermission',
                  'Egroup': 'CWGroup',
                  'Euser': 'CWUser',
                  'Eproperty': 'CWProperty',
                  'Emailaddress': 'EmailAddress',
                  'Rqlexpression': 'RQLExpression',
                  'Trinfo': 'TrInfo',
                  }



# XXX cubic web cube migration map
CW_MIGRATION_MAP = {'erudi': 'cubicweb',

                    'eaddressbook': 'addressbook',
                    'ebasket': 'basket',
                    'eblog': 'blog',
                    'ebook': 'book',
                    'ecomment': 'comment',
                    'ecompany': 'company',
                    'econference':  'conference',
                    'eemail': 'email',
                    'eevent': 'event',
                    'eexpense': 'expense',
                    'efile': 'file',
                    'einvoice': 'invoice',
                    'elink': 'link',
                    'emailinglist': 'mailinglist',
                    'eperson': 'person',
                    'eshopcart': 'shopcart',
                    'eskillmat': 'skillmat',
                    'etask': 'task',
                    'eworkcase': 'workcase',
                    'eworkorder': 'workorder',
                    'ezone': 'zone',
                    'i18ncontent': 'i18ncontent',
                    'svnfile': 'vcsfile',

                    'eclassschemes': 'keyword',
                    'eclassfolders': 'folder',
                    'eclasstags': 'tag',

                    'jpl': 'jpl',
                    'jplintra': 'jplintra',
                    'jplextra': 'jplextra',
                    'jplorg': 'jplorg',
                    'jplrecia': 'jplrecia',
                    'crm': 'crm',
                    'agueol': 'agueol',
                    'docaster': 'docaster',
                    'asteretud': 'asteretud',
                    }

def neg_role(role):
    if role == 'subject':
        return 'object'
    return 'subject'

def role(obj):
    try:
        return obj.role
    except AttributeError:
        return neg_role(obj.target)

def target(obj):
    try:
        return obj.target
    except AttributeError:
        return neg_role(obj.role)

def underline_title(title, car='-'):
    return title+'\n'+(car*len(title))


class CubicWebEventManager(object):
    """simple event / callback manager.

    Typical usage to register a callback::

      >>> from cubicweb import CW_EVENT_MANAGER
      >>> CW_EVENT_MANAGER.bind('after-source-reload', mycallback)

    Typical usage to emit an event::

      >>> from cubicweb import CW_EVENT_MANAGER
      >>> CW_EVENT_MANAGER.emit('after-source-reload')

    emit() accepts an additional context parameter that will be passed
    to the callback if specified (and only in that case)
    """
    def __init__(self):
        self.callbacks = {}

    def bind(self, event, callback, *args, **kwargs):
        self.callbacks.setdefault(event, []).append( (callback, args, kwargs) )

    def emit(self, event, context=None):
        for callback, args, kwargs in self.callbacks.get(event, ()):
            if context is None:
                callback(*args, **kwargs)
            else:
                callback(context, *args, **kwargs)

CW_EVENT_MANAGER = CubicWebEventManager()
