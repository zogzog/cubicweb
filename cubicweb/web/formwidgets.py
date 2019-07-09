# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
Widgets
~~~~~~~

.. Note::
   A widget is responsible for the display of a field. It may use more than one
   HTML input tags. When the form is posted, a widget is also reponsible to give
   back to the field something it can understand.

   Of course you can not use any widget with any field...

.. autoclass:: cubicweb.web.formwidgets.FieldWidget


HTML <input> based widgets
''''''''''''''''''''''''''

.. autoclass:: cubicweb.web.formwidgets.HiddenInput
.. autoclass:: cubicweb.web.formwidgets.TextInput
.. autoclass:: cubicweb.web.formwidgets.EmailInput
.. autoclass:: cubicweb.web.formwidgets.PasswordSingleInput
.. autoclass:: cubicweb.web.formwidgets.FileInput
.. autoclass:: cubicweb.web.formwidgets.ButtonInput


Other standard HTML widgets
'''''''''''''''''''''''''''

.. autoclass:: cubicweb.web.formwidgets.TextArea
.. autoclass:: cubicweb.web.formwidgets.Select
.. autoclass:: cubicweb.web.formwidgets.CheckBox
.. autoclass:: cubicweb.web.formwidgets.Radio


Date and time widgets
'''''''''''''''''''''

.. autoclass:: cubicweb.web.formwidgets.DateTimePicker
.. autoclass:: cubicweb.web.formwidgets.JQueryDateTimePicker
.. autoclass:: cubicweb.web.formwidgets.JQueryDatePicker
.. autoclass:: cubicweb.web.formwidgets.JQueryTimePicker


Ajax / javascript widgets
'''''''''''''''''''''''''

.. autoclass:: cubicweb.web.formwidgets.FCKEditor
.. autoclass:: cubicweb.web.formwidgets.AjaxWidget
.. autoclass:: cubicweb.web.formwidgets.AutoCompletionWidget
.. autoclass:: cubicweb.web.formwidgets.InOutWidget

.. kill or document StaticFileAutoCompletionWidget
.. kill or document LazyRestrictedAutoCompletionWidget
.. kill or document RestrictedAutoCompletionWidget


Other widgets
'''''''''''''

.. autoclass:: cubicweb.web.formwidgets.PasswordInput
.. autoclass:: cubicweb.web.formwidgets.IntervalWidget
.. autoclass:: cubicweb.web.formwidgets.BitSelect
.. autoclass:: cubicweb.web.formwidgets.HorizontalLayoutWidget
.. autoclass:: cubicweb.web.formwidgets.EditableURLWidget


Form controls
'''''''''''''

Those classes are not proper widget (they are not associated to field) but are
used as form controls. Their API is similar to widgets except that `field`
argument given to :meth:`render` will be `None`.

