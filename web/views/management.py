"""security management and error screens


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import html_escape

from cubicweb.selectors import yes, none_rset, match_user_groups
from cubicweb.view import AnyRsetView, StartupView, EntityView
from cubicweb.common.uilib import html_traceback, rest_traceback
from cubicweb.web import formwidgets
from cubicweb.web.form import FieldsForm, EntityFieldsForm
from cubicweb.web.formfields import guess_field
from cubicweb.web.formrenderers import HTableFormRenderer

SUBMIT_MSGID = _('Submit bug report')
MAIL_SUBMIT_MSGID = _('Submit bug report by mail')

class SecurityViewMixIn(object):
    """display security information for a given schema """
    def schema_definition(self, eschema, link=True,  access_types=None):
        w = self.w
        _ = self.req._
        if not access_types:
            access_types = eschema.ACTIONS
        w(u'<table class="schemaInfo">')
        w(u'<tr><th>%s</th><th>%s</th><th>%s</th></tr>' % (
            _("permission"), _('granted to groups'), _('rql expressions')))
        for access_type in access_types:
            w(u'<tr>')
            w(u'<td>%s</td>' % self.req.__('%s_perm' % access_type))
            groups = eschema.get_groups(access_type)
            l = []
            groups = [(_(group), group) for group in groups]
            for trad, group in sorted(groups):
                if link:
                    l.append(u'<a href="%s" class="%s">%s</a><br/>' % (
                    self.build_url('egroup/%s' % group), group, trad))
                else:
                    l.append(u'<div class="%s">%s</div>' % (group, trad))
            w(u'<td>%s</td>' % u''.join(l))
            rqlexprs = eschema.get_rqlexprs(access_type)
            w(u'<td>%s</td>' % u'<br/><br/>'.join(expr.expression for expr in rqlexprs))
            w(u'</tr>\n')
        w(u'</table>')

    def has_schema_modified_permissions(self, eschema, access_types):
        """ return True if eschema's actual permissions are diffrents
        from the default ones
        """
        for access_type in access_types:
            if eschema.get_rqlexprs(access_type):
                return True
            if eschema.get_groups(access_type) != \
                    frozenset(eschema.get_default_groups()[access_type]):
                return True
        return False


class SecurityManagementView(EntityView, SecurityViewMixIn):
    """display security information for a given entity"""
    id = 'security'
    title = _('security')
    def call(self):
        self.w(u'<div id="progress">%s</div>' % self.req._('validating...'))
        super(SecurityManagementView, self).call()

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
        self.schema_definition(entity.e_schema)
        self.w('<h2>%s</h2>' % _('manage security'))
        # ownership information
        if self.schema.rschema('owned_by').has_perm(self.req, 'add',
                                                    fromeid=entity.eid):
            self.owned_by_edit_form(entity)
        else:
            self.owned_by_information(entity)
        # cwpermissions
        if 'require_permission' in entity.e_schema.subject_relations():
            w('<h3>%s</h3>' % _('permissions for this entity'))
            reqpermschema = self.schema.rschema('require_permission')
            self.require_permission_information(entity, reqpermschema)
            if reqpermschema.has_perm(self.req, 'add', fromeid=entity.eid):
                self.require_permission_edit_form(entity)

    def owned_by_edit_form(self, entity):
        self.w('<h3>%s</h3>' % self.req._('ownership'))
        msg = self.req._('ownerships have been changed')
        form = EntityFieldsForm(self.req, None, entity=entity, submitmsg=msg,
                                form_buttons=[formwidgets.SubmitButton()],
                                domid='ownership%s' % entity.eid,
                                __redirectvid='security',
                                __redirectpath=entity.rest_path())
        field = guess_field(entity.e_schema, self.schema.rschema('owned_by'))
        form.append_field(field)
        self.w(form.form_render(display_progress_div=False))

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
            for cwperm in entity.require_permission:
                w(u'<tr>')
                if dellinktempl:
                    w(u'<td>%s%s</td>' % (dellinktempl % cwperm.eid,
                                          cwperm.view('oneline')))
                else:
                    w(u'<td>%s</td>' % cwperm.view('oneline'))
                w(u'<td>%s</td>' % self.view('csv', cwperm.related('require_group'), 'null'))
                w(u'</tr>\n')
            w(u'</table>')
        else:
            self.w(self.req._('no associated permissions'))

    def require_permission_edit_form(self, entity):
        w = self.w
        _ = self.req._
        newperm = self.vreg.etype_class('CWPermission')(self.req, None)
        newperm.eid = self.req.varmaker.next()
        w(u'<p>%s</p>' % _('add a new permission'))
        form = EntityFieldsForm(self.req, None, entity=newperm,
                                form_buttons=[formwidgets.SubmitButton()],
                                domid='reqperm%s' % entity.eid,
                                __redirectvid='security',
                                __redirectpath=entity.rest_path())
        form.form_add_hidden('require_permission', entity.eid, role='object',
                             eidparam=True)
        permnames = getattr(entity, '__permissions__', None)
        cwpermschema = newperm.e_schema
        if permnames is not None:
            field = guess_field(cwpermschema, self.schema.rschema('name'),
                                widget=formwidgets.Select({'size': 1}),
                                choices=permnames)
        else:
            field = guess_field(cwpermschema, self.schema.rschema('name'))
        form.append_field(field)
        field = guess_field(cwpermschema, self.schema.rschema('label'))
        form.append_field(field)
        field = guess_field(cwpermschema, self.schema.rschema('require_group'))
        form.append_field(field)
        self.w(form.form_render(renderer=HTableFormRenderer(display_progress_div=False)))



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
        w = self.w
        ex = req.data.get('ex')#_("unable to find exception information"))
        excinfo = req.data.get('excinfo')
        title = self.req._('an error occured')
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
        eversion = vcconf.get('cubicweb', self.req._('no version information'))
        # NOTE: tuple wrapping needed since eversion is itself a tuple
        w(u"<b>CubicWeb version:</b> %s<br/>\n" % (eversion,))
        cversions = []
        for cube in self.config.cubes():
            cubeversion = vcconf.get(cube, self.req._('no version information'))
            w(u"<b>Package %s version:</b> %s<br/>\n" % (cube, cubeversion))
            cversions.append((cube, cubeversion))
        w(u"</div>")
        # creates a bug submission link if SUBMIT_URL is set
        submiturl = self.config['submit-url']
        submitmail = self.config['submit-mail']
        if submiturl or submitmail:
            form = FieldsForm(self.req, set_error_url=False)
            binfo = text_error_description(ex, excinfo, req, eversion, cversions)
            form.form_add_hidden('description', binfo)
            form.form_add_hidden('__bugreporting', '1')
            if submitmail:
                form.form_buttons = [formwidgets.SubmitButton(MAIL_SUBMIT_MSGID)]
                form.action = req.build_url('reportbug')
                w(form.form_render())
            if submiturl:
                form.form_add_hidden('description_format', 'text/rest')
                form.form_buttons = [formwidgets.SubmitButton(SUBMIT_MSGID)]
                form.action = submiturl
                w(form.form_render())


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

