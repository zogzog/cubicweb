"""widget classes for form construction

:organization: Logilab
:copyright: 2009-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from datetime import date
from warnings import warn

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

from cubicweb import tags, uilib, utils
from cubicweb.web import stdmsgs, INTERNAL_FIELD_VALUE, ProcessFormError

class FieldWidget(object):
    """abstract widget class"""
    # javascript / css files required by the widget
    needs_js = ()
    needs_css = ()
    # automatically set id and tabindex attributes ?
    setdomid = True
    settabindex = True
    # to ease usage as a sub-widgets (eg widget used by another widget)
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
        self.add_media(form)
        return self._render(form, field, renderer)

    def _render(self, form, field, renderer):
        raise NotImplementedError()

    def typed_value(self, form, field):
        """return field's *typed* value specified in:
        3. extra form values given to render()
        4. field's typed value
        """
        qname = field.input_name(form)
        for key in (field, qname):
            try:
                return form.formvalues[key]
            except KeyError:
                continue
        if field.name != qname and field.name in form.formvalues:
            return form.formvalues[field.name]
        return field.typed_value(form)

    def format_value(self, form, field, value):
        return field.format_value(form._cw, value)

    def values_and_attributes(self, form, field):
        """found field's *string* value in:
        1. previously submitted form values if any (eg on validation error)
        2. req.form
        3. extra form values given to render()
        4. field's typed value

        values found in 1. and 2. are expected te be already some 'display'
        value while those found in 3. and 4. are expected to be correctly typed.

        3 and 4 are handle by the .typed_value(form, field) method
        """
        attrs = dict(self.attrs)
        if self.setdomid:
            attrs['id'] = field.dom_id(form, self.suffix)
        if self.settabindex and not 'tabindex' in attrs:
            attrs['tabindex'] = form._cw.next_tabindex()
        return self.values(form, field), attrs

    def values(self, form, field):
        qname = field.input_name(form, self.suffix)
        if qname in form.form_previous_values:
            values = form.form_previous_values[qname]
        elif qname in form._cw.form:
            values = form._cw.form[qname]
        elif field.name != qname and field.name in form._cw.form:
            # compat: accept attr=value in req.form to specify value of attr-subject
            values = form._cw.form[field.name]
        else:
            values = self.typed_value(form, field)
            if values != INTERNAL_FIELD_VALUE:
                values = self.format_value(form, field, values)
        if not isinstance(values, (tuple, list)):
            values = (values,)
        return values

    def process_field_data(self, form, field):
        posted = form._cw.form
        val = posted.get(field.input_name(form, self.suffix))
        if isinstance(val, basestring):
            val = val.strip()
        return val

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
    """<input type='text'>"""
    type = 'text'


class PasswordInput(Input):
    """<input type='password'> and its confirmation field (using
    <field's name>-confirm as name)
    """
    type = 'password'

    def _render(self, form, field, renderer):
        assert self.suffix is None, 'suffix not supported'
        values, attrs = self.values_and_attributes(form, field)
        assert len(values) == 1
        id = attrs.pop('id')
        inputs = [tags.input(name=field.input_name(form),
                             value=values[0], type=self.type, id=id, **attrs),
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


class PasswordSingleInput(Input):
    """<input type='password'> without a confirmation field"""
    type = 'password'

    def process_field_data(self, form, field):
        value = super(PasswordSingleInput, self).process_field_data(form, field)
        if value is not None:
            return value.encode('utf-8')
        return value


class FileInput(Input):
    """<input type='file'>"""
    type = 'file'

    def values_and_attributes(self, form, field):
        # ignore value which makes no sense here (XXX even on form validation error?)
        values, attrs = super(FileInput, self).values_and_attributes(form, field)
        return ('',), attrs


class HiddenInput(Input):
    """<input type='hidden'>"""
    type = 'hidden'
    setdomid = False # by default, don't set id attribute on hidden input
    settabindex = False


class ButtonInput(Input):
    """<input type='button'>

    if you want a global form button, look at the Button, SubmitButton,
    ResetButton and ImgButton classes below.
    """
    type = 'button'


class TextArea(FieldWidget):
    """<textarea>"""

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
    """FCKEditor enabled <textarea>"""
    def __init__(self, *args, **kwargs):
        super(FCKEditor, self).__init__(*args, **kwargs)
        self.attrs['cubicweb:type'] = 'wysiwyg'

    def _render(self, form, field, renderer):
        form._cw.fckeditor_config()
        return super(FCKEditor, self)._render(form, field, renderer)


class Select(FieldWidget):
    """<select>, for field having a specific vocabulary"""
    vocabulary_widget = True

    def __init__(self, attrs=None, multiple=False):
        super(Select, self).__init__(attrs)
        self._multiple = multiple

    def render(self, form, field, renderer):
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
    """<input type='checkbox'>, for field having a specific vocabulary. One
    input will be generated for each possible value.
    """
    type = 'checkbox'
    vocabulary_widget = True

    def render(self, form, field, renderer):
        curvalues, attrs = self.values_and_attributes(form, field)
        domid = attrs.pop('id', None)
        sep = attrs.pop('separator', u'<br/>\n')
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
            options.append(tag + label)
        return sep.join(options)


class Radio(CheckBox):
    """<input type='radio'>, for field having a specific vocabulary. One
    input will be generated for each possible value.
    """
    type = 'radio'


# compound widgets #############################################################

class IntervalWidget(FieldWidget):
    """custom widget to display an interval composed by 2 fields. This widget
    is expected to be used with a CompoundField containing the two actual
    fields.

    Exemple usage::

from uicfg import autoform_field, autoform_section
autoform_field.tag_attribute(('Concert', 'minprice'),
                              CompoundField(fields=(IntField(name='minprice'),
                                                    IntField(name='maxprice')),
                                            label=_('price'),
                                            widget=IntervalWidget()
                                            ))
# we've to hide the other field manually for now
autoform_section.tag_attribute(('Concert', 'maxprice'), 'generated')
    """
    def render(self, form, field, renderer):
        actual_fields = field.fields
        assert len(actual_fields) == 2
        return u'<div>%s %s %s %s</div>' % (
            form._cw._('from_interval_start'),
            actual_fields[0].render(form, renderer),
            form._cw._('to_interval_end'),
            actual_fields[1].render(form, renderer),
            )


class HorizontalLayoutWidget(FieldWidget):
    """custom widget to display a set of fields grouped together horizontally
    in a form. See `IntervalWidget` for example usage.
    """
    def render(self, form, field, renderer):
        if self.attrs.get('display_label', True):
            subst = self.attrs.get('label_input_substitution', '%(label)s %(input)s')
            fields = [subst % {'label': renderer.render_label(form, f),
                              'input': f.render(form, renderer)}
                      for f in field.subfields(form)]
        else:
            fields = [f.render(form, renderer) for f in field.subfields(form)]
        return u'<div>%s</div>' % ' '.join(fields)


# javascript widgets ###########################################################

class DateTimePicker(TextInput):
    """<input type='text' + javascript date/time picker for date or datetime
    fields
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
        # import here to avoid dependancy from cubicweb to simplejson
        _ = req._
        monthnames = [_(mname) for mname in cls.monthnames]
        daynames = [_(dname) for dname in cls.daynames]
        req.html_headers.define_var('MONTHNAMES', monthnames)
        req.html_headers.define_var('DAYNAMES', daynames)

    def render(self, form, field, renderer):
        txtwidget = super(DateTimePicker, self).render(form, field, renderer)
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
    """use jquery.ui.datepicker to define a date time picker"""
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
    """use jquery.timePicker.js to define a js time picker"""
    needs_js = ('jquery.timePicker.js',)
    needs_css = ('jquery.timepicker.css',)

    def __init__(self, timestr=None, timesteps=30, **kwargs):
        super(JQueryTimePicker, self).__init__(**kwargs)
        self.timestr = timestr
        self.timesteps = timesteps

    def _render(self, form, field, renderer):
        req = form._cw
        domid = field.dom_id(form, self.suffix)
        req.add_onload(u'jqNode("%s").timePicker({selectedTime: "%s", step: %s})' % (
            domid, self.timestr, self.timesteps))
        if self.timestr is None:
            value = self.values(form, field)[0]
        else:
            value = self.timestr
        return tags.input(id=domid, name=domid, value=value,
                          type='text', size='5')


class JQueryDateTimePicker(FieldWidget):
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
                                            datepicker.render(form, field),
                                            timepicker.render(form, field))

    def process_field_data(self, form, field):
        req = form._cw
        datestr = req.form.get(field.input_name(form, 'date')).strip() or None
        timestr = req.form.get(field.input_name(form, 'time')).strip() or None
        if datestr is None:
            return None
        date = utils.todatetime(req.parse_datetime(datestr, 'Date'))
        if timestr is None:
            return date
        time = req.parse_datetime(timestr, 'Time')
        return date.replace(hour=time.hour, minute=time.minute, second=time.second)


