# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""security management and error screens"""

__docformat__ = "restructuredtext en"
from cubicweb import _


from logilab.mtconverter import xml_escape
from logilab.common.registry import yes

from cubicweb.predicates import none_rset, match_user_groups, authenticated_user
from cubicweb.view import AnyRsetView, StartupView, EntityView, View
from cubicweb.uilib import html_traceback, rest_traceback, exc_message
from cubicweb.web import formwidgets as wdgs
from cubicweb.web.formfields import guess_field
from cubicweb.web.views.schema import SecurityViewMixIn

from yams.buildobjs import EntityType

SUBMIT_MSGID = _('Submit bug report')
MAIL_SUBMIT_MSGID = _('Submit bug report by mail')

class SecurityManagementView(SecurityViewMixIn, EntityView):
    """display security information for a given entity"""
    __regid__ = 'security'
    __select__ = EntityView.__select__ & authenticated_user()

    title = _('security')

    def call(self):
        self.w(u'<div id="progress">%s</div>' % self._cw._('validating...'))
        super(SecurityManagementView, self).call()

    def entity_call(self, entity):
        self._cw.add_js('cubicweb.edition.js')
        self._cw.add_css('cubicweb.acl.css')
        w = self.w
        _ = self._cw._
        w(u'<h1><span class="etype">%s</span> <a href="%s">%s</a></h1>'
          % (entity.dc_type().capitalize(),
             xml_escape(entity.absolute_url()),
             xml_escape(entity.dc_title())))
        # first show permissions defined by the schema
        self.w('<h2>%s</h2>' % _('Schema\'s permissions definitions'))
        self.permissions_table(entity.e_schema)
        self.w('<h2>%s</h2>' % _('Manage security'))
        # ownership information
        if self._cw.vreg.schema.rschema('owned_by').has_perm(self._cw, 'add',
                                                    fromeid=entity.eid):
            self.owned_by_edit_form(entity)
        else:
            self.owned_by_information(entity)

    def owned_by_edit_form(self, entity):
        self.w('<h3>%s</h3>' % self._cw._('Ownership'))
        msg = self._cw._('ownerships have been changed')
        form = self._cw.vreg['forms'].select('base', self._cw, entity=entity,
                                         form_renderer_id='onerowtable', submitmsg=msg,
                                         form_buttons=[wdgs.SubmitButton()],
                                         domid='ownership%s' % entity.eid,
                                         __redirectvid='security',
                                         __redirectpath=entity.rest_path())
        field = guess_field(entity.e_schema,
                            self._cw.vreg.schema['owned_by'],
                            req=self._cw)
        form.append_field(field)
        form.render(w=self.w, display_progress_div=False)

    def owned_by_information(self, entity):
        ownersrset = entity.related('owned_by')
        if ownersrset:
            self.w('<h3>%s</h3>' % self._cw._('Ownership'))
            self.w(u'<div class="ownerInfo">')
            self.w(self._cw._('this entity is currently owned by') + ' ')
            self.wview('csv', entity.related('owned_by'), 'null')
            self.w(u'</div>')
        # else we don't know if this is because entity has no owner or becayse
        # user as no access to owner users entities


class ErrorView(AnyRsetView):
    """default view when no result has been found"""
    __select__ = yes()
    __regid__ = 'error'

    def page_title(self):
        """returns a title according to the result set - used for the
        title in the HTML header
        """
        return self._cw._('an error occurred')

    def _excinfo(self):
        req = self._cw
        ex = req.data.get('ex')
        excinfo = req.data.get('excinfo')
        if 'errmsg' in req.data:
            errmsg = req.data['errmsg']
            exclass = None
        else:
            errmsg = exc_message(ex, req.encoding)
            exclass = ex.__class__.__name__
        return errmsg, exclass, excinfo

    def call(self):
        req = self._cw.reset_headers()
        w = self.w
        title = self._cw._('an error occurred')
        w(u'<h2>%s</h2>' % title)
        ex, exclass, excinfo = self._excinfo()
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
        vcconf = self._cw.cnx.repo.get_versions()
        w(u"<div>")
        eversion = vcconf.get('cubicweb', self._cw._('no version information'))
        # NOTE: tuple wrapping needed since eversion is itself a tuple
        w(u"<b>CubicWeb version:</b> %s<br/>\n" % (eversion,))
        cversions = []
        for cube in self._cw.vreg.config.cubes():
            cubeversion = vcconf.get(cube, self._cw._('no version information'))
            w(u"<b>Cube %s version:</b> %s<br/>\n" % (cube, cubeversion))
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
            # add a signature so one can't send arbitrary text
            form.add_hidden('__signature', req.vreg.config.sign_text(binfo))
            form.add_hidden('__bugreporting', '1')
            form.form_buttons = [wdgs.SubmitButton(MAIL_SUBMIT_MSGID)]
            form.action = req.build_url('reportbug')
            form.render(w=w)


def text_error_description(ex, excinfo, req, eversion, cubes):
    binfo = rest_traceback(excinfo, xml_escape(ex))
    binfo += u'\n\n:URL: %s\n' % req.url()
    if not '__bugreporting' in req.form:
        binfo += u'\n:form params:\n'
        binfo += u'\n'.join(u'  * %s = %s' % (k, v) for k, v in req.form.items())
    binfo += u'\n\n:CubicWeb version: %s\n'  % (eversion,)
    for pkg, pkgversion in cubes:
        binfo += u":Cube %s version: %s\n" % (pkg, pkgversion)
    binfo += '\n'
    return binfo


class CwStats(View):
    """A textual stats output for monitoring tools such as munin """

    __regid__ = 'processinfo'
    content_type = 'text/plain'
    templatable = False
    __select__ = none_rset() & match_user_groups('users', 'managers')

    def call(self):
        stats = self._cw.call_service('repo_stats')
        stats['looping_tasks'] = ', '.join('%s (%s seconds)' % (n, i) for n, i in stats['looping_tasks'])
        stats['threads'] = ', '.join(sorted(stats['threads']))
        for k in stats:
            if k in ('extid_cache_size', 'type_source_cache_size'):
                continue
            if k.endswith('_cache_size'):
                stats[k] = '%s / %s' % (stats[k]['size'], stats[k]['maxsize'])
        results = []
        for element in stats:
            results.append(u'%s %s' % (element, stats[element]))
        self.w(u'\n'.join(results))
