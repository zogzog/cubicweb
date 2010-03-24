# -*- coding: utf-8 -*-
"""Set of base controllers, which are directly plugged into the application
object to handle publication.


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from smtplib import SMTP

import simplejson

from logilab.common.decorators import cached
from logilab.common.date import strptime

from cubicweb import (NoSelectableObject, ValidationError, ObjectNotFound,
                      typed_eid)
from cubicweb.utils import CubicWebJsonEncoder
from cubicweb.selectors import authenticated_user, match_form_params
from cubicweb.mail import format_mail
from cubicweb.web import ExplicitLogin, Redirect, RemoteCallFailed, json_dumps
from cubicweb.web.controller import Controller
from cubicweb.web.views import vid_from_rset
from cubicweb.web.views.formrenderers import FormRenderer
try:
    from cubicweb.web.facet import (FilterRQLBuilder, get_facet,
                                    prepare_facets_rqlst)
    HAS_SEARCH_RESTRICTION = True
except ImportError: # gae
    HAS_SEARCH_RESTRICTION = False

def jsonize(func):
    """decorator to sets correct content_type and calls `simplejson.dumps` on
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
        data = self._cw.get_session_data(self._cw.pageid)
        if data is None:
            raise RemoteCallFailed(self._cw._('pageid-not-found'))
        return func(self, *args, **kwargs)
    return wrapper


class LoginController(Controller):
    __regid__ = 'login'

    def publish(self, rset=None):
        """log in the instance"""
        if self._cw.vreg.config['auth-mode'] == 'http':
            # HTTP authentication
            raise ExplicitLogin()
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
        if self._cw.https:
            # XXX hack to generate an url on the http version of the site
            self._cw._base_url =  self._cw.vreg.config['base-url']
            self._cw.https = False
        return self._cw.build_url('view', vid='index', __message=msg)

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
            rset = self.process_rql(req.form.get('rql'))
        if rset and rset.rowcount == 1 and '__method' in req.form:
            entity = rset.get_entity(0, 0)
            try:
                method = getattr(entity, req.form.pop('__method'))
                method()
            except Redirect: # propagate redirect that might occur in method()
                raise
            except Exception, ex:
                self.exception('while handling __method')
                req.set_message(req._("error while handling __method: %s") % req._(ex))
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
            self.warning("the view %s can not be applied to this query", vid)
            vid = req.form.get('fallbackvid') or vid_from_rset(req, rset, req.vreg.schema)
            view = req.vreg['views'].select(vid, req, rset=rset)
        return view, rset

    def add_to_breadcrumbs(self, view):
        # update breadcrumps **before** validating cache, unless the view
        # specifies explicitly it should not be added to breadcrumb or the
        # view is a binary view
        if view.add_to_breadcrumbs and not view.binary:
            self._cw.update_breadcrumbs()

    def validate_cache(self, view):
        view.set_http_cache_headers()
        self._cw.validate_cache()

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
                req.execute(rql, {'x': eid, 'y': typed_eid(teid)}, ('x', 'y'))


def _validation_error(req, ex):
    req.cnx.rollback()
    # XXX necessary to remove existant validation error?
    # imo (syt), it's not necessary
    req.get_session_data(req.form.get('__errorurl'), pop=True)
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
            return (False, req._(str(ex).decode('utf-8')), ctrl._edited_entity)
        else:
            # complete entity: it can be used in js callbacks where we might
            # want every possible information
            if ctrl._edited_entity:
                ctrl._edited_entity.complete()
            return (True, ex.location, ctrl._edited_entity)
    except Exception, ex:
        req.cnx.rollback()
        req.exception('unexpected error while validating form')
        return (False, req._(str(ex).decode('utf-8')), ctrl._edited_entity)
    return (False, '???', None)


