"""management and error screens


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.selectors import yes, none_rset, match_user_groups
from cubicweb.common.view import AnyRsetView, StartupView, EntityView
from cubicweb.common.uilib import html_traceback, rest_traceback
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param, stdmsgs
from cubicweb.web.widgets import StaticComboBoxWidget

_ = unicode

def begin_form(w, entity, redirectvid, redirectpath=None, msg=None):
    w(u'<form method="post" action="%s">\n' % entity.req.build_url('edit'))
    w(u'<fieldset>\n')
    w(u'<input type="hidden" name="__redirectvid" value="%s"/>\n' % redirectvid)
    w(u'<input type="hidden" name="__redirectpath" value="%s"/>\n' % (
        html_escape(redirectpath or entity.rest_path())))
    w(u'<input type="hidden" name="eid" value="%s"/>\n' % entity.eid)
    w(u'<input type="hidden" name="%s" value="%s"/>\n' % (
        eid_param('__type', entity.eid), entity.e_schema))
    if msg:
        w(u'<input type="hidden" name="__message" value="%s"/>\n'
          % html_escape(msg))


class SecurityManagementView(EntityView):
    """display security information for a given entity"""
    id = 'security'
    title = _('security')

    def cell_call(self, row, col):
        self.req.add_js('cubicweb.edition.js')
        self.req.add_css('cubicweb.acl.css')
        entity = self.entity(row, col)
        w = self.w
        _ = self.req._
        w(u'<h1><span class="etype">%s</span> <a href="%s">%s</a></h1>'
          % (entity.dc_type().capitalize(),
             html_escape(entity.absolute_url()),
             html_escape(entity.dc_title())))
        # first show permissions defined by the schema
        self.w('<h2>%s</h2>' % _('schema\'s permissions definitions'))
        self.schema_definition(entity)
        self.w('<h2>%s</h2>' % _('manage security'))
        # ownership information
        if self.schema.rschema('owned_by').has_perm(self.req, 'add',
                                                    fromeid=entity.eid):
            self.owned_by_edit_form(entity)
        else:
            self.owned_by_information(entity)
        # epermissions
        if 'require_permission' in entity.e_schema.subject_relations():
            w('<h3>%s</h3>' % _('permissions for this entity'))
            reqpermschema = self.schema.rschema('require_permission')
            self.require_permission_information(entity, reqpermschema)
            if reqpermschema.has_perm(self.req, 'add', fromeid=entity.eid):
                self.require_permission_edit_form(entity)

    def schema_definition(self, entity):
        w = self.w
        _ = self.req._
        w(u'<table class="schemaInfo">')
        w(u'<tr><th>%s</th><th>%s</th><th>%s</th></tr>' % (
            _("access type"), _('granted to groups'), _('rql expressions')))
        for access_type in ('read', 'add', 'update', 'delete'):
            w(u'<tr>')
            w(u'<th>%s</th>' % self.req.__('%s_permission' % access_type))
            groups = entity.e_schema.get_groups(access_type)
            l = []
            for group in groups:
                l.append(u'<a href="%s">%s</a>' % (
                    self.build_url('egroup/%s' % group), _(group)))
            w(u'<td>%s</td>' % u', '.join(l))
            rqlexprs = entity.e_schema.get_rqlexprs(access_type)
            w(u'<td>%s</td>' % u'<br/>'.join(expr.expression for expr in rqlexprs))
            w(u'</tr>\n')
        w(u'</table>')

    def owned_by_edit_form(self, entity):
        self.w('<h3>%s</h3>' % self.req._('ownership'))
        begin_form(self.w, entity, 'security', msg= _('ownerships have been changed'))
        self.w(u'<table border="0">\n')
        self.w(u'<tr><td>\n')
        wdg = entity.get_widget('owned_by')
        self.w(wdg.edit_render(entity))
        self.w(u'</td><td>\n')
        self.w(self.button_ok())
        self.w(u'</td></tr>\n</table>\n')
        self.w(u'</fieldset></form>\n')

    def owned_by_information(self, entity):
        ownersrset = entity.related('owned_by')
        if ownersrset:
            self.w('<h3>%s</h3>' % self.req._('ownership'))
            self.w(u'<div class="ownerInfo">')
            self.w(self.req._('this entity is currently owned by') + ' ')
            self.wview('csv', entity.related('owned_by'), 'null')
            self.w(u'</div>')
        # else we don't know if this is because entity has no owner or becayse
        # user as no access to owner users entities

    def require_permission_information(self, entity, reqpermschema):
        if entity.require_permission:
            w = self.w
            _ = self.req._
            if reqpermschema.has_perm(self.req, 'delete', fromeid=entity.eid):
                delurl = self.build_url('edit', __redirectvid='security',
                                        __redirectpath=entity.rest_path())
                delurl = delurl.replace('%', '%%')
                # don't give __delete value to build_url else it will be urlquoted
                # and this will replace %s by %25s
                delurl += '&__delete=%s:require_permission:%%s' % entity.eid
                dellinktempl = u'[<a href="%s" title="%s">-</a>]&nbsp;' % (
                    html_escape(delurl), _('delete this permission'))
            else:
                dellinktempl = None
            w(u'<table class="schemaInfo">')
            w(u'<tr><th>%s</th><th>%s</th></tr>' % (_("permission"),
                                                    _('granted to groups')))
            for eperm in entity.require_permission:
                w(u'<tr>')
                if dellinktempl:
                    w(u'<td>%s%s</td>' % (dellinktempl % eperm.eid,
                                          eperm.view('oneline')))
                else:
                    w(u'<td>%s</td>' % eperm.view('oneline'))
                w(u'<td>%s</td>' % self.view('csv', eperm.related('require_group'), 'null'))
                w(u'</tr>\n')
            w(u'</table>')
        else:
            self.w(self.req._('no associated epermissions'))

    def require_permission_edit_form(self, entity):
        w = self.w
        _ = self.req._
        newperm = self.vreg.etype_class('EPermission')(self.req, None)
        newperm.eid = self.req.varmaker.next()
        w(u'<p>%s</p>' % _('add a new permission'))
        begin_form(w, newperm, 'security', entity.rest_path())
        w(u'<input type="hidden" name="%s" value="%s"/>'
          % (eid_param('edito-require_permission', newperm.eid), INTERNAL_FIELD_VALUE))
        w(u'<input type="hidden" name="%s" value="%s"/>'
          % (eid_param('require_permission', newperm.eid), entity.eid))
        w(u'<table border="0">\n')
        w(u'<tr><th>%s</th><th>%s</th><th>%s</th><th>&nbsp;</th></tr>\n'
               % (_("name"), _("label"), _('granted to groups')))
        if getattr(entity, '__permissions__', None):
            wdg = StaticComboBoxWidget(self.vreg, self.schema['EPermission'],
                                       self.schema['name'], self.schema['String'],
                                       vocabfunc=lambda x: entity.__permissions__)
        else:
            wdg = newperm.get_widget('name')
        w(u'<tr><td>%s</td>\n' % wdg.edit_render(newperm))
        wdg = newperm.get_widget('label')
        w(u'<td>%s</td>\n' % wdg.edit_render(newperm))
        wdg = newperm.get_widget('require_group')
        w(u'<td>%s</td>\n' % wdg.edit_render(newperm))
        w(u'<td>%s</td></tr>\n' % self.button_ok())
        w(u'</table>')
        w(u'</fieldset></form>\n')

    def button_ok(self):
        return (u'<input class="validateButton" type="submit" name="submit" value="%s"/>'
                % self.req._(stdmsgs.BUTTON_OK))


class ErrorView(AnyRsetView):
    """default view when no result has been found"""
    __select__ = yes()
    id = 'error'

    def page_title(self):
        """returns a title according to the result set - used for the
        title in the HTML header
        """
        return self.req._('an error occured')

    def call(self):
        req = self.req.reset_headers()
        _ = req._; w = self.w
        ex = req.data.get('ex')#_("unable to find exception information"))
        excinfo = req.data.get('excinfo')
        title = _('an error occured')
        w(u'<h2>%s</h2>' % title)
        if 'errmsg' in req.data:
            ex = req.data['errmsg']
            exclass = None
        else:
            exclass = ex.__class__.__name__
            ex = exc_message(ex, req.encoding)
        if excinfo is not None and self.config['print-traceback']:
            if exclass is None:
                w(u'<div class="tb">%s</div>'
                       % html_escape(ex).replace("\n","<br />"))
            else:
                w(u'<div class="tb">%s: %s</div>'
                       % (exclass, html_escape(ex).replace("\n","<br />")))
            w(u'<hr />')
            w(u'<div class="tb">%s</div>' % html_traceback(excinfo, ex, ''))
        else:
            w(u'<div class="tb">%s</div>' % (html_escape(ex).replace("\n","<br />")))
        # if excinfo is not None, it's probably not a bug
        if excinfo is None:
            return
        vcconf = self.config.vc_config()
        w(u"<div>")
        eversion = vcconf.get('cubicweb', _('no version information'))
        # NOTE: tuple wrapping needed since eversion is itself a tuple
        w(u"<b>CubicWeb version:</b> %s<br/>\n" % (eversion,))
        for pkg in self.config.cubes():
            pkgversion = vcconf.get(pkg, _('no version information'))
            w(u"<b>Package %s version:</b> %s<br/>\n" % (pkg, pkgversion))
        w(u"</div>")
        # creates a bug submission link if SUBMIT_URL is set
        submiturl = self.config['submit-url']
        if submiturl:
            binfo = text_error_description(ex, excinfo, req, eversion,
                                           [(pkg, vcconf.get(pkg, _('no version information')))
                                            for pkg in self.config.cubes()])
            w(u'<form action="%s" method="post">\n' % html_escape(submiturl))
            w(u'<fieldset>\n')
            w(u'<textarea class="hidden" name="description">%s</textarea>' % html_escape(binfo))
            w(u'<input type="hidden" name="description_format" value="text/rest"/>')
            w(u'<input type="hidden" name="__bugreporting" value="1"/>')
            w(u'<input type="submit" value="%s"/>' % _('Submit bug report'))
            w(u'</fieldset>\n')
            w(u'</form>\n')
        submitmail = self.config['submit-mail']
        if submitmail:
            binfo = text_error_description(ex, excinfo, req, eversion,
                                           [(pkg, vcconf.get(pkg, _('no version information')))
                                            for pkg in self.config.cubes()])
            w(u'<form action="%s" method="post">\n' % req.build_url('reportbug'))
            w(u'<fieldset>\n')
            w(u'<input type="hidden" name="description" value="%s"/>' % html_escape(binfo))
            w(u'<input type="hidden" name="__bugreporting" value="1"/>')
            w(u'<input type="submit" value="%s"/>' % _('Submit bug report by mail'))
            w(u'</fieldset>\n')
            w(u'</form>\n')


def exc_message(ex, encoding):
    try:
        return unicode(ex)
    except:
        try:
            return unicode(str(ex), encoding, 'replace')
        except:
            return unicode(repr(ex), encoding, 'replace')

def text_error_description(ex, excinfo, req, eversion, cubes):
    binfo = rest_traceback(excinfo, html_escape(ex))
    binfo += u'\n\n:URL: %s\n' % req.url()
    if not '__bugreporting' in req.form:
        binfo += u'\n:form params:\n'
        binfo += u'\n'.join(u'  * %s = %s' % (k, v) for k, v in req.form.iteritems())
    binfo += u'\n\n:CubicWeb version: %s\n'  % (eversion,)
    for pkg, pkgversion in cubes:
        binfo += u":Package %s version: %s\n" % (pkg, pkgversion)
    binfo += '\n'
    return binfo

class ProcessInformationView(StartupView):
    id = 'info'
    __select__ = none_rset() & match_user_groups('managers')
    
    title = _('server information')

    def call(self, **kwargs):
        """display server information"""
        vcconf = self.config.vc_config()
        req = self.req
        _ = req._
        # display main information
        self.w(u'<h3>%s</h3>' % _('Application'))
        self.w(u'<table border="1">')
        self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            'CubicWeb', vcconf.get('cubicweb', _('no version information'))))
        for pkg in self.config.cubes():
            pkgversion = vcconf.get(pkg, _('no version information'))
            self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
                pkg, pkgversion))
        self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('home'), self.config.apphome))
        self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('base url'), req.base_url()))
        self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('data directory url'), req.datadir_url))
        self.w(u'</table>')
        self.w(u'<br/>')
        # environment and request and server information
        try:
            # need to remove our adapter and then modpython-apache wrapper...
            env = req._areq._req.subprocess_env
        except AttributeError:
            return
        self.w(u'<h3>%s</h3>' % _('Environment'))
        self.w(u'<table border="1">')
        for attr in env.keys():
            self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>'
                   % (attr, html_escape(env[attr])))
        self.w(u'</table>')
        self.w(u'<h3>%s</h3>' % _('Request'))
        self.w(u'<table border="1">')
        for attr in ('filename', 'form', 'hostname', 'main', 'method',
                     'path_info', 'protocol',
                     'search_state', 'the_request', 'unparsed_uri', 'uri'):
            val = getattr(req, attr)
            self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>'
                   % (attr, html_escape(val)))
        self.w(u'</table>')
        server = req.server
        self.w(u'<h3>%s</h3>' % _('Server'))
        self.w(u'<table border="1">')
        for attr in dir(server):
            val = getattr(server, attr)
            if attr.startswith('_') or callable(val):
                continue
            self.w(u'<tr><th align="left">%s</th><td>%s</td></tr>'
                   % (attr, html_escape(val)))
        self.w(u'</table>')

