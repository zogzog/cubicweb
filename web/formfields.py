"""field classes for form construction

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from logilab.mtconverter import html_escape
from yams.constraints import SizeConstraint, StaticVocabularyConstraint

from cubicweb.schema import FormatConstraint
from cubicweb.utils import ustrftime
from cubicweb.common import tags, uilib
from cubicweb.web import INTERNAL_FIELD_VALUE
from cubicweb.web.formwidgets import (HiddenInput, TextInput, FileInput, PasswordInput,
                                      TextArea, FCKEditor, Radio, Select,
                                      DateTimePicker) 

class Field(object):
    """field class is introduced to control what's displayed in edition form
    """
    widget = TextInput
    needs_multipart = False
    creation_rank = 0

    def __init__(self, name=None, id=None, label=None,
                 widget=None, required=False, initial=None,
                 choices=None, help=None, eidparam=False, role='subject'):
        self.required = required
        if widget is not None:
            self.widget = widget
        if isinstance(self.widget, type):
            self.widget = self.widget()
        self.name = name
        self.label = label or name
        self.id = id or name
        self.initial = initial
        self.choices = choices
        self.help = help
        self.eidparam = eidparam
        self.role = role
        # global fields ordering in forms
        self.creation_rank = Field.creation_rank
        Field.creation_rank += 1

    def __unicode__(self):
        return u'<%s name=%r label=%r id=%r initial=%r>' % (
            self.__class__.__name__, self.name, self.label,
            self.id, self.initial)

    def __repr__(self):
        return self.__unicode__().encode('utf-8')

    def set_name(self, name):
        assert name
        self.name = name
        if not self.id:
            self.id = name
        if not self.label:
            self.label = name
            
    def is_visible(self):
        return not isinstance(self.widget, HiddenInput)
    
    def actual_fields(self, form):
        yield self
    
    def format_value(self, req, value):
        if isinstance(value, (list, tuple)):
            return [self.format_single_value(req, val) for val in value]
        return self.format_single_value(req, value)
    
    def format_single_value(self, req, value):
        if value is None:
            return u''
        return unicode(value)

    def get_widget(self, form):
        return self.widget
    
    def example_format(self, req):
        return u''

    def render(self, form, renderer):
        return self.get_widget(form).render(form, self)

    def vocabulary(self, form):
        if self.choices is not None:
            return self.choices
        return form.form_field_vocabulary(self)

    
class StringField(Field):
    def __init__(self, max_length=None, **kwargs):
        super(StringField, self).__init__(**kwargs)
        self.max_length = max_length


class TextField(Field):
    widget = TextArea
    def __init__(self, rows=10, cols=80, **kwargs):
        super(TextField, self).__init__(**kwargs)
        self.rows = rows
        self.cols = cols


class RichTextField(TextField):
    widget = None
    def __init__(self, format_field=None, **kwargs):
        super(RichTextField, self).__init__(**kwargs)
        self.format_field = format_field

    def get_widget(self, form):
        if self.widget is None:
            if self.use_fckeditor(form):
                return FCKEditor()
            return TextArea()
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
            if self.use_fckeditor(form):
                # if fckeditor is used and format field isn't explicitly
                # deactivated, we want an hidden field for the format
                widget = HiddenInput()
                choices = None
            else:
                # else we want a format selector
                # XXX compute vocabulary
                widget = Select
                fcstr = FormatConstraint()
                choices = [(req._(fmt), fmt) for fmt in fcstr.vocabulary(req=req)]
            field = StringField(name=self.name + '_format', widget=widget,
                                choices=choices)
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
                        (html_escape(uilib.toggle_action(divid)),
                         form.req._('show advanced fields'),
                         html_escape(form.req.build_url('data/puce_down.png')),
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
            data = form.form_field_value(self, {}, load_bytes=True)
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
        return self.format_value(req, 1.234)


class DateField(StringField):
    format_prop = 'ui.date-format'
    widget = DateTimePicker
    
    def format_single_value(self, req, value):
        return value and ustrftime(value, req.property_value(self.format_prop)) or u''

    def render_example(self, req):
        return self.format_value(req, datetime.now())


class DateTimeField(DateField):
    format_prop = 'ui.datetime-format'


class TimeField(DateField):
    format_prop = 'ui.datetime-format'


class HiddenInitialValueField(Field):
    def __init__(self, visible_field, name):
        super(HiddenInitialValueField, self).__init__(name=name,
                                                      widget=HiddenInput,
                                                      eidparam=True)
        self.visible_field = visible_field
    
                 
class RelationField(Field):
    def __init__(self, **kwargs):
        super(RelationField, self).__init__(**kwargs)

    @staticmethod
    def fromcardinality(card, **kwargs):
        return RelationField(widget=Select(multiple=card in '*+'), **kwargs)
        
    def vocabulary(self, form):
        entity = form.entity
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
        return res + form.form_field_vocabulary(self) + relatedvocab
    
    def format_single_value(self, req, value):
        return value


def stringfield_from_constraints(constraints, **kwargs):
    field = None
    for cstr in constraints:
        if isinstance(cstr, StaticVocabularyConstraint):
            return StringField(widget=Select(vocabulary=cstr.vocabulary),
                               **kwargs)
        if isinstance(cstr, SizeConstraint) and cstr.max is not None:
            if cstr.max > 257:
                rows_cols_from_constraint(cstr, kwargs)
                field = TextField(**kwargs)
            else:
                field = StringField(max_length=cstr.max, **kwargs)
    return field or TextField(**kwargs)


def rows_cols_from_constraint(constraint, kwargs):
    if constraint.max < 513:
        rows, cols = 5, 60
    else:
        rows, cols = 10, 80
    kwargs.setdefault('rows', rows)
    kwargs.setdefault('cols', cols)


def guess_field(eclass, rschema, role='subject', **kwargs):
    """return the most adapated widget to edit the relation
    'subjschema rschema objschema' according to information found in the schema
    """
    fieldclass = None
    eschema = eclass.e_schema
    if role == 'subject':
        targetschema = rschema.objects(eschema)[0]
        card = rschema.rproperty(eschema, targetschema, 'cardinality')[0]
    else:
        targetschema = rschema.subjects(eschema)[0]
        card = rschema.rproperty(targetschema, eschema, 'cardinality')[1]
    kwargs['required'] = card in '1+'
    kwargs['name'] = rschema.type
    if rschema.is_final():
        if rschema in eschema.format_fields:
            return None
        if targetschema == 'Password':
            return StringField(widget=PasswordInput(), **kwargs)
        if eschema.has_metadata(rschema, 'format'):
            constraints = rschema.rproperty(eschema, targetschema, 'constraints')
            for cstr in constraints:
                if isinstance(cstr, StaticVocabularyConstraint):
                    raise Exception('rich text field with static vocabulary')
                if isinstance(cstr, SizeConstraint) and cstr.max is not None:
                    rows_cols_from_constraint(cstr, kwargs)
            return RichTextField(**kwargs)
        fieldclass = FIELDS[targetschema]
        if fieldclass is StringField:
            constraints = rschema.rproperty(eschema, targetschema, 'constraints')
            return stringfield_from_constraints(constraints, **kwargs)
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
