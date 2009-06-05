"""Specific views for CWProperty

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import html_escape

from logilab.common.decorators import cached

from cubicweb import UnknownProperty
from cubicweb.selectors import (one_line_rset, none_rset, implements,
                                match_user_groups)
from cubicweb.view import StartupView
from cubicweb.web import uicfg, stdmsgs
from cubicweb.web.form import FormViewMixIn
from cubicweb.web.formfields import FIELDS, StringField
from cubicweb.web.formwidgets import Select, Button, SubmitButton
from cubicweb.web.views import primary, formrenderers


# some string we want to be internationalizable for nicer display of property
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


def make_togglable_link(nodeid, label):
    """builds a HTML link that switches the visibility & remembers it"""
    action = u"javascript: togglePrefVisibility('%s')" % nodeid
    return u'<a href="%s">%s</a>' % (action, label)

def css_class(someclass):
    return someclass and 'class="%s"' % someclass or ''


class CWPropertyPrimaryView(primary.PrimaryView):
    __select__ = implements('CWProperty')
    skip_none = False


class SystemCWPropertiesForm(FormViewMixIn, StartupView):
    id = 'systempropertiesform'
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
        self.req.add_js(('cubicweb.edition.js', 'cubicweb.preferences.js', 'cubicweb.ajax.js'))
        self.req.add_css('cubicweb.preferences.css')
        vreg = self.vreg
        values = self.defined_keys
        groupedopts = {}
        mainopts = {}
        # "self.id=='systempropertiesform'" to skip site wide properties on
        # user's preference but not site's configuration
        for key in vreg.user_property_keys(self.id=='systempropertiesform'):
            parts = key.split('.')
            if parts[0] in vreg:
                # appobject configuration
                reg, oid, propid = parts
                groupedopts.setdefault(reg, {}).setdefault(oid, []).append(key)
            else:
                mainopts.setdefault(parts[0], []).append(key)
        # precompute form to consume error message
        for group, keys in mainopts.items():
            mainopts[group] = self.form(group, keys, False)

        for group, objects in groupedopts.items():
            for oid, keys in objects.items():
                groupedopts[group][oid] = self.form(group + '-' + oid, keys, True)

        w = self.w
        req = self.req
        _ = req._
        w(u'<h1>%s</h1>\n' % _(self.title))
        for label, group, form in sorted((_(g), g, f)
                                         for g, f in mainopts.iteritems()):
            status = css_class(self._group_status(group))
            w(u'<h2 class="propertiesform">%s</h2>\n' %
            (make_togglable_link('fieldset_' + group, label.capitalize())))
            w(u'<div id="fieldset_%s" %s>' % (group, status))
            w(u'<fieldset class="preferences">')
            w(form)
            w(u'</fieldset></div>')

        for label, group, objects in sorted((_(g), g, o)
                                            for g, o in groupedopts.iteritems()):
            status = css_class(self._group_status(group))
            w(u'<h2 class="propertiesform">%s</h2>\n' %
              (make_togglable_link('fieldset_' + group, label.capitalize())))
            w(u'<div id="fieldset_%s" %s>' % (group, status))

            # create selection
            sorted_objects =  sorted((self.req.__('%s_%s' % (group, o)), o, f)
                                           for o, f in objects.iteritems())
            for label, oid, form in sorted_objects:
                w(u'<div class="component">')
                w(u'''<div class="componentLink"><a href="javascript:noop();"
                           onclick="javascript:toggleVisibility('field_%(oid)s_%(group)s')"
                           class="componentTitle">%(label)s</a>''' % {'label':label, 'oid':oid, 'group':group})
                w(u''' (<div class="openlink"><a href="javascript:noop();"
                             onclick="javascript:openFieldset('fieldset_%(group)s')">%(label)s</a></div>)'''
                  % {'label':_('open all'), 'group':group})
                w(u'</div>')
                docmsgid = '%s_%s_description' % (group, oid)
                doc = _(docmsgid)
                if doc != docmsgid:
                    w(u'<div class="helper">%s</div>' % html_escape(doc).capitalize())
                w(u'</div>')
                w(u'<fieldset id="field_%(oid)s_%(group)s" class="%(group)s preferences hidden">'
                  % {'oid':oid, 'group':group})
                w(form)
                w(u'</fieldset>')
            w(u'</div>')

    @property
    @cached
    def cwprops_rset(self):
        return self.req.execute('Any P,K,V WHERE P is CWProperty, P pkey K, '
                                'P value V, NOT P for_user U')

    @property
    def defined_keys(self):
        values = {}
        for i, entity in enumerate(self.cwprops_rset.entities()):
            values[entity.pkey] = i
        return values

    def entity_for_key(self, key):
        values = self.defined_keys
        if key in values:
            entity = self.cwprops_rset.get_entity(values[key], 0)
        else:
            entity = self.vreg.etype_class('CWProperty')(self.req, None, None)
            entity.eid = self.req.varmaker.next()
            entity['pkey'] = key
            entity['value'] = self.vreg.property_value(key)
        return entity

    def form(self, formid, keys, splitlabel=False):
        buttons = [SubmitButton()]
        form = self.vreg.select('forms', 'composite', self.req,
                                domid=formid, action=self.build_url(),
                                form_buttons=buttons,
                                onsubmit="return validatePrefsForm('%s')" % formid,
                                submitmsg=self.req._('changes applied'))
        path = self.req.relative_path()
        if '?' in path:
            path, params = path.split('?', 1)
            form.form_add_hidden('__redirectparams', params)
        form.form_add_hidden('__redirectpath', path)
        for key in keys:
            self.form_row(form, key, splitlabel)
        renderer = self.vreg.select('formrenderers', 'cwproperties', self.req,
                                    display_progress_div=False)
        return form.form_render(renderer=renderer)

    def form_row(self, form, key, splitlabel):
        entity = self.entity_for_key(key)
        if splitlabel:
            label = key.split('.')[-1]
        else:
            label = key
        subform = self.vreg.select('forms', 'base', self.req, entity=entity,
                                   mainform=False)
        subform.append_field(PropertyValueField(name='value', label=label,
                                                eidparam=True))
        subform.vreg = self.vreg
        subform.form_add_hidden('pkey', key, eidparam=True)
        subform.form_add_hidden("current-value:%s" % entity.eid,)
        form.form_add_subform(subform)
        return subform

def is_user_prefs(cls, req, rset, row=None, col=0, **kwargs):
    return req.user.eid == rset[row or 0][col]


class CWPropertiesForm(SystemCWPropertiesForm):
    id = 'propertiesform'
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
    def cwprops_rset(self):
        return self.req.execute('Any P,K,V WHERE P is CWProperty, P pkey K, P value V,'
                                'P for_user U, U eid %(x)s', {'x': self.user.eid})

    def form_row(self, form, key, splitlabel):
        subform = super(CWPropertiesForm, self).form_row(form, key, splitlabel)
        # if user is in the managers group and the property is being created,
        # we have to set for_user explicitly
        if not subform.edited_entity.has_eid() and self.user.matching_groups('managers'):
            subform.form_add_hidden('for_user', self.user.eid, eidparam=True)


# cwproperty form objects ######################################################

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


uicfg.autoform_field.tag_attribute(('CWProperty', 'pkey'), PropertyKeyField)
uicfg.autoform_field.tag_attribute(('CWProperty', 'value'), PropertyValueField)


class CWPropertiesFormRenderer(formrenderers.FormRenderer):
    """specific renderer for properties"""
    id = 'cwproperties'

    def open_form(self, form, values):
        err = '<div class="formsg"></div>'
        return super(CWPropertiesFormRenderer, self).open_form(form, values) + err

    def _render_fields(self, fields, w, form):
        for field in fields:
            w(u'<div class="preffield">\n')
            if self.display_label:
                w(u'%s' % self.render_label(form, field))
            error = form.form_field_error(field)
            w(u'%s' % self.render_help(form, field))
            w(u'<div class="prefinput">')
            w(field.render(form, self))
            w(u'</div>')
            w(u'</div>')

    def render_buttons(self, w, form):
        w(u'<div>\n')
        for button in form.form_buttons:
            w(u'%s\n' % button.render(form))
        w(u'</div>')