.. autoclass:: cubicweb.web.formwidgets.Button
.. autoclass:: cubicweb.web.formwidgets.SubmitButton
.. autoclass:: cubicweb.web.formwidgets.ResetButton
.. autoclass:: cubicweb.web.formwidgets.ImgButton
"""


from functools import reduce
from datetime import date

from logilab.mtconverter import xml_escape
from logilab.common.date import todatetime

from cubicweb import tags, uilib
from cubicweb.utils import json_dumps
from cubicweb.web import stdmsgs, INTERNAL_FIELD_VALUE, ProcessFormError


class FieldWidget(object):
    """The abstract base class for widgets.

    **Attributes**

    Here are standard attributes of a widget, that may be set on concrete class
    to override default behaviours:

    :attr:`needs_js`
       list of javascript files needed by the widget.

    :attr:`needs_css`
       list of css files needed by the widget.

    :attr:`setdomid`
       flag telling if HTML DOM identifier should be set on input.

    :attr:`suffix`
       string to use a suffix when generating input, to ease usage as a
       sub-widgets (eg widget used by another widget)

    :attr:`vocabulary_widget`
       flag telling if this widget expect a vocabulary

    Also, widget instances takes as first argument a `attrs` dictionary which
    will be stored in the attribute of the same name. It contains HTML
    attributes that should be set in the widget's input tag (though concrete
    classes may ignore it).

    .. currentmodule:: cubicweb.web.formwidgets

    **Form generation methods**

    .. automethod:: render
    .. automethod:: _render
    .. automethod:: values
    .. automethod:: attributes

    **Post handling methods**

    .. automethod:: process_field_data

    """
    needs_js = ()
    needs_css = ()
    setdomid = True
    suffix = None
    # does this widget expect a vocabulary
    vocabulary_widget = False

    def __init__(self, attrs=None, setdomid=None, suffix=None):
        if attrs is None:
            attrs = {}
        self.attrs = attrs
        if setdomid is not None:
            # override class's default value
            self.setdomid = setdomid
        if suffix is not None:
            self.suffix = suffix

    def add_media(self, form):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            form._cw.add_js(self.needs_js)
        if self.needs_css:
            form._cw.add_css(self.needs_css)

    def render(self, form, field, renderer=None):
        """Called to render the widget for the given `field` in the given
        `form`.  Return a unicode string containing the HTML snippet.

        You will usually prefer to override the :meth:`_render` method so you
        don't have to handle addition of needed javascript / css files.
        """
        self.add_media(form)
        return self._render(form, field, renderer)

    def _render(self, form, field, renderer):
        """This is the method you have to implement in concrete widget classes.
        """
        raise NotImplementedError()

    def format_value(self, form, field, value):
        return field.format_value(form._cw, value)

    def attributes(self, form, field):
        """Return HTML attributes for the widget, automatically setting DOM
        identifier when desired (see :attr:`setdomid` attribute)
        """
        attrs = dict(self.attrs)
        if self.setdomid:
            attrs['id'] = field.dom_id(form, self.suffix)
        if 'placeholder' in attrs:
            attrs['placeholder'] = form._cw._(attrs['placeholder'])
        return attrs

    def values(self, form, field):
        """Return the current *string* values (i.e. for display in an HTML
        string) for the given field. This method returns a list of values since
        it's suitable for all kind of widgets, some of them taking multiple
        values, but you'll get a single value in the list in most cases.

        Those values are searched in:

        1. previously submitted form values if any (on validation error)

        2. req.form (specified using request parameters)

        3. extra form values given to form.render call (specified the code
           generating the form)

        4. field's typed value (returned by its
           :meth:`~cubicweb.web.formfields.Field.typed_value` method)

        Values found in 1. and 2. are expected te be already some 'display
        value' (eg a string) while those found in 3. and 4. are expected to be
        correctly typed value.

        3 and 4 are handle by the :meth:`typed_value` method to ease reuse in
        concrete classes.
        """
        values = None
        if not field.ignore_req_params:
            qname = field.input_name(form, self.suffix)
            # value from a previous post that has raised a validation error
            if qname in form.form_previous_values:
                values = form.form_previous_values[qname]
            # value specified using form parameters
            elif qname in form._cw.form:
                values = form._cw.form[qname]
            elif field.name != qname and field.name in form._cw.form:
                # XXX compat: accept attr=value in req.form to specify value of
                # attr-subject
                values = form._cw.form[field.name]
        if values is None:
            values = self.typed_value(form, field)
            if values != INTERNAL_FIELD_VALUE:
                values = self.format_value(form, field, values)
        if not isinstance(values, (tuple, list)):
            values = (values,)
        return values

    def typed_value(self, form, field):
        """return field's *typed* value specified in:
        3. extra form values given to render()
        4. field's typed value
        """
        qname = field.input_name(form)
        for key in ((field, form), qname):
            try:
                return form.formvalues[key]
            except KeyError:
                continue
        if field.name != qname and field.name in form.formvalues:
            return form.formvalues[field.name]
        return field.typed_value(form)

    def process_field_data(self, form, field):
        """Return process posted value(s) for widget and return something
        understandable by the associated `field`. That value may be correctly
        typed or a string that the field may parse.
        """
        posted = form._cw.form
        val = posted.get(field.input_name(form, self.suffix))
        if isinstance(val, str):
            val = val.strip()
        return val

    # XXX deprecates
    def values_and_attributes(self, form, field):
        return self.values(form, field), self.attributes(form, field)


class Input(FieldWidget):
    """abstract widget class for <input> tag based widgets"""
    type = None

    def _render(self, form, field, renderer):
        """render the widget for the given `field` of `form`.

        Generate one <input> tag for each field's value
        """
        values, attrs = self.values_and_attributes(form, field)
        # ensure something is rendered
        if not values:
            values = (INTERNAL_FIELD_VALUE,)
        inputs = [tags.input(name=field.input_name(form, self.suffix),
                             type=self.type, value=value, **attrs)
                  for value in values]
        return u'\n'.join(inputs)


# basic html widgets ###########################################################

class TextInput(Input):
    """Simple <input type='text'>, will return a unicode string."""
    type = 'text'


class EmailInput(Input):
    """Simple <input type='email'>, will return a unicode string."""
    type = 'email'


class PasswordSingleInput(Input):
    """Simple <input type='password'>, will return a utf-8 encoded string.

    You may prefer using the :class:`~cubicweb.web.formwidgets.PasswordInput`
    widget which handles password confirmation.
    """
    type = 'password'

    def process_field_data(self, form, field):
        value = super(PasswordSingleInput, self).process_field_data(form, field)
        if value is not None:
            return value.encode('utf-8')
        return value


class PasswordInput(Input):
    """<input type='password'> and a confirmation input. Form processing will
    fail if password and confirmation differs, else it will return the password
    as a utf-8 encoded string.
    """
    type = 'password'

    def _render(self, form, field, renderer):
        assert self.suffix is None, 'suffix not supported'
        values, attrs = self.values_and_attributes(form, field)
        assert len(values) == 1
        domid = attrs.pop('id')
        inputs = [tags.input(name=field.input_name(form),
                             value=values[0], type=self.type, id=domid, **attrs),
                  '<br/>',
                  tags.input(name=field.input_name(form, '-confirm'),
                             value=values[0], type=self.type, **attrs),
                  '&#160;', tags.span(form._cw._('confirm password'),
                                      **{'class': 'emphasis'})]
        return u'\n'.join(inputs)

    def process_field_data(self, form, field):
        passwd1 = super(PasswordInput, self).process_field_data(form, field)
        passwd2 = form._cw.form.get(field.input_name(form, '-confirm'))
        if passwd1 == passwd2:
            if passwd1 is None:
                return None
            return passwd1.encode('utf-8')
        raise ProcessFormError(form._cw._("password and confirmation don't match"))


class FileInput(Input):
    """Simple <input type='file'>, will return a tuple (name, stream) where
    name is the posted file name and stream a file like object containing the
    posted file data.
    """
    type = 'file'

    def values(self, form, field):
        # ignore value which makes no sense here (XXX even on form validation error?)
        return ('',)


class HiddenInput(Input):
    """Simple <input type='hidden'> for hidden value, will return a unicode
    string.
    """
    type = 'hidden'
    setdomid = False  # by default, don't set id attribute on hidden input


class ButtonInput(Input):
    """Simple <input type='button'>, will return a unicode string.

    If you want a global form button, look at the :class:`Button`,
    :class:`SubmitButton`, :class:`ResetButton` and :class:`ImgButton` below.
    """
    type = 'button'


class TextArea(FieldWidget):
    """Simple <textarea>, will return a unicode string."""
    _minrows = 2
    _maxrows = 15
    _columns = 80

    def _render(self, form, field, renderer):
        values, attrs = self.values_and_attributes(form, field)
        attrs.setdefault('onkeyup', 'autogrow(this)')
        if not values:
            value = u''
        elif len(values) == 1:
            value = values[0]
        else:
            raise ValueError('a textarea is not supposed to be multivalued')
        lines = value.splitlines()
        linecount = len(lines)
        for line in lines:
            linecount += len(line) // self._columns
        attrs.setdefault('cols', self._columns)
        attrs.setdefault('rows', min(self._maxrows, linecount + self._minrows))
        return tags.textarea(value, name=field.input_name(form, self.suffix),
                             **attrs)


class FCKEditor(TextArea):
    """FCKEditor enabled <textarea>, will return a unicode string containing
    HTML formated text.
    """
    def __init__(self, *args, **kwargs):
        super(FCKEditor, self).__init__(*args, **kwargs)
        self.attrs['cubicweb:type'] = 'wysiwyg'

    def _render(self, form, field, renderer):
        form._cw.fckeditor_config()
        return super(FCKEditor, self)._render(form, field, renderer)


class Select(FieldWidget):
    """Simple <select>, for field having a specific vocabulary. Will return
    a unicode string, or a list of unicode strings.
    """
    vocabulary_widget = True
    default_size = 10

    def __init__(self, attrs=None, multiple=False, **kwargs):
        super(Select, self).__init__(attrs, **kwargs)
        self._multiple = multiple

    def _render(self, form, field, renderer):
        curvalues, attrs = self.values_and_attributes(form, field)
        options = []
        optgroup_opened = False
        vocab = field.vocabulary(form)
        for option in vocab:
            try:
                label, value, oattrs = option
            except ValueError:
                label, value = option
                oattrs = {}
            if value is None:
                # handle separator
                if optgroup_opened:
                    options.append(u'</optgroup>')
                oattrs.setdefault('label', label or '')
                options.append(u'<optgroup %s>' % uilib.sgml_attributes(oattrs))
                optgroup_opened = True
            elif self.value_selected(value, curvalues):
                options.append(tags.option(label, value=value,
                                           selected='selected', **oattrs))
            else:
                options.append(tags.option(label, value=value, **oattrs))
        if optgroup_opened:
            options.append(u'</optgroup>')
        if 'size' not in attrs:
            if self._multiple:
                size = str(min(self.default_size, len(vocab) or 1))
            else:
                size = u'1'
            attrs['size'] = size
        return tags.select(name=field.input_name(form, self.suffix),
                           multiple=self._multiple, options=options, **attrs)

    def value_selected(self, value, curvalues):
        return value in curvalues


class InOutWidget(Select):
    needs_js = ('cubicweb.widgets.js', )
    default_size = 10
    template = """
