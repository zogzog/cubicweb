# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Set of base controllers, which are directly plugged into the application
object to handle publication.
"""


from cubicweb import _

from warnings import warn

from six import text_type
from six.moves import http_client

from logilab.common.deprecation import deprecated

from cubicweb import (NoSelectableObject, ObjectNotFound, ValidationError,
                      AuthenticationError, UndoTransactionException,
                      Forbidden)
from cubicweb.utils import json_dumps
from cubicweb.predicates import (authenticated_user, anonymous_user,
                                match_form_params)
from cubicweb.web import Redirect, RemoteCallFailed
from cubicweb.web.controller import Controller, append_url_params
from cubicweb.web.views import vid_from_rset
import cubicweb.transaction as tx

@deprecated('[3.15] jsonize is deprecated, use AjaxFunction appobjects instead')
def jsonize(func):
    """decorator to sets correct content_type and calls `json_dumps` on
    results
    """
    def wrapper(self, *args, **kwargs):
        self._cw.set_content_type('application/json')
        return json_dumps(func(self, *args, **kwargs))
    wrapper.__name__ = func.__name__
    return wrapper

@deprecated('[3.15] xhtmlize is deprecated, use AjaxFunction appobjects instead')
def xhtmlize(func):
    """decorator to sets correct content_type and calls `xmlize` on results"""
    def wrapper(self, *args, **kwargs):
        self._cw.set_content_type(self._cw.html_content_type())
        result = func(self, *args, **kwargs)
        return ''.join((u'<div>', result.strip(),
                        u'</div>'))
    wrapper.__name__ = func.__name__
    return wrapper

@deprecated('[3.15] check_pageid is deprecated, use AjaxFunction appobjects instead')
def check_pageid(func):
    """decorator which checks the given pageid is found in the
    user's session data
    """
    def wrapper(self, *args, **kwargs):
        data = self._cw.session.data.get(self._cw.pageid)
        if data is None:
            raise RemoteCallFailed(self._cw._('pageid-not-found'))
        return func(self, *args, **kwargs)
    return wrapper


class LoginController(Controller):
    __regid__ = 'login'
    __select__ = anonymous_user()

    def publish(self, rset=None):
        """log in the instance"""
        if self._cw.vreg.config['auth-mode'] == 'http':
            # HTTP authentication
            raise AuthenticationError()
        else:
            # Cookie authentication
            self._cw.status_out = http_client.FORBIDDEN
            return self.appli.need_login_content(self._cw)

class LoginControllerForAuthed(Controller):
    __regid__ = 'login'
    __select__ = ~anonymous_user()

    def publish(self, rset=None):
        """log in the instance"""
        path = self._cw.form.get('postlogin_path', '')
        # Redirect expects a URL, not a path. Also path may contain a query
        # string, hence should not be given to _cw.build_url()
        raise Redirect(self._cw.base_url() + path)


class LogoutController(Controller):
    __regid__ = 'logout'

    def publish(self, rset=None):
        """logout from the instance"""
        return self.appli.session_handler.logout(self._cw, self.goto_url())

    def goto_url(self):
        # * in http auth mode, url will be ignored
        # * in cookie mode redirecting to the index view is enough : either
        #   anonymous connection is allowed and the page will be displayed or
        #   we'll be redirected to the login form
        msg = self._cw._('you have been logged out')
        return self._cw.build_url('view', vid='loggedout')


class ViewController(Controller):
    """standard entry point :
    - build result set
    - select and call main template
    """
    __regid__ = 'view'
    template = 'main-template'

    def publish(self, rset=None):
        """publish a request, returning an encoded string"""
        view, rset = self._select_view_and_rset(rset)
        view.set_http_cache_headers()
        if self._cw.is_client_cache_valid():
            return b''
        template = self.appli.main_template_id(self._cw)
        return self._cw.vreg['views'].main_template(self._cw, template,
                                                    rset=rset, view=view)

    def _select_view_and_rset(self, rset):
        req = self._cw
        if rset is None and not hasattr(req, '_rql_processed'):
            req._rql_processed = True
            if req.cnx:
                rset = self.process_rql()
            else:
                rset = None
        vid = req.form.get('vid') or vid_from_rset(req, rset, self._cw.vreg.schema)
        try:
            view = self._cw.vreg['views'].select(vid, req, rset=rset)
        except ObjectNotFound:
            self.warning("the view %s could not be found", vid)
            req.set_message(req._("The view %s could not be found") % vid)
            vid = vid_from_rset(req, rset, self._cw.vreg.schema)
            view = self._cw.vreg['views'].select(vid, req, rset=rset)
        except NoSelectableObject:
            if rset:
                req.set_message(req._("The view %s can not be applied to this query") % vid)
            else:
                req.set_message(req._("You have no access to this view or it can not "
                                      "be used to display the current data."))
            vid = req.form.get('fallbackvid') or vid_from_rset(req, rset, req.vreg.schema)
            view = req.vreg['views'].select(vid, req, rset=rset)
        return view, rset

    def execute_linkto(self, eid=None):
        """XXX __linkto parameter may cause security issue

        defined here since custom application controller inheriting from this
        one use this method?
        """
        req = self._cw
        if not '__linkto' in req.form:
            return
        if eid is None:
            eid = int(req.form['eid'])
        for linkto in req.list_form_param('__linkto', pop=True):
            rtype, eids, target = linkto.split(':')
            assert target in ('subject', 'object')
            eids = eids.split('_')
            if target == 'subject':
                rql = 'SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype
            else:
                rql = 'SET Y %s X WHERE X eid %%(x)s, Y eid %%(y)s' % rtype
            for teid in eids:
                req.execute(rql, {'x': eid, 'y': int(teid)})


def _validation_error(req, ex):
    req.cnx.rollback()
    ex.translate(req._) # translate messages using ui language
    # XXX necessary to remove existant validation error?
    # imo (syt), it's not necessary
    req.session.data.pop(req.form.get('__errorurl'), None)
    foreid = ex.entity
    eidmap = req.data.get('eidmap', {})
    for var, eid in eidmap.items():
        if foreid == eid:
            foreid = var
            break
    return (foreid, ex.errors)


def _validate_form(req, vreg):
    # XXX should use the `RemoteCallFailed` mechanism
    try:
        ctrl = vreg['controllers'].select('edit', req=req)
    except NoSelectableObject:
        return (False, {None: req._('not authorized')}, None)
    try:
        ctrl.publish(None)
    except ValidationError as ex:
        return (False, _validation_error(req, ex), ctrl._edited_entity)
    except Redirect as ex:
        try:
            txuuid = req.cnx.commit() # ValidationError may be raised on commit
        except ValidationError as ex:
            return (False, _validation_error(req, ex), ctrl._edited_entity)
        except Exception as ex:
            req.cnx.rollback()
            req.exception('unexpected error while validating form')
            return (False, str(ex).decode('utf-8'), ctrl._edited_entity)
        else:
            if txuuid is not None:
                req.data['last_undoable_transaction'] = txuuid
            # complete entity: it can be used in js callbacks where we might
            # want every possible information
            if ctrl._edited_entity:
                ctrl._edited_entity.complete()
            return (True, ex.location, ctrl._edited_entity)
    except Exception as ex:
        req.cnx.rollback()
        req.exception('unexpected error while validating form')
        return (False, text_type(ex), ctrl._edited_entity)
    return (False, '???', None)


class FormValidatorController(Controller):
    __regid__ = 'validateform'

    def response(self, domid, status, args, entity):
        callback = str(self._cw.form.get('__onsuccess', 'null'))
        errback = str(self._cw.form.get('__onfailure', 'null'))
        cbargs = str(self._cw.form.get('__cbargs', 'null'))
        self._cw.set_content_type('text/html')
        jsargs = json_dumps((status, args, entity))
        return """<script type="text/javascript">
 window.parent.handleFormValidationResponse('%s', %s, %s, %s, %s);
