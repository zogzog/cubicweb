"""Fake objects to ease testing of cubicweb without a fully working environment

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.testlib import mock_object as Mock
from logilab.common.adbh import get_adv_func_helper

from indexer import get_indexer

from cubicweb import RequestSessionMixIn
from cubicweb.web.request import CubicWebRequestBase
from cubicweb.devtools import BASE_URL, BaseApptestConfiguration


class FakeConfig(dict, BaseApptestConfiguration):
    translations = {}
    apphome = None
    def __init__(self, appid='data', apphome=None, cubes=()):
        self.appid = appid
        self.apphome = apphome
        self._cubes = cubes
        self['auth-mode'] = 'cookie'
        self['uid'] = None
        self['base-url'] = BASE_URL
        self['rql-cache-size'] = 100

    def cubes(self, expand=False):
        return self._cubes

    def sources(self):
        return {}

class FakeVReg(object):
    def __init__(self, schema=None, config=None):
        self.schema = schema
        self.config = config or FakeConfig()
        self.properties = {'ui.encoding': 'UTF8',
                           'ui.language': 'en',
                           }

    def property_value(self, key):
        return self.properties[key]

    _registries = {
        'controllers' : [Mock(id='view'), Mock(id='login'),
                         Mock(id='logout'), Mock(id='edit')],
        'views' : [Mock(id='primary'), Mock(id='oneline'), Mock(id='list')],
        }

    def registry_objects(self, name, oid=None):
        return self._registries[name]

    def etype_class(self, etype):
        class Entity(dict):
            e_schema = self.schema[etype]
            def __init__(self, session, eid, row=0, col=0):
                self.req = session
                self.eid = eid
                self.row, self.col = row, col
            def set_eid(self, eid):
                self.eid = self['eid'] = eid
        return Entity


class FakeRequest(CubicWebRequestBase):
    """test implementation of an cubicweb request object"""

    def __init__(self, *args, **kwargs):
        if not (args or 'vreg' in kwargs):
            kwargs['vreg'] = FakeVReg()
        kwargs['https'] = False
        self._url = kwargs.pop('url', 'view?rql=Blop&vid=blop')
        super(FakeRequest, self).__init__(*args, **kwargs)
        self._session_data = {}
        self._headers = {}

    def header_accept_language(self):
        """returns an ordered list of preferred languages"""
        return ('en',)

    def header_if_modified_since(self):
        return None

    def base_url(self):
        """return the root url of the application"""
        return BASE_URL

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the application's root, but some other normalization may be needed
        so that the returned path may be used to compare to generated urls
        """
        if self._url.startswith(BASE_URL):
            url = self._url[len(BASE_URL):]
        else:
            url = self._url
        if includeparams:
            return url
        return url.split('?', 1)[0]

    def set_content_type(self, content_type, filename=None, encoding=None):
        """set output content type for this request. An optional filename
        may be given
        """
        pass

    def set_header(self, header, value):
        """set an output HTTP header"""
        pass

    def add_header(self, header, value):
        """set an output HTTP header"""
        pass

    def remove_header(self, header):
        """remove an output HTTP header"""
        pass

    def get_header(self, header, default=None):
        """return the value associated with the given input header,
        raise KeyError if the header is not set
        """
        return self._headers.get(header, default)

    def set_cookie(self, cookie, key, maxage=300):
        """set / update a cookie key

        by default, cookie will be available for the next 5 minutes
        """
        pass

    def remove_cookie(self, cookie, key):
        """remove a cookie by expiring it"""
        pass

    def validate_cache(self):
        pass

    # session compatibility (in some test are using this class to test server
    # side views...)
    def actual_session(self):
        """return the original parent session if any, else self"""
        return self

    def unsafe_execute(self, *args, **kwargs):
        """return the original parent session if any, else self"""
        kwargs.pop('propagate', None)
        return self.execute(*args, **kwargs)


# class FakeRequestNoCnx(FakeRequest):
#     def get_session_data(self, key, default=None, pop=False):
#         """return value associated to `key` in session data"""
#         if pop:
#             return self._session_data.pop(key, default)
#         else:
#             return self._session_data.get(key, default)

#     def set_session_data(self, key, value):
#         """set value associated to `key` in session data"""
#         self._session_data[key] = value

#     def del_session_data(self, key):
#         try:
#             del self._session_data[key]
#         except KeyError:
#             pass


class FakeUser(object):
    login = 'toto'
    eid = 0
    def in_groups(self, groups):
        return True


class FakeSession(RequestSessionMixIn):
    def __init__(self, repo=None, user=None):
        self.repo = repo
        self.vreg = getattr(self.repo, 'vreg', FakeVReg())
        self.pool = FakePool()
        self.user = user or FakeUser()
        self.is_internal_session = False
        self.is_super_session = self.user.eid == -1
        self.transaction_data = {}

    def execute(self, *args):
        pass
    unsafe_execute = execute
    
    def commit(self, *args):
        self.transaction_data.clear()
    def close(self, *args):
        pass
    def system_sql(self, sql, args=None):
        pass

    def decorate_rset(self, rset, propagate=False):
        rset.vreg = self.vreg
        rset.req = self
        return rset

    def set_entity_cache(self, entity):
        pass

class FakeRepo(object):
    querier = None
    def __init__(self, schema, vreg=None, config=None):
        self.extids = {}
        self.eids = {}
        self._count = 0
        self.schema = schema
        self.vreg = vreg or FakeVReg()
        self.config = config or FakeConfig()

    def internal_session(self):
        return FakeSession(self)

    def extid2eid(self, source, extid, etype, session, insert=True,
                  recreate=False):
        try:
            return self.extids[extid]
        except KeyError:
            if not insert:
                return None
            self._count += 1
            eid = self._count
            entity = source.before_entity_insertion(session, extid, etype, eid)
            self.extids[extid] = eid
            self.eids[eid] = extid
            source.after_entity_insertion(session, extid, entity)
            return eid

    def eid2extid(self, source, eid, session=None):
        return self.eids[eid]


class FakeSource(object):
    dbhelper = get_adv_func_helper('sqlite')
    indexer = get_indexer('sqlite', 'UTF8')
    dbhelper.fti_uid_attr = indexer.uid_attr
    dbhelper.fti_table = indexer.table
    dbhelper.fti_restriction_sql = indexer.restriction_sql
    dbhelper.fti_need_distinct_query = indexer.need_distinct
    def __init__(self, uri):
        self.uri = uri


class FakePool(object):
    def source(self, uri):
        return FakeSource(uri)

# commented until proven to be useful
## from logging import getLogger
## from cubicweb import set_log_methods
## for cls in (FakeConfig, FakeVReg, FakeRequest, FakeSession, FakeRepo,
##             FakeSource, FakePool):
##     set_log_methods(cls, getLogger('fake'))
