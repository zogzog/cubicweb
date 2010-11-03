# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
Renderers
---------

.. Note::
   Form renderers are responsible to layout a form to HTML.

Here are the base renderers available:

.. autoclass:: cubicweb.web.views.formrenderers.FormRenderer
.. autoclass:: cubicweb.web.views.formrenderers.HTableFormRenderer
.. autoclass:: cubicweb.web.views.formrenderers.EntityCompositeFormRenderer
.. autoclass:: cubicweb.web.views.formrenderers.EntityFormRenderer
.. autoclass:: cubicweb.web.views.formrenderers.EntityInlinedFormRenderer

"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common import dictattr
from logilab.mtconverter import xml_escape

from cubicweb import tags
from cubicweb.appobject import AppObject
from cubicweb.selectors import is_instance, yes
from cubicweb.utils import json_dumps
from cubicweb.web import eid_param, formwidgets as fwdgs


def checkbox(name, value, attrs='', checked=None):
    if checked is None:
        checked = value
    checked = checked and 'checked="checked"' or ''
    return u'<input type="checkbox" name="%s" value="%s" %s %s />' % (
        name, value, checked, attrs)

def field_label(form, field):
    # XXX with 3.6 we can now properly rely on 'if field.role is not None' and
    # stop having a tuple for label
    if isinstance(field.label, tuple): # i.e. needs contextual translation
        return form._cw.pgettext(*field.label)
    return form._cw._(field.label)



class FormRenderer(AppObject):
    """This is the 'default' renderer, displaying fields in a two columns table:

    +--------------+--------------+
    | field1 label | field1 input |
    +--------------+--------------+
    | field2 label | field2 input |
    +--------------+--------------+

    +---------+
    | buttons |
    +---------+
    """
    __registry__ = 'formrenderers'
    __regid__ = 'default'

    _options = ('display_label', 'display_help',
                'display_progress_div', 'table_class', 'button_bar_class',
                # add entity since it may be given to select the renderer
                'entity')
    display_label = True
    display_help = True
    display_progress_div = True
    table_class = u'attributeForm'
    button_bar_class = u'formButtonBar'

    def __init__(self, req=None, rset=None, row=None, col=None, **kwargs):
        super(FormRenderer, self).__init__(req, rset=rset, row=row, col=col)
        if self._set_options(kwargs):
            raise ValueError('unconsumed arguments %s' % kwargs)

    def _set_options(self, kwargs):
        for key in self._options:
            try:
                setattr(self, key, kwargs.pop(key))
            except KeyError:
                continue
        return kwargs

    # renderer interface ######################################################

    def render(self, form, values):
        self._set_options(values)
        form.add_media()
        data = []
        w = data.append
        w(self.open_form(form, values))
        if self.display_progress_div:
            w(u'<div id="progress">%s</div>' % self._cw._('validating...'))
        w(u'<fieldset>')
        self.render_fields(w, form, values)
        self.render_buttons(w, form)
        w(u'</fieldset>')
        w(self.close_form(form, values))
        errormsg = self.error_message(form)
        if errormsg:
            data.insert(0, errormsg)
        return '\n'.join(data)

    def render_label(self, form, field):
        if field.label is None:
            return u''
        label = field_label(form, field)
        attrs = {'for': field.dom_id(form)}
        if field.required:
            attrs['class'] = 'required'
        return tags.label(label, **attrs)

    def render_help(self, form, field):
        help = []
        descr = field.help
        if callable(descr):
            descr = descr(form)
        if descr:
            help.append('<div class="helper">%s</div>' % self._cw._(descr))
        example = field.example_format(self._cw)
        if example:
            help.append('<div class="helper">(%s: %s)</div>'
                        % (self._cw._('sample format'), example))
        return u'&#160;'.join(help)

    # specific methods (mostly to ease overriding) #############################

    def error_message(self, form):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        req = self._cw
        errex = form.form_valerror
        # get extra errors
        if errex is not None:
            errormsg = req._('please correct the following errors:')
            errors = form.remaining_errors()
            if errors:
                if len(errors) > 1:
                    templstr = u'<li>%s</li>\n'
                else:
                    templstr = u'&#160;%s\n'
                for field, err in errors:
                    if field is None:
                        errormsg += templstr % err
                    else:
                        errormsg += templstr % '%s: %s' % (req._(field), err)
                if len(errors) > 1:
                    errormsg = '<ul>%s</ul>' % errormsg
            return u'<div class="errorMessage">%s</div>' % errormsg
        return u''

    def open_form(self, form, values):
        if form.needs_multipart:
            enctype = 'multipart/form-data'
        else:
            enctype = 'application/x-www-form-urlencoded'
        tag = ('<form action="%s" method="post" enctype="%s"' % (
            xml_escape(form.form_action() or '#'), enctype))
        if form.domid:
            tag += ' id="%s"' % form.domid
        if form.onsubmit:
            tag += ' onsubmit="%s"' % xml_escape(form.onsubmit % dictattr(form))
        if form.cssstyle:
            tag += ' style="%s"' % xml_escape(form.cssstyle)
        if form.cssclass:
            tag += ' class="%s"' % xml_escape(form.cssclass)
        if form.cwtarget:
            tag += ' cubicweb:target="%s"' % xml_escape(form.cwtarget)
        return tag + '>'

    def close_form(self, form, values):
        """seems dumb but important for consistency w/ close form, and necessary
        for form renderers overriding open_form to use something else or more than
        and <form>
        """
        return '</form>'

    def render_fields(self, w, form, values):
        fields = self._render_hidden_fields(w, form)
        if fields:
            self._render_fields(fields, w, form)
        self.render_child_forms(w, form, values)

    def render_child_forms(self, w, form, values):
        # render
        for childform in getattr(form, 'forms', []):
            self.render_fields(w, childform, values)

    def _render_hidden_fields(self, w, form):
        fields = form.fields[:]
        for field in form.fields:
            if not field.is_visible():
                w(field.render(form, self))
                fields.remove(field)
        return fields

    def _render_fields(self, fields, w, form):
        byfieldset = {}
        for field in fields:
            byfieldset.setdefault(field.fieldset, []).append(field)
        if form.fieldsets_in_order:
            fieldsets = form.fieldsets_in_order
        else:
            fieldsets = byfieldset.keys()
        for fieldset in fieldsets:
            try:
                fields = byfieldset.pop(fieldset)
            except KeyError:
                self.warning('no such fieldset: %s (%s)', fieldset, form)
                continue
            w(u'<fieldset class="%s">' % (fieldset or u'default'))
            if fieldset:
                w(u'<legend>%s</legend>' % self._cw._(fieldset))
            w(u'<table class="%s">' % self.table_class)
            for field in fields:
                w(u'<tr class="%s_%s_row">' % (field.name, field.role))
                if self.display_label and field.label is not None:
                    w(u'<th class="labelCol">%s</th>' % self.render_label(form, field))
                w('<td')
                if field.label is None:
                    w(' colspan="2"')
                error = form.field_error(field)
                if error:
                    w(u' class="error"')
                w(u'>')
                w(field.render(form, self))
                if error:
                    self.render_error(w, error)
                if self.display_help:
                    w(self.render_help(form, field))
                w(u'</td></tr>')
            w(u'</table></fieldset>')
        if byfieldset:
            self.warning('unused fieldsets: %s', ', '.join(byfieldset))

    def render_buttons(self, w, form):
        if not form.form_buttons:
            return
        w(u'<table class="%s">\n<tr>\n' % self.button_bar_class)
        for button in form.form_buttons:
            w(u'<td>%s</td>\n' % button.render(form))
        w(u'</tr></table>')

    def render_error(self, w, err):
        """return validation error for widget's field, if any"""
        w(u'<span class="errorMsg">%s</span>' % err)