</script>""" %  (domid, callback, errback, jsargs, cbargs)

    def publish(self, rset=None):
        self._cw.ajax_request = True
        # XXX unclear why we have a separated controller here vs
        # js_validate_form on the json controller
        status, args, entity = _validate_form(self._cw, self._cw.vreg)
        domid = self._cw.form.get('__domid', 'entityForm')
        return self.response(domid, status, args, entity).encode(self._cw.encoding)


class JSonController(Controller):
    __regid__ = 'json'

    def publish(self, rset=None):
        warn('[3.15] JSONController is deprecated, use AjaxController instead',
             DeprecationWarning)
        ajax_controller = self._cw.vreg['controllers'].select('ajax', self._cw, appli=self.appli)
        return ajax_controller.publish(rset)


class MailBugReportController(Controller):
    __regid__ = 'reportbug'
    __select__ = match_form_params('description')

    def publish(self, rset=None):
        req = self._cw
        desc = req.form['description']
        # The description is generated and signed by cubicweb itself, check
        # description's signature so we don't want to send spam here
        sign = req.form.get('__signature', '')
        if not (sign and req.vreg.config.check_text_sign(desc, sign)):
            raise Forbidden('Invalid content')
        self.sendmail(req.vreg.config['submit-mail'],
                      req._('%s error report') % req.vreg.config.appid,
                      desc)
        raise Redirect(req.build_url(__message=req._('bug report sent')))


class UndoController(Controller):
    __regid__ = 'undo'
    __select__ = authenticated_user() & match_form_params('txuuid')

    def publish(self, rset=None):
        txuuid = self._cw.form['txuuid']
        try:
            self._cw.cnx.undo_transaction(txuuid)
        except UndoTransactionException as exc:
            errors = exc.errors
            #This will cause a rollback in main_publish
            raise ValidationError(None, {None: '\n'.join(errors)})
        else :
            self.redirect() # Will raise Redirect

    def redirect(self, msg=None):
        req = self._cw
        msg = msg or req._("transaction undone")
        self._redirect({'_cwmsgid': req.set_redirect_message(msg)})