# ajax widgets ################################################################

def init_ajax_attributes(attrs, wdgtype, loadtype=u'auto'):
    try:
        attrs['klass'] += u' widget'
    except KeyError:
        attrs['klass'] = u'widget'
    attrs.setdefault('cubicweb:wdgtype', wdgtype)
    attrs.setdefault('cubicweb:loadtype', loadtype)


class AjaxWidget(FieldWidget):
    """simple <div> based ajax widget"""
    def __init__(self, wdgtype, inputid=None, **kwargs):
        super(AjaxWidget, self).__init__(**kwargs)
        init_ajax_attributes(self.attrs, wdgtype)
        if inputid is not None:
            self.attrs['cubicweb:inputid'] = inputid

    def _render(self, form, field, renderer):
        attrs = self.values_and_attributes(form, field)[-1]
        return tags.div(**attrs)


class AutoCompletionWidget(TextInput):
    """ajax widget for StringField, proposing matching existing values as you
    type.
    """
    needs_js = ('cubicweb.widgets.js', 'jquery.autocomplete.js')
    needs_css = ('jquery.autocomplete.css',)
    wdgtype = 'SuggestField'
    loadtype = 'auto'

    def __init__(self, *args, **kwargs):
        try:
            self.autocomplete_initfunc = kwargs.pop('autocomplete_initfunc')
        except KeyError:
            warn('use autocomplete_initfunc argument of %s constructor '
                 'instead of relying on autocomplete_initfuncs dictionary on '
                 'the entity class' % self.__class__.__name__,
                 DeprecationWarning)
            self.autocomplete_initfunc = None
        super(AutoCompletionWidget, self).__init__(*args, **kwargs)

    def values_and_attributes(self, form, field):
        values, attrs = super(AutoCompletionWidget, self).values_and_attributes(form, field)
        init_ajax_attributes(attrs, self.wdgtype, self.loadtype)
        # XXX entity form specific
        attrs['cubicweb:dataurl'] = self._get_url(form.edited_entity, field)
        if not values:
            values = ('',)
        return values, attrs

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


