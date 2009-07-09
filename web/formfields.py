"""field classes for form construction

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn
from datetime import datetime

from logilab.mtconverter import xml_escape
from yams.constraints import SizeConstraint, StaticVocabularyConstraint

from cubicweb.schema import FormatConstraint
from cubicweb.utils import ustrftime, compute_cardinality
from cubicweb.common import tags, uilib
from cubicweb.web import INTERNAL_FIELD_VALUE
from cubicweb.web.formwidgets import (
    HiddenInput, TextInput, FileInput, PasswordInput, TextArea, FCKEditor,
    Radio, Select, DateTimePicker)


class Field(object):
    """field class is introduced to control what's displayed in forms. It makes
    the link between something to edit and its display in the form. Actual
    display is handled by a widget associated to the field.

    Attributes
    ----------
    all the attributes described below have sensible default value which may be
    overriden by value given to field's constructor.

    :name:
       name of the field (basestring), should be unique in a form.
    :id:
       dom identifier (default to the same value as `name`), should be unique in
       a form.
    :label:
       label of the field (default to the same value as `name`).
    :help:
       help message about this field.
    :widget:
       widget associated to the field. Each field class has a default widget
       class which may be overriden per instance.
    :required:
       bool flag telling if the field is required or not.
    :initial:
       initial value, used when no value specified by other means.
    :choices:
       static vocabulary for this field. May be a list of values or a list of
       (label, value) tuples if specified.
    :sort:
       bool flag telling if the vocabulary (either static vocabulary specified
       in `choices` or dynamic vocabulary fetched from the form) should be
       sorted on label.
    :internationalizable:
       bool flag telling if the vocabulary labels should be translated using the
       current request language.
    :eidparam:
       bool flag telling if this field is linked to a specific entity
    :role:
       when the field is linked to an entity attribute or relation, tells the
       role of the entity in the relation (eg 'subject' or 'object')

    """
    # default widget associated to this class of fields. May be overriden per
    # instance
    widget = TextInput
    # does this field requires a multipart form
    needs_multipart = False
    # class attribute used for ordering of fields in a form
    __creation_rank = 0

    def __init__(self, name=None, id=None, label=None, help=None,
                 widget=None, required=False, initial=None,
                 choices=None, sort=True, internationalizable=False,
                 eidparam=False, role='subject'):
        self.name = name
        self.id = id or name
        self.label = label or name
        self.help = help
        self.required = required
        self.initial = initial
        self.choices = choices
        self.sort = sort
        self.internationalizable = internationalizable
        self.eidparam = eidparam
        self.role = role
        self.init_widget(widget)
        # ordering number for this field instance
        self.creation_rank = Field.__creation_rank
        Field.__creation_rank += 1

    def __unicode__(self):
        return u'<%s name=%r label=%r id=%r initial=%r visible=%r @%x>' % (
            self.__class__.__name__, self.name, self.label,
            self.id, self.initial, self.is_visible(), id(self))

    def __repr__(self):
        return self.__unicode__().encode('utf-8')

    def init_widget(self, widget):
        if widget is not None:
            self.widget = widget
        elif self.choices and not self.widget.vocabulary_widget:
            self.widget = Select()
        if isinstance(self.widget, type):
            self.widget = self.widget()

    def set_name(self, name):
        """automatically set .id and .label when name is set"""
        assert name
        self.name = name
        if not self.id:
            self.id = name
        if not self.label:
            self.label = name

    def is_visible(self):
        """return true if the field is not an hidden field"""
        return not isinstance(self.widget, HiddenInput)

    def actual_fields(self, form):
        """return actual fields composing this field in case of a compound
        field, usually simply return self
        """
        yield self

    def format_value(self, req, value):
        """return value suitable for display where value may be a list or tuple
        of values
        """
        if isinstance(value, (list, tuple)):
            return [self.format_single_value(req, val) for val in value]
        return self.format_single_value(req, value)

    def format_single_value(self, req, value):
        """return value suitable for display"""
        if value is None or value is False:
            return u''
        if value is True:
            return u'1'
        return unicode(value)

    def get_widget(self, form):
        """return the widget instance associated to this field"""
        return self.widget

    def example_format(self, req):
        """return a sample string describing what can be given as input for this
        field
        """
        return u''

    def render(self, form, renderer):
        """render this field, which is part of form, using the given form
        renderer
        """
        return self.get_widget(form).render(form, self)

    def vocabulary(self, form):
        """return vocabulary for this field. This method will be called by
        widgets which desire it."""
        if self.choices is not None:
            if callable(self.choices):
                try:
                    vocab = self.choices(form=form)
                except TypeError:
                    warn('vocabulary method (eg field.choices) should now take '
                         'the form instance as argument', DeprecationWarning)
                    vocab = self.choices(req=form.req)
            else:
                vocab = self.choices
            if vocab and not isinstance(vocab[0], (list, tuple)):
                vocab = [(x, x) for x in vocab]
        else:
            vocab = form.form_field_vocabulary(self)
        if self.internationalizable:
            vocab = [(form.req._(label), value) for label, value in vocab]
        if self.sort:
            vocab = sorted(vocab)
        return vocab

    def form_init(self, form):
        """method called before by form_build_context to trigger potential field
        initialization requiring the form instance
        """
        pass


class StringField(Field):
    widget = TextArea

    def __init__(self, max_length=None, **kwargs):
        self.max_length = max_length # must be set before super call
        super(StringField, self).__init__(**kwargs)

    def init_widget(self, widget):
        if widget is None:
            if self.choices:
                widget = Select()
            elif self.max_length and self.max_length < 257:
                widget = TextInput()
                widget.attrs.setdefault('size', min(45, self.max_length))
                widget.attrs.setdefault('maxlength', self.max_length)

        super(StringField, self).init_widget(widget)
        if isinstance(self.widget, TextArea):
            self.init_text_area(self.widget)

    def init_text_area(self, widget):
        if self.max_length < 513:
            widget.attrs.setdefault('cols', 60)
            widget.attrs.setdefault('rows', 5)


class RichTextField(StringField):
    widget = None
    def __init__(self, format_field=None, **kwargs):
        super(RichTextField, self).__init__(**kwargs)
        self.format_field = format_field

    def get_widget(self, form):
        if self.widget is None:
            if self.use_fckeditor(form):
                return FCKEditor()
            widget = TextArea()
            self.init_text_area(widget)
            return widget
        return self.widget

    def get_format_field(self, form):
        if self.format_field:
            return self.format_field
        # we have to cache generated field since it's use as key in the
        # context dictionnary
        req = form.req
        try:
            return req.data[self]
        except KeyError:
            fkwargs = {}
            if self.use_fckeditor(form):
                # if fckeditor is used and format field isn't explicitly
                # deactivated, we want an hidden field for the format
                fkwargs['widget'] = HiddenInput()
                fkwargs['initial'] = 'text/html'
            else:
                # else we want a format selector
                fkwargs['widget'] = Select()
                fcstr = FormatConstraint()
                fkwargs['choices'] = fcstr.vocabulary(req=req)
                fkwargs['internationalizable'] = True
                fkwargs['initial'] = lambda f: f.form_field_format(self)
            field = StringField(name=self.name + '_format', **fkwargs)
            req.data[self] = field
            return field

    def actual_fields(self, form):
        yield self
        format_field = self.get_format_field(form)
        if format_field:
            yield format_field

    def use_fckeditor(self, form):
        """return True if fckeditor should be used to edit entity's attribute named
        `attr`, according to user preferences
        """
        if form.req.use_fckeditor():
            return form.form_field_format(self) == 'text/html'
        return False

    def render(self, form, renderer):
        format_field = self.get_format_field(form)
        if format_field:
            # XXX we want both fields to remain vertically aligned
            format_field.widget.attrs['style'] = 'display: block'
            result = format_field.render(form, renderer)
        else:
            result = u''
        return result + self.get_widget(form).render(form, self)


class FileField(StringField):
    widget = FileInput
    needs_multipart = True

    def __init__(self, format_field=None, encoding_field=None, **kwargs):
        super(FileField, self).__init__(**kwargs)
        self.format_field = format_field
        self.encoding_field = encoding_field

    def actual_fields(self, form):
        yield self
        if self.format_field:
            yield self.format_field
        if self.encoding_field:
            yield self.encoding_field

    def render(self, form, renderer):
        wdgs = [self.get_widget(form).render(form, self)]
        if self.format_field or self.encoding_field:
            divid = '%s-advanced' % form.context[self]['name']
            wdgs.append(u'<a href="%s" title="%s"><img src="%s" alt="%s"/></a>' %
                        (xml_escape(uilib.toggle_action(divid)),
                         form.req._('show advanced fields'),
                         xml_escape(form.req.build_url('data/puce_down.png')),
                         form.req._('show advanced fields')))
            wdgs.append(u'<div id="%s" class="hidden">' % divid)
            if self.format_field:
                wdgs.append(self.render_subfield(form, self.format_field, renderer))
            if self.encoding_field:
                wdgs.append(self.render_subfield(form, self.encoding_field, renderer))
            wdgs.append(u'</div>')
        if not self.required and form.context[self]['value']:
            # trick to be able to delete an uploaded file
            wdgs.append(u'<br/>')
            wdgs.append(tags.input(name=u'%s__detach' % form.context[self]['name'],
                                   type=u'checkbox'))
            wdgs.append(form.req._('detach attached file'))
        return u'\n'.join(wdgs)

    def render_subfield(self, form, field, renderer):
        return (renderer.render_label(form, field)
                + field.render(form, renderer)
                + renderer.render_help(form, field)
                + u'<br/>')


class EditableFileField(FileField):
    editable_formats = ('text/plain', 'text/html', 'text/rest')

    def render(self, form, renderer):
        wdgs = [super(EditableFileField, self).render(form, renderer)]
        if form.form_field_format(self) in self.editable_formats:
            data = form.form_field_value(self, load_bytes=True)
            if data:
                encoding = form.form_field_encoding(self)
                try:
                    form.context[self]['value'] = unicode(data.getvalue(), encoding)
                except UnicodeError:
                    pass
                else:
                    if not self.required:
                        msg = form.req._(
                            'You can either submit a new file using the browse button above'
                            ', or choose to remove already uploaded file by checking the '
                            '"detach attached file" check-box, or edit file content online '
                            'with the widget below.')
                    else:
                        msg = form.req._(
                            'You can either submit a new file using the browse button above'
                            ', or edit file content online with the widget below.')
                    wdgs.append(u'<p><b>%s</b></p>' % msg)
                    wdgs.append(TextArea(setdomid=False).render(form, self))
                    # XXX restore form context?
        return '\n'.join(wdgs)


class IntField(Field):
    def __init__(self, min=None, max=None, **kwargs):
        super(IntField, self).__init__(**kwargs)
        self.min = min
        self.max = max
        if isinstance(self.widget, TextInput):
            self.widget.attrs.setdefault('size', 5)
            self.widget.attrs.setdefault('maxlength', 15)


class BooleanField(Field):
    widget = Radio

    def vocabulary(self, form):
        if self.choices:
            return self.choices
        return [(form.req._('yes'), '1'), (form.req._('no'), '')]


class FloatField(IntField):
    def format_single_value(self, req, value):
        formatstr = req.property_value('ui.float-format')
        if value is None:
            return u''
        return formatstr % float(value)

    def render_example(self, req):
        return self.format_single_value(req, 1.234)


class DateField(StringField):
    format_prop = 'ui.date-format'
    widget = DateTimePicker

    def format_single_value(self, req, value):
        return value and ustrftime(value, req.property_value(self.format_prop)) or u''

    def render_example(self, req):
        return self.format_single_value(req, datetime.now())


class DateTimeField(DateField):
    format_prop = 'ui.datetime-format'


class TimeField(DateField):
    format_prop = 'ui.time-format'
    widget = TextInput


class HiddenInitialValueField(Field):
    def __init__(self, visible_field):
        name = 'edit%s-%s' % (visible_field.role[0], visible_field.name)
        super(HiddenInitialValueField, self).__init__(
            name=name, widget=HiddenInput, eidparam=True)
        self.visible_field = visible_field

    def format_single_value(self, req, value):
        return self.visible_field.format_single_value(req, value)


class RelationField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault('sort', False)
        super(RelationField, self).__init__(**kwargs)

    @staticmethod
    def fromcardinality(card, **kwargs):
        kwargs.setdefault('widget', Select(multiple=card in '*+'))
        return RelationField(**kwargs)

    def vocabulary(self, form):
        entity = form.edited_entity
        req = entity.req
        # first see if its specified by __linkto form parameters
        linkedto = entity.linked_to(self.name, self.role)
        if linkedto:
            entities = (req.eid_rset(eid).get_entity(0, 0) for eid in linkedto)
            return [(entity.view('combobox'), entity.eid) for entity in entities]
        # it isn't, check if the entity provides a method to get correct values
        res = []
        if not self.required:
            res.append(('', INTERNAL_FIELD_VALUE))
        # vocabulary doesn't include current values, add them
        if entity.has_eid():
            rset = entity.related(self.name, self.role)
            relatedvocab = [(e.view('combobox'), e.eid) for e in rset.entities()]
        else:
            relatedvocab = []
        vocab = res + form.form_field_vocabulary(self) + relatedvocab
        if self.sort:
            vocab = sorted(vocab)
        return vocab

    def format_single_value(self, req, value):
        return value


def guess_field(eschema, rschema, role='subject', skip_meta_attr=True, **kwargs):
    """return the most adapated widget to edit the relation
    'subjschema rschema objschema' according to information found in the schema
    """
    fieldclass = None
    if role == 'subject':
        targetschema = rschema.objects(eschema)[0]
        card = compute_cardinality(eschema, rschema, role)
        help = rschema.rproperty(eschema, targetschema, 'description')
        if rschema.is_final():
            if rschema.rproperty(eschema, targetschema, 'internationalizable'):
                kwargs.setdefault('internationalizable', True)
            def get_default(form, es=eschema, rs=rschema):
                return es.default(rs)
            kwargs.setdefault('initial', get_default)
    else:
        targetschema = rschema.subjects(eschema)[0]
        card = compute_cardinality(eschema, rschema, role)
        help = rschema.rproperty(targetschema, eschema, 'description')
    kwargs['required'] = card in '1+'
    kwargs['name'] = rschema.type
    kwargs.setdefault('help', help)
    if rschema.is_final():
        if skip_meta_attr and rschema in eschema.meta_attributes():
            return None
        fieldclass = FIELDS[targetschema]
        if fieldclass is StringField:
            if targetschema == 'Password':
                # special case for Password field: specific PasswordInput widget
                kwargs.setdefault('widget', PasswordInput())
                return StringField(**kwargs)
            if eschema.has_metadata(rschema, 'format'):
                # use RichTextField instead of StringField if the attribute has
                # a "format" metadata. But getting information from constraints
                # may be useful anyway...
                constraints = rschema.rproperty(eschema, targetschema, 'constraints')
                for cstr in constraints:
                    if isinstance(cstr, StaticVocabularyConstraint):
                        raise Exception('rich text field with static vocabulary')
                return RichTextField(**kwargs)
            constraints = rschema.rproperty(eschema, targetschema, 'constraints')
            # init StringField parameters according to constraints
            for cstr in constraints:
                if isinstance(cstr, StaticVocabularyConstraint):
                    kwargs.setdefault('choices', cstr.vocabulary)
                    break
            for cstr in constraints:
                if isinstance(cstr, SizeConstraint) and cstr.max is not None:
                    kwargs['max_length'] = cstr.max
            return StringField(**kwargs)
        if fieldclass is FileField:
            for metadata in ('format', 'encoding'):
                metaschema = eschema.has_metadata(rschema, metadata)
                if metaschema is not None:
                    kwargs['%s_field' % metadata] = guess_field(eschema, metaschema,
                                                                skip_meta_attr=False)
        return fieldclass(**kwargs)
    kwargs['role'] = role
    return RelationField.fromcardinality(card, **kwargs)


FIELDS = {
    'Boolean':  BooleanField,
    'Bytes':    FileField,
    'Date':     DateField,
    'Datetime': DateTimeField,
    'Int':      IntField,
    'Float':    FloatField,
    'Decimal':  StringField,
    'Password': StringField,
    'String' :  StringField,
    'Time':     TimeField,
    }
