"""widget classes for form construction

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from datetime import date
from warnings import warn

from cubicweb.common import tags, uilib
from cubicweb.web import stdmsgs, INTERNAL_FIELD_VALUE


class FieldWidget(object):
    """abstract widget class"""
    # javascript / css files required by the widget
    needs_js = ()
    needs_css = ()
    # automatically set id and tabindex attributes ?
    setdomid = True
    settabindex = True
    # does this widget expect a vocabulary
    vocabulary_widget = False

    def __init__(self, attrs=None, setdomid=None, settabindex=None):
        if attrs is None:
            attrs = {}
        self.attrs = attrs
        if setdomid is not None:
            # override class's default value
            self.setdomid = setdomid
        if settabindex is not None:
            # override class's default value
            self.settabindex = settabindex

    def add_media(self, form):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            form.req.add_js(self.needs_js)
        if self.needs_css:
            form.req.add_css(self.needs_css)

    def render(self, form, field, renderer):
        """render the widget for the given `field` of `form`.
        To override in concrete class
        """
        raise NotImplementedError

    def _render_attrs(self, form, field):
        """return html tag name, attributes and a list of values for the field
        """
        name = form.context[field]['name']
        values = form.context[field]['value']
        if not isinstance(values, (tuple, list)):
            values = (values,)
        attrs = dict(self.attrs)
        if self.setdomid:
            attrs['id'] = form.context[field]['id']
        if self.settabindex and not 'tabindex' in attrs:
            attrs['tabindex'] = form.req.next_tabindex()
        return name, values, attrs


class Input(FieldWidget):
    """abstract widget class for <input> tag based widgets"""
    type = None

    def render(self, form, field, renderer):
        """render the widget for the given `field` of `form`.

        Generate one <input> tag for each field's value
        """
        self.add_media(form)
        name, values, attrs = self._render_attrs(form, field)
        # ensure something is rendered
        if not values:
            values = (INTERNAL_FIELD_VALUE,)
        inputs = [tags.input(name=name, value=value, type=self.type, **attrs)
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

    def render(self, form, field, renderer):
        self.add_media(form)
        name, values, attrs = self._render_attrs(form, field)
        assert len(values) == 1
        id = attrs.pop('id')
        try:
            confirmname = '%s-confirm:%s' % tuple(name.rsplit(':', 1))
        except TypeError:
            confirmname = '%s-confirm' % name
        inputs = [tags.input(name=name, value=values[0], type=self.type, id=id,
                             **attrs),
                  '<br/>',
                  tags.input(name=confirmname, value=values[0], type=self.type,
                             **attrs),
                  '&#160;', tags.span(form.req._('confirm password'),
                                      **{'class': 'emphasis'})]
        return u'\n'.join(inputs)


class PasswordSingleInput(Input):
    """<input type='password'> without a confirmation field"""
    type = 'password'


class FileInput(Input):
    """<input type='file'>"""
    type = 'file'

    def _render_attrs(self, form, field):
        # ignore value which makes no sense here (XXX even on form validation error?)
        name, values, attrs = super(FileInput, self)._render_attrs(form, field)
        return name, ('',), attrs


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

    def render(self, form, field, renderer):
        name, values, attrs = self._render_attrs(form, field)
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
        return tags.textarea(value, name=name, **attrs)


class FCKEditor(TextArea):
    """FCKEditor enabled <textarea>"""
    def __init__(self, *args, **kwargs):
        super(FCKEditor, self).__init__(*args, **kwargs)
        self.attrs['cubicweb:type'] = 'wysiwyg'

    def render(self, form, field, renderer):
        form.req.fckeditor_config()
        return super(FCKEditor, self).render(form, field, renderer)


class Select(FieldWidget):
    """<select>, for field having a specific vocabulary"""
    vocabulary_widget = True

    def __init__(self, attrs=None, multiple=False):
        super(Select, self).__init__(attrs)
        self._multiple = multiple

    def render(self, form, field, renderer):
        name, curvalues, attrs = self._render_attrs(form, field)
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
        return tags.select(name=name, multiple=self._multiple,
                           options=options, **attrs)


class CheckBox(Input):
    """<input type='checkbox'>, for field having a specific vocabulary. One
    input will be generated for each possible value.
    """
    type = 'checkbox'
    vocabulary_widget = True

    def render(self, form, field, renderer):
        name, curvalues, attrs = self._render_attrs(form, field)
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
            tag = tags.input(name=name, type=self.type, value=value, **iattrs)
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
            form.req._('from_interval_start'),
            actual_fields[0].render(form, renderer),
            form.req._('to_interval_end'),
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
        # import here to avoid dependancy from cubicweb-common to simplejson
        _ = req._
        monthnames = [_(mname) for mname in cls.monthnames]
        daynames = [_(dname) for dname in cls.daynames]
        req.html_headers.define_var('MONTHNAMES', monthnames)
        req.html_headers.define_var('DAYNAMES', daynames)

    def render(self, form, field, renderer):
        txtwidget = super(DateTimePicker, self).render(form, field, renderer)
        self.add_localized_infos(form.req)
        cal_button = self._render_calendar_popup(form, field)
        return txtwidget + cal_button

    def _render_calendar_popup(self, form, field):
        value = form.form_field_value(field)
        if not value:
            value = date.today()
        inputid = form.context[field]['id']
        helperid = '%shelper' % inputid
        year, month = value.year, value.month
        return (u"""<a onclick="toggleCalendar('%s', '%s', %s, %s);" class="calhelper">
