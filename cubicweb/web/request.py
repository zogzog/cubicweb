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
"""abstract class for http request"""

import time
import random
import base64
from hashlib import sha1  # pylint: disable=E0611
from calendar import timegm
from datetime import date, datetime
from warnings import warn
from io import BytesIO

from six import PY2, text_type, string_types
from six.moves import http_client
from six.moves.urllib.parse import urlsplit, quote as urlquote
from six.moves.http_cookies import SimpleCookie

from rql.utils import rqlvar_maker

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated

from cubicweb import AuthenticationError
from cubicweb.req import RequestSessionBase
from cubicweb.uilib import remove_html_tags, js
from cubicweb.utils import HTMLHead, make_uid
from cubicweb.web import (INTERNAL_FIELD_VALUE, LOGGER, NothingToEdit,
                          RequestError, StatusResponse)
from cubicweb.web.httpcache import get_validators
from cubicweb.web.http_headers import Headers, Cookie


_MARKER = object()


def build_cb_uid(seed):
    sha = sha1(('%s%s%s' % (time.time(), seed, random.random())).encode('ascii'))
    return 'cb_%s' % (sha.hexdigest())


def list_form_param(form, param, pop=False):
    """get param from form parameters and return its value as a list,
    skipping internal markers if any

    * if the parameter isn't defined, return an empty list
    * if the parameter is a single (unicode) value, return a list
      containing that value
    * if the parameter is already a list or tuple, just skip internal
      markers

    if pop is True, the parameter is removed from the form dictionary
    """
    if pop:
        try:
            value = form.pop(param)
        except KeyError:
            return []
    else:
        value = form.get(param, ())
    if value is None:
        value = ()
    elif not isinstance(value, (list, tuple)):
        value = [value]
    return [v for v in value if v != INTERNAL_FIELD_VALUE]


class Counter(object):
    """A picklable counter object, usable for e.g. page tab index count"""
    __slots__ = ('value',)

    def __init__(self, initialvalue=0):
        self.value = initialvalue

    def __call__(self):
        value = self.value
        self.value += 1
        return value

    def __getstate__(self):
        return {'value': self.value}

    def __setstate__(self, state):
        self.value = state['value']


