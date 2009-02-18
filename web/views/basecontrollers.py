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

from mx.DateTime.Parser import DateFromString

from logilab.common.decorators import cached

from cubicweb import NoSelectableObject, ValidationError, typed_eid
from cubicweb.selectors import yes, match_user_groups
from cubicweb.view import STRICT_DOCTYPE, CW_XHTML_EXTENSIONS
from cubicweb.common.mail import format_mail
from cubicweb.web import ExplicitLogin, Redirect, RemoteCallFailed
from cubicweb.web.controller import Controller
from cubicweb.web.views import vid_from_rset
try:
    from cubicweb.web.facet import (FilterRQLBuilder, get_facet,
                                    prepare_facets_rqlst)
    HAS_SEARCH_RESTRICTION = True
except ImportError: # gae
    HAS_SEARCH_RESTRICTION = False
    
    
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
    id = 'view'
    template = 'main'
    
    def publish(self, rset=None):
        """publish a request, returning an encoded string"""
        template = self.req.property_value('ui.main-template')
        if template not in self.vreg.registry('templates') :
            template = self.template
        return self.vreg.main_template(self.req, template, rset=rset)

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
        
def xmlize(source):
    head = u'<?xml version="1.0"?>\n' + STRICT_DOCTYPE % CW_XHTML_EXTENSIONS
    return head + u'<div xmlns="http://www.w3.org/1999/xhtml" xmlns:cubicweb="http://www.logilab.org/2008/cubicweb">%s</div>' % source.strip()

def jsonize(func):
    """sets correct content_type and calls `simplejson.dumps` on results
    """
    def wrapper(self, *args, **kwargs):
        self.req.set_content_type('application/json')
        result = func(self, *args, **kwargs)
        return simplejson.dumps(result)
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
    