<table id="%(widgetid)s">
  <tr>
    <td>%(inoutinput)s</td>
    <td><div style="margin-bottom:3px">%(addinput)s</div>
        <div>%(removeinput)s</div>
    </td>
    <td>%(resinput)s</td>
  </tr>
</table>
"""
    add_button = ('<input type="button" class="wdgButton cwinoutadd" '
                  'value="&gt;&gt;" size="10" />')
    remove_button = ('<input type="button" class="wdgButton cwinoutremove" '
                     'value="&lt;&lt;" size="10" />')

    def __init__(self, *args, **kwargs):
        super(InOutWidget, self).__init__(*args, **kwargs)
        self._multiple = True

    def render_select(self, form, field, name, selected=False):
        values, attrs = self.values_and_attributes(form, field)
        options = []
        inputs = []
        for option in field.vocabulary(form):
            try:
                label, value, _oattrs = option
            except ValueError:
                label, value = option
            if selected:
                # add values
                if value in values:
                    options.append(tags.option(label, value=value))
                    # add hidden inputs
                    inputs.append(tags.input(value=value,
                                             name=field.dom_id(form),
                                             type="hidden"))
            else:
                if value not in values:
                    options.append(tags.option(label, value=value))
        if 'size' not in attrs:
            attrs['size'] = self.default_size
        if 'id' in attrs:
            attrs.pop('id')
        return tags.select(name=name, multiple=self._multiple, id=name,
                           options=options, **attrs) + '\n'.join(inputs)

    def _render(self, form, field, renderer):
        domid = field.dom_id(form)
        jsnodes = {'widgetid': domid,
                   'from': 'from_' + domid,
                   'to': 'to_' + domid}
        form._cw.add_onload(u'$(cw.jqNode("%s")).cwinoutwidget("%s", "%s");'
                            % (jsnodes['widgetid'], jsnodes['from'], jsnodes['to']))
        field.required = True
        return (self.template %
                {'widgetid': jsnodes['widgetid'],
                 # helpinfo select tag
                 'inoutinput': self.render_select(form, field, jsnodes['from']),
                 # select tag with resultats
                 'resinput': self.render_select(form, field, jsnodes['to'], selected=True),
                 'addinput': self.add_button % jsnodes,
                 'removeinput': self.remove_button % jsnodes
                 })


class BitSelect(Select):
    """Select widget for IntField using a vocabulary with bit masks as values.

    See also :class:`~cubicweb.web.facet.BitFieldFacet`.
    """
    def __init__(self, attrs=None, multiple=True, **kwargs):
        super(BitSelect, self).__init__(attrs, multiple=multiple, **kwargs)

    def value_selected(self, value, curvalues):
        mask = reduce(lambda x, y: int(x) | int(y), curvalues, 0)
        return int(value) & mask

    def process_field_data(self, form, field):
        """Return process posted value(s) for widget and return something
        understandable by the associated `field`. That value may be correctly
        typed or a string that the field may parse.
        """
        val = super(BitSelect, self).process_field_data(form, field)
        if isinstance(val, list):
            val = reduce(lambda x, y: int(x) | int(y), val, 0)
        elif val:
            val = int(val)
        else:
            val = 0
        return val


class CheckBox(Input):
    """Simple <input type='checkbox'>, for field having a specific
    vocabulary. One input will be generated for each possible value.

    You can specify separator using the `separator` constructor argument, by
    default <br/> is used.
    """
    type = 'checkbox'
    default_separator = u'<br/>\n'
    vocabulary_widget = True

    def __init__(self, attrs=None, separator=None, **kwargs):
        super(CheckBox, self).__init__(attrs, **kwargs)
        self.separator = separator or self.default_separator

    def _render(self, form, field, renderer):
        curvalues, attrs = self.values_and_attributes(form, field)
        domid = attrs.pop('id', None)
        sep = self.separator
        options = []
        for i, option in enumerate(field.vocabulary(form)):
            try:
                label, value, oattrs = option
            except ValueError:
                label, value = option
                oattrs = {}
            iattrs = attrs.copy()
            iattrs.update(oattrs)
            if i == 0 and domid is not None:
                iattrs.setdefault('id', domid)
            if value in curvalues:
                iattrs['checked'] = u'checked'
            tag = tags.input(name=field.input_name(form, self.suffix),
                             type=self.type, value=value, **iattrs)
            options.append(u'<label>%s&#160;%s</label>' % (tag, xml_escape(label)))
        return sep.join(options)


class Radio(CheckBox):
    """Simle <input type='radio'>, for field having a specific vocabulary. One
    input will be generated for each possible value.

    You can specify separator using the `separator` constructor argument, by
    default <br/> is used.
    """
    type = 'radio'


# javascript widgets ###########################################################

class DateTimePicker(TextInput):
    """<input type='text'> + javascript date/time picker for date or datetime
    fields. Will return the date or datetime as a unicode string.
    """
    monthnames = ('january', 'february', 'march', 'april',
                  'may', 'june', 'july', 'august',
                  'september', 'october', 'november', 'december')
    daynames = ('monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday')

    needs_js = ('cubicweb.calendar.js',)
    needs_css = ('cubicweb.calendar_popup.css',)

    @classmethod
    def add_localized_infos(cls, req):
        """inserts JS variables defining localized months and days"""
        _ = req._
        monthnames = [_(mname) for mname in cls.monthnames]
        daynames = [_(dname) for dname in cls.daynames]
        req.html_headers.define_var('MONTHNAMES', monthnames)
        req.html_headers.define_var('DAYNAMES', daynames)

    def _render(self, form, field, renderer):
        txtwidget = super(DateTimePicker, self)._render(form, field, renderer)
        self.add_localized_infos(form._cw)
        cal_button = self._render_calendar_popup(form, field)
        return txtwidget + cal_button

    def _render_calendar_popup(self, form, field):
        value = field.typed_value(form)
        if not value:
            value = date.today()
        inputid = field.dom_id(form)
        helperid = '%shelper' % inputid
        year, month = value.year, value.month
        return (u"""<a onclick="toggleCalendar('%s', '%s', %s, %s);" class="calhelper">
