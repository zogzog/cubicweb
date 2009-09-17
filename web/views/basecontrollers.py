# -*- coding: utf-8 -*-
"""Set of base controllers, which are directly plugged into the application
object to handle publication.


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from smtplib import SMTP

import simplejson

from logilab.common.decorators import cached

from cubicweb import NoSelectableObject, ValidationError, ObjectNotFound, typed_eid
from cubicweb.utils import strptime, CubicWebJsonEncoder
from cubicweb.selectors import yes, match_user_groups
from cubicweb.common.mail import format_mail
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
        self.req.set_content_type('application/json')
        return json_dumps(func(self, *args, **kwargs))
    wrapper.__name__ = func.__name__
    return wrapper

def xhtmlize(func):
    """decorator to sets correct content_type and calls `xmlize` on results"""
    def wrapper(self, *args, **kwargs):
        self.req.set_content_type(self.req.html_content_type())
        result = func(self, *args, **kwargs)
        return ''.join((self.req.document_surrounding_div(), result.strip(),
                        u'</div>'))
    wrapper.__name__ = func.__name__
    return wrapper

def check_pageid(func):
    """decorator which checks the given pageid is found in the
    user's session data
    """
    def wrapper(self, *args, **kwargs):
        data = self.req.get_session_data(self.req.pageid)
        if data is None:
            raise RemoteCallFailed(self.req._('pageid-not-found'))
        return func(self, *args, **kwargs)
    return wrapper


class LoginController(Controller):
    id = 'login'

    def publish(self, rset=None):
        """log in the instance"""
        if self.config['auth-mode'] == 'http':
            # HTTP authentication
            raise ExplicitLogin()
        else:
            # Cookie authentication
            return self.appli.need_login_content(self.req)


class LogoutController(Controller):
    id = 'logout'

    def publish(self, rset=None):
        """logout from the instance"""
        return self.appli.session_handler.logout(self.req)


class ViewController(Controller):
    """standard entry point :
    - build result set
    - select and call main template
    """
    id = 'view'
    template = 'main-template'

    def publish(self, rset=None):
        """publish a request, returning an encoded string"""
        view, rset = self._select_view_and_rset(rset)
        self.add_to_breadcrumbs(view)
        self.validate_cache(view)
        template = self.appli.main_template_id(self.req)
        return self.vreg['views'].main_template(self.req, template,
                                                rset=rset, view=view)

    def _select_view_and_rset(self, rset):
        req = self.req
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
        vid = req.form.get('vid') or vid_from_rset(req, rset, self.schema)
        try:
            view = self.vreg['views'].select(vid, req, rset=rset)
        except ObjectNotFound:
            self.warning("the view %s could not be found", vid)
            req.set_message(req._("The view %s could not be found") % vid)
            vid = vid_from_rset(req, rset, self.schema)
            view = self.vreg['views'].select(vid, req, rset=rset)
        except NoSelectableObject:
            if rset:
                req.set_message(req._("The view %s can not be applied to this query") % vid)
            else:
                req.set_message(req._("You have no access to this view or it can not "
                                      "be used to display the current data."))
            self.warning("the view %s can not be applied to this query", vid)
            vid = vid_from_rset(req, rset, self.schema)
            view = self.vreg['views'].select(vid, req, rset=rset)
        return view, rset

    def add_to_breadcrumbs(self, view):
        # update breadcrumps **before** validating cache, unless the view
        # specifies explicitly it should not be added to breadcrumb or the
        # view is a binary view
        if view.add_to_breadcrumbs and not view.binary:
            self.req.update_breadcrumbs()

    def validate_cache(self, view):
        view.set_http_cache_headers()
        self.req.validate_cache()

    def execute_linkto(self, eid=None):
        """XXX __linkto parameter may cause security issue

        defined here since custom application controller inheriting from this
        one use this method?
        """
        req = self.req
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
    forminfo = req.get_session_data(req.form.get('__errorurl'), pop=True)
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
        if ctrl._edited_entity:
            ctrl._edited_entity.complete()
        try:
            req.cnx.commit() # ValidationError may be raise on commit
        except ValidationError, ex:
            return (False, _validation_error(req, ex), ctrl._edited_entity)
        else:
            return (True, ex.location, ctrl._edited_entity)
    except Exception, ex:
        req.cnx.rollback()
        req.exception('unexpected error while validating form')
        return (False, req._(str(ex).decode('utf-8')), ctrl._edited_entity)
    return (False, '???', None)


class FormValidatorController(Controller):
    id = 'validateform'

    def response(self, domid, status, args, entity):
        callback = str(self.req.form.get('__onsuccess', 'null'))
        errback = str(self.req.form.get('__onfailure', 'null'))
        self.req.set_content_type('text/html')
        jsargs = simplejson.dumps((status, args, entity), cls=CubicWebJsonEncoder)
        return """<script type="text/javascript">
 wp = window.parent;
 window.parent.handleFormValidationResponse('%s', %s, %s, %s);
