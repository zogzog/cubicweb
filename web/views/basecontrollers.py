# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.date import strptime

from cubicweb import (NoSelectableObject, ObjectNotFound, ValidationError,
                      AuthenticationError, typed_eid)
from cubicweb.utils import UStringIO, json, json_dumps
from cubicweb.uilib import exc_message
from cubicweb.selectors import authenticated_user, anonymous_user, match_form_params
from cubicweb.mail import format_mail
from cubicweb.web import Redirect, RemoteCallFailed, DirectResponse
from cubicweb.web.controller import Controller
from cubicweb.web.views import vid_from_rset, formrenderers

try:
    from cubicweb.web.facet import (FilterRQLBuilder, get_facet,
                                    prepare_facets_rqlst)
    HAS_SEARCH_RESTRICTION = True
except ImportError: # gae
    HAS_SEARCH_RESTRICTION = False

def jsonize(func):
    """decorator to sets correct content_type and calls `json_dumps` on
    results
    """
    def wrapper(self, *args, **kwargs):
        self._cw.set_content_type('application/json')
        return json_dumps(func(self, *args, **kwargs))
    wrapper.__name__ = func.__name__
    return wrapper

def xhtmlize(func):
    """decorator to sets correct content_type and calls `xmlize` on results"""
    def wrapper(self, *args, **kwargs):
        self._cw.set_content_type(self._cw.html_content_type())
        result = func(self, *args, **kwargs)
        return ''.join((self._cw.document_surrounding_div(), result.strip(),
                        u'</div>'))
    wrapper.__name__ = func.__name__
    return wrapper

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
            return self.appli.need_login_content(self._cw)


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
        # force base_url so on dual http/https configuration, we generate an url
        # on the http version of the site
        return self._cw.build_url('view', vid='index', __message=msg,
                                  base_url=self._cw.vreg.config['base-url'])


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
        self.add_to_breadcrumbs(view)
        self.validate_cache(view)
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

    def add_to_breadcrumbs(self, view):
        # update breadcrumbs **before** validating cache, unless the view
        # specifies explicitly it should not be added to breadcrumb or the
        # view is a binary view
        if view.add_to_breadcrumbs and not view.binary:
            self._cw.update_breadcrumbs()

    def execute_linkto(self, eid=None):
        """XXX __linkto parameter may cause security issue

        defined here since custom application controller inheriting from this
        one use this method?
        """
        req = self._cw
        if not '__linkto' in req.form:
            return
        if eid is None:
            eid = typed_eid(req.form['eid'])
        for linkto in req.list_form_param('__linkto', pop=True):
            rtype, eids, target = linkto.split(':')
            assert target in ('subject', 'object')
            eids = eids.split('_')
            if target == 'subject':
                rql = 'SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype
            else:
                rql = 'SET Y %s X WHERE X eid %%(x)s, Y eid %%(y)s' % rtype
            for teid in eids:
                req.execute(rql, {'x': eid, 'y': typed_eid(teid)})


def _validation_error(req, ex):
    req.cnx.rollback()
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
    except ValidationError, ex:
        return (False, _validation_error(req, ex), ctrl._edited_entity)
    except Redirect, ex:
        try:
            req.cnx.commit() # ValidationError may be raise on commit
        except ValidationError, ex:
            return (False, _validation_error(req, ex), ctrl._edited_entity)
        except Exception, ex:
            req.cnx.rollback()
            req.exception('unexpected error while validating form')
            return (False, str(ex).decode('utf-8'), ctrl._edited_entity)
        else:
            # complete entity: it can be used in js callbacks where we might
            # want every possible information
            if ctrl._edited_entity:
                ctrl._edited_entity.complete()
            return (True, ex.location, ctrl._edited_entity)
    except Exception, ex:
        req.cnx.rollback()
        req.exception('unexpected error while validating form')
        return (False, str(ex).decode('utf-8'), ctrl._edited_entity)
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
        self._cw.json_request = True
        # XXX unclear why we have a separated controller here vs
        # js_validate_form on the json controller
        status, args, entity = _validate_form(self._cw, self._cw.vreg)
        domid = self._cw.form.get('__domid', 'entityForm').encode(
            self._cw.encoding)
        return self.response(domid, status, args, entity)

def optional_kwargs(extraargs):
    if extraargs is None:
        return {}
    # we receive unicode keys which is not supported by the **syntax
    return dict((str(key), value) for key, value in extraargs.iteritems())