class BaseFormRenderer(FormRenderer):
    """use form_renderer_id = 'base' if you want base FormRenderer layout even
    when selected for an entity
    """
    __regid__ = 'base'



class HTableFormRenderer(FormRenderer):
    """The 'htable' form renderer display fields horizontally in a table:

    +--------------+--------------+---------+
    | field1 label | field2 label |         |
    +--------------+--------------+---------+
    | field1 input | field2 input | buttons |
    +--------------+--------------+---------+
    """
    __regid__ = 'htable'

    display_help = False
    def _render_fields(self, fields, w, form):
        w(u'<table border="0" class="htableForm">')
        w(u'<tr>')
        for field in fields:
            if self.display_label:
                w(u'<th class="labelCol">%s</th>' % self.render_label(form, field))
            if self.display_help:
                w(self.render_help(form, field))
        # empty slot for buttons
        w(u'<th class="labelCol">&#160;</th>')
        w(u'</tr>')
        w(u'<tr>')
        for field in fields:
            error = form.field_error(field)
            if error:
                w(u'<td class="error">')
                self.render_error(w, error)
            else:
                w(u'<td>')
            w(field.render(form, self))
            w(u'</td>')
        w(u'<td>')
        for button in form.form_buttons:
            w(button.render(form))
        w(u'</td>')
        w(u'</tr>')
        w(u'</table>')

    def render_buttons(self, w, form):
        pass


