# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from contextlib import contextmanager

from six import string_types

from logilab.database import get_db_helper

from cubicweb.req import RequestSessionBase
from cubicweb.cwvreg import CWRegistryStore
from cubicweb.web.request import ConnectionCubicWebRequestBase

from cubicweb.devtools import BASE_URL, BaseApptestConfiguration


class FakeConfig(dict, BaseApptestConfiguration):
    translations = {}
    uiprops = {}
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

    def cubes(self, expand=False):
        return self._cubes

    def sources(self):
        return {'system': {'db-driver': 'sqlite'}}


class FakeCWRegistryStore(CWRegistryStore):

    def property_value(self, key):
        if key == 'ui.language':
            return 'en'
        assert False


class FakeRequest(ConnectionCubicWebRequestBase):
    """test implementation of an cubicweb request object"""

    def __init__(self, *args, **kwargs):
        if not (args or 'vreg' in kwargs):
            kwargs['vreg'] = FakeCWRegistryStore(FakeConfig(), initlog=False)
        self._http_method = kwargs.pop('method', 'GET')
        self._url = kwargs.pop('url', None)
        if self._url is None:
            self._url = 'view?rql=Blop&vid=blop'
        super(FakeRequest, self).__init__(*args, **kwargs)
        self._session_data = {}

    def set_cookie(self, name, value, maxage=300, expires=None, secure=False, httponly=False):
        super(FakeRequest, self).set_cookie(name, value, maxage, expires, secure, httponly)
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
        """set an incoming HTTP header (for test purpose only)"""
        if isinstance(value, string_types):
            value = [value]
        if raw:
            # adding encoded header is important, else page content
            # will be reconverted back to unicode and apart unefficiency, this
            # may cause decoding problem (e.g. when downloading a file)
            self._headers_in.setRawHeaders(header, value)
        else:
            self._headers_in.setHeader(header, value) #

    def get_response_header(self, header, default=None, raw=False):
        """return output header (for test purpose only)"""
        if raw:
            return self.headers_out.getRawHeaders(header, [default])[0]
        return self.headers_out.getHeader(header, default)

    def build_url_params(self, **kwargs):
        # overriden to get predictable resultts
        args = []
        for param, values in sorted(kwargs.items()):
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


class FakeConnection(RequestSessionBase):

    def __init__(self, repo=None, user=None, vreg=None):
        self.repo = repo
        if vreg is None:
            vreg = getattr(self.repo, 'vreg', None)
        if vreg is None:
            vreg = FakeCWRegistryStore(FakeConfig(), initlog=False)
        self.vreg = vreg
        self.cnxset = FakeConnectionsSet()
        self.user = user or FakeUser()
        self.is_internal_session = False
        self.transaction_data = {}

    def execute(self, *args, **kwargs):
        pass

    def commit(self, *args):
        self.transaction_data.clear()

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

    @contextmanager
    def running_hooks_ops(self):
        yield


class FakeRepo(object):
    querier = None

    def __init__(self, schema, vreg=None, config=None):
        self.eids = {}
        self._count = 0
        self.schema = schema
        self.config = config or FakeConfig()
        self.vreg = vreg or FakeCWRegistryStore(self.config, initlog=False)
        self.vreg.schema = schema


class FakeSource(object):
    dbhelper = get_db_helper('sqlite')
    def __init__(self, uri):
        self.uri = uri


class FakeConnectionsSet(object):
    def source(self, uri):
        return FakeSource(uri)