class FormValidatorController(Controller):
    __regid__ = 'validateform'

    def response(self, domid, status, args, entity):
        callback = str(self._cw.form.get('__onsuccess', 'null'))
        errback = str(self._cw.form.get('__onfailure', 'null'))
        cbargs = str(self._cw.form.get('__cbargs', 'null'))
        self._cw.set_content_type('text/html')
        jsargs = simplejson.dumps((status, args, entity), cls=CubicWebJsonEncoder)
        return """<script type="text/javascript">
 wp = window.parent;
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
        args = [simplejson.loads(arg) for arg in args]
        try:
            result = func(*args)
        except RemoteCallFailed:
            raise
        except Exception, ex:
            import traceback
            traceback.print_exc()
            self.exception('an exception occured while calling js_%s(%s): %s',
                           fname, args, ex)
            raise RemoteCallFailed(repr(ex))
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

    def _exec(self, rql, args=None, eidkey=None, rocheck=True):
        """json mode: execute RQL and return resultset as json"""
        if rocheck:
            self._cw.ensure_ro_rql(rql)
        try:
            return self._cw.execute(rql, args, eidkey)
        except Exception, ex:
            self.exception("error in _exec(rql=%s): %s", rql, ex)
            return None
        return None

    def _call_view(self, view, **kwargs):
        req = self._cw
        divid = req.form.get('divid', 'pageContent')
        # we need to call pagination before with the stream set
        stream = view.set_stream()
        if req.form.get('paginate'):
            if divid == 'pageContent':
                # mimick main template behaviour
                stream.write(u'<div id="pageContent">')
                vtitle = self._cw.form.get('vtitle')
                if vtitle:
                    stream.write(u'<h1 class="vtitle">%s</h1>\n' % vtitle)
            view.paginate()
            if divid == 'pageContent':
                stream.write(u'<div id="contentmain">')
        view.render(**kwargs)
        extresources = req.html_headers.getvalue(skiphead=True)
        if extresources:
            stream.write(u'<div class="ajaxHtmlHead">\n') # XXX use a widget ?
            stream.write(extresources)
            stream.write(u'</div>\n')
        if req.form.get('paginate') and divid == 'pageContent':
            stream.write(u'</div></div>')
        return stream.getvalue()

    @xhtmlize
    def js_view(self):
        # XXX try to use the page-content template
        req = self._cw
        rql = req.form.get('rql')
        if rql:
            rset = self._exec(rql)
        else:
            rset = None
        vid = req.form.get('vid') or vid_from_rset(req, rset, self._cw.vreg.schema)
        try:
            view = self._cw.vreg['views'].select(vid, req, rset=rset)
        except NoSelectableObject:
            vid = req.form.get('fallbackvid', 'noresult')
            view = self._cw.vreg['views'].select(vid, req, rset=rset)
        self.validate_cache(view)
        return self._call_view(view)

    @xhtmlize
    def js_prop_widget(self, propkey, varname, tabindex=None):
        """specific method for CWProperty handling"""
        entity = self._cw.vreg['etypes'].etype_class('CWProperty')(self._cw)
        entity.eid = varname
        entity['pkey'] = propkey
        form = self._cw.vreg['forms'].select('edition', self._cw, entity=entity)
        form.build_context()
        vfield = form.field_by_name('value')
        renderer = FormRenderer(self._cw)
        return vfield.render(form, renderer, tabindex=tabindex) \
               + renderer.render_help(form, vfield)

    @xhtmlize
    def js_component(self, compid, rql, registry='components', extraargs=None):
        if rql:
            rset = self._exec(rql)
        else:
            rset = None
        if extraargs is None:
            extraargs = {}
        else: # we receive unicode keys which is not supported by the **syntax
            extraargs = dict((str(key), value)
                             for key, value in extraargs.items())
        comp = self._cw.vreg[registry].select(compid, self._cw, rset=rset, **extraargs)
        extraargs = extraargs or {}
        stream = comp.set_stream()
        comp.render(**extraargs)
        extresources = self._cw.html_headers.getvalue(skiphead=True)
        if extresources:
            stream.write(u'<div class="ajaxHtmlHead">\n')
            stream.write(extresources)
            stream.write(u'</div>\n')
        return stream.getvalue()

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
        args = dict((x, self._cw.form[x])
                    for x in frozenset(('rtype', 'role', 'reload', 'landing_zone')))
        entity = self._cw.entity_from_eid(int(self._cw.form['eid']))
        # note: default is reserved in js land
        args['default'] = self._cw.form['default_value']
        args['reload'] = simplejson.loads(args['reload'])
        rset = req.eid_rset(int(self._cw.form['eid']))
        view = req.vreg['views'].select('doreledit', req, rset=rset, rtype=args['rtype'])
        stream = view.set_stream()
        view.render(**args)
        extresources = req.html_headers.getvalue(skiphead=True)
        if extresources:
            stream.write(u'<div class="ajaxHtmlHead">\n')
            stream.write(extresources)
            stream.write(u'</div>\n')
        return stream.getvalue()

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
        return self._cw.external_resource(resource)

    @check_pageid
    @jsonize
    def js_user_callback(self, cbname):
        page_data = self._cw.get_session_data(self._cw.pageid, {})
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
        self._cw.del_session_data(self._cw.pageid)

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
            marked = set(filter(None, treestate.value.split(';')))
            if nodeeid in marked:
                marked.remove(nodeeid)
            else:
                marked.add(nodeeid)
            cookies[statename] = ';'.join(marked)
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
        pendings = self._cw.get_session_data(key, set())
        pendings.add( (typed_eid(eidfrom), rel, typed_eid(eidto)) )
        self._cw.set_session_data(key, pendings)

    def _remove_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind
        pendings = self._cw.get_session_data(key)
        pendings.remove( (typed_eid(eidfrom), rel, typed_eid(eidto)) )
        self._cw.set_session_data(key, pendings)

    def js_remove_pending_insert(self, (eidfrom, rel, eidto)):
        self._remove_pending(eidfrom, rel, eidto, 'insert')

    def js_add_pending_inserts(self, tripletlist):
        for eidfrom, rel, eidto in tripletlist:
            self._add_pending(eidfrom, rel, eidto, 'insert')

    def js_remove_pending_delete(self, (eidfrom, rel, eidto)):
        self._remove_pending(eidfrom, rel, eidto, 'delete')

    def js_add_pending_delete(self, (eidfrom, rel, eidto)):
        self._add_pending(eidfrom, rel, eidto, 'delete')

    # XXX specific code. Kill me and my AddComboBox friend
    @jsonize
    def js_add_and_link_new_entity(self, etype_to, rel, eid_to, etype_from, value_from):
        # create a new entity
        eid_from = self._cw.execute('INSERT %s T : T name "%s"' % ( etype_from, value_from ))[0][0]
        # link the new entity to the main entity
        rql = 'SET F %(rel)s T WHERE F eid %(eid_to)s, T eid %(eid_from)s' % {'rel' : rel, 'eid_to' : eid_to, 'eid_from' : eid_from}
        return eid_from


class SendMailController(Controller):
    __regid__ = 'sendmail'
    __select__ = authenticated_user() & match_form_params('recipient', 'mailbody', 'subject')

    def recipients(self):
        """returns an iterator on email's recipients as entities"""
        eids = self._cw.form['recipient']
        # make sure we have a list even though only one recipient was specified
        if isinstance(eids, basestring):
            eids = (eids,)
        rql = 'Any X WHERE X eid in (%s)' % (','.join(eids))
        rset = self._cw.execute(rql)
        for entity in rset.entities():
            yield entity

    @property
    @cached
    def smtp(self):
        mailhost, port = self._cw.config['smtp-host'], self._cw.config['smtp-port']
        try:
            return SMTP(mailhost, port)
        except Exception, ex:
            self.exception("can't connect to smtp server %s:%s (%s)",
                             mailhost, port, ex)
            url = self._cw.build_url(__message=self._cw._('could not connect to the SMTP server'))
            raise Redirect(url)

    def sendmail(self, recipient, subject, body):
        helo_addr = '%s <%s>' % (self._cw.config['sender-name'],
                                 self._cw.config['sender-addr'])
        msg = format_mail({'email' : self._cw.user.get_email(),
                           'name' : self._cw.user.dc_title(),},
                          [recipient], body, subject)
        self.smtp.sendmail(helo_addr, [recipient], msg.as_string())

    def publish(self, rset=None):
        # XXX this allows users with access to an cubicweb instance to use it as
        # a mail relay
        body = self._cw.form['mailbody']
        subject = self._cw.form['subject']
        for recipient in self.recipients():
            text = body % recipient.as_email_context()
            self.sendmail(recipient.get_email(), subject, text)
        # breadcrumbs = self._cw.get_session_data('breadcrumbs', None)
        url = self._cw.build_url(__message=self._cw._('emails successfully sent'))
        raise Redirect(url)


class MailBugReportController(SendMailController):
    __regid__ = 'reportbug'
    __select__ = match_form_params('description')

    def publish(self, rset=None):
        body = self._cw.form['description']
        self.sendmail(self._cw.config['submit-mail'], _('%s error report') % self._cw.config.appid, body)
        url = self._cw.build_url(__message=self._cw._('bug report sent'))
        raise Redirect(url)


class UndoController(SendMailController):
    __regid__ = 'undo'
    __select__ = authenticated_user() & match_form_params('txuuid')

    def publish(self, rset=None):
        txuuid = self._cw.form['txuuid']
        errors = self._cw.cnx.undo_transaction(txuuid)
        if errors:
            self.w(self._cw._('some errors occured:'))
            self.wview('pyvalist', pyvalue=errors)
        else:
            self.redirect()

    def redirect(self):
        req = self._cw
        breadcrumbs = req.get_session_data('breadcrumbs', None)
        if breadcrumbs is not None and len(breadcrumbs) > 1:
            url = req.rebuild_url(breadcrumbs[-2],
                                  __message=req._('transaction undoed'))
        else:
            url = req.build_url(__message=req._('transaction undoed'))
        raise Redirect(url)

