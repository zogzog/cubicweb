# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Fake objects to ease testing of cubicweb without a fully working environment
"""

__docformat__ = "restructuredtext en"

from logilab.database import get_db_helper

from cubicweb.req import RequestSessionBase
from cubicweb.cwvreg import CWRegistryStore
from cubicweb.web.request import CubicWebRequestBase

from cubicweb.devtools import BASE_URL, BaseApptestConfiguration


class FakeConfig(dict, BaseApptestConfiguration):
    translations = {}
    uiprops = {}
    https_uiprops = {}
    apphome = None
    debugmode = False
    def __init__(self, appid='data', apphome=None, cubes=()):
        self.appid = appid
        self.apphome = apphome
        self._cubes = cubes
        self['auth-mode'] = 'cookie'
        self['uid'] = None
        self['base-url'] = BASE_URL
        self['rql-cache-size'] = 3000
        self.datadir_url = BASE_URL + 'data/'
        self.https_datadir_url = (BASE_URL + 'data/').replace('http://', 'https://')

    def cubes(self, expand=False):
        return self._cubes

    def sources(self):
        return {'system': {'db-driver': 'sqlite'}}


class FakeRequest(CubicWebRequestBase):
    """test implementation of an cubicweb request object"""

    def __init__(self, *args, **kwargs):
        if not (args or 'vreg' in kwargs):
            kwargs['vreg'] = CWRegistryStore(FakeConfig(), initlog=False)
        kwargs['https'] = False
        self._http_method = kwargs.pop('method', 'GET')
        self._url = kwargs.pop('url', None) or 'view?rql=Blop&vid=blop'
        super(FakeRequest, self).__init__(*args, **kwargs)
        self._session_data = {}

    def set_cookie(self, name, value, maxage=300, expires=None, secure=False):
        super(FakeRequest, self).set_cookie(name, value, maxage, expires, secure)
        cookie = self.get_response_header('Set-Cookie')
        self._headers_in.setHeader('Cookie', cookie)

    ## Implement request abstract API
    def http_method(self):
        return self._http_method

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

    def set_request_header(self, header, value, raw=False):
        """set an incoming HTTP header (For test purpose only)"""
        if isinstance(value, basestring):
            value = [value]
        if raw: #
            # adding encoded header is important, else page content
            # will be reconverted back to unicode and apart unefficiency, this
            # may cause decoding problem (e.g. when downloading a file)
            self._headers_in.setRawHeaders(header, value)
        else: #
            self._headers_in.setHeader(header, value) #

    def get_response_header(self, header, default=None, raw=False):
        """return output header (For test purpose only"""
        if raw: #
            return self.headers_out.getRawHeaders(header, [default])[0]
        return self.headers_out.getHeader(header, default)

    def build_url_params(self, **kwargs):
        # overriden to get predictable resultts
        args = []
        for param, values in sorted(kwargs.iteritems()):
            if not isinstance(values, (list, tuple)):
                values = (values,)
            for value in values:
                assert value is not None
                args.append(u'%s=%s' % (param, self.url_quote(value)))
        return '&'.join(args)

class FakeUser(object):
    login = 'toto'
    eid = 0
    def in_groups(self, groups):
        return True


class FakeSession(RequestSessionBase):

    def __init__(self, repo=None, user=None, vreg=None):
        self.repo = repo
        if vreg is None:
            vreg = getattr(self.repo, 'vreg', None)
        if vreg is None:
            vreg = CWRegistryStore(FakeConfig(), initlog=False)
        self.vreg = vreg
        self.cnxset = FakeConnectionsSet()
        self.user = user or FakeUser()
        self.is_internal_session = False
        self.transaction_data = {}

    def execute(self, *args, **kwargs):
        pass

    def commit(self, *args):
        self.transaction_data.clear()
    def close(self, *args):
        pass
    def system_sql(self, sql, args=None):
        pass

    def set_entity_cache(self, entity):
        pass

    def security_enabled(self, read=False, write=False):
        class FakeCM(object):
            def __enter__(self): pass
            def __exit__(self, exctype, exc, traceback): pass
        return FakeCM()

    # for use with enabled_security context manager
    read_security = write_security = True

class FakeRepo(object):
    querier = None
    def __init__(self, schema, vreg=None, config=None):
        self.extids = {}
        self.eids = {}
        self._count = 0
        self.schema = schema
        self.config = config or FakeConfig()
        self.vreg = vreg or CWRegistryStore(self.config, initlog=False)
        self.vreg.schema = schema
        self.sources = []

    def internal_session(self):
        return FakeSession(self)

    def extid2eid(self, source, extid, etype, session, insert=True):
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
    dbhelper = get_db_helper('sqlite')
    def __init__(self, uri):
        self.uri = uri


class FakeConnectionsSet(object):
    def source(self, uri):
        return FakeSource(uri)
