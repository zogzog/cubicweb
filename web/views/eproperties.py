"""Specific views for EProperty


:organization: Logilab
:copyright: 2007-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from logilab.common.decorators import cached

from cubicweb.selectors import (one_line_rset, none_rset, implements,
                                match_user_groups, chainfirst, chainall)
from cubicweb.common.utils import UStringIO
from cubicweb.common.view import StartupView
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param, stdmsgs
from cubicweb.web.views import baseviews
from cubicweb.web.form import FormMixIn

_ = unicode

# some string we want to be internationalizable for nicer display of eproperty
# groups
_('navigation')
_('ui')
_('actions')
_('boxes')
_('components')
_('contentnavigation')

class EPropertyPrimaryView(baseviews.PrimaryView):
    __select__ = implements('EProperty')
    skip_none = False


def make_togglable_link(nodeid, label, cookiename):
    """builds a HTML link that switches the visibility & remembers it"""
    action = u"javascript: toggle_and_remember_visibility('%s', '%s')" % \
        (nodeid, cookiename)
    return u'<a href="%s">%s</a>' % (action, label)

def css_class(someclass):
    return someclass and 'class="%s"' % someclass or ''

class SystemEPropertiesForm(FormMixIn, StartupView):
    id = 'systemepropertiesform'
    __select__ = none_rset & match_user_groups('managers')

    title = _('site configuration')
    controller = 'edit'
    category = 'startupview'

    def linkable(self):
        return True

    def url(self):
        """return the url associated with this view. We can omit rql here"""
        return self.build_url('view', vid=self.id)

    def _cookie_name(self, somestr):
        return str('%s_property_%s' % (self.config.appid, somestr))

    def _group_status(self, group, default=u'hidden'):
        cookies = self.req.get_cookie()
        cookiename = self._cookie_name(group)
        cookie = cookies.get(cookiename)
        if cookie is None:
            cookies[cookiename] = default
            self.req.set_cookie(cookies, cookiename, maxage=None)
            status = default
        else:
            status = cookie.value
        return status

    def call(self, **kwargs):
        """The default view representing the application's index"""
        self.req.add_js(('cubicweb.edition.js', 'cubicweb.preferences.js'))
        self.req.add_css('cubicweb.preferences.css')
        vreg = self.vreg
        values = self.defined_keys
        groupedopts = {}
        mainopts = {}
        # "self.id=='systemepropertiesform'" to skip site wide properties on
        # user's preference but not site's configuration
        for key in vreg.user_property_keys(self.id=='systemepropertiesform'):
            parts = key.split('.')
            if parts[0] in vreg:
                # appobject configuration
                reg, oid, propid = parts
                groupedopts.setdefault(reg, {}).setdefault(oid, []).append(key)
            else:
                mainopts.setdefault(parts[0], []).append(key)
        # precompute form to consume error message
        for group, keys in mainopts.items():
            mainopts[group] = self.form(keys, False)
        for group, objects in groupedopts.items():
            for oid, keys in objects.items():
                groupedopts[group][oid] = self.form(keys, True)

        w = self.w
        req = self.req
        _ = req._
        w(u'<h1>%s</h1>\n' % _(self.title))
        w(self.error_message())
        for label, group, form in sorted((_(g), g, f)
                                         for g, f in mainopts.iteritems()):
            status = css_class(self._group_status(group)) #'hidden' (collapsed), or '' (open) ?
            w(u'<h2 class="propertiesform">%s</h2>\n' %
              (make_togglable_link('fieldset_' + group, label,
                                   self._cookie_name(group))))
            w(u'<div id="fieldset_%s" %s>' % (group, status))
            w(u'<fieldset class="subentity">')
            w(form)
            w(u'</fieldset></div>')
        for label, group, objects in sorted((_(g), g, o)
                                            for g, o in groupedopts.iteritems()):
            status = css_class(self._group_status(group))
            w(u'<h2 class="propertiesform">%s</h2>\n' %
              (make_togglable_link('fieldset_' + group, label,
                                   self._cookie_name(group))))
            w(u'<div id="fieldset_%s" %s>' % (group, status))
            for label, oid, form in sorted((self.req.__('%s_%s' % (group, o)), o, f)
                                           for o, f in objects.iteritems()):
                w(u'<fieldset class="subentity">')
                w(u'<legend class="componentTitle">%s</legend>\n' % label)
                docmsgid = '%s_%s_description' % (group, oid)
                doc = _(docmsgid)
                if doc != docmsgid:
                    w(u'<p class="description">%s</p>' % html_escape(doc))
                w(form)
                w(u'</fieldset>')
            w(u'</div>')

    @property
    @cached
    def eprops_rset(self):
        return self.req.execute('Any P,K,V WHERE P is EProperty, P pkey K, P value V, NOT P for_user U')

    @property
    def defined_keys(self):
        values = {}
        for i, entity in enumerate(self.eprops_rset.entities()):
            values[entity.pkey] = i
        return values

    def entity_for_key(self, key):
        values = self.defined_keys
        if key in values:
            entity = self.eprops_rset.get_entity(values[key], 0)
        else:
            entity = self.vreg.etype_class('EProperty')(self.req, None, None)
            entity.eid = self.req.varmaker.next()
            entity['value'] = self.vreg.property_value(key)
        return entity

    def form(self, keys, splitlabel=False):
        stream = UStringIO()
        w = stream.write
        w(u'<form action="%s" method="post">\n' % self.build_url())
        w(u'<fieldset>\n')
        w(u'<input type="hidden" name="__errorurl" value="%s"/>\n'
          % html_escape(self.req.url()))
        w(u'<input type="hidden" name="__form_id" value="%s"/>\n' % self.id)
        path = self.req.relative_path()
        if '?' in path:
            path, params = path.split('?', 1)
            w(u'<input type="hidden" name="__redirectparams" value="%s"/>\n'
              % html_escape(params))
        w(u'<input type="hidden" name="__redirectpath" value="%s"/>\n' % path)
        #w(u'<input type="hidden" name="__redirectrql" value=""/>\n')
        w(u'<input type="hidden" name="__message" value="%s"/>\n'
          % self.req._('changes applied'))
        w(u'<table><tr><td>\n')

        w(u'<table>\n')
        for key in keys:
            w(u'<tr>\n')
            self.form_row(w, key, splitlabel)
            w(u'</tr>\n')
        w(u'</table>\n')
        w(u'</td></tr><tr><td>\n')
        w(self.button_ok())
        w(self.button_cancel())
        w(u'</td></tr></table>\n')
        w(u'</fieldset>\n')
        w(u'</form>\n')
        return stream.getvalue()

    def form_row(self, w, key, splitlabel):
        entity = self.entity_for_key(key)
        eid = entity.eid
        if splitlabel:
            w(u'<td class="label">%s</td>' % self.req._(key.split('.')[-1]))
        else:
            w(u'<td class="label">%s</td>' % self.req._(key))
        wdg = self.vreg.property_value_widget(key, req=self.req)
        error = wdg.render_error(entity)
        w(u'<td class="%s">' % (error and 'error' or ''))
        w(error)
        self.form_row_hiddens(w, entity, key)
        w(wdg.edit_render(entity))
        w(u'</td>\n')
        w(u'<td>%s</td>' % wdg.render_help(entity))
        return entity

    def form_row_hiddens(self, w, entity, key):
        eid = entity.eid
        w(u'<input type="hidden" name="eid" value="%s"/>' % eid)
        w(u'<input type="hidden" name="%s" value="EProperty"/>' % eid_param('__type', eid))
        w(u'<input type="hidden" name="%s" value="%s"/>' % (eid_param('pkey', eid), key))
        w(u'<input type="hidden" name="%s" value="%s"/>' % (eid_param('edits-pkey', eid), ''))



