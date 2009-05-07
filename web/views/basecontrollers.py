# -*- coding: utf-8 -*-
"""Set of base controllers, which are directly plugged into the application
object to handle publication.


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from smtplib import SMTP

import simplejson

from logilab.common.decorators import cached

from cubicweb import NoSelectableObject, ValidationError, ObjectNotFound, typed_eid
from cubicweb.utils import strptime
from cubicweb.selectors import yes, match_user_groups
from cubicweb.view import STRICT_DOCTYPE
from cubicweb.common.mail import format_mail
from cubicweb.web import ExplicitLogin, Redirect, RemoteCallFailed, json_dumps
from cubicweb.web.formrenderers import FormRenderer
from cubicweb.web.controller import Controller
from cubicweb.web.views import vid_from_rset
try:
    from cubicweb.web.facet import (FilterRQLBuilder, get_facet,
                                    prepare_facets_rqlst)
    HAS_SEARCH_RESTRICTION = True
except ImportError: # gae
    HAS_SEARCH_RESTRICTION = False


def xhtml_wrap(source):
    head = u'<?xml version="1.0"?>\n' + STRICT_DOCTYPE
    return head + u'<div xmlns="http://www.w3.org/1999/xhtml" xmlns:cubicweb="http://www.logilab.org/2008/cubicweb">%s</div>' % source.strip()

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
        return xhtml_wrap(result)
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
        """log in the application"""
        if self.config['auth-mode'] == 'http':
            # HTTP authentication
            raise ExplicitLogin()
        else:
            # Cookie authentication
            return self.appli.need_login_content(self.req)


class LogoutController(Controller):
    id = 'logout'

    def publish(self, rset=None):
        """logout from the application"""
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
        return self.vreg.main_template(self.req, template, rset=rset, view=view)

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
            except Exception, ex:
                self.exception('while handling __method')
                req.set_message(req._("error while handling __method: %s") % req._(ex))
        vid = req.form.get('vid') or vid_from_rset(req, rset, self.schema)
        try:
            view = self.vreg.select_view(vid, req, rset)
        except ObjectNotFound:
            self.warning("the view %s could not be found", vid)
            req.set_message(req._("The view %s could not be found") % vid)
            vid = vid_from_rset(req, rset, self.schema)
            view = self.vreg.select_view(vid, req, rset)
        except NoSelectableObject:
            if rset:
                req.set_message(req._("The view %s can not be applied to this query") % vid)
            else:
                req.set_message(req._("You have no access to this view or it's not applyable to current data"))
            self.warning("the view %s can not be applied to this query", vid)
            vid = vid_from_rset(req, rset, self.schema)
            view = self.vreg.select_view(vid, req, rset)
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


class FormValidatorController(Controller):
    id = 'validateform'

    def publish(self, rset=None):
        vreg = self.vreg
        try:
            ctrl = vreg.select(vreg.registry_objects('controllers', 'edit'),
                               req=self.req, appli=self.appli)
        except NoSelectableObject:
            status, args = (False, {None: self.req._('not authorized')})
        else:
            try:
                ctrl.publish(None, fromjson=True)
            except ValidationError, err:
                status, args = self.validation_error(err)
            except Redirect, err:
                try:
                    self.req.cnx.commit() # ValidationError may be raise on commit
                except ValidationError, err:
                    status, args = self.validation_error(err)
                else:
                    status, args = (True, err.location)
            except Exception, err:
                self.req.cnx.rollback()
                self.exception('unexpected error in validateform')
                try:
                    status, args = (False, self.req._(unicode(err)))
                except UnicodeError:
                    status, args = (False, repr(err))
            else:
                status, args = (False, '???')
        self.req.set_content_type('text/html')
        jsarg = simplejson.dumps( (status, args) )
        return """<script type="text/javascript">
 window.parent.handleFormValidationResponse('entityForm', null, %s);