<img src="%s" title="%s" alt="" /></a><div class="calpopup hidden" id="%s"></div>"""
                % (helperid, inputid, year, month,
                   form._cw.uiprops['CALENDAR_ICON'],
                   form._cw._('calendar'), helperid))


class JQueryDatePicker(FieldWidget):
    """Use jquery.ui.datepicker to define a date picker. Will return the date as
    a unicode string.

    You can couple DatePickers by using the min_of and/or max_of parameters.
    The DatePicker identified by the value of min_of(/max_of) will force the user to
    choose a date anterior(/posterior) to this DatePicker.

    example:

    start and end are two JQueryDatePicker and start must always be before end::

        affk.set_field_kwargs(etype, 'start_date', widget=JQueryDatePicker(min_of='end_date'))
        affk.set_field_kwargs(etype, 'end_date', widget=JQueryDatePicker(max_of='start_date'))

    That way, on change of end(/start) value a new max(/min) will be set for start(/end)
    The invalid dates will be gray colored in the datepicker
    """
    needs_js = ('jquery.ui.js', )
    needs_css = ('jquery.ui.css',)
    default_size = 10

    def __init__(self, datestr=None, min_of=None, max_of=None, **kwargs):
        super(JQueryDatePicker, self).__init__(**kwargs)
        self.min_of = min_of
        self.max_of = max_of
        self.value = datestr

    def attributes(self, form, field):
        form._cw.add_js('cubicweb.widgets.js')
        attrs = super(JQueryDatePicker, self).attributes(form, field)
        if self.max_of:
            attrs['data-max-of'] = '%s-subject:%s' % (self.max_of, form.edited_entity.eid)
        if self.min_of:
            attrs['data-min-of'] = '%s-subject:%s' % (self.min_of, form.edited_entity.eid)
        return attrs

    def _render(self, form, field, renderer):
        req = form._cw
        if req.lang != 'en':
            req.add_js('jquery.ui.datepicker-%s.js' % req.lang)
        domid = field.dom_id(form, self.suffix)
        # XXX find a way to understand every format
        fmt = req.property_value('ui.date-format')
        picker_fmt = fmt.replace('%Y', 'yy').replace('%m', 'mm').replace('%d', 'dd')
        max_date = min_date = None
        if self.min_of:
            current = getattr(form.edited_entity, self.min_of)
            if current is not None:
                max_date = current.strftime(fmt)
        if self.max_of:
            current = getattr(form.edited_entity, self.max_of)
            if current is not None:
                min_date = current.strftime(fmt)
        req.add_onload(u'renderJQueryDatePicker("%s", "%s", "%s", %s, %s);'
                       % (domid, req.uiprops['CALENDAR_ICON'], picker_fmt, json_dumps(min_date),
                          json_dumps(max_date)))
        return self._render_input(form, field)

    def _render_input(self, form, field):
        if self.value is None:
            value = self.values(form, field)[0]
        else:
            value = self.value
        attrs = self.attributes(form, field)
        attrs.setdefault('size', str(self.default_size))
        return tags.input(name=field.input_name(form, self.suffix),
                          value=value, type='text', **attrs)


class JQueryTimePicker(JQueryDatePicker):
    """Use jquery.timePicker to define a time picker. Will return the time as a
    unicode string.
    """
    needs_js = ('jquery.timePicker.js',)
    needs_css = ('jquery.timepicker.css',)
    default_size = 5

    def __init__(self, timestr=None, timesteps=30, separator=u':', **kwargs):
        super(JQueryTimePicker, self).__init__(timestr, **kwargs)
        self.timesteps = timesteps
        self.separator = separator

    def _render(self, form, field, renderer):
        domid = field.dom_id(form, self.suffix)
        form._cw.add_onload(u'cw.jqNode("%s").timePicker({step: %s, separator: "%s"})' % (
            domid, self.timesteps, self.separator))
        return self._render_input(form, field)


class JQueryDateTimePicker(FieldWidget):
    """Compound widget using :class:`JQueryDatePicker` and
    :class:`JQueryTimePicker` widgets to define a date and time picker. Will
    return the date and time as python datetime instance.
    """
    def __init__(self, initialtime=None, timesteps=15, separator=u':', **kwargs):
        super(JQueryDateTimePicker, self).__init__(**kwargs)
        self.initialtime = initialtime
        self.timesteps = timesteps
        self.separator = separator

    def _render(self, form, field, renderer):
        """render the widget for the given `field` of `form`.

        Generate one <input> tag for each field's value
        """
        req = form._cw
        dateqname = field.input_name(form, 'date')
        timeqname = field.input_name(form, 'time')
        if dateqname in form.form_previous_values:
            datestr = form.form_previous_values[dateqname]
            timestr = form.form_previous_values[timeqname]
        else:
            datestr = timestr = u''
            if field.name in req.form:
                value = req.parse_datetime(req.form[field.name])
            else:
                value = self.typed_value(form, field)
            if value:
                datestr = req.format_date(value)
                timestr = req.format_time(value)
            elif self.initialtime:
                timestr = req.format_time(self.initialtime)
        datepicker = JQueryDatePicker(datestr=datestr, suffix='date')
        timepicker = JQueryTimePicker(timestr=timestr, timesteps=self.timesteps,
                                      separator=self.separator, suffix='time')
        return u'<div id="%s">%s%s</div>' % (field.dom_id(form),
                                             datepicker.render(form, field, renderer),
                                             timepicker.render(form, field, renderer))

    def process_field_data(self, form, field):
        req = form._cw
        datestr = req.form.get(field.input_name(form, 'date'))
        if datestr:
            datestr = datestr.strip()
        if not datestr:
            return None
        try:
            date = todatetime(req.parse_datetime(datestr, 'Date'))
        except ValueError as exc:
            raise ProcessFormError(str(exc))
        timestr = req.form.get(field.input_name(form, 'time'))
        if timestr:
            timestr = timestr.strip()
        if not timestr:
            return date
        try:
            time = req.parse_datetime(timestr, 'Time')
        except ValueError as exc:
            raise ProcessFormError(str(exc))
        return date.replace(hour=time.hour, minute=time.minute, second=time.second)


# ajax widgets ################################################################

def init_ajax_attributes(attrs, wdgtype, loadtype=u'auto'):
    try:
        attrs['class'] += u' widget'
    except KeyError:
        attrs['class'] = u'widget'
    attrs.setdefault('cubicweb:wdgtype', wdgtype)
    attrs.setdefault('cubicweb:loadtype', loadtype)


class AjaxWidget(FieldWidget):
    """Simple <div> based ajax widget, requiring a `wdgtype` argument telling
    which javascript widget should be used.
    """
    def __init__(self, wdgtype, inputid=None, **kwargs):
        super(AjaxWidget, self).__init__(**kwargs)
        init_ajax_attributes(self.attrs, wdgtype)
        if inputid is not None:
            self.attrs['cubicweb:inputid'] = inputid

    def _render(self, form, field, renderer):
        attrs = self.values_and_attributes(form, field)[-1]
        return tags.div(**attrs)


class AutoCompletionWidget(TextInput):
    """<input type='text'> based ajax widget, taking a `autocomplete_initfunc`
    argument which should specify the name of a method of the json
    controller. This method is expected to return allowed values for the input,
    that the widget will use to propose matching values as you type.
    """
    needs_js = ('cubicweb.widgets.js', 'jquery.ui.js')
    needs_css = ('jquery.ui.css',)
    default_settings = {}

    def __init__(self, *args, **kwargs):
        self.autocomplete_settings = kwargs.pop('autocomplete_settings',
                                                self.default_settings)
        self.autocomplete_initfunc = kwargs.pop('autocomplete_initfunc')
        super(AutoCompletionWidget, self).__init__(*args, **kwargs)

    def values(self, form, field):
        values = super(AutoCompletionWidget, self).values(form, field)
        if not values:
            values = ('',)
        return values

    def _render(self, form, field, renderer):
        entity = form.edited_entity
        domid = field.dom_id(form).replace(':', r'\\:')
        if callable(self.autocomplete_initfunc):
            data = self.autocomplete_initfunc(form, field)
        else:
            data = xml_escape(self._get_url(entity, field))
        form._cw.add_onload(u'$("#%s").cwautocomplete(%s, %s);'
                            % (domid, json_dumps(data),
                               json_dumps(self.autocomplete_settings)))
        return super(AutoCompletionWidget, self)._render(form, field, renderer)

    def _get_url(self, entity, field):
        fname = self.autocomplete_initfunc
        return entity._cw.build_url('ajax', fname=fname, mode='remote',
                                    pageid=entity._cw.pageid)


class StaticFileAutoCompletionWidget(AutoCompletionWidget):
    """XXX describe me"""
    wdgtype = 'StaticFileSuggestField'

    def _get_url(self, entity, field):
        return entity._cw.data_url(self.autocomplete_initfunc)


class RestrictedAutoCompletionWidget(AutoCompletionWidget):
    """XXX describe me"""
    default_settings = {'mustMatch': True}


class LazyRestrictedAutoCompletionWidget(RestrictedAutoCompletionWidget):
    """remote autocomplete """

    def values_and_attributes(self, form, field):
        """override values_and_attributes to handle initial displayed values"""
        values, attrs = super(LazyRestrictedAutoCompletionWidget, self).values_and_attributes(
            form, field)
        assert len(values) == 1, "multiple selection is not supported yet by LazyWidget"
        if not values[0]:
            values = form.cw_extra_kwargs.get(field.name, '')
            if not isinstance(values, (tuple, list)):
                values = (values,)
        try:
            values = list(values)
            values[0] = int(values[0])
            attrs['cubicweb:initialvalue'] = values[0]
            values = (self.display_value_for(form, values[0]),)
        except (TypeError, ValueError):
            pass
        return values, attrs

    def display_value_for(self, form, value):
        entity = form._cw.entity_from_eid(value)
        return entity.view('combobox')


# more widgets #################################################################

class IntervalWidget(FieldWidget):
    """Custom widget to display an interval composed by 2 fields. This widget is
    expected to be used with a :class:`CompoundField` containing the two actual
    fields.

    Exemple usage::

      class MyForm(FieldsForm):
         price = CompoundField(fields=(IntField(name='minprice'),
                                       IntField(name='maxprice')),
                               label=_('price'),
                               widget=IntervalWidget())
    """
    def _render(self, form, field, renderer):
        actual_fields = field.fields
        assert len(actual_fields) == 2
        return u'<div>%s %s %s %s</div>' % (
            form._cw._('from_interval_start'),
            actual_fields[0].render(form, renderer),
            form._cw._('to_interval_end'),
            actual_fields[1].render(form, renderer),
        )


class HorizontalLayoutWidget(FieldWidget):
    """Custom widget to display a set of fields grouped together horizontally in
    a form. See `IntervalWidget` for example usage.
    """
    def _render(self, form, field, renderer):
        if self.attrs.get('display_label', True):
            subst = self.attrs.get('label_input_substitution', '%(label)s %(input)s')
            fields = [subst % {'label': renderer.render_label(form, f),
                               'input': f.render(form, renderer)}
                      for f in field.subfields(form)]
        else:
            fields = [f.render(form, renderer) for f in field.subfields(form)]
        return u'<div>%s</div>' % ' '.join(fields)


class EditableURLWidget(FieldWidget):
    """Custom widget to edit separatly a URL path / query string (used by
    default for the `path` attribute of `Bookmark` entities).

    It deals with url quoting nicely so that the user edit the unquoted value.
    """

    def _render(self, form, field, renderer):
        assert self.suffix is None, 'not supported'
        req = form._cw
        pathqname = field.input_name(form, 'path')
        fqsqname = field.input_name(form, 'fqs')  # formatted query string
        if pathqname in form.form_previous_values:
            path = form.form_previous_values[pathqname]
            fqs = form.form_previous_values[fqsqname]
        else:
            if field.name in req.form:
                value = req.form[field.name]
            else:
                value = self.typed_value(form, field)
            if value:
                try:
                    path, qs = value.split('?', 1)
                except ValueError:
                    path = value
                    qs = ''
            else:
                path = qs = ''
            fqs = u'\n'.join(u'%s=%s' % (k, v) for k, v in req.url_parse_qsl(qs))
        attrs = dict(self.attrs)
        if self.setdomid:
            attrs['id'] = field.dom_id(form)
        # ensure something is rendered
        inputs = [u'<table><tr><th>',
                  req._('i18n_bookmark_url_path'),
                  u'</th><td>',
                  tags.input(name=pathqname, type='string', value=path, **attrs),
                  u'</td></tr><tr><th>',
                  req._('i18n_bookmark_url_fqs'),
                  u'</th><td>']
        if self.setdomid:
            attrs['id'] = field.dom_id(form, 'fqs')
        attrs.setdefault('cols', 60)
        attrs.setdefault('onkeyup', 'autogrow(this)')
        inputs += [tags.textarea(fqs, name=fqsqname, **attrs),
                   u'</td></tr></table>']
        # surrounding div necessary for proper error localization
        return u'<div id="%s">%s</div>' % (
            field.dom_id(form), u'\n'.join(inputs))

    def process_field_data(self, form, field):
        req = form._cw
        values = {}
        path = req.form.get(field.input_name(form, 'path'))
        if isinstance(path, str):
            path = path.strip()
        if path is None:
            path = u''
        fqs = req.form.get(field.input_name(form, 'fqs'))
        if isinstance(fqs, str):
            fqs = fqs.strip() or None
            if fqs:
                for i, line in enumerate(fqs.split('\n')):
                    line = line.strip()
                    if line:
                        try:
                            key, val = line.split('=', 1)
                        except ValueError:
                            msg = req._("wrong query parameter line %s") % (i + 1)
                            raise ProcessFormError(msg)
                        # value will be url quoted by build_url_params
                        values.setdefault(key, []).append(val)
        if not values:
            return path
        return u'%s?%s' % (path, req.build_url_params(**values))


# form controls ######################################################################

class Button(Input):
    """Simple <input type='button'>, base class for global form buttons.

    Note that `label` is a msgid which will be translated at form generation
    time, you should not give an already translated string.
    """
    type = 'button'
    css_class = 'validateButton'

    def __init__(self, label=stdmsgs.BUTTON_OK, attrs=None,
                 setdomid=None,
                 name='', value='', onclick=None, cwaction=None):
        super(Button, self).__init__(attrs, setdomid)
        if isinstance(label, tuple):
            self.label = label[0]
            self.icon = label[1]
        else:
            self.label = label
            self.icon = None
        self.name = name
        self.value = ''
        self.onclick = onclick
        self.cwaction = cwaction

    def render(self, form, field=None, renderer=None):
        label = form._cw._(self.label)
        attrs = self.attrs.copy()
        attrs.setdefault('class', self.css_class)
        if self.cwaction:
            assert self.onclick is None
            attrs['onclick'] = "postForm('__action_%s', \'%s\', \'%s\')" % (
                self.cwaction, self.label, form.domid)
        elif self.onclick:
            attrs['onclick'] = self.onclick
        if self.name:
            attrs['name'] = self.name
            if self.setdomid:
                attrs['id'] = self.name
        if self.icon:
            img = tags.img(src=form._cw.uiprops[self.icon], alt=self.icon)
        else:
            img = u''
        return tags.button(img + xml_escape(label), escapecontent=False,
                           value=label, type=self.type, **attrs)


class SubmitButton(Button):
    """Simple <input type='submit'>, main button to submit a form"""
    type = 'submit'


class ResetButton(Button):
    """Simple <input type='reset'>, main button to reset a form. You usually
    don't want to use this.
    """
    type = 'reset'


class ImgButton(object):
    """Simple <img> wrapped into a <a> tag with href triggering something (usually a
    javascript call).
    """
    def __init__(self, domid, href, label, imgressource):
        self.domid = domid
        self.href = href
        self.imgressource = imgressource
        self.label = label

    def render(self, form, field=None, renderer=None):
        label = form._cw._(self.label)
        imgsrc = form._cw.uiprops[self.imgressource]
        return '<a id="%(domid)s" href="%(href)s">'\
               '<img src="%(imgsrc)s" alt="%(label)s"/>%(label)s</a>' % {
                   'label': label, 'imgsrc': imgsrc,
                   'domid': self.domid, 'href': self.href}