<img src="%s" title="%s" alt="" /></a><div class="calpopup hidden" id="%s"></div>"""
                % (helperid, inputid, year, month,
                   form.req.external_resource('CALENDAR_ICON'),
                   form.req._('calendar'), helperid) )



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

    def render(self, form, field, renderer):
        self.add_media(form)
        attrs = self._render_attrs(form, field)[-1]
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

    def _render_attrs(self, form, field):
        name, values, attrs = super(AutoCompletionWidget, self)._render_attrs(form, field)
        init_ajax_attributes(attrs, self.wdgtype, self.loadtype)
        # XXX entity form specific
        attrs['cubicweb:dataurl'] = self._get_url(form.edited_entity, field)
        return name, values, attrs

    def _get_url(self, entity, field):
        if self.autocomplete_initfunc is None:
            # XXX for bw compat
            fname = entity.autocomplete_initfuncs[field.name]
        else:
            fname = self.autocomplete_initfunc
        return entity.req.build_url('json', fname=fname, mode='remote',
                                    pageid=entity.req.pageid)


class StaticFileAutoCompletionWidget(AutoCompletionWidget):
    """XXX describe me"""
    wdgtype = 'StaticFileSuggestField'

    def _get_url(self, entity, field):
        if self.autocomplete_initfunc is None:
            # XXX for bw compat
            fname = entity.autocomplete_initfuncs[field.name]
        else:
            fname = self.autocomplete_initfunc
        return entity.req.datadir_url + fname


class RestrictedAutoCompletionWidget(AutoCompletionWidget):
    """XXX describe me"""
    wdgtype = 'RestrictedSuggestField'


class AddComboBoxWidget(Select):
    def _render_attrs(self, form, field):
        name, values, attrs = super(AddComboBoxWidget, self)._render_attrs(form, field)
        init_ajax_attributes(self.attrs, 'AddComboBox')
        # XXX entity form specific
        entity = form.edited_entity
        attrs['cubicweb:etype_to'] = entity.e_schema
        etype_from = entity.e_schema.subject_relation(field.name).objects(entity.e_schema)[0]
        attrs['cubicweb:etype_from'] = etype_from
        return name, values, attrs

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
        self.label = label
        self.name = name
        self.value = ''
        self.onclick = onclick
        self.cwaction = cwaction
        self.attrs.setdefault('klass', 'validateButton')

    def render(self, form, field=None, renderer=None):
        label = form.req._(self.label)
        attrs = self.attrs.copy()
        if self.cwaction:
            assert self.onclick is None
            attrs['onclick'] = "postForm('__action_%s', \'%s\', \'%s\')" % (
                self.cwaction, self.label, form.domid)
        elif self.onclick:
            attrs['onclick'] = self.onclick
        if self.name:
            attrs['name'] = name
            if self.setdomid:
                attrs['id'] = self.name
        if self.settabindex and not 'tabindex' in attrs:
            attrs['tabindex'] = form.req.next_tabindex()
        return tags.input(value=label, type=self.type, **attrs)


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
        label = form.req._(self.label)
        imgsrc = form.req.external_resource(self.imgressource)
        return '<a id="%(domid)s" href="%(href)s">'\
               '<img src="%(imgsrc)s" alt="%(label)s"/>%(label)s</a>' % {
            'label': label, 'imgsrc': imgsrc,
            'domid': self.domid, 'href': self.href}



# XXX EntityLinkComboBoxWidget, [Raw]DynamicComboBoxWidget
