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

.. kill or document AddComboBoxWidget
.. kill or document StaticFileAutoCompletionWidget
.. kill or document LazyRestrictedAutoCompletionWidget
.. kill or document RestrictedAutoCompletionWidget

Other widgets
'''''''''''''
.. autoclass:: cubicweb.web.formwidgets.PasswordInput
.. autoclass:: cubicweb.web.formwidgets.IntervalWidget
.. autoclass:: cubicweb.web.formwidgets.HorizontalLayoutWidget
.. autoclass:: cubicweb.web.formwidgets.EditableURLWidget

Form controls
'''''''''''''
Those classes are not proper widget (they are not associated to
field) but are used as form controls. Their API is similar
to widgets except that `field` argument given to :meth:`render`
will be `None`.

.. autoclass:: cubicweb.web.formwidgets.Button
.. autoclass:: cubicweb.web.formwidgets.SubmitButton
.. autoclass:: cubicweb.web.formwidgets.ResetButton
.. autoclass:: cubicweb.web.formwidgets.ImgButton
"""
__docformat__ = "restructuredtext en"

from datetime import date
from warnings import warn

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated
from logilab.common.date import todatetime

from cubicweb import tags, uilib
from cubicweb.web import stdmsgs, INTERNAL_FIELD_VALUE, ProcessFormError


class FieldWidget(object):
    """The abstract base class for widgets.

    **Attributes**

    Here are standard attributes of a widget, that may be set on concret
    class to override default behaviours:

    :attr:`needs_js`
       list of javascript files needed by the widget.
    :attr:`needs_css`
       list of css files needed by the widget.
    :attr:`setdomid`
       flag telling if HTML DOM identifier should be set on input.
    :attr:`settabindex`
       flag telling if HTML tabindex attribute of inputs should be set.
    :attr:`suffix`
       string to use a suffix when generating input, to ease usage as a
       sub-widgets (eg widget used by another widget)
    :attr:`vocabulary_widget`
       flag telling if this widget expect a vocabulary

    Also, widget instances takes as first argument a `attrs` dictionary which
    will be stored in the attribute of the same name. It contains HTML
    attributes that should be set in the widget's input tag (though concret
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
    settabindex = True
    suffix = None
    # does this widget expect a vocabulary
    vocabulary_widget = False

    def __init__(self, attrs=None, setdomid=None, settabindex=None, suffix=None):
        if attrs is None:
            attrs = {}
        self.attrs = attrs
        if setdomid is not None:
            # override class's default value
            self.setdomid = setdomid
        if settabindex is not None:
            # override class's default value
            self.settabindex = settabindex
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
        """This is the method you have to implement in concret widget classes.
        """
        raise NotImplementedError()

    def format_value(self, form, field, value):
        return field.format_value(form._cw, value)

    def attributes(self, form, field):
        """Return HTML attributes for the widget, automatically setting DOM
        identifier and tabindex when desired (see :attr:`setdomid` and
        :attr:`settabindex` attributes)
        """
        attrs = dict(self.attrs)
        if self.setdomid:
            attrs['id'] = field.dom_id(form, self.suffix)
        if self.settabindex and not 'tabindex' in attrs:
            attrs['tabindex'] = form._cw.next_tabindex()
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
        concret classes.
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
        if isinstance(val, basestring):
            val = val.strip()
        return val

    # XXX deprecates
    def values_and_attributes(self, form, field):
        return self.values(form, field), self.attributes(form, field)

    @deprecated('[3.6] use values_and_attributes')
    def _render_attrs(self, form, field):
        """return html tag name, attributes and a list of values for the field
        """
        values, attrs = self.values_and_attributes(form, field)
        return field.input_name(form, self.suffix), values, attrs


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
    """Simple <input type='text'>, will return an unicode string."""
    type = 'text'