def is_user_prefs(cls, req, rset, row=None, col=0, **kwargs):
    return req.user.eid == rset[row or 0][col]


class EPropertiesForm(SystemEPropertiesForm):
    id = 'epropertiesform'
    __select__ = (
        # we don't want guests to be able to come here
        match_user_groups('users', 'managers') &
        (none_rset | ((one_line_rset() & is_user_prefs) &
                      (one_line_rset() & match_user_groups('managers'))))
        )
    
    title = _('preferences')

    @property
    def user(self):
        if self.rset is None:
            return self.req.user
        return self.rset.get_entity(self.row or 0, self.col or 0)

    @property
    @cached
    def eprops_rset(self):
        return self.req.execute('Any P,K,V WHERE P is EProperty, P pkey K, P value V,'
                                'P for_user U, U eid %(x)s', {'x': self.user.eid})

    def form_row_hiddens(self, w, entity, key):
        super(EPropertiesForm, self).form_row_hiddens(w, entity, key)
        # if user is in the managers group and the property is being created,
        # we have to set for_user explicitly
        if not entity.has_eid() and self.user.matching_groups('managers'):
            eid = entity.eid
            w(u'<input type="hidden" name="%s" value="%s"/>'
              % (eid_param('edits-for_user', eid), INTERNAL_FIELD_VALUE))
            w(u'<input type="hidden" name="%s" value="%s"/>'
              % (eid_param('for_user', eid), self.user.eid))

