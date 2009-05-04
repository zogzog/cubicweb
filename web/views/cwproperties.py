"""Specific views for CWProperty

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import html_escape

from logilab.common.decorators import cached

from cubicweb import UnknownProperty
from cubicweb.selectors import (one_line_rset, none_rset, implements,
                                match_user_groups)
from cubicweb.view import StartupView
from cubicweb.web import uicfg
from cubicweb.web.views import baseviews
from cubicweb.web import stdmsgs
from cubicweb.web.form import CompositeForm, EntityFieldsForm, FormViewMixIn
from cubicweb.web.formfields import FIELDS, StringField
from cubicweb.web.formwidgets import Select, Button, SubmitButton


# some string we want to be internationalizable for nicer display of eproperty
# groups
_('navigation')
_('ui')
_('actions')
_('boxes')
_('components')
_('contentnavigation')
_('navigation.combobox-limit')
_('navigation.page-size')
_('navigation.related-limit')
_('navigation.short-line-size')
_('ui.date-format')
_('ui.datetime-format')
_('ui.default-text-format')
_('ui.fckeditor')
_('ui.float-format')
_('ui.language')
_('ui.time-format')
_('open all')
_('ui.main-template')
_('ui.site-title')
_('ui.encoding')
_('category')


def make_togglable_link(nodeid, label, cookiename):
    """builds a HTML link that switches the visibility & remembers it"""
    action = u"javascript: toggle_and_remember_visibility('%s', '%s')" % \
        (nodeid, cookiename)
    return u'<a href="%s">%s</a>' % (action, label)

def css_class(someclass):
    return someclass and 'class="%s"' % someclass or ''


class CWPropertyPrimaryView(baseviews.PrimaryView):
    __select__ = implements('CWProperty')
    skip_none = False


class SystemEPropertiesForm(FormViewMixIn, StartupView):
    id = 'systemepropertiesform'
    __select__ = none_rset() & match_user_groups('managers')

    title = _('site configuration')
    category = 'startupview'

    def linkable(self):
        return True

    def url(self):
        """return the url associated with this view. We can omit rql here"""
        return self.build_url('view', vid=self.id)

    def _cookie_name(self, somestr):
        return str('%s_property_%s' % (self.config.appid, somestr))

    def _group_status(self, group, default=u'hidden'):
        """return css class name 'hidden' (collapsed), or '' (open)"""
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
        self.req.add_js('cubicweb.preferences.js')
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
            mainopts[group] = self.form(keys, True)
        for group, objects in groupedopts.items():
            for oid, keys in objects.items():
                groupedopts[group][oid] = self.form(keys, True)
        w = self.w
        req = self.req
        _ = req._
        w(u'<h1>%s</h1>\n' % _(self.title))
        # we don't want this in each sub-forms
        w(u'<div id="progress">%s</div>' % self.req._('validating...'))
        for label, group, form in sorted((_(g), g, f)
                                         for g, f in mainopts.iteritems()):
            status = css_class(self._group_status(group))
            w(u'<h2 class="propertiesform">%s</h2>\n' %
              (make_togglable_link('fieldset_' + group, label,
                                   self._cookie_name(group))))
            w(u'<div id="fieldset_%s" %s>' % (group, status))
            w(form)
            w(u'</div>')
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
        return self.req.execute('Any P,K,V WHERE P is CWProperty, P pkey K, '
                                'P value V, NOT P for_user U')

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
            entity = self.vreg.etype_class('CWProperty')(self.req, None, None)
            entity.eid = self.req.varmaker.next()
            entity['pkey'] = key
            entity['value'] = self.vreg.property_value(key)
        return entity

    def form(self, keys, splitlabel=False):
        buttons = [SubmitButton(),
                   Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]
        form = CompositeForm(self.req, domid=None, action=self.build_url(),
                             form_buttons=buttons,
                             submitmsg=self.req._('changes applied'))
        path = self.req.relative_path()
        if '?' in path:
            path, params = path.split('?', 1)
            form.form_add_hidden('__redirectparams', params)
        form.form_add_hidden('__redirectpath', path)
        for key in keys:
            self.form_row(form, key, splitlabel)
        return form.form_render(display_progress_div=False)

    def form_row(self, form, key, splitlabel):
        entity = self.entity_for_key(key)
        if splitlabel:
            label = key.split('.')[-1]
        else:
            label = key
        subform = EntityFieldsForm(self.req, entity=entity, set_error_url=False)
        subform.append_field(PropertyValueField(name='value', label=label,
                                                eidparam=True))
        subform.vreg = self.vreg
        subform.form_add_hidden('pkey', key, eidparam=True)
        form.form_add_subform(subform)
        return subform


def is_user_prefs(cls, req, rset, row=None, col=0, **kwargs):
    return req.user.eid == rset[row or 0][col]


class EPropertiesForm(SystemEPropertiesForm):
    id = 'epropertiesform'
    __select__ = (
        # we don't want guests to be able to come here
        match_user_groups('users', 'managers') &
        (none_rset() | ((one_line_rset() & is_user_prefs) &
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
        return self.req.execute('Any P,K,V WHERE P is CWProperty, P pkey K, P value V,'
                                'P for_user U, U eid %(x)s', {'x': self.user.eid})

    def form_row(self, form, key, splitlabel):
        subform = super(EPropertiesForm, self).form_row(form, key, splitlabel)
        # if user is in the managers group and the property is being created,
        # we have to set for_user explicitly
        if not subform.edited_entity.has_eid() and self.user.matching_groups('managers'):
            subform.form_add_hidden('for_user', self.user.eid, eidparam=True)


# eproperty form objects ######################################################

class PlaceHolderWidget(object):

    def render(self, form, field):
        domid = form.context[field]['id']
        # empty span as well else html validation fail (label is refering to
        # this id)
        return '<div id="div:%s"><span id="%s">%s</span></div>' % (
            domid, domid, form.req._('select a key first'))


class NotEditableWidget(object):
    def __init__(self, value, msg=None):
        self.value = value
        self.msg = msg

    def render(self, form, field):
        domid = form.context[field]['id']
        value = '<span class="value" id="%s">%s</span>' % (domid, self.value)
        if self.msg:
            value + '<div class="helper">%s</div>' % self.msg
        return value


class PropertyKeyField(StringField):
    """specific field for CWProperty.pkey to set the value widget according to
    the selected key
    """
    widget = Select

    def render(self, form, renderer):
        wdg = self.get_widget(form)
        wdg.attrs['tabindex'] = form.req.next_tabindex()
        wdg.attrs['onchange'] = "javascript:setPropValueWidget('%s', %s)" % (
            form.edited_entity.eid, form.req.next_tabindex())
        return wdg.render(form, self)

    def vocabulary(self, form):
        entity = form.edited_entity
        _ = form.req._
        if entity.has_eid():
            return [(_(entity.pkey), entity.pkey)]
        # key beginning with 'system.' should usually not be edited by hand
        choices = entity.vreg.user_property_keys()
        return [(u'', u'')] + sorted(zip((_(v) for v in choices), choices))


class PropertyValueField(StringField):
    """specific field for CWProperty.value  which will be different according to
    the selected key type and vocabulary information
    """
    widget = PlaceHolderWidget

    def render(self, form, renderer=None, tabindex=None):
        wdg = self.get_widget(form)
        if tabindex is not None:
            wdg.attrs['tabindex'] = tabindex
        return wdg.render(form, self)

    def form_init(self, form):
        entity = form.edited_entity
        if not (entity.has_eid() or 'pkey' in entity):
            # no key set yet, just include an empty div which will be filled
            # on key selection
            return
        try:
            pdef = form.vreg.property_info(entity.pkey)
        except UnknownProperty, ex:
            self.warning('%s (you should probably delete that property '
                         'from the database)', ex)
            msg = form.req._('you should probably delete that property')
            self.widget = NotEditableWidget(entity.printable_value('value'),
                                            '%s (%s)' % (msg, ex))
        if entity.pkey.startswith('system.'):
            msg = form.req._('value associated to this key is not editable '
                             'manually')
            self.widget = NotEditableWidget(entity.printable_value('value'), msg)
        # XXX race condition when used from CWPropertyForm, should not rely on
        # instance attributes
        self.initial = pdef['default']
        self.help = pdef['help']
        vocab = pdef['vocabulary']
        if vocab is not None:
            if callable(vocab):
                # list() just in case its a generator function
                self.choices = list(vocab(form.req))
            else:
                self.choices = vocab
            wdg = Select()
        else:
            wdg = FIELDS[pdef['type']].widget()
            if pdef['type'] == 'Boolean':
                self.choices = [(form.req._('yes'), '1'), (form.req._('no'), '')]
            elif pdef['type'] in ('Float', 'Int'):
                wdg.attrs.setdefault('size', 3)
        self.widget = wdg


uicfg.rfields.tag_relation(PropertyKeyField, ('CWProperty', 'pkey', '*'), 'subject')
uicfg.rfields.tag_relation(PropertyValueField, ('CWProperty', 'value', '*'), 'subject')