</script>""" %  (domid, callback, errback, jsargs)

    def publish(self, rset=None):
        self.req.json_request = True
        # XXX unclear why we have a separated controller here vs
        # js_validate_form on the json controller
        status, args, entity = _validate_form(self.req, self.vreg)
        domid = self.req.form.get('__domid', 'entityForm').encode(
            self.req.encoding)
        return self.response(domid, status, args, entity)


class JSonController(Controller):
    id = 'json'

    def publish(self, rset=None):
        """call js_* methods. Expected form keys:

        :fname: the method name without the js_ prefix
        :args: arguments list (json)

        note: it's the responsability of js_* methods to set the correct
        response content type
        """
        self.req.json_request = True
        self.req.pageid = self.req.form.get('pageid')
        try:
            fname = self.req.form['fname']
            func = getattr(self, 'js_%s' % fname)
        except KeyError:
            raise RemoteCallFailed('no method specified')
        except AttributeError:
            raise RemoteCallFailed('no %s method' % fname)
        # no <arg> attribute means the callback takes no argument
        args = self.req.form.get('arg', ())
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
            return result.encode(self.req.encoding)
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
            self.req.ensure_ro_rql(rql)
        try:
            return self.req.execute(rql, args, eidkey)
        except Exception, ex:
            self.exception("error in _exec(rql=%s): %s", rql, ex)
            return None
        return None

    def _call_view(self, view, **kwargs):
        req = self.req
        divid = req.form.get('divid', 'pageContent')
        # we need to call pagination before with the stream set
        stream = view.set_stream()
        if req.form.get('paginate'):
            if divid == 'pageContent':
                # mimick main template behaviour
                stream.write(u'<div id="pageContent">')
                vtitle = self.req.form.get('vtitle')
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
        req = self.req
        rql = req.form.get('rql')
        if rql:
            rset = self._exec(rql)
        else:
            rset = None
        vid = req.form.get('vid') or vid_from_rset(req, rset, self.schema)
        try:
            view = self.vreg['views'].select(vid, req, rset=rset)
        except NoSelectableObject:
            vid = req.form.get('fallbackvid', 'noresult')
            view = self.vreg['views'].select(vid, req, rset=rset)
        return self._call_view(view)

    @xhtmlize
    def js_prop_widget(self, propkey, varname, tabindex=None):
        """specific method for CWProperty handling"""
        entity = self.vreg['etypes'].etype_class('CWProperty')(self.req)
        entity.eid = varname
        entity['pkey'] = propkey
        form = self.vreg['forms'].select('edition', self.req, entity=entity)
        form.form_build_context()
        vfield = form.field_by_name('value')
        renderer = FormRenderer(self.req)
        return vfield.render(form, renderer, tabindex=tabindex) \
               + renderer.render_help(form, vfield)

    @xhtmlize
    def js_component(self, compid, rql, registry='components', extraargs=None):
        if rql:
            rset = self._exec(rql)
        else:
            rset = None
        comp = self.vreg[registry].select(compid, self.req, rset=rset)
        if extraargs is None:
            extraargs = {}
        else: # we receive unicode keys which is not supported by the **syntax
            extraargs = dict((str(key), value)
                             for key, value in extraargs.items())
        extraargs = extraargs or {}
        return comp.render(**extraargs)

    @check_pageid
    @xhtmlize
    def js_inline_creation_form(self, peid, ttype, rtype, role):
        view = self.vreg['views'].select('inline-creation', self.req,
                                         etype=ttype, peid=peid, rtype=rtype,
                                         role=role)
        return self._call_view(view, etype=ttype, peid=peid,
                               rtype=rtype, role=role)

    @jsonize
    def js_validate_form(self, action, names, values):
        return self.validate_form(action, names, values)

    def validate_form(self, action, names, values):
        self.req.form = self._rebuild_posted_form(names, values, action)
        return _validate_form(self.req, self.vreg)

    @jsonize
    def js_edit_field(self, action, names, values, rtype, eid, default):
        success, args, _ = self.validate_form(action, names, values)
        if success:
            # Any X,N where we don't seem to use N is an optimisation
            # printable_value won't need to query N again
            rset = self.req.execute('Any X,N WHERE X eid %%(x)s, X %s N' % rtype,
                                    {'x': eid}, 'x')
            entity = rset.get_entity(0, 0)
            value = entity.printable_value(rtype) or default
            return (success, args, value)
        else:
            return (success, args, None)

    @jsonize
    def js_reledit_form(self, eid, rtype, role, default, lzone):
        """XXX we should get rid of this and use loadxhtml"""
        entity = self.req.entity_from_eid(eid)
        return entity.view('reledit', rtype=rtype, role=role,
                           default=default, landing_zone=lzone)

    @jsonize
    def js_i18n(self, msgids):
        """returns the translation of `msgid`"""
        return [self.req._(msgid) for msgid in msgids]

    @jsonize
    def js_format_date(self, strdate):
        """returns the formatted date for `msgid`"""
        date = strptime(strdate, '%Y-%m-%d %H:%M:%S')
        return self.format_date(date)

    @jsonize
    def js_external_resource(self, resource):
        """returns the URL of the external resource named `resource`"""
        return self.req.external_resource(resource)

    @check_pageid
    @jsonize
    def js_user_callback(self, cbname):
        page_data = self.req.get_session_data(self.req.pageid, {})
        try:
            cb = page_data[cbname]
        except KeyError:
            return None
        return cb(self.req)

    if HAS_SEARCH_RESTRICTION:
        @jsonize
        def js_filter_build_rql(self, names, values):
            form = self._rebuild_posted_form(names, values)
            self.req.form = form
            builder = FilterRQLBuilder(self.req)
            return builder.build_rql()

        @jsonize
        def js_filter_select_content(self, facetids, rql):
            rqlst = self.vreg.parse(self.req, rql) # XXX Union unsupported yet
            mainvar = prepare_facets_rqlst(rqlst)[0]
            update_map = {}
            for facetid in facetids:
                facet = get_facet(self.req, facetid, rqlst.children[0], mainvar)
                update_map[facetid] = facet.possible_values()
            return update_map

    def js_unregister_user_callback(self, cbname):
        self.req.unregister_callback(self.req.pageid, cbname)

    def js_unload_page_data(self):
        self.req.del_session_data(self.req.pageid)

    def js_cancel_edition(self, errorurl):
        """cancelling edition from javascript

        We need to clear associated req's data :
          - errorurl
          - pending insertions / deletions
        """
        self.req.cancel_edition(errorurl)

    def js_delete_bookmark(self, beid):
        rql = 'DELETE B bookmarked_by U WHERE B eid %(b)s, U eid %(u)s'
        self.req.execute(rql, {'b': typed_eid(beid), 'u' : self.req.user.eid})

    def js_node_clicked(self, treeid, nodeeid):
        """add/remove eid in treestate cookie"""
        from cubicweb.web.views.treeview import treecookiename
        cookies = self.req.get_cookie()
        statename = treecookiename(treeid)
        treestate = cookies.get(statename)
        if treestate is None:
            cookies[statename] = nodeeid
            self.req.set_cookie(cookies, statename)
        else:
            marked = set(filter(None, treestate.value.split(';')))
            if nodeeid in marked:
                marked.remove(nodeeid)
            else:
                marked.add(nodeeid)
            cookies[statename] = ';'.join(marked)
            self.req.set_cookie(cookies, statename)

    def js_set_cookie(self, cookiename, cookievalue):
        # XXX we should consider jQuery.Cookie
        cookiename, cookievalue = str(cookiename), str(cookievalue)
        cookies = self.req.get_cookie()
        cookies[cookiename] = cookievalue
        self.req.set_cookie(cookies, cookiename)

    # relations edition stuff ##################################################

    def _add_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind
        pendings = self.req.get_session_data(key, set())
        pendings.add( (typed_eid(eidfrom), rel, typed_eid(eidto)) )
        self.req.set_session_data(key, pendings)

    def _remove_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind
        pendings = self.req.get_session_data(key)
        pendings.remove( (typed_eid(eidfrom), rel, typed_eid(eidto)) )
        self.req.set_session_data(key, pendings)

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
        eid_from = self.req.execute('INSERT %s T : T name "%s"' % ( etype_from, value_from ))[0][0]
        # link the new entity to the main entity
        rql = 'SET F %(rel)s T WHERE F eid %(eid_to)s, T eid %(eid_from)s' % {'rel' : rel, 'eid_to' : eid_to, 'eid_from' : eid_from}
        return eid_from


class SendMailController(Controller):
    id = 'sendmail'
    __select__ = match_user_groups('managers', 'users')

    def recipients(self):
        """returns an iterator on email's recipients as entities"""
        eids = self.req.form['recipient']
        # make sure we have a list even though only one recipient was specified
        if isinstance(eids, basestring):
            eids = (eids,)
        rql = 'Any X WHERE X eid in (%s)' % (','.join(eids))
        rset = self.req.execute(rql)
        for entity in rset.entities():
            entity.complete() # XXX really?
            yield entity

    @property
    @cached
    def smtp(self):
        mailhost, port = self.config['smtp-host'], self.config['smtp-port']
        try:
            return SMTP(mailhost, port)
        except Exception, ex:
            self.exception("can't connect to smtp server %s:%s (%s)",
                             mailhost, port, ex)
            url = self.build_url(__message=self.req._('could not connect to the SMTP server'))
            raise Redirect(url)

    def sendmail(self, recipient, subject, body):
        helo_addr = '%s <%s>' % (self.config['sender-name'],
                                 self.config['sender-addr'])
        msg = format_mail({'email' : self.req.user.get_email(),
                           'name' : self.req.user.dc_title(),},
                          [recipient], body, subject)
        self.smtp.sendmail(helo_addr, [recipient], msg.as_string())

    def publish(self, rset=None):
        # XXX this allows users with access to an cubicweb instance to use it as
        # a mail relay
        body = self.req.form['mailbody']
        subject = self.req.form['subject']
        for recipient in self.recipients():
            text = body % recipient.as_email_context()
            self.sendmail(recipient.get_email(), subject, text)
        # breadcrumbs = self.req.get_session_data('breadcrumbs', None)
        url = self.build_url(__message=self.req._('emails successfully sent'))
        raise Redirect(url)


class MailBugReportController(SendMailController):
    id = 'reportbug'
    __select__ = yes()

    def publish(self, rset=None):
        body = self.req.form['description']
        self.sendmail(self.config['submit-mail'], _('%s error report') % self.config.appid, body)
        url = self.build_url(__message=self.req._('bug report sent'))
        raise Redirect(url)