class _CubicWebRequestBase(RequestSessionBase):
    """abstract HTTP request, should be extended according to the HTTP backend
    Immutable attributes that describe the received query and generic configuration
    """
    ajax_request = False # to be set to True by ajax controllers

    def __init__(self, vreg, form=None, headers=None):
        """
        :vreg: Vregistry,
        :form: Forms value
        :headers: dict, request header
        """
        super(_CubicWebRequestBase, self).__init__(vreg)
        #: User interface property (see :ref:`uiprops`)
        self.uiprops = None
        #: url for serving datadir (see :ref:`resources`)
        self.datadir_url = None
        # some config (i.e. "pyramid") do not have "uiprops" nor "datadir_url"
        # attributes)
        self.uiprops = getattr(vreg.config, 'uiprops', None)
        self.datadir_url = getattr(vreg.config, 'datadir_url', None)
        #: enable UStringIO's write tracing
        self.tracehtml = False
        if vreg.config.debugmode:
            self.tracehtml = bool(form.pop('_cwtracehtml', False))
        #: raw html headers that can be added from any view
        self.html_headers = HTMLHead(self, tracewrites=self.tracehtml)
        #: received headers
        self._headers_in = Headers()
        if headers is not None:
            for k, v in headers.items():
                self._headers_in.addRawHeader(k, v)
        #: form parameters
        self.setup_params(form)
        #: received body
        self.content = BytesIO()
        # prepare output header
        #: Header used for the final response
        self.headers_out = Headers()
        #: HTTP status use by the final response
        self.status_out = 200
        # set up language based on site default (we don't have a user yet, and might not get one)
        self.set_language(vreg.property_value('ui.language'))
        #: dictionary that may be used to store request data that has to be
        #: shared among various components used to publish the request (views,
        #: controller, application...)
        self.data = {}
        self._search_state = None
        #: page id, set by htmlheader template
        self.pageid = None
        self._set_pageid()

    def _set_pageid(self):
        """initialize self.pageid
        if req.form provides a specific pageid, use it, otherwise build a
        new one.
        """
        pid = self.form.get('pageid')
        if pid is None:
            pid = make_uid(id(self))
            self.html_headers.define_var('pageid', pid, override=False)
        self.pageid = pid

    def _get_json_request(self):
        warn('[3.15] self._cw.json_request is deprecated, use self._cw.ajax_request instead',
             DeprecationWarning, stacklevel=2)
        return self.ajax_request
    def _set_json_request(self, value):
        warn('[3.15] self._cw.json_request is deprecated, use self._cw.ajax_request instead',
             DeprecationWarning, stacklevel=2)
        self.ajax_request = value
    json_request = property(_get_json_request, _set_json_request)

    @property
    def authmode(self):
        """Authentification mode of the instance
        (see :ref:`WebServerConfig`)"""
        return self.vreg.config['auth-mode']

    # Various variable generator.

    @property
    def varmaker(self):
        """the rql varmaker is exposed both as a property and as the
        set_varmaker function since we've two use cases:

        * accessing the req.varmaker property to get a new variable name

        * calling req.set_varmaker() to ensure a varmaker is set for later ajax
          calls sharing our .pageid
        """
        return self.set_varmaker()

    def set_varmaker(self):
        varmaker = self.get_page_data('rql_varmaker')
        if varmaker is None:
            varmaker = rqlvar_maker()
        self.set_page_data('rql_varmaker', varmaker)
        return varmaker

    # input form parameters management ########################################

    # common form parameters which should be protected against html values
    # XXX can't add 'eid' for instance since it may be multivalued
    # dont put rql as well, if query contains < and > it will be corrupted!
    no_script_form_params = set(('vid',
                                 'etype',
                                 'vtitle', 'title',
                                 '__redirectvid', '__redirectrql'))

    def setup_params(self, params):
        """WARNING: we're intentionally leaving INTERNAL_FIELD_VALUE here

        subclasses should overrides to
        """
        self.form = {}
        if params is None:
            return
        encoding = self.encoding
        for param, val in params.items():
            if isinstance(val, (tuple, list)):
                if PY2:
                    val = [unicode(x, encoding) for x in val]
                if len(val) == 1:
                    val = val[0]
            elif PY2 and isinstance(val, str):
                val = unicode(val, encoding)
            if param in self.no_script_form_params and val:
                val = self.no_script_form_param(param, val)
            if param == '_cwmsgid':
                self.set_message_id(val)
            else:
                self.form[param] = val

    def no_script_form_param(self, param, value):
        """ensure there is no script in a user form param

        by default return a cleaned string instead of raising a security
        exception

        this method should be called on every user input (form at least) fields
        that are at some point inserted in a generated html page to protect
        against script kiddies
        """
        # safety belt for strange urls like http://...?vtitle=yo&vtitle=yo
        if isinstance(value, (list, tuple)):
            self.error('no_script_form_param got a list (%s). Who generated the URL ?',
                       repr(value))
            value = value[0]
        return remove_html_tags(value)

    def list_form_param(self, param, form=None, pop=False):
        """get param from form parameters and return its value as a list,
        skipping internal markers if any

        * if the parameter isn't defined, return an empty list
        * if the parameter is a single (unicode) value, return a list
          containing that value
        * if the parameter is already a list or tuple, just skip internal
          markers

        if pop is True, the parameter is removed from the form dictionary
        """
        if form is None:
            form = self.form
        return list_form_param(form, param, pop)

    def reset_headers(self):
        """used by AutomaticWebTest to clear html headers between tests on
        the same resultset
        """
        self.html_headers = HTMLHead(self)
        return self

    # web state helpers #######################################################

    @property
    def message(self):
        try:
            return self.session.data.pop(self._msgid, u'')
        except AttributeError:
            try:
                return self._msg
            except AttributeError:
                return None

    def set_message(self, msg):
        assert isinstance(msg, text_type)
        self.reset_message()
        self._msg = msg

    def set_message_id(self, msgid):
        self._msgid = msgid

    @cached
    def redirect_message_id(self):
        return make_uid()

    def set_redirect_message(self, msg):
        # TODO - this should probably be merged with append_to_redirect_message
        assert isinstance(msg, text_type)
        msgid = self.redirect_message_id()
        self.session.data[msgid] = msg
        return msgid

    def append_to_redirect_message(self, msg):
        msgid = self.redirect_message_id()
        currentmsg = self.session.data.get(msgid)
        if currentmsg is not None:
            currentmsg = u'%s %s' % (currentmsg, msg)
        else:
            currentmsg = msg
        self.session.data[msgid] = currentmsg
        return msgid

    def reset_message(self):
        if hasattr(self, '_msg'):
            del self._msg
        if hasattr(self, '_msgid'):
            self.session.data.pop(self._msgid, u'')
            del self._msgid

    def _load_search_state(self, searchstate):
        if searchstate is None or searchstate == 'normal':
            self._search_state = ('normal',)
        else:
            self._search_state = ('linksearch', searchstate.split(':'))
            assert len(self._search_state[-1]) == 4, 'invalid searchstate'

    @property
    def search_state(self):
        """search state: 'normal' or 'linksearch' (i.e. searching for an object
        to create a relation with another)"""
        if self._search_state is None:
            searchstate = self.session.data.get('search_state', 'normal')
            self._load_search_state(searchstate)
        return self._search_state

    @search_state.setter
    def search_state(self, searchstate):
        self._search_state = searchstate

    def update_search_state(self):
        """update the current search state if needed"""
        searchstate = self.form.get('__mode')
        if searchstate:
            self.set_search_state(searchstate)

    def set_search_state(self, searchstate):
        """set a new search state"""
        self.session.data['search_state'] = searchstate
        self._load_search_state(searchstate)

    def match_search_state(self, rset):
        """when searching an entity to create a relation, return True if entities in
        the given rset may be used as relation end
        """
        try:
            searchedtype = self.search_state[1][-1]
        except IndexError:
            return False # no searching for association
        for etype in rset.column_types(0):
            if etype != searchedtype:
                return False
        return True

    # web edition helpers #####################################################

    @cached # so it's writed only once
    def fckeditor_config(self):
        fckeditor_url = self.build_url('fckeditor/fckeditor.js')
        self.add_js(fckeditor_url, localfile=False)
        self.html_headers.define_var('fcklang', self.lang)
        self.html_headers.define_var('fckconfigpath',
                                     self.data_url('cubicweb.fckcwconfig.js'))
    def use_fckeditor(self):
        return self.vreg.config.fckeditor_installed() and self.property_value('ui.fckeditor')

    def edited_eids(self, withtype=False):
        """return a list of edited eids"""
        yielded = False
        # warning: use .keys since the caller may change `form`
        form = self.form
        try:
            eids = form['eid']
        except KeyError:
            raise NothingToEdit(self._('no selected entities'))
        if isinstance(eids, string_types):
            eids = (eids,)
        for peid in eids:
            if withtype:
                typekey = '__type:%s' % peid
                assert typekey in form, 'no entity type specified'
                yield peid, form[typekey]
            else:
                yield peid
            yielded = True
        if not yielded:
            raise NothingToEdit(self._('no selected entities'))

    # minparams=3 by default: at least eid, __type, and some params to change
    def extract_entity_params(self, eid, minparams=3):
        """extract form parameters relative to the given eid"""
        params = {}
        eid = str(eid)
        form = self.form
        for param in form:
            try:
                name, peid = param.split(':', 1)
            except ValueError:
                if not param.startswith('__') and param not in ('eid', '_cw_fields'):
                    self.warning('param %s mis-formatted', param)
                continue
            if peid == eid:
                value = form[param]
                if value == INTERNAL_FIELD_VALUE:
                    value = None
                params[name] = value
        params['eid'] = eid
        if len(params) < minparams:
            raise RequestError(self._('missing parameters for entity %s') % eid)
        return params

    # XXX this should go to the GenericRelationsField. missing edition cancel protocol.

    def remove_pending_operations(self):
        """shortcut to clear req's pending_{delete,insert} entries

        This is needed when the edition is completed (whether it's validated
        or cancelled)
        """
        self.session.data.pop('pending_insert', None)
        self.session.data.pop('pending_delete', None)

    def cancel_edition(self, errorurl):
        """remove pending operations and `errorurl`'s specific stored data
        """
        self.session.data.pop(errorurl, None)
        self.remove_pending_operations()

    # high level methods for HTTP headers management ##########################

    # must be cached since login/password are popped from the form dictionary
    # and this method may be called multiple times during authentication
    @cached
    def get_authorization(self):
        """Parse and return the Authorization header"""
        if self.authmode == "cookie":
            try:
                user = self.form.pop("__login")
                passwd = self.form.pop("__password", '')
                return user, passwd.encode('UTF8')
            except KeyError:
                self.debug('no login/password in form params')
                return None, None
        else:
            return self.header_authorization()

    def get_cookie(self):
        """retrieve request cookies, returns an empty cookie if not found"""
        # XXX use http_headers implementation
        try:
            return SimpleCookie(self.get_header('Cookie'))
        except KeyError:
            return SimpleCookie()

    def set_cookie(self, name, value, maxage=300, expires=None, secure=False, httponly=False):
        """set / update a cookie

        by default, cookie will be available for the next 5 minutes.
        Give maxage = None to have a "session" cookie expiring when the
        client close its browser
        """
        if isinstance(name, SimpleCookie):
            warn('[3.13] set_cookie now takes name and value as two first '
                 'argument, not anymore cookie object and name',
                 DeprecationWarning, stacklevel=2)
            secure = name[value]['secure']
            name, value = value, name[value].value
        if maxage: # don't check is None, 0 may be specified
            assert expires is None, 'both max age and expires cant be specified'
            expires = maxage + time.time()
        elif expires:
            # we don't want to handle times before the EPOCH (cause bug on
            # windows). Also use > and not >= else expires == 0 and Cookie think
            # that means no expire...
            assert expires > date(1970, 1, 1)
            expires = timegm(expires.timetuple())
        else:
            expires = None
        # make sure cookie is set on the correct path
        cookie = Cookie(str(name), str(value), self.base_url_path(),
                        expires=expires, secure=secure, httponly=httponly)
        self.headers_out.addHeader('Set-cookie', cookie)

    def remove_cookie(self, name, bwcompat=None):
        """remove a cookie by expiring it"""
        if bwcompat is not None:
            warn('[3.13] remove_cookie now take only a name as argument',
                 DeprecationWarning, stacklevel=2)
            name = bwcompat
        self.set_cookie(name, '', maxage=0, expires=date(2000, 1, 1))

    def set_content_type(self, content_type, filename=None, encoding=None,
                         disposition='inline'):
        """set output content type for this request. An optional filename
        may be given.

        The disposition argument may be `attachement` or `inline` as specified
        for the Content-disposition HTTP header. The disposition parameter have
        no effect if no filename are specified.
        """
        if content_type.startswith('text/') and ';charset=' not in content_type:
            content_type += ';charset=' + (encoding or self.encoding)
        self.set_header('content-type', content_type)
        if filename:
            header = [disposition]
            unicode_filename = None
            try:
                ascii_filename = filename.encode('ascii').decode('ascii')
            except UnicodeEncodeError:
                # fallback filename for very old browser
                unicode_filename = filename
                ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
            # escape " and \
            # see http://greenbytes.de/tech/tc2231/#attwithfilenameandextparamescaped
            ascii_filename = ascii_filename.replace('\x5c', r'\\').replace('"', r'\"')
            header.append('filename="%s"' % ascii_filename)
            if unicode_filename is not None:
                # encoded filename according RFC5987
                urlquoted_filename = urlquote(unicode_filename.encode('utf-8'), '')
                header.append("filename*=utf-8''" + urlquoted_filename)
            self.set_header('content-disposition', ';'.join(header))

    # high level methods for HTML headers management ##########################

    def add_onload(self, jscode):
        self.html_headers.add_onload(jscode)

    def add_js(self, jsfiles, localfile=True):
        """specify a list of JS files to include in the HTML headers.

        :param jsfiles: a JS filename or a list of JS filenames
        :param localfile: if True, the default data dir prefix is added to the
                          JS filename
        """
        if isinstance(jsfiles, string_types):
            jsfiles = (jsfiles,)
        for jsfile in jsfiles:
            if localfile:
                jsfile = self.data_url(jsfile)
            self.html_headers.add_js(jsfile)

    def add_css(self, cssfiles, media=u'all', localfile=True, ieonly=False,
                iespec=u'[if lt IE 8]'):
        """specify a CSS file to include in the HTML headers

        :param cssfiles: a CSS filename or a list of CSS filenames.
        :param media: the CSS's media if necessary
        :param localfile: if True, the default data dir prefix is added to the
                          CSS filename
        :param ieonly: True if this css is specific to IE
        :param iespec: conditional expression that will be used around
                       the css inclusion. cf:
                       http://msdn.microsoft.com/en-us/library/ms537512(VS.85).aspx
        """
        if isinstance(cssfiles, string_types):
            cssfiles = (cssfiles,)
        if ieonly:
            if self.ie_browser():
                extraargs = [iespec]
                add_css = self.html_headers.add_ie_css
            else:
                return # no need to do anything on non IE browsers
        else:
            extraargs = []
            add_css = self.html_headers.add_css
        for cssfile in cssfiles:
            if localfile:
                cssfile = self.data_url(cssfile)
            add_css(cssfile, media, *extraargs)

    def ajax_replace_url(self, nodeid, replacemode='replace', **extraparams):
        """builds an ajax url that will replace nodeid's content

        :param nodeid: the dom id of the node to replace
        :param replacemode: defines how the replacement should be done.

          Possible values are :
          - 'replace' to replace the node's content with the generated HTML
          - 'swap' to replace the node itself with the generated HTML
          - 'append' to append the generated HTML to the node's content

        Arbitrary extra named arguments may be given, they will be included as
        parameters of the generated url.
        """
        # define a function in headers and use it in the link to avoid url
        # unescaping pb: browsers give the js expression to the interpreter
        # after having url unescaping the content. This may make appear some
        # quote or other special characters that will break the js expression.
        extraparams.setdefault('fname', 'view')
        # remove pageid from the generated URL as it's forced as a parameter
        # to the loadxhtml call below.
        extraparams.pop('pageid', None)
        url = self.build_url('ajax', **extraparams)
        cbname = build_cb_uid(url[:50])
        # think to propagate pageid. XXX see https://www.cubicweb.org/ticket/1753121
        jscode = u'function %s() { $("#%s").%s; }' % (
            cbname, nodeid, js.loadxhtml(url, {'pageid': self.pageid},
                                         'get', replacemode))
        self.html_headers.add_post_inline_script(jscode)
        return "javascript: %s()" % cbname

    # urls/path management ####################################################

    def build_url(self, *args, **kwargs):
        """return an absolute URL using params dictionary key/values as URL
        parameters. Values are automatically URL quoted, and the
        publishing method to use may be specified or will be guessed.
        """
        if '__message' in kwargs:
            msg = kwargs.pop('__message')
            kwargs['_cwmsgid'] = self.set_redirect_message(msg)
        if not args:
            method = 'view'
            if (self.from_controller() == 'view'
                and not '_restpath' in kwargs):
                method = self.relative_path(includeparams=False) or 'view'
            args = (method,)
        return super(_CubicWebRequestBase, self).build_url(*args, **kwargs)

    def build_url_path(self, *args):
        path = super(_CubicWebRequestBase, self).build_url_path(*args)
        lang_prefix = ''
        if self.lang is not None and self.vreg.config.get('language-mode') == 'url-prefix':
            lang_prefix = '%s/' % self.lang
        return lang_prefix + path

    def url(self, includeparams=True):
        """return currently accessed url"""
        return self.base_url() + self.relative_path(includeparams)

    def selected(self, url):
        """return True if the url is equivalent to currently accessed url"""
        reqpath = self.relative_path().lower()
        baselen = len(self.base_url())
        return (reqpath == url[baselen:].lower())

    def base_url_prepend_host(self, hostname):
        protocol, roothost = urlsplit(self.base_url())[:2]
        if roothost.startswith('www.'):
            roothost = roothost[4:]
        return '%s://%s.%s' % (protocol, hostname, roothost)

    def base_url_path(self):
        """returns the absolute path of the base url"""
        return urlsplit(self.base_url())[2]

    def data_url(self, relpath):
        """returns the absolute path for a data resource"""
        return self.datadir_url + relpath

    @cached
    def from_controller(self):
        """return the id (string) of the controller issuing the request"""
        controller = self.relative_path(False).split('/', 1)[0]
        if controller in self.vreg['controllers']:
            return controller
        return 'view'

    def is_client_cache_valid(self):
        """check if a client cached page exists (as specified in request
        headers) and is still usable.

        Return False if the page has to be calculated, else True.

        Some response cache headers may be set by this method.
        """
        modified = True
        # Here, we search for any invalid 'not modified' condition
        # see http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.3
        validators = get_validators(self._headers_in)
        if validators: # if we have no
            modified = any(func(val, self.headers_out) for func, val in validators)
        # Forge expected response
        if not modified:
            # overwrite headers_out to forge a brand new not-modified response
            self.headers_out = self._forge_cached_headers()
            if self.http_method() in ('HEAD', 'GET'):
                self.status_out = http_client.NOT_MODIFIED
            else:
                self.status_out = http_client.PRECONDITION_FAILED
            # XXX replace by True once validate_cache bw compat method is dropped
            return self.status_out
        # XXX replace by False once validate_cache bw compat method is dropped
        return None

    @deprecated('[3.18] use .is_client_cache_valid() method instead')
    def validate_cache(self):
        """raise a `StatusResponse` exception if a cached page along the way
        exists and is still usable.
        """
        status_code = self.is_client_cache_valid()
        if status_code is not None:
            raise StatusResponse(status_code)

    # abstract methods to override according to the web front-end #############

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        raise NotImplementedError()

    def _forge_cached_headers(self):
        # overwrite headers_out to forge a brand new not-modified response
        headers = Headers()
        for header in (
            # Required from sec 10.3.5:
            'date', 'etag', 'content-location', 'expires',
            'cache-control', 'vary',
            # Others:
            'server', 'proxy-authenticate', 'www-authenticate', 'warning'):
            value = self.headers_out.getRawHeaders(header)
            if value is not None:
                headers.setRawHeaders(header, value)
        return headers

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the instance's root, but some other normalization may be needed
        so that the returned path may be used to compare to generated urls

        :param includeparams:
           boolean indicating if GET form parameters should be kept in the path
        """
        raise NotImplementedError()

    # http headers ############################################################

    ### incoming headers

    def get_header(self, header, default=None, raw=True):
        """return the value associated with the given input header, raise
        KeyError if the header is not set
        """
        if raw:
            return self._headers_in.getRawHeaders(header, [default])[0]
        return self._headers_in.getHeader(header, default)

    def header_accept_language(self):
        """returns an ordered list of preferred languages"""
        acceptedlangs = self.get_header('Accept-Language', raw=False) or {}
        for lang, _ in sorted(acceptedlangs.items(), key=lambda x: x[1],
                              reverse=True):
            lang = lang.split('-')[0]
            yield lang

    def header_if_modified_since(self):
        """If the HTTP header If-modified-since is set, return the equivalent
        date time value (GMT), else return None
        """
        mtime = self.get_header('If-modified-since', raw=False)
        if mtime:
            return datetime.utcfromtimestamp(mtime)
        return None

    ### outcoming headers
    def set_header(self, header, value, raw=True):
        """set an output HTTP header"""
        if raw:
            # adding encoded header is important, else page content
            # will be reconverted back to unicode and apart unefficiency, this
            # may cause decoding problem (e.g. when downloading a file)
            self.headers_out.setRawHeaders(header, [str(value)])
        else:
            self.headers_out.setHeader(header, value)

    def add_header(self, header, value):
        """add an output HTTP header"""
        # adding encoded header is important, else page content
        # will be reconverted back to unicode and apart unefficiency, this
        # may cause decoding problem (e.g. when downloading a file)
        self.headers_out.addRawHeader(header, str(value))

    def remove_header(self, header):
        """remove an output HTTP header"""
        self.headers_out.removeHeader(header)

    def header_authorization(self):
        """returns a couple (auth-type, auth-value)"""
        auth = self.get_header("Authorization", None)
        if auth:
            scheme, rest = auth.split(' ', 1)
            scheme = scheme.lower()
            try:
                assert scheme == "basic"
                user, passwd = base64.decodestring(rest.encode('ascii')).split(b":", 1)
                # XXX HTTP header encoding: use email.Header?
                return user.decode('UTF8'), passwd
            except Exception as ex:
                self.debug('bad authorization %s (%s: %s)',
                           auth, ex.__class__.__name__, ex)
        return None, None

    def parse_accept_header(self, header):
        """returns an ordered list of accepted values"""
        try:
            value_parser, value_sort_key = ACCEPT_HEADER_PARSER[header.lower()]
        except KeyError:
            value_parser = value_sort_key = None
        accepteds = self.get_header(header, '')
        values = _parse_accept_header(accepteds, value_parser, value_sort_key)
        return (raw_value for (raw_value, parsed_value, score) in values)

    @deprecated('[3.17] demote_to_html is deprecated as we always serve html')
    def demote_to_html(self):
        """helper method to dynamically set request content type to text/html

        The global doctype and xmldec must also be changed otherwise the browser
        will display '<[' at the beginning of the page
        """
        pass


    # xml doctype #############################################################

    def set_doctype(self, doctype, reset_xmldecl=None):
        """helper method to dynamically change page doctype

        :param doctype: the new doctype, e.g. '<!DOCTYPE html>'
        """
        if reset_xmldecl is not None:
            warn('[3.17] reset_xmldecl is deprecated as we only serve html',
                 DeprecationWarning, stacklevel=2)
        self.main_stream.set_doctype(doctype)

    # page data management ####################################################

    def get_page_data(self, key, default=None):
        """return value associated to `key` in current page data"""
        page_data = self.session.data.get(self.pageid)
        if page_data is None:
            return default
        return page_data.get(key, default)

    def set_page_data(self, key, value):
        """set value associated to `key` in current page data"""
        self.html_headers.add_unload_pagedata()
        page_data = self.session.data.setdefault(self.pageid, {})
        page_data[key] = value
        self.session.data[self.pageid] = page_data

    def del_page_data(self, key=None):
        """remove value associated to `key` in current page data
        if `key` is None, all page data will be cleared
        """
        if key is None:
            self.session.data.pop(self.pageid, None)
        else:
            try:
                page_data = self.session.data[self.pageid]
                del page_data[key]
            except KeyError:
                pass
            else:
                # make sure we write the session data value in the
                # self.session.data dict-like object so any session
                # handler can "detect" and manage the persistency
                self.session.data[self.pageid] = page_data

    # user-agent detection ####################################################

    @cached
    def useragent(self):
        return self.get_header('User-Agent', None)

    def ie_browser(self):
        useragent = self.useragent()
        return useragent and 'MSIE' in useragent

    @deprecated('[3.17] xhtml_browser is deprecated (xhtml is no longer served)')
    def xhtml_browser(self):
        """return True if the browser is considered as xhtml compatible.

        If the instance is configured to always return text/html and not
        application/xhtml+xml, this method will always return False, even though
        this is semantically different
        """
        return False

    def html_content_type(self):
        return 'text/html'

    def negotiated_language(self):
        self.headers_out.addHeader('Vary', 'Accept-Language')
        for lang in self.header_accept_language():
            if lang in self.translations:
                return lang
        return None


def _cnx_func(name):
    def proxy(req, *args, **kwargs):
        return getattr(req.cnx, name)(*args, **kwargs)
    return proxy

class _NeedAuthAccessMock(object):

    def __getattribute__(self, attr):
        raise AuthenticationError()

    def __bool__(self):
        return False

    __nonzero__ = __bool__

class _MockAnonymousSession(object):
    sessionid = 'thisisnotarealsession'

    @property
    def data(self):
        return {}

    @property
    def anonymous_session(self):
        return True

class ConnectionCubicWebRequestBase(_CubicWebRequestBase):
    cnx = None
    session = None

    def __init__(self, vreg, form=None, headers={}):
        """"""
        self.vreg = vreg
        try:
            # no vreg or config which doesn't handle translations
            self.translations = vreg.config.translations
        except AttributeError:
            self.translations = {}
        super(ConnectionCubicWebRequestBase, self).__init__(vreg, form=form, headers=headers)
        self.session = _MockAnonymousSession()
        self.cnx = self.user = _NeedAuthAccessMock()

    @property
    def transaction_data(self):
        return self.cnx.transaction_data

    def set_cnx(self, cnx):
        self.cnx = cnx
        self.session = cnx.session
        self._set_user(cnx.user)
        # set language according to the one defined on the connection which consider user's
        # preference
        self.set_language(cnx.lang)

    def execute(self, *args, **kwargs):
        rset = self.cnx.execute(*args, **kwargs)
        rset.req = self
        return rset

    entity_metas = _cnx_func('entity_metas')  # XXX deprecated
    entity_type = _cnx_func('entity_type')
    source_defs = _cnx_func('source_defs')

    # security #################################################################

    security_enabled = _cnx_func('security_enabled')

    # server-side service call #################################################

    def call_service(self, regid, **kwargs):
        return self.cnx.call_service(regid, **kwargs)

    # entities cache management ###############################################

    def entity_cache(self, eid):
        return self.transaction_data['req_ecache'][eid]

    def set_entity_cache(self, entity):
        ecache = self.transaction_data.setdefault('req_ecache', {})
        ecache.setdefault(entity.eid, entity)

    def cached_entities(self):
        return self.transaction_data.get('req_ecache', {}).values()

    def drop_entity_cache(self):
        self.transaction_data.pop('req_ecache', None)


CubicWebRequestBase = ConnectionCubicWebRequestBase


## HTTP-accept parsers / utilies ##############################################
def _mimetype_sort_key(accept_info):
    """accepted mimetypes must be sorted by :

    1/ highest score first
    2/ most specific mimetype first, e.g. :
       - 'text/html level=1' is more specific 'text/html'
       - 'text/html' is more specific than 'text/*'
       - 'text/*' itself more specific than '*/*'

    """
    raw_value, (media_type, media_subtype, media_type_params), score = accept_info
    # FIXME: handle '+' in media_subtype ? (should xhtml+xml have a
    # higher precedence than xml ?)
    if media_subtype == '*':
        score -= 0.0001
    if media_type == '*':
        score -= 0.0001
    return 1./score, media_type, media_subtype, 1./(1+len(media_type_params))

def _charset_sort_key(accept_info):
    """accepted mimetypes must be sorted by :

    1/ highest score first
    2/ most specific charset first, e.g. :
       - 'utf-8' is more specific than '*'
    """
    raw_value, value, score = accept_info
    if value == '*':
        score -= 0.0001
    return 1./score, value

def _parse_accept_header(raw_header, value_parser=None, value_sort_key=None):
    """returns an ordered list accepted types

    :param value_parser: a function to parse a raw accept chunk. If None
    is provided, the function defaults to identity. If a function is provided,
    it must accept 2 parameters ``value`` and ``other_params``. ``value`` is
    the value found before the first ';', `other_params` is a dictionary
    built from all other chunks after this first ';'

    :param value_sort_key: a key function to sort values found in the accept
    header. This function will be passed a 3-tuple
    (raw_value, parsed_value, score). If None is provided, the default
    sort_key is 1./score

    :return: a list of 3-tuple (raw_value, parsed_value, score),
    ordered by score. ``parsed_value`` will be the return value of
    ``value_parser(raw_value)``
    """
    if value_sort_key is None:
        value_sort_key = lambda infos: 1./infos[-1]
    values = []
    for info in raw_header.split(','):
        score = 1.0
        other_params = {}
        try:
            value, infodef = info.split(';', 1)
        except ValueError:
            value = info
        else:
            for info in infodef.split(';'):
                try:
                    infokey, infoval = info.split('=')
                    if infokey == 'q': # XXX 'level'
                        score = float(infoval)
                        continue
                except ValueError:
                    continue
                other_params[infokey] = infoval
        parsed_value = value_parser(value, other_params) if value_parser else value
        values.append( (value.strip(), parsed_value, score) )
    values.sort(key=value_sort_key)
    return values


def _mimetype_parser(value, other_params):
    """return a 3-tuple
    (type, subtype, type_params) corresponding to the mimetype definition
    e.g. : for 'text/*', `mimetypeinfo` will be ('text', '*', {}), for
    'text/html;level=1', `mimetypeinfo` will be ('text', '*', {'level': '1'})
    """
    try:
        media_type, media_subtype = value.strip().split('/', 1)
    except ValueError: # safety belt : '/' should always be present
        media_type = value.strip()
        media_subtype = '*'
    return (media_type, media_subtype, other_params)


ACCEPT_HEADER_PARSER = {
    'accept': (_mimetype_parser, _mimetype_sort_key),
    'accept-charset': (None, _charset_sort_key),
    }

from cubicweb import set_log_methods
set_log_methods(_CubicWebRequestBase, LOGGER)
