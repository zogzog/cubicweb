"""Fake objects to ease testing of cubicweb without a fully working environment

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.adbh import get_adv_func_helper

from indexer import get_indexer

from cubicweb.req import RequestSessionBase
from cubicweb.cwvreg import CubicWebVRegistry
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


class FakeRequest(CubicWebRequestBase):
    """test implementation of an cubicweb request object"""

    def __init__(self, *args, **kwargs):
        if not (args or 'vreg' in kwargs):
            kwargs['vreg'] = CubicWebVRegistry(FakeConfig(), initlog=False)
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
        """return the root url of the instance"""
        return BASE_URL

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the instance's root, but some other normalization may be needed
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
        self._headers[header] = value

    def add_header(self, header, value):
        """set an output HTTP header"""
        self._headers[header] = value # XXX

    def remove_header(self, header):
        """remove an output HTTP header"""
        self._headers.pop(header, None)

    def get_header(self, header, default=None):
        """return the value associated with the given input header,
        raise KeyError if the header is not set
        """
        return self._headers.get(header, default)

    def set_cookie(self, cookie, key, maxage=300, expires=None):
        """set / update a cookie key

        by default, cookie will be available for the next 5 minutes
        """
        morsel = cookie[key]
        if maxage is not None:
            morsel['Max-Age'] = maxage
        if expires:
            morsel['expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S %z')
        # make sure cookie is set on the correct path
        morsel['path'] = self.base_url_path()
        self.add_header('Set-Cookie', morsel.OutputString())
        self.add_header('Cookie', morsel.OutputString())

    def remove_cookie(self, cookie, key):
        self.remove_header('Set-Cookie')
        self.remove_header('Cookie')

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


class FakeUser(object):
    login = 'toto'
    eid = 0
    def in_groups(self, groups):
        return True


class FakeSession(RequestSessionBase):
    def __init__(self, repo=None, user=None):
        self.repo = repo
        self.vreg = getattr(self.repo, 'vreg', CubicWebVRegistry(FakeConfig(), initlog=False))
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
        self.config = config or FakeConfig()
        self.vreg = vreg or CubicWebVRegistry(self.config, initlog=False)
        self.vreg.schema = schema

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