class JSonController(Controller):
    id = 'json'
    template = 'main'

    def publish(self, rset=None):
        mode = self.req.form.get('mode', 'html')
        self.req.pageid = self.req.form.get('pageid')
        try:
            func = getattr(self, '%s_exec' % mode)
        except AttributeError, ex:
            self.error('json controller got an unknown mode %r', mode)
            self.error('\t%s', ex)
            result = u''
        else:
            try:
                result = func(rset)
            except RemoteCallFailed:
                raise
            except Exception, ex:
                self.exception('an exception occured on json request(rset=%s): %s',
                               rset, ex)
                raise RemoteCallFailed(repr(ex))
        return result.encode(self.req.encoding)

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

    @jsonize
    def json_exec(self, rset=None):
        """json mode: execute RQL and return resultset as json"""
        rql = self.req.form.get('rql')
        if rset is None and rql:
            rset = self._exec(rql)
        return rset and rset.rows or []

    def _set_content_type(self, vobj, data):
        """sets req's content type according to vobj's content type
        (and xmlize data if needed)
        """
        content_type = vobj.content_type
        if content_type == 'application/xhtml+xml':
            self.req.set_content_type(content_type)
            return xmlize(data)
        return data
    
    def html_exec(self, rset=None):
        # XXX try to use the page-content template
        req = self.req
        rql = req.form.get('rql')
        if rset is None and rql:
            rset = self._exec(rql)
        
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
        stream.write(u'<div class="ajaxHtmlHead">\n') # XXX use a widget ?
        stream.write(extresources)
        stream.write(u'</div>\n')
        if req.form.get('paginate') and divid == 'pageContent':
            stream.write(u'</div></div>')
        source = stream.getvalue()
        return self._set_content_type(view, source)

    def rawremote_exec(self, rset=None):
        """like remote_exec but doesn't change content type"""
        # no <arg> attribute means the callback takes no argument
        args = self.req.form.get('arg', ())
        if not isinstance(args, (list, tuple)):
            args = (args,)
        fname = self.req.form['fname']
        args = [simplejson.loads(arg) for arg in args]
        try:
            func = getattr(self, 'js_%s' % fname)
        except AttributeError:
            self.exception('rawremote_exec fname=%s', fname)
            return u""
        return func(*args)

    remote_exec = jsonize(rawremote_exec)
        
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
    
    def js_validate_form(self, action, names, values):
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

    def js_edit_field(self, action, names, values, rtype, eid):
        success, args = self.js_validate_form(action, names, values)
        if success:
            rset = self.req.execute('Any X,N WHERE X eid %%(x)s, X %s N' % rtype,
                                    {'x': eid}, 'x')
            entity = rset.get_entity(0, 0)
            return (success, args, entity.printable_value(rtype))
        else:
            return (success, args, None)
            
    def js_rql(self, rql):
        rset = self._exec(rql)
        return rset and rset.rows or []
    
    def js_i18n(self, msgids):
        """returns the translation of `msgid`"""
        return [self.req._(msgid) for msgid in msgids]

    def js_format_date(self, strdate):
        """returns the formatted date for `msgid`"""
        date = DateFromString(strdate)
        return self.format_date(date)

    def js_external_resource(self, resource):
        """returns the URL of the external resource named `resource`"""
        return self.req.external_resource(resource)

    def js_prop_widget(self, propkey, varname, tabindex=None):
        """specific method for EProperty handling"""
        w = self.vreg.property_value_widget(propkey, req=self.req)
        entity = self.vreg.etype_class('EProperty')(self.req, None, None)
        entity.eid = varname
        self.req.form['value'] = self.vreg.property_info(propkey)['default']
        return w.edit_render(entity, tabindex, includehelp=True)

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
        return self._set_content_type(comp, comp.dispatch(**extraargs))

    @check_pageid
    def js_user_callback(self, cbname):
        page_data = self.req.get_session_data(self.req.pageid, {})
        try:
            cb = page_data[cbname]
        except KeyError:
            return None
        return cb(self.req)
    
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
    
    @check_pageid
    def js_inline_creation_form(self, peid, ptype, ttype, rtype, role):
        view = self.vreg.select_view('inline-creation', self.req, None,
                                     etype=ttype, ptype=ptype, peid=peid,
                                     rtype=rtype, role=role)
        source = view.dispatch(etype=ttype, ptype=ptype, peid=peid, rtype=rtype,
                               role=role)
        return self._set_content_type(view, source)

    def js_remove_pending_insert(self, (eidfrom, rel, eidto)):
        self._remove_pending(eidfrom, rel, eidto, 'insert')
        
    def js_add_pending_insert(self, (eidfrom, rel, eidto)):
        self._add_pending(eidfrom, rel, eidto, 'insert')
        
    def js_add_pending_inserts(self, tripletlist):
        for eidfrom, rel, eidto in tripletlist:
            self._add_pending(eidfrom, rel, eidto, 'insert')
        
    def js_remove_pending_delete(self, (eidfrom, rel, eidto)):
        self._remove_pending(eidfrom, rel, eidto, 'delete')
    
    def js_add_pending_delete(self, (eidfrom, rel, eidto)):
        self._add_pending(eidfrom, rel, eidto, 'delete')

    if HAS_SEARCH_RESTRICTION:
        def js_filter_build_rql(self, names, values):
            form = self._rebuild_posted_form(names, values)
            self.req.form = form
            builder = FilterRQLBuilder(self.req)
            return builder.build_rql()

        def js_filter_select_content(self, facetids, rql):
            rqlst = self.vreg.parse(self.req, rql) # XXX Union unsupported yet
            mainvar = prepare_facets_rqlst(rqlst)[0]
            update_map = {}
            for facetid in facetids:
                facet = get_facet(self.req, facetid, rqlst.children[0], mainvar)
                update_map[facetid] = facet.possible_values()
            return update_map

    def js_delete_bookmark(self, beid):
        try:
            rql = 'DELETE B bookmarked_by U WHERE B eid %(b)s, U eid %(u)s'
            self.req.execute(rql, {'b': typed_eid(beid), 'u' : self.req.user.eid})
        except Exception, ex:
            self.exception(unicode(ex))
            return self.req._('Problem occured')

    def _add_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind
        pendings = self.req.get_session_data(key, set())
        pendings.add( (typed_eid(eidfrom), rel, typed_eid(eidto)) )
        self.req.set_session_data(key, pendings)

    def _remove_pending(self, eidfrom, rel, eidto, kind):
        key = 'pending_%s' % kind        
        try:
            pendings = self.req.get_session_data(key)
            pendings.remove( (typed_eid(eidfrom), rel, typed_eid(eidto)) )
        except:
            self.exception('while removing pending eids')
        else:
            self.req.set_session_data(key, pendings)

    def js_add_and_link_new_entity(self, etype_to, rel, eid_to, etype_from, value_from):
        # create a new entity
        eid_from = self.req.execute('INSERT %s T : T name "%s"' % ( etype_from, value_from ))[0][0]
        # link the new entity to the main entity
        rql = 'SET F %(rel)s T WHERE F eid %(eid_to)s, T eid %(eid_from)s' % {'rel' : rel, 'eid_to' : eid_to, 'eid_from' : eid_from}
        return eid_from

    def js_set_cookie(self, cookiename, cookievalue):
        # XXX we should consider jQuery.Cookie
        cookiename, cookievalue = str(cookiename), str(cookievalue)
        cookies = self.req.get_cookie()
        cookies[cookiename] = cookievalue
        self.req.set_cookie(cookies, cookiename)

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
        subject = self.req.form['mailsubject']
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
    