class AddComboBoxWidget(Select):
    def values_and_attributes(self, form, field):
        values, attrs = super(AddComboBoxWidget, self).values_and_attributes(form, field)
        init_ajax_attributes(self.attrs, 'AddComboBox')
        # XXX entity form specific
        entity = form.edited_entity
        attrs['cubicweb:etype_to'] = entity.e_schema
        etype_from = entity.e_schema.subjrels[field.name].objects(entity.e_schema)[0]
        attrs['cubicweb:etype_from'] = etype_from
        return values, attrs

    def render(self, form, field, renderer):
        return super(AddComboBoxWidget, self).render(form, field, renderer) + u'''
<div id="newvalue">
  <input type="text" id="newopt" />
  <a href="javascript:noop()" id="add_newopt">&#160;</a></div>
'''

# buttons ######################################################################

class Button(Input):
    """<input type='button'>, base class for global form buttons

    note label is a msgid which will be translated at form generation time, you
    should not give an already translated string.
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
        self.attrs.setdefault('klass', 'validateButton')

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
    """<input type='submit'>, main button to submit a form"""
    type = 'submit'


class ResetButton(Button):
    """<input type='reset'>, main button to reset a form.
    You usually don't want this.
    """
    type = 'reset'


class ImgButton(object):
    """<img> wrapped into a <a> tag with href triggering something (usually a
    javascript call)

    note label is a msgid which will be translated at form generation time, you
    should not give an already translated string.
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


# more widgets #################################################################

class EditableURLWidget(FieldWidget):
    """custom widget to edit separatly an url path / query string (used by
    default for Bookmark.path for instance), dealing with url quoting nicely
    (eg user edit the unquoted value).
    """

    def _render(self, form, field, renderer):
        """render the widget for the given `field` of `form`.

        Generate one <input> tag for each field's value
        """
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
            try:
                path, qs = value.split('?', 1)
            except ValueError:
                path = value
                qs = ''
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
        attrs.setdefault('onkeyup', 'autogrow(this)')
        inputs += [tags.textarea(fqs, name=fqsqname, **attrs),
                   u'</td></tr></table>']
        # surrounding div necessary for proper error localization
        return u'<div id="%s">%s%s</div>' % (
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
