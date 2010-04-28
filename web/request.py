# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"

import Cookie
import sha
import time
import random
import base64
from datetime import date
from urlparse import urlsplit
from itertools import count

from rql.utils import rqlvar_maker

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated
from logilab.mtconverter import xml_escape

from cubicweb.dbapi import DBAPIRequest
from cubicweb.mail import header
from cubicweb.uilib import remove_html_tags
from cubicweb.utils import SizeConstrainedList, HTMLHead, make_uid
from cubicweb.view import STRICT_DOCTYPE, TRANSITIONAL_DOCTYPE_NOEXT
from cubicweb.web import (INTERNAL_FIELD_VALUE, LOGGER, NothingToEdit,
                          RequestError, StatusResponse, json)
from cubicweb.web.http_headers import Headers

dumps = json.dumps

_MARKER = object()


def list_form_param(form, param, pop=False):
    """get param from form parameters and return its value as a list,
    skipping internal markers if any

    * if the parameter isn't defined, return an empty list
    * if the parameter is a single (unicode) value, return a list
      containing that value
    * if the parameter is already a list or tuple, just skip internal
      markers

    if pop is True, the parameter is removed from the form dictionnary
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



class CubicWebRequestBase(DBAPIRequest):
    """abstract HTTP request, should be extended according to the HTTP backend"""
    json_request = False # to be set to True by json controllers

    def __init__(self, vreg, https, form=None):
        super(CubicWebRequestBase, self).__init__(vreg)
        self.authmode = vreg.config['auth-mode']
        self.https = https
        # raw html headers that can be added from any view
        self.html_headers = HTMLHead()
        # form parameters
        self.setup_params(form)
        # dictionnary that may be used to store request data that has to be
        # shared among various components used to publish the request (views,
        # controller, application...)
        self.data = {}
        # search state: 'normal' or 'linksearch' (eg searching for an object
        # to create a relation with another)
        self.search_state = ('normal',)
        # tabindex generator
        self.tabindexgen = count(1)
        self.next_tabindex = self.tabindexgen.next
        # page id, set by htmlheader template
        self.pageid = None
        self.datadir_url = self._datadir_url()
        self._set_pageid()
        # prepare output header
        self.headers_out = Headers()

    def _set_pageid(self):
        """initialize self.pageid
        if req.form provides a specific pageid, use it, otherwise build a
        new one.
        """
        pid = self.form.get('pageid')
        if pid is None:
            pid = make_uid(id(self))
        self.pageid = pid
        self.html_headers.define_var('pageid', pid, override=False)

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

    def set_session(self, session, user=None):
        """method called by the session handler when the user is authenticated
        or an anonymous connection is open
        """
        super(CubicWebRequestBase, self).set_session(session, user)
        # set request language
        vreg = self.vreg
        if self.user:
            try:
                # 1. user specified language
                lang = vreg.typed_value('ui.language',
                                        self.user.properties['ui.language'])
                self.set_language(lang)
                return
            except KeyError:
                pass
        if vreg.config['language-negociation']:
            # 2. http negociated language
            for lang in self.header_accept_language():
                if lang in self.translations:
                    self.set_language(lang)
                    return
        # 3. default language
        self.set_default_language(vreg)

    def set_language(self, lang):
        gettext, self.pgettext = self.translations[lang]
        self._ = self.__ = gettext
        self.lang = lang
        self.debug('request language: %s', lang)
        if self.cnx:
            self.cnx.set_session_props(lang=lang)

    # input form parameters management ########################################

    # common form parameters which should be protected against html values
    # XXX can't add 'eid' for instance since it may be multivalued
    # dont put rql as well, if query contains < and > it will be corrupted!
    no_script_form_params = set(('vid',
                                 'etype',
                                 'vtitle', 'title',
                                 '__message',
                                 '__redirectvid', '__redirectrql'))

    def setup_params(self, params):
        """WARNING: we're intentionaly leaving INTERNAL_FIELD_VALUE here

        subclasses should overrides to
        """
        self.form = {}
        if params is None:
            return
        encoding = self.encoding
        for param, val in params.iteritems():
            if isinstance(val, (tuple, list)):
                val = [unicode(x, encoding) for x in val]
                if len(val) == 1:
                    val = val[0]
            elif isinstance(val, str):
                val = unicode(val, encoding)
            if param in self.no_script_form_params and val:
                val = self.no_script_form_param(param, val)
            if param == '_cwmsgid':
                self.set_message_id(val)
            elif param == '__message':
                self.set_message(val)
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

        if pop is True, the parameter is removed from the form dictionnary
        """
        if form is None:
            form = self.form
        return list_form_param(form, param, pop)


    def reset_headers(self):
        """used by AutomaticWebTest to clear html headers between tests on
        the same resultset
        """
        self.html_headers = HTMLHead()
        return self

    # web state helpers #######################################################

    @property
    def message(self):
        try:
            return self.session.data.pop(self._msgid, '')
        except AttributeError:
            try:
                return self._msg
            except AttributeError:
                return None

    def set_message(self, msg):
        assert isinstance(msg, unicode)
        self._msg = msg

    def set_message_id(self, msgid):
        self._msgid = msgid

    @cached
    def redirect_message_id(self):
        return make_uid()

    def set_redirect_message(self, msg):
        assert isinstance(msg, unicode)
        msgid = self.redirect_message_id()
        self.session.data[msgid] = msg
        return msgid

    def append_to_redirect_message(self, msg):
        msgid = self.redirect_message_id()
        currentmsg = self.session.data.get(msgid)
        if currentmsg is not None:
            currentmsg = '%s %s' % (currentmsg, msg)
        else:
            currentmsg = msg
        self.session.data[msgid] = currentmsg
        return msgid

    def reset_message(self):
        if hasattr(self, '_msg'):
            del self._msg
        if hasattr(self, '_msgid'):
            del self._msgid

    def update_search_state(self):
        """update the current search state"""
        searchstate = self.form.get('__mode')
        if not searchstate and self.cnx:
            searchstate = self.session.data.get('search_state', 'normal')
        self.set_search_state(searchstate)

    def set_search_state(self, searchstate):
        """set a new search state"""
        if searchstate is None or searchstate == 'normal':
            self.search_state = (searchstate or 'normal',)
        else:
            self.search_state = ('linksearch', searchstate.split(':'))
            assert len(self.search_state[-1]) == 4
        if self.cnx:
            self.session.data['search_state'] = searchstate

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

    def update_breadcrumbs(self):
        """stores the last visisted page in session data"""
        searchstate = self.session.data.get('search_state')
        if searchstate == 'normal':
            breadcrumbs = self.session.data.get('breadcrumbs')
            if breadcrumbs is None:
                breadcrumbs = SizeConstrainedList(10)
                self.session.data['breadcrumbs'] = breadcrumbs
                breadcrumbs.append(self.url())
            else:
                url = self.url()
                if breadcrumbs and breadcrumbs[-1] != url:
                    breadcrumbs.append(url)

    def last_visited_page(self):
        breadcrumbs = self.session.data.get('breadcrumbs')
        if breadcrumbs:
            return breadcrumbs.pop()
        return self.base_url()

    def user_rql_callback(self, args, msg=None):
        """register a user callback to execute some rql query and return an url
        to call it ready to be inserted in html
        """
        def rqlexec(req, rql, args=None, key=None):
            req.execute(rql, args, key)
        return self.user_callback(rqlexec, args, msg)

    def user_callback(self, cb, args, msg=None, nonify=False):
        """register the given user callback and return an url to call it ready to be
        inserted in html
        """
        self.add_js('cubicweb.ajax.js')
        cbname = self.register_onetime_callback(cb, *args)
        msg = dumps(msg or '')
        return "javascript:userCallbackThenReloadPage('%s', %s)" % (
            cbname, msg)

    def register_onetime_callback(self, func, *args):
        cbname = 'cb_%s' % (
            sha.sha('%s%s%s%s' % (time.time(), func.__name__,
                                  random.random(),
                                  self.user.login)).hexdigest())
        def _cb(req):
            try:
                ret = func(req, *args)
            except TypeError:
                from warnings import warn
                warn('user callback should now take request as argument')
                ret = func(*args)
            self.unregister_callback(self.pageid, cbname)
            return ret
        self.set_page_data(cbname, _cb)
        return cbname

    def unregister_callback(self, pageid, cbname):
        assert pageid is not None
        assert cbname.startswith('cb_')
        self.info('unregistering callback %s for pageid %s', cbname, pageid)
        self.del_page_data(cbname)

    def clear_user_callbacks(self):
        if self.session is not None: # XXX
            for key in self.session.data.keys():
                if key.startswith('cb_'):
                    del self.session.data[key]

    # web edition helpers #####################################################

    @cached # so it's writed only once
    def fckeditor_config(self):
        self.add_js('fckeditor/fckeditor.js')
        self.html_headers.define_var('fcklang', self.lang)
        self.html_headers.define_var('fckconfigpath',
                                     self.build_url('data/cubicweb.fckcwconfig.js'))
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
        if isinstance(eids, basestring):
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
                if not param.startswith('__') and param != "eid":
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
        try:
            return Cookie.SimpleCookie(self.get_header('Cookie'))
        except KeyError:
            return Cookie.SimpleCookie()

    def set_cookie(self, cookie, key, maxage=300, expires=None):
        """set / update a cookie key

        by default, cookie will be available for the next 5 minutes.
        Give maxage = None to have a "session" cookie expiring when the
        client close its browser
        """
        morsel = cookie[key]
        if maxage is not None:
            morsel['Max-Age'] = maxage
        if expires:
            morsel['expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S %z')
        # make sure cookie is set on the correct path
        morsel['path'] = self.base_url_path()
        self.add_header('Set-Cookie', morsel.OutputString())

    def remove_cookie(self, cookie, key):
        """remove a cookie by expiring it"""
        self.set_cookie(cookie, key, maxage=0, expires=date(1970, 1, 1))

    def set_content_type(self, content_type, filename=None, encoding=None):
        """set output content type for this request. An optional filename
        may be given
        """
        if content_type.startswith('text/'):
            content_type += ';charset=' + (encoding or self.encoding)
        self.set_header('content-type', content_type)
        if filename:
            if isinstance(filename, unicode):
                filename = header(filename).encode()
            self.set_header('content-disposition', 'inline; filename=%s'
                            % filename)

    # high level methods for HTML headers management ##########################

    def add_onload(self, jscode):
        self.html_headers.add_onload(jscode)

    def add_js(self, jsfiles, localfile=True):
        """specify a list of JS files to include in the HTML headers
        :param jsfiles: a JS filename or a list of JS filenames
        :param localfile: if True, the default data dir prefix is added to the
                          JS filename
        """
        if isinstance(jsfiles, basestring):
            jsfiles = (jsfiles,)
        for jsfile in jsfiles:
            if localfile:
                jsfile = self.datadir_url + jsfile
            self.html_headers.add_js(jsfile)

    def add_css(self, cssfiles, media=u'all', localfile=True, ieonly=False,
                iespec=u'[if lt IE 8]'):
        """specify a CSS file to include in the HTML headers

        :param cssfiles: a CSS filename or a list of CSS filenames
        :param media: the CSS's media if necessary
        :param localfile: if True, the default data dir prefix is added to the
                          CSS filename
        :param ieonly: True if this css is specific to IE
        :param iespec: conditional expression that will be used around
                       the css inclusion. cf:
                       http://msdn.microsoft.com/en-us/library/ms537512(VS.85).aspx
        """
        if isinstance(cssfiles, basestring):
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
                cssfile = self.datadir_url + cssfile
            add_css(cssfile, media, *extraargs)

    def build_ajax_replace_url(self, nodeid, rql, vid, replacemode='replace',
                               **extraparams):
        """builds an ajax url that will replace nodeid's content

        :param nodeid: the dom id of the node to replace
        :param rql: rql to execute
        :param vid: the view to apply on the resultset
        :param replacemode: defines how the replacement should be done.

        Possible values are :
        - 'replace' to replace the node's content with the generated HTML
        - 'swap' to replace the node itself with the generated HTML
        - 'append' to append the generated HTML to the node's content
        """
        url = self.build_url('view', rql=rql, vid=vid, __notemplate=1,
                             **extraparams)
        return "javascript: loadxhtml('%s', '%s', '%s')" % (
            nodeid, xml_escape(url), replacemode)

    # urls/path management ####################################################

    def url(self, includeparams=True):
        """return currently accessed url"""
        return self.base_url() + self.relative_path(includeparams)

    def _datadir_url(self):
        """return url of the instance's data directory"""
        return self.base_url() + 'data%s/' % self.vreg.config.instance_md5_version()

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

    @cached
    def from_controller(self):
        """return the id (string) of the controller issuing the request"""
        controller = self.relative_path(False).split('/', 1)[0]
        registered_controllers = self.vreg['controllers'].keys()
        if controller in registered_controllers:
            return controller
        return 'view'

    def external_resource(self, rid, default=_MARKER):
        """return a path to an external resource, using its identifier

        raise KeyError  if the resource is not defined
        """
        try:
            value = self.vreg.config.ext_resources[rid]
        except KeyError:
            if default is _MARKER:
                raise
            return default
        if value is None:
            return None
        baseurl = self.datadir_url[:-1] # remove trailing /
        if isinstance(value, list):
            return [v.replace('DATADIR', baseurl) for v in value]
        return value.replace('DATADIR', baseurl)
    external_resource = cached(external_resource, keyarg=1)

    def validate_cache(self):
        """raise a `DirectResponse` exception if a cached page along the way
        exists and is still usable.

        calls the client-dependant implementation of `_validate_cache`
        """
        self._validate_cache()
        if self.http_method() == 'HEAD':
            raise StatusResponse(200, '')

    # abstract methods to override according to the web front-end #############

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        raise NotImplementedError()

    def _validate_cache(self):
        """raise a `DirectResponse` exception if a cached page along the way
        exists and is still usable
        """
        raise NotImplementedError()

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the instance's root, but some other normalization may be needed
        so that the returned path may be used to compare to generated urls

        :param includeparams:
           boolean indicating if GET form parameters should be kept in the path
        """
        raise NotImplementedError()

    def get_header(self, header, default=None):
        """return the value associated with the given input HTTP header,
        raise KeyError if the header is not set
        """
        raise NotImplementedError()

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
                user, passwd = base64.decodestring(rest).split(":", 1)
                # XXX HTTP header encoding: use email.Header?
                return user.decode('UTF8'), passwd
            except Exception, ex:
                self.debug('bad authorization %s (%s: %s)',
                           auth, ex.__class__.__name__, ex)
        return None, None

    @deprecated("[3.4] use parse_accept_header('Accept-Language')")
    def header_accept_language(self):
        """returns an ordered list of preferred languages"""
        return [value.split('-')[0] for value in
                self.parse_accept_header('Accept-Language')]

    def parse_accept_header(self, header):
        """returns an ordered list of preferred languages"""
        accepteds = self.get_header(header, '')
        values = []
        for info in accepteds.split(','):
            try:
                value, scores = info.split(';', 1)
            except ValueError:
                value = info
                score = 1.0
            else:
                for score in scores.split(';'):
                    try:
                        scorekey, scoreval = score.split('=')
                        if scorekey == 'q': # XXX 'level'
                            score = float(scoreval)
                    except ValueError:
                        continue
            values.append((score, value))
        values.sort(reverse=True)
        return (value for (score, value) in values)

    def header_if_modified_since(self):
        """If the HTTP header If-modified-since is set, return the equivalent
        mx date time value (GMT), else return None
        """
        raise NotImplementedError()

    def demote_to_html(self):
        """helper method to dynamically set request content type to text/html

        The global doctype and xmldec must also be changed otherwise the browser
        will display '<[' at the beginning of the page
        """
        self.set_content_type('text/html')
        self.main_stream.doctype = TRANSITIONAL_DOCTYPE_NOEXT
        self.main_stream.xmldecl = u''

    # page data management ####################################################

    def get_page_data(self, key, default=None):
        """return value associated to `key` in curernt page data"""
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
                del self.session.data[self.pageid][key]
            except KeyError:
                pass

    # user-agent detection ####################################################

    @cached
    def useragent(self):
        return self.get_header('User-Agent', None)

    def ie_browser(self):
        useragent = self.useragent()
        return useragent and 'MSIE' in useragent

    def xhtml_browser(self):
        """return True if the browser is considered as xhtml compatible.

        If the instance is configured to always return text/html and not
        application/xhtml+xml, this method will always return False, even though
        this is semantically different
        """
        if self.vreg.config['force-html-content-type']:
            return False
        useragent = self.useragent()
        # * MSIE/Konqueror does not support xml content-type
        # * Opera supports xhtml and handles namespaces properly but it breaks
        #   jQuery.attr()
        if useragent and ('MSIE' in useragent or 'KHTML' in useragent
                          or 'Opera' in useragent):
            return False
        return True

    def html_content_type(self):
        if self.xhtml_browser():
            return 'application/xhtml+xml'
        return 'text/html'

    def document_surrounding_div(self):
        if self.xhtml_browser():
            return (u'<?xml version="1.0"?>\n' + STRICT_DOCTYPE + # XXX encoding ?
                    u'<div xmlns="http://www.w3.org/1999/xhtml" xmlns:cubicweb="http://www.logilab.org/2008/cubicweb">')
        return u'<div>'

from cubicweb import set_log_methods
set_log_methods(CubicWebRequestBase, LOGGER)