class PasswordSingleInput(Input):
    """Simple <input type='password'>, will return an utf-8 encoded string.

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
    as an utf-8 encoded string.
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
    """Simple <input type='hidden'> for hidden value, will return an unicode
    string.
    """
    type = 'hidden'
    setdomid = False # by default, don't set id attribute on hidden input
    settabindex = False


class ButtonInput(Input):
    """Simple <input type='button'>, will return an unicode string.

    If you want a global form button, look at the :class:`Button`,
    :class:`SubmitButton`, :class:`ResetButton` and :class:`ImgButton` below.
    """
    type = 'button'


class TextArea(FieldWidget):
    """Simple <textarea>, will return an unicode string."""

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
            linecount += len(line) / 80
        attrs.setdefault('cols', 80)
        attrs.setdefault('rows', min(15, linecount + 2))
        return tags.textarea(value, name=field.input_name(form, self.suffix),
                             **attrs)


class FCKEditor(TextArea):
    """FCKEditor enabled <textarea>, will return an unicode string containing
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
    an unicode string, or a list of unicode strings.
    """
    vocabulary_widget = True

    def __init__(self, attrs=None, multiple=False, **kwargs):
        super(Select, self).__init__(attrs, **kwargs)
        self._multiple = multiple

    def _render(self, form, field, renderer):
        curvalues, attrs = self.values_and_attributes(form, field)
        if not 'size' in attrs:
            attrs['size'] = self._multiple and '5' or '1'
        options = []
        optgroup_opened = False
        for option in field.vocabulary(form):
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
            elif value in curvalues:
                options.append(tags.option(label, value=value,
                                           selected='selected', **oattrs))
            else:
                options.append(tags.option(label, value=value, **oattrs))
        if optgroup_opened:
            options.append(u'</optgroup>')
        return tags.select(name=field.input_name(form, self.suffix),
                           multiple=self._multiple, options=options, **attrs)


class CheckBox(Input):
    """Simple <input type='checkbox'>, for field having a specific
    vocabulary. One input will be generated for each possible value.

    You can specify separator using the `separator` constructor argument, by
    default <br/> is used.
    """
    type = 'checkbox'
    vocabulary_widget = True

    def __init__(self, attrs=None, separator=u'<br/>\n', **kwargs):
        super(CheckBox, self).__init__(attrs, **kwargs)
        self.separator = separator

    def _render(self, form, field, renderer):
        curvalues, attrs = self.values_and_attributes(form, field)
        domid = attrs.pop('id', None)
        # XXX turn this as initializer argument
        try:
            sep = attrs.pop('separator')
            warn('[3.8] separator should be specified using initializer argument',
                 DeprecationWarning)
        except KeyError:
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
            options.append(u'%s&#160;%s' % (tag, label))
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
    fields. Will return the date or datetime as an unicode string.
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
                   form._cw.external_resource('CALENDAR_ICON'),
                   form._cw._('calendar'), helperid) )


class JQueryDatePicker(FieldWidget):
    """Use jquery.ui.datepicker to define a date picker. Will return the date as
    an unicode string.
    """
    needs_js = ('jquery.ui.js', )
    needs_css = ('jquery.ui.css',)

    def __init__(self, datestr=None, **kwargs):
        super(JQueryDatePicker, self).__init__(**kwargs)
        self.datestr = datestr

    def _render(self, form, field, renderer):
        req = form._cw
        domid = field.dom_id(form, self.suffix)
        # XXX find a way to understand every format
        fmt = req.property_value('ui.date-format')
        fmt = fmt.replace('%Y', 'yy').replace('%m', 'mm').replace('%d', 'dd')
        req.add_onload(u'jqNode("%s").datepicker('
                       '{buttonImage: "%s", dateFormat: "%s", firstDay: 1,'
                       ' showOn: "button", buttonImageOnly: true})' % (
                           domid, req.external_resource('CALENDAR_ICON'), fmt))
        if self.datestr is None:
            value = self.values(form, field)[0]
        else:
            value = self.datestr
        return tags.input(id=domid, name=domid, value=value,
                          type='text', size='10')


class JQueryTimePicker(FieldWidget):
    """Use jquery.timePicker to define a time picker. Will return the time as an
    unicode string.
    """
    needs_js = ('jquery.timePicker.js',)
    needs_css = ('jquery.timepicker.css',)

    def __init__(self, timestr=None, timesteps=30, separator=u':', **kwargs):
        super(JQueryTimePicker, self).__init__(**kwargs)
        self.timestr = timestr
        self.timesteps = timesteps
        self.separator = separator

    def _render(self, form, field, renderer):
        req = form._cw
        domid = field.dom_id(form, self.suffix)
        req.add_onload(u'jqNode("%s").timePicker({selectedTime: "%s", step: %s, separator: "%s"})' % (
            domid, self.timestr, self.timesteps, self.separator))
        if self.timestr is None:
            value = self.values(form, field)[0]
        else:
            value = self.timestr
        return tags.input(id=domid, name=domid, value=value,
                          type='text', size='5')


class JQueryDateTimePicker(FieldWidget):
    """Compound widget using :class:`JQueryDatePicker` and
    :class:`JQueryTimePicker` widgets to define a date and time picker. Will
    return the date and time as python datetime instance.
    """
    def __init__(self, initialtime=None, timesteps=15, **kwargs):
        super(JQueryDateTimePicker, self).__init__(**kwargs)
        self.initialtime = initialtime
        self.timesteps = timesteps

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
                                      suffix='time')
        return u'<div id="%s">%s%s</div>' % (field.dom_id(form),
                                            datepicker.render(form, field, renderer),
                                            timepicker.render(form, field, renderer))

    def process_field_data(self, form, field):
        req = form._cw
        datestr = req.form.get(field.input_name(form, 'date')).strip() or None
        timestr = req.form.get(field.input_name(form, 'time')).strip() or None
        if datestr is None:
            return None
        date = todatetime(req.parse_datetime(datestr, 'Date'))
        if timestr is None:
            return date
        time = req.parse_datetime(timestr, 'Time')
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
    needs_js = ('cubicweb.widgets.js', 'jquery.autocomplete.js')
    needs_css = ('jquery.autocomplete.css',)
    wdgtype = 'SuggestField'
    loadtype = 'auto'

    def __init__(self, *args, **kwargs):
        try:
            self.autocomplete_initfunc = kwargs.pop('autocomplete_initfunc')
        except KeyError:
            warn('[3.6] use autocomplete_initfunc argument of %s constructor '
                 'instead of relying on autocomplete_initfuncs dictionary on '
                 'the entity class' % self.__class__.__name__,
                 DeprecationWarning)
            self.autocomplete_initfunc = None
        super(AutoCompletionWidget, self).__init__(*args, **kwargs)

    def values(self, form, field):
        values = super(AutoCompletionWidget, self).values(form, field)
        if not values:
            values = ('',)
        return values

    def attributes(self, form, field):
        attrs = super(AutoCompletionWidget, self).attributes(form, field)
        init_ajax_attributes(attrs, self.wdgtype, self.loadtype)
        # XXX entity form specific
        attrs['cubicweb:dataurl'] = self._get_url(form.edited_entity, field)
        return attrs

    def _get_url(self, entity, field):
        if self.autocomplete_initfunc is None:
            # XXX for bw compat
            fname = entity.autocomplete_initfuncs[field.name]
        else:
            fname = self.autocomplete_initfunc
        return entity._cw.build_url('json', fname=fname, mode='remote',
                                    pageid=entity._cw.pageid)


class StaticFileAutoCompletionWidget(AutoCompletionWidget):
    """XXX describe me"""
    wdgtype = 'StaticFileSuggestField'

    def _get_url(self, entity, field):
        if self.autocomplete_initfunc is None:
            # XXX for bw compat
            fname = entity.autocomplete_initfuncs[field.name]
        else:
            fname = self.autocomplete_initfunc
        return entity._cw.datadir_url + fname


class RestrictedAutoCompletionWidget(AutoCompletionWidget):
    """XXX describe me"""
    wdgtype = 'RestrictedSuggestField'


class LazyRestrictedAutoCompletionWidget(RestrictedAutoCompletionWidget):
    """remote autocomplete """
    wdgtype = 'LazySuggestField'

    def values_and_attributes(self, form, field):
        """override values_and_attributes to handle initial displayed values"""
        values, attrs = super(LazyRestrictedAutoCompletionWidget, self).values_and_attributes(form, field)
        assert len(values) == 1, "multiple selection is not supported yet by LazyWidget"
        if not values[0]:
            values = form.cw_extra_kwargs.get(field.name,'')
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


class AddComboBoxWidget(Select):
    def attributes(self, form, field):
        attrs = super(AddComboBoxWidget, self).attributes(form, field)
        init_ajax_attributes(attrs, 'AddComboBox')
        # XXX entity form specific
        entity = form.edited_entity
        attrs['cubicweb:etype_to'] = entity.e_schema
        etype_from = entity.e_schema.subjrels[field.name].objects(entity.e_schema)[0]
        attrs['cubicweb:etype_from'] = etype_from
        return attrs

    def _render(self, form, field, renderer):
        return super(AddComboBoxWidget, self)._render(form, field, renderer) + u'''
<div id="newvalue">
  <input type="text" id="newopt" />
  <a href="javascript:noop()" id="add_newopt">&#160;</a></div>
'''

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
    """Custom widget to edit separatly an url path / query string (used by
    default for the `path` attribute of `Bookmark` entities).

    It deals with url quoting nicely so that the user edit the unquoted value.
    """

    def _render(self, form, field, renderer):
        assert self.suffix is None, 'not supported'
        req = form._cw
        pathqname = field.input_name(form, 'path')
        fqsqname = field.input_name(form, 'fqs') # formatted query string
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
        if self.settabindex and not 'tabindex' in attrs:
            attrs['tabindex'] = req.next_tabindex()
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
        if self.settabindex:
            attrs['tabindex'] = req.next_tabindex()
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
        if isinstance(path, basestring):
            path = path.strip() or None
        fqs = req.form.get(field.input_name(form, 'fqs'))
        if isinstance(fqs, basestring):
            fqs = fqs.strip() or None
            if fqs:
                for i, line in enumerate(fqs.split('\n')):
                    line = line.strip()
                    if line:
                        try:
                            key, val = line.split('=', 1)
                        except ValueError:
                            raise ProcessFormError(req._("wrong query parameter line %s") % (i+1))
                        # value will be url quoted by build_url_params
                        values.setdefault(key.encode(req.encoding), []).append(val)
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
    def __init__(self, label=stdmsgs.BUTTON_OK, attrs=None,
                 setdomid=None, settabindex=None,
                 name='', value='', onclick=None, cwaction=None):
        super(Button, self).__init__(attrs, setdomid, settabindex)
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
        self.attrs.setdefault('class', 'validateButton')

    def render(self, form, field=None, renderer=None):
        label = form._cw._(self.label)
        attrs = self.attrs.copy()
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
        if self.settabindex and not 'tabindex' in attrs:
            attrs['tabindex'] = form._cw.next_tabindex()
        if self.icon:
            img = tags.img(src=form._cw.external_resource(self.icon), alt=self.icon)
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
        imgsrc = form._cw.external_resource(self.imgressource)
        return '<a id="%(domid)s" href="%(href)s">'\
               '<img src="%(imgsrc)s" alt="%(label)s"/>%(label)s</a>' % {
            'label': label, 'imgsrc': imgsrc,
            'domid': self.domid, 'href': self.href}