class EntityCompositeFormRenderer(FormRenderer):
    """This is a specific renderer for the multiple entities edition form
    ('muledit').

    Each entity form will be displayed in row off a table, with a check box for
    each entities to indicate which ones are edited. Those checkboxes should be
    automatically updated when something is edited.
    """
    __regid__ = 'composite'

    _main_display_fields = None

    def render_fields(self, w, form, values):
        if form.parent_form is None:
            w(u'<table class="listing">')
            # get fields from the first subform with something to display (we
            # may have subforms with nothing editable that will simply be
            # skipped later)
            for subform in form.forms:
                subfields = [field for field in subform.fields
                             if field.is_visible()]
                if subfields:
                    break
            if subfields:
                # main form, display table headers
                w(u'<tr class="header">')
                w(u'<th align="left">%s</th>' %
                  tags.input(type='checkbox',
                             title=self._cw._('toggle check boxes'),
                             onclick="setCheckboxesState('eid', null, this.checked)"))
                for field in subfields:
                    w(u'<th>%s</th>' % field_label(form, field))
                w(u'</tr>')
        super(EntityCompositeFormRenderer, self).render_fields(w, form, values)
        if form.parent_form is None:
            w(u'</table>')
            if self._main_display_fields:
                super(EntityCompositeFormRenderer, self)._render_fields(
                    self._main_display_fields, w, form)

    def _render_fields(self, fields, w, form):
        if form.parent_form is not None:
            entity = form.edited_entity
            values = form.form_previous_values
            qeid = eid_param('eid', entity.eid)
            cbsetstate = "setCheckboxesState('eid', %s, 'checked')" % \
                         xml_escape(json_dumps(entity.eid))
            w(u'<tr class="%s">' % (entity.cw_row % 2 and u'even' or u'odd'))
            # XXX turn this into a widget used on the eid field
            w(u'<td>%s</td>' % checkbox('eid', entity.eid,
                                        checked=qeid in values))
            for field in fields:
                error = form.field_error(field)
                if error:
                    w(u'<td class="error">')
                    self.render_error(w, error)
                else:
                    w(u'<td>')
                if isinstance(field.widget, (fwdgs.Select, fwdgs.CheckBox,
                                             fwdgs.Radio)):
                    field.widget.attrs['onchange'] = cbsetstate
                elif isinstance(field.widget, fwdgs.Input):
                    field.widget.attrs['onkeypress'] = cbsetstate
                # XXX else
                w(u'<div>%s</div>' % field.render(form, self))
                w(u'</td>\n')
            w(u'</tr>')
        else:
            self._main_display_fields = fields


class EntityFormRenderer(BaseFormRenderer):
    """This is the 'default' renderer for entity's form.

    You can still use form_renderer_id = 'base' if you want base FormRenderer
    layout even when selected for an entity.
    """
    __regid__ = 'default'
    # needs some additional points in some case (XXX explain cases)
    __select__ = is_instance('Any') & yes()

    _options = FormRenderer._options + ('main_form_title',)
    main_form_title = _('main informations')

    def open_form(self, form, values):
        attrs_fs_label = ''
        if self.main_form_title:
            attrs_fs_label += ('<div class="iformTitle"><span>%s</span></div>'
                               % self._cw._(self.main_form_title))
        attrs_fs_label += '<div class="formBody">'
        return attrs_fs_label + super(EntityFormRenderer, self).open_form(form, values)

    def close_form(self, form, values):
        """seems dumb but important for consistency w/ close form, and necessary
        for form renderers overriding open_form to use something else or more than
        and <form>
        """
        return super(EntityFormRenderer, self).close_form(form, values) + '</div>'

    def render_buttons(self, w, form):
        if len(form.form_buttons) == 3:
            w("""<table width="100%%">
  <tbody>
   <tr><td align="center">
     %s
   </td><td style="align: right; width: 50%%;">
     %s
     %s
   </td></tr>
  </tbody>
 </table>""" % tuple(button.render(form) for button in form.form_buttons))
        else:
            super(EntityFormRenderer, self).render_buttons(w, form)


class EntityInlinedFormRenderer(EntityFormRenderer):
    """This is a specific renderer for entity's form inlined into another
    entity's form.
    """
    __regid__ = 'inline'

    def render(self, form, values):
        form.add_media()
        data = []
        w = data.append
        try:
            w(u'<div id="div-%(divid)s" onclick="%(divonclick)s">' % values)
        except KeyError:
            w(u'<div id="div-%(divid)s">' % values)
        else:
            w(u'<div id="notice-%s" class="notice">%s</div>' % (
                values['divid'], self._cw._('click on the box to cancel the deletion')))
        w(u'<div class="iformBody">')
        eschema = form.edited_entity.e_schema
        if values['removejs']:
            values['removemsg'] = self._cw._('remove-inlined-entity-form')
            w(u'<div class="iformTitle"><span>%(title)s</span> '
              '#<span class="icounter">%(counter)s</span> '
              '[<a href="javascript: %(removejs)s;noop();">%(removemsg)s</a>]</div>'
              % values)
        else:
            w(u'<div class="iformTitle"><span>%(title)s</span> '
              '#<span class="icounter">%(counter)s</span></div>'
              % values)
        # XXX that stinks
        # cleanup values
        for key in ('title', 'removejs', 'removemsg'):
            values.pop(key, None)
        self.render_fields(w, form, values)
        w(u'</div></div>')
        return '\n'.join(data)

    def render_fields(self, w, form, values):
        w(u'<fieldset id="fs-%(divid)s">' % values)
        fields = self._render_hidden_fields(w, form)
        w(u'</fieldset>')
        w(u'<fieldset class="subentity">')
        if fields:
            self._render_fields(fields, w, form)
        self.render_child_forms(w, form, values)
        w(u'</fieldset>')

