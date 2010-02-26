"""security management and error screens


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape

from cubicweb.selectors import yes, none_rset, match_user_groups, authenticated_user
from cubicweb.view import AnyRsetView, StartupView, EntityView, View
from cubicweb.uilib import html_traceback, rest_traceback
from cubicweb.web import formwidgets as wdgs
from cubicweb.web.formfields import guess_field

SUBMIT_MSGID = _('Submit bug report')
MAIL_SUBMIT_MSGID = _('Submit bug report by mail')


class SecurityViewMixIn(object):
    """display security information for a given schema """

    def schema_definition(self, eschema, link=True,  access_types=None):
        w = self.w
        _ = self._cw._
        if not access_types:
            access_types = eschema.ACTIONS
        w(u'<table class="schemaInfo">')
        w(u'<tr><th>%s</th><th>%s</th><th>%s</th></tr>' % (
            _("permission"), _('granted to groups'), _('rql expressions')))
        for access_type in access_types:
            w(u'<tr>')
            w(u'<td>%s</td>' % self._cw.__('%s_perm' % access_type))
            groups = eschema.get_groups(access_type)
            l = []
            groups = [(_(group), group) for group in groups]
            for trad, group in sorted(groups):
                if link:
                    # XXX we should get a group entity and call its absolute_url
                    # method
                    l.append(u'<a href="%s" class="%s">%s</a><br/>' % (
                    self._cw.build_url('cwgroup/%s' % group), group, trad))
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
    __regid__ = 'security'
    __select__ = EntityView.__select__ & authenticated_user()

    title = _('security')

    def call(self):
        self.w(u'<div id="progress">%s</div>' % self._cw._('validating...'))
        super(SecurityManagementView, self).call()

    def cell_call(self, row, col):
        self._cw.add_js('cubicweb.edition.js')
        self._cw.add_css('cubicweb.acl.css')
        entity = self.cw_rset.get_entity(row, col)
        w = self.w
        _ = self._cw._
        w(u'<h1><span class="etype">%s</span> <a href="%s">%s</a></h1>'
          % (entity.dc_type().capitalize(),
             xml_escape(entity.absolute_url()),
             xml_escape(entity.dc_title())))
        # first show permissions defined by the schema
        self.w('<h2>%s</h2>' % _('schema\'s permissions definitions'))
        self.schema_definition(entity.e_schema)
        self.w('<h2>%s</h2>' % _('manage security'))
        # ownership information
        if self._cw.vreg.schema.rschema('owned_by').has_perm(self._cw, 'add',
                                                    fromeid=entity.eid):
            self.owned_by_edit_form(entity)
        else:
            self.owned_by_information(entity)
        # cwpermissions
        if 'require_permission' in entity.e_schema.subject_relations():
            w('<h3>%s</h3>' % _('permissions for this entity'))
            reqpermschema = self._cw.vreg.schema.rschema('require_permission')
            self.require_permission_information(entity, reqpermschema)
            if reqpermschema.has_perm(self._cw, 'add', fromeid=entity.eid):
                self.require_permission_edit_form(entity)

    def owned_by_edit_form(self, entity):
        self.w('<h3>%s</h3>' % self._cw._('ownership'))
        msg = self._cw._('ownerships have been changed')
        form = self._cw.vreg['forms'].select('base', self._cw, entity=entity,
                                         form_renderer_id='base', submitmsg=msg,
                                         form_buttons=[wdgs.SubmitButton()],
                                         domid='ownership%s' % entity.eid,
                                         __redirectvid='security',
                                         __redirectpath=entity.rest_path())
        field = guess_field(entity.e_schema, self._cw.vreg.schema.rschema('owned_by'))
        form.append_field(field)
        self.w(form.render(display_progress_div=False))

    def owned_by_information(self, entity):
        ownersrset = entity.related('owned_by')
        if ownersrset:
            self.w('<h3>%s</h3>' % self._cw._('ownership'))
            self.w(u'<div class="ownerInfo">')
            self.w(self._cw._('this entity is currently owned by') + ' ')
            self.wview('csv', entity.related('owned_by'), 'null')
            self.w(u'</div>')
        # else we don't know if this is because entity has no owner or becayse
        # user as no access to owner users entities

    def require_permission_information(self, entity, reqpermschema):
        if entity.require_permission:
            w = self.w
            _ = self._cw._
            if reqpermschema.has_perm(self._cw, 'delete', fromeid=entity.eid):
                delurl = self._cw.build_url('edit', __redirectvid='security',
                                            __redirectpath=entity.rest_path())
                delurl = delurl.replace('%', '%%')
                # don't give __delete value to build_url else it will be urlquoted
                # and this will replace %s by %25s
                delurl += '&__delete=%s:require_permission:%%s' % entity.eid
                dellinktempl = u'[<a href="%s" title="%s">-</a>]&#160;' % (
                    xml_escape(delurl), _('delete this permission'))
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
            self.w(self._cw._('no associated permissions'))

    def require_permission_edit_form(self, entity):
        newperm = self._cw.vreg['etypes'].etype_class('CWPermission')(self._cw)
        newperm.eid = self._cw.varmaker.next()
        self.w(u'<p>%s</p>' % self._cw._('add a new permission'))
        form = self._cw.vreg['forms'].select('base', self._cw, entity=newperm,
                                         form_buttons=[wdgs.SubmitButton()],
                                         domid='reqperm%s' % entity.eid,
                                         __redirectvid='security',
                                         __redirectpath=entity.rest_path())
        form.add_hidden('require_permission', entity.eid, role='object',
                        eidparam=True)
        permnames = getattr(entity, '__permissions__', None)
        cwpermschema = newperm.e_schema
        if permnames is not None:
            field = guess_field(cwpermschema, self._cw.vreg.schema.rschema('name'),
                                widget=wdgs.Select({'size': 1}),
                                choices=permnames)
        else:
            field = guess_field(cwpermschema, self._cw.vreg.schema.rschema('name'))
        form.append_field(field)
        field = guess_field(cwpermschema, self._cw.vreg.schema.rschema('label'))
        form.append_field(field)
        field = guess_field(cwpermschema, self._cw.vreg.schema.rschema('require_group'))
        form.append_field(field)
        renderer = self._cw.vreg['formrenderers'].select(
            'htable', self._cw, rset=None, display_progress_div=False)
        self.w(form.render(renderer=renderer))


class ErrorView(AnyRsetView):
    """default view when no result has been found"""
    __select__ = yes()
    __regid__ = 'error'

    def page_title(self):
        """returns a title according to the result set - used for the
        title in the HTML header
        """
        return self._cw._('an error occured')

    def call(self):
        req = self._cw.reset_headers()
        w = self.w
        ex = req.data.get('ex')#_("unable to find exception information"))
        excinfo = req.data.get('excinfo')
        title = self._cw._('an error occured')
        w(u'<h2>%s</h2>' % title)
        if 'errmsg' in req.data:
            ex = req.data['errmsg']
            exclass = None
        else:
            exclass = ex.__class__.__name__
            ex = exc_message(ex, req.encoding)
        if excinfo is not None and self._cw.vreg.config['print-traceback']:
            if exclass is None:
                w(u'<div class="tb">%s</div>'
                       % xml_escape(ex).replace("\n","<br />"))
            else:
                w(u'<div class="tb">%s: %s</div>'
                       % (exclass, xml_escape(ex).replace("\n","<br />")))
            w(u'<hr />')
            w(u'<div class="tb">%s</div>' % html_traceback(excinfo, ex, ''))
        else:
            w(u'<div class="tb">%s</div>' % (xml_escape(ex).replace("\n","<br />")))
        # if excinfo is not None, it's probably not a bug
        if excinfo is None:
            return
        vcconf = self._cw.vreg.config.vc_config()
        w(u"<div>")
        eversion = vcconf.get('cubicweb', self._cw._('no version information'))
        # NOTE: tuple wrapping needed since eversion is itself a tuple
        w(u"<b>CubicWeb version:</b> %s<br/>\n" % (eversion,))
        cversions = []
        for cube in self._cw.vreg.config.cubes():
            cubeversion = vcconf.get(cube, self._cw._('no version information'))
            w(u"<b>Package %s version:</b> %s<br/>\n" % (cube, cubeversion))
            cversions.append((cube, cubeversion))
        w(u"</div>")
        # creates a bug submission link if submit-mail is set
        if self._cw.vreg.config['submit-mail']:
            form = self._cw.vreg['forms'].select('base', self._cw, rset=None,
                                             mainform=False)
            binfo = text_error_description(ex, excinfo, req, eversion, cversions)
            form.add_hidden('description', binfo,
                            # we must use a text area to keep line breaks
                            widget=wdgs.TextArea({'class': 'hidden'}))
            form.add_hidden('__bugreporting', '1')
            form.form_buttons = [wdgs.SubmitButton(MAIL_SUBMIT_MSGID)]
            form.action = req.build_url('reportbug')
            w(form.render())


def exc_message(ex, encoding):
    try:
        return unicode(ex)
    except:
        try:
            return unicode(str(ex), encoding, 'replace')
        except:
            return unicode(repr(ex), encoding, 'replace')

def text_error_description(ex, excinfo, req, eversion, cubes):
    binfo = rest_traceback(excinfo, xml_escape(ex))
    binfo += u'\n\n:URL: %s\n' % req.url()
    if not '__bugreporting' in req.form:
        binfo += u'\n:form params:\n'
        binfo += u'\n'.join(u'  * %s = %s' % (k, v) for k, v in req.form.iteritems())
    binfo += u'\n\n:CubicWeb version: %s\n'  % (eversion,)
    for pkg, pkgversion in cubes:
        binfo += u":Package %s version: %s\n" % (pkg, pkgversion)
    binfo += '\n'
    return binfo


class CwStats(View):
    """A textual stats output for monitoring tools such as munin """

    __regid__ = 'processinfo'
    content_type = 'text/txt'
    templatable = False
    __select__ = none_rset() & match_user_groups('users', 'managers')

    def call(self):
        stats = self._cw.vreg.config.repository(None).stats()
        results = []
        for element in stats:
            results.append(u'%s %s' % (element, stats[element]))
        self.w(u'\n'.join(results))