</script>""" %  simplejson.dumps( (status, args) )

    def validation_error(self, err):
        self.req.cnx.rollback()
        try:
            eid = err.entity.eid
        except AttributeError:
            eid = err.entity
        return (False, (eid, err.errors))


class JSonController(Controller):
    id = 'json'

    def publish(self, rset=None):
        """call js_* methods. Expected form keys:

        :fname: the method name without the js_ prefix
        :args: arguments list (json)

        note: it's the responsability of js_* methods to set the correct
        response content type
        """
        self.req.pageid = self.req.form.get('pageid')
        fname = self.req.form['fname']
        try:
            func = getattr(self, 'js_%s' % fname)
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
            self.ensure_ro_rql(rql)
        try:
            return self.req.execute(rql, args, eidkey)
        except Exception, ex:
            self.exception("error in _exec(rql=%s): %s", rql, ex)
            return None
        return None

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
            view = self.vreg.select_view(vid, req, rset)
        except NoSelectableObject:
            vid = req.form.get('fallbackvid', 'noresult')
            view = self.vreg.select_view(vid, req, rset)
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
            view.pagination(req, rset, view.w, not view.need_navigation)
            if divid == 'pageContent':
                stream.write(u'<div id="contentmain">')
        view.dispatch()
        extresources = req.html_headers.getvalue(skiphead=True)
        if extresources:
            stream.write(u'<div class="ajaxHtmlHead">\n') # XXX use a widget ?
            stream.write(extresources)
            stream.write(u'</div>\n')
        if req.form.get('paginate') and divid == 'pageContent':
            stream.write(u'</div></div>')
        return stream.getvalue()

    @xhtmlize
    def js_prop_widget(self, propkey, varname, tabindex=None):
        """specific method for CWProperty handling"""
        entity = self.vreg.etype_class('CWProperty')(self.req, None, None)
        entity.eid = varname
        entity['pkey'] = propkey
        form = self.vreg.select_object('forms', 'edition', self.req, None,
                                       entity=entity)
        form.form_build_context()
        vfield = form.field_by_name('value')
        renderer = FormRenderer()
        return vfield.render(form, renderer, tabindex=tabindex) \
               + renderer.render_help(form, vfield)

    @xhtmlize
    def js_component(self, compid, rql, registry='components', extraargs=None):
        if rql:
            rset = self._exec(rql)
        else:
            rset = None
        comp = self.vreg.select_object(registry, compid, self.req, rset)
        if extraargs is None:
            extraargs = {}
        else: # we receive unicode keys which is not supported by the **syntax
            extraargs = dict((str(key), value)
                             for key, value in extraargs.items())
        extraargs = extraargs or {}
        return comp.dispatch(**extraargs)

    @check_pageid
    @xhtmlize
    def js_inline_creation_form(self, peid, ttype, rtype, role):
        view = self.vreg.select_view('inline-creation', self.req, None,
                                     etype=ttype, peid=peid, rtype=rtype,
                                     role=role)
        return view.dispatch(etype=ttype, peid=peid, rtype=rtype, role=role)

    @jsonize
    def js_validate_form(self, action, names, values):
        return self.validate_form(action, names, values)

    def validate_form(self, action, names, values):
        # XXX this method (and correspoding js calls) should use the new
        #     `RemoteCallFailed` mechansim
        self.req.form = self._rebuild_posted_form(names, values, action)
        vreg = self.vreg
        try:
            ctrl = vreg.select(vreg.registry_objects('controllers', 'edit'),
                               req=self.req)
        except NoSelectableObject:
            return (False, {None: self.req._('not authorized')})
        try:
            ctrl.publish(None, fromjson=True)
        except ValidationError, err:
            self.req.cnx.rollback()
            if not err.entity or isinstance(err.entity, (long, int)):
                eid = err.entity
            else:
                eid = err.entity.eid
            return (False, (eid, err.errors))
        except Redirect, err:
            return (True, err.location)
        except Exception, err:
            self.req.cnx.rollback()
            self.exception('unexpected error in js_validateform')
            return (False, self.req._(str(err)))
        return (False, '???')

    @jsonize
    def js_edit_field(self, action, names, values, rtype, eid):
        success, args = self.validate_form(action, names, values)
        if success:
            # Any X,N where we don't seem to use N is an optimisation
            # printable_value won't need to query N again
            rset = self.req.execute('Any X,N WHERE X eid %%(x)s, X %s N' % rtype,
                                    {'x': eid}, 'x')
            entity = rset.get_entity(0, 0)
            return (success, args, entity.printable_value(rtype))
        else:
            return (success, args, None)

    @jsonize
    def js_edit_relation(self, action, names, values,
                         rtype, eid, role='subject', vid='list'):
        # XXX validate_form
        success, args = self.validate_form(action, names, values)
        if success:
            entity = self.req.eid_rset(eid).get_entity(0, 0)
            rset = entity.related('person_in_charge', role)
            return (success, args, self.view(vid, rset))
        else:
            return (success, args, None)

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
        # XXX this allow anybody with access to an cubicweb application to use it as a mail relay
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