class JSonController(Controller):
    __regid__ = 'json'

    def publish(self, rset=None):
        """call js_* methods. Expected form keys:

        :fname: the method name without the js_ prefix
        :args: arguments list (json)

        note: it's the responsability of js_* methods to set the correct
        response content type
        """
        self._cw.json_request = True
        try:
            fname = self._cw.form['fname']
            func = getattr(self, 'js_%s' % fname)
        except KeyError:
            raise RemoteCallFailed('no method specified')
        except AttributeError:
            raise RemoteCallFailed('no %s method' % fname)
        # no <arg> attribute means the callback takes no argument
        args = self._cw.form.get('arg', ())
        if not isinstance(args, (list, tuple)):
            args = (args,)
        try:
            args = [json.loads(arg) for arg in args]
        except ValueError, exc:
            self.exception('error while decoding json arguments for js_%s: %s (err: %s)',
                           fname, args, exc)
            raise RemoteCallFailed(exc_message(exc, self._cw.encoding))
        try:
            result = func(*args)
        except (RemoteCallFailed, DirectResponse):
            raise
        except Exception, exc:
            self.exception('an exception occurred while calling js_%s(%s): %s',
                           fname, args, exc)
            raise RemoteCallFailed(exc_message(exc, self._cw.encoding))
        if result is None:
            return ''
        # get unicode on @htmlize methods, encoded string on @jsonize methods
        elif isinstance(result, unicode):
            return result.encode(self._cw.encoding)
        return result

    def _rebuild_posted_form(self, names, values, action=None):
        form = {}
        for name, value in zip(names, values):
            # remove possible __action_xxx inputs
            if name.startswith('__action'):
                if action is None:
                    # strip '__action_' to get the actual action name
                    action = name[9:]
                continue
            # form.setdefault(name, []).append(value)
            if name in form:
                curvalue = form[name]
                if isinstance(curvalue, list):
                    curvalue.append(value)
                else:
                    form[name] = [curvalue, value]
            else:
                form[name] = value
        # simulate click on __action_%s button to help the controller
        if action:
            form['__action_%s' % action] = u'whatever'
        return form

    def _exec(self, rql, args=None, rocheck=True):
        """json mode: execute RQL and return resultset as json"""
        rql = rql.strip()
        if rql.startswith('rql:'):
            rql = rql[4:]
        if rocheck:
            self._cw.ensure_ro_rql(rql)
        try:
            return self._cw.execute(rql, args)
        except Exception, ex:
            self.exception("error in _exec(rql=%s): %s", rql, ex)
            return None
        return None

    def _call_view(self, view, paginate=False, **kwargs):
        divid = self._cw.form.get('divid')
        # we need to call pagination before with the stream set
        try:
            stream = view.set_stream()
        except AttributeError:
            stream = UStringIO()
            kwargs['w'] = stream.write
            assert not paginate
        if divid == 'pageContent':
            # ensure divid isn't reused by the view (e.g. table view)
            del self._cw.form['divid']
            # mimick main template behaviour
            stream.write(u'<div id="pageContent">')
            vtitle = self._cw.form.get('vtitle')
            if vtitle:
                stream.write(u'<h1 class="vtitle">%s</h1>\n' % vtitle)
            paginate = True
        if paginate:
            view.paginate()
        if divid == 'pageContent':
            stream.write(u'<div id="contentmain">')
        view.render(**kwargs)
        extresources = self._cw.html_headers.getvalue(skiphead=True)
        if extresources:
            stream.write(u'<div class="ajaxHtmlHead">\n') # XXX use a widget ?
            stream.write(extresources)
            stream.write(u'</div>\n')
        if divid == 'pageContent':
            stream.write(u'</div></div>')
        return stream.getvalue()

    @xhtmlize
    def js_view(self):
        # XXX try to use the page-content template
        req = self._cw
        rql = req.form.get('rql')
        if rql:
            rset = self._exec(rql)
        elif 'eid' in req.form:
            rset = self._cw.eid_rset(req.form['eid'])
        else:
            rset = None
        vid = req.form.get('vid') or vid_from_rset(req, rset, self._cw.vreg.schema)
        try:
            view = self._cw.vreg['views'].select(vid, req, rset=rset)
        except NoSelectableObject:
            vid = req.form.get('fallbackvid', 'noresult')
            view = self._cw.vreg['views'].select(vid, req, rset=rset)
        self.validate_cache(view)
        return self._call_view(view, paginate=req.form.pop('paginate', False))

    @xhtmlize
    def js_prop_widget(self, propkey, varname, tabindex=None):
        """specific method for CWProperty handling"""
        entity = self._cw.vreg['etypes'].etype_class('CWProperty')(self._cw)
        entity.eid = varname
        entity['pkey'] = propkey
        form = self._cw.vreg['forms'].select('edition', self._cw, entity=entity)
        form.build_context()
        vfield = form.field_by_name('value')
        renderer = formrenderers.FormRenderer(self._cw)
        return vfield.render(form, renderer, tabindex=tabindex) \
               + renderer.render_help(form, vfield)

    @xhtmlize
    def js_component(self, compid, rql, registry='components', extraargs=None):
        if rql:
            rset = self._exec(rql)
        else:
            rset = None
        # XXX while it sounds good, addition of the try/except below cause pb:
        # when filtering using facets return an empty rset, the edition box
        # isn't anymore selectable, as expected. The pb is that with the
        # try/except below, we see a "an error occurred" message in the ui, while
        # we don't see it without it. Proper fix would probably be to deal with
        # this by allowing facet handling code to tell to js_component that such
        # error is expected and should'nt be reported.
        #try:
        comp = self._cw.vreg[registry].select(compid, self._cw, rset=rset,
                                              **optional_kwargs(extraargs))
        #except NoSelectableObject:
        #    raise RemoteCallFailed('unselectable')
        return self._call_view(comp, **optional_kwargs(extraargs))

    @xhtmlize
    def js_render(self, registry, oid, eid=None,
                  selectargs=None, renderargs=None):
        if eid is not None:
            rset = self._cw.eid_rset(eid)
            # XXX set row=0
        elif self._cw.form.get('rql'):
            rset = self._cw.execute(self._cw.form['rql'])
        else:
            rset = None
        view = self._cw.vreg[registry].select(oid, self._cw, rset=rset,
                                              **optional_kwargs(selectargs))
        return self._call_view(view, **optional_kwargs(renderargs))

    @check_pageid
    @xhtmlize
    def js_inline_creation_form(self, peid, petype, ttype, rtype, role, i18nctx):
        view = self._cw.vreg['views'].select('inline-creation', self._cw,
                                             etype=ttype, rtype=rtype, role=role,
                                             peid=peid, petype=petype)
        return self._call_view(view, i18nctx=i18nctx)

    @jsonize
    def js_validate_form(self, action, names, values):
        return self.validate_form(action, names, values)

    def validate_form(self, action, names, values):
        self._cw.form = self._rebuild_posted_form(names, values, action)
        return _validate_form(self._cw, self._cw.vreg)

    @xhtmlize
    def js_reledit_form(self):
        req = self._cw
        args = dict((x, req.form[x])
                    for x in ('formid', 'rtype', 'role', 'reload', 'action'))
        rset = req.eid_rset(typed_eid(self._cw.form['eid']))
        try:
            args['reload'] = json.loads(args['reload'])
        except ValueError: # not true/false, an absolute url
            assert args['reload'].startswith('http')
        view = req.vreg['views'].select('reledit', req, rset=rset, rtype=args['rtype'])
        return self._call_view(view, **args)

    @jsonize
    def js_i18n(self, msgids):
        """returns the translation of `msgid`"""
        return [self._cw._(msgid) for msgid in msgids]

    @jsonize
    def js_format_date(self, strdate):
        """returns the formatted date for `msgid`"""
        date = strptime(strdate, '%Y-%m-%d %H:%M:%S')
        return self._cw.format_date(date)

    @jsonize
    def js_external_resource(self, resource):
        """returns the URL of the external resource named `resource`"""
        return self._cw.uiprops[resource]

    @check_pageid
    @jsonize
    def js_user_callback(self, cbname):
        page_data = self._cw.session.data.get(self._cw.pageid, {})
        try:
            cb = page_data[cbname]
        except KeyError:
            return None
        return cb(self._cw)

    if HAS_SEARCH_RESTRICTION:
        @jsonize
        def js_filter_build_rql(self, names, values):
            form = self._rebuild_posted_form(names, values)
            self._cw.form = form
            builder = FilterRQLBuilder(self._cw)
            return builder.build_rql()

        @jsonize
        def js_filter_select_content(self, facetids, rql):
            rqlst = self._cw.vreg.parse(self._cw, rql) # XXX Union unsupported yet
            mainvar = prepare_facets_rqlst(rqlst)[0]
            update_map = {}
            for facetid in facetids:
                facet = get_facet(self._cw, facetid, rqlst.children[0], mainvar)
                update_map[facetid] = facet.possible_values()
            return update_map

    def js_unregister_user_callback(self, cbname):
        self._cw.unregister_callback(self._cw.pageid, cbname)

    def js_unload_page_data(self):
        self._cw.session.data.pop(self._cw.pageid, None)

    def js_cancel_edition(self, errorurl):
        """cancelling edition from javascript

        We need to clear associated req's data :
          - errorurl
          - pending insertions / deletions
        """
        self._cw.cancel_edition(errorurl)

    def js_delete_bookmark(self, beid):
        rql = 'DELETE B bookmarked_by U WHERE B eid %(b)s, U eid %(u)s'
        self._cw.execute(rql, {'b': typed_eid(beid), 'u' : self._cw.user.eid})

    def js_node_clicked(self, treeid, nodeeid):
        """add/remove eid in treestate cookie"""
        from cubicweb.web.views.treeview import treecookiename
        cookies = self._cw.get_cookie()
        statename = treecookiename(treeid)
        treestate = cookies.get(statename)
        if treestate is None:
            cookies[statename] = nodeeid
            self._cw.set_cookie(cookies, statename)
        else:
            marked = set(filter(None, treestate.value.split(':')))
            if nodeeid in marked:
                marked.remove(nodeeid)
            else:
                marked.add(nodeeid)
            cookies[statename] = ':'.join(marked)
            self._cw.set_cookie(cookies, statename)

    @jsonize
    def js_set_cookie(self, cookiename, cookievalue):
        # XXX we should consider jQuery.Cookie
        cookiename, cookievalue = str(cookiename), str(cookievalue)
        cookies = self._cw.get_cookie()
        cookies[cookiename] = cookievalue
        self._cw.set_cookie(cookies, cookiename)

    # relations edition stuff ##################################################

    def _add_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind
        pendings = self._cw.session.data.setdefault(key, set())
        pendings.add( (typed_eid(eidfrom), rel, typed_eid(eidto)) )

    def _remove_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind
        pendings = self._cw.session.data[key]
        pendings.remove( (typed_eid(eidfrom), rel, typed_eid(eidto)) )

    def js_remove_pending_insert(self, (eidfrom, rel, eidto)):
        self._remove_pending(eidfrom, rel, eidto, 'insert')

    def js_add_pending_inserts(self, tripletlist):
        for eidfrom, rel, eidto in tripletlist:
            self._add_pending(eidfrom, rel, eidto, 'insert')

    def js_remove_pending_delete(self, (eidfrom, rel, eidto)):
        self._remove_pending(eidfrom, rel, eidto, 'delete')

    def js_add_pending_delete(self, (eidfrom, rel, eidto)):
        self._add_pending(eidfrom, rel, eidto, 'delete')


# XXX move to massmailing

class MailBugReportController(Controller):
    __regid__ = 'reportbug'
    __select__ = match_form_params('description')

    def publish(self, rset=None):
        body = self._cw.form['description']
        self.sendmail(self._cw.config['submit-mail'],
                      self._cw._('%s error report') % self._cw.config.appid,
                      body)
        url = self._cw.build_url(__message=self._cw._('bug report sent'))
        raise Redirect(url)


class UndoController(Controller):
    __regid__ = 'undo'
    __select__ = authenticated_user() & match_form_params('txuuid')

    def publish(self, rset=None):
        txuuid = self._cw.form['txuuid']
        errors = self._cw.cnx.undo_transaction(txuuid)
        if not errors:
            self.redirect()
        return self._cw._('some errors occurred:') + self._cw.view(
            'pyvalist', pyvalue=errors)

    def redirect(self):
        req = self._cw
        breadcrumbs = req.session.data.get('breadcrumbs', None)
        if breadcrumbs is not None and len(breadcrumbs) > 1:
            url = req.rebuild_url(breadcrumbs[-2],
                                  __message=req._('transaction undoed'))
        else:
            url = req.build_url(__message=req._('transaction undoed'))
        raise Redirect(url)

