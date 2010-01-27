"""field classes for form construction

:organization: Logilab
:copyright: 2009-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn
from datetime import datetime

from logilab.mtconverter import xml_escape
from logilab.common.decorators import cached

from yams.schema import KNOWN_METAATTRIBUTES
from yams.constraints import (SizeConstraint, StaticVocabularyConstraint,
                              FormatConstraint)

from cubicweb import Binary, tags, uilib, utils
from cubicweb.web import INTERNAL_FIELD_VALUE, ProcessFormError, eid_param, \
     formwidgets as fw


class UnmodifiedField(Exception):
    """raise this when a field has not actually been edited and you want to skip
    it
    """


def vocab_sort(vocab):
    """sort vocabulary, considering option groups"""
    result = []
    partresult = []
    for label, value in vocab:
        if value is None: # opt group start
            if partresult:
                result += sorted(partresult)
                partresult = []
            result.append( (label, value) )
        else:
            partresult.append( (label, value) )
    result += sorted(partresult)
    return result

_MARKER = object()

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
    :value:
       field's value, used when no value specified by other means. XXX explain
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
    :fieldset:
       optional fieldset to which this field belongs to
    :order:
       key used by automatic forms to sort fields

    """
    # default widget associated to this class of fields. May be overriden per
    # instance
    widget = fw.TextInput
    # does this field requires a multipart form
    needs_multipart = False
    # class attribute used for ordering of fields in a form
    __creation_rank = 0

    eidparam = False
    role = None
    id = None
    help = None
    required = False
    choices = None
    sort = True
    internationalizable = False
    fieldset = None
    order = None
    value = _MARKER

    def __init__(self, name=None, label=_MARKER, widget=None, **kwargs):
        for key, val in kwargs.items():
            if key == 'initial':
                warn('[3.6] use value instead of initial', DeprecationWarning,
                     stacklevel=3)
                key = 'value'
            assert hasattr(self.__class__, key) and not key[0] == '_', key
            setattr(self, key, val)
        self.name = name
        if label is _MARKER:
            label = name or _MARKER
        self.label = label
        # has to be done after other attributes initialization
        self.init_widget(widget)
        # ordering number for this field instance
        self.creation_rank = Field.__creation_rank
        Field.__creation_rank += 1

    def __unicode__(self):
        return u'<%s name=%r eidparam=%s role=%r id=%r value=%r visible=%r @%x>' % (
            self.__class__.__name__, self.name, self.eidparam, self.role,
            self.id, self.value, self.is_visible(), id(self))

    def __repr__(self):
        return self.__unicode__().encode('utf-8')

    def init_widget(self, widget):
        if widget is not None:
            self.widget = widget
        elif self.choices and not self.widget.vocabulary_widget:
            self.widget = fw.Select()
        if isinstance(self.widget, type):
            self.widget = self.widget()

    def set_name(self, name):
        """automatically set .label when name is set"""
        assert name
        self.name = name
        if self.label is _MARKER:
            self.label = name

    def is_visible(self):
        """return true if the field is not an hidden field"""
        return not isinstance(self.widget, fw.HiddenInput)

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

    # cached is necessary else we get some pb on entity creation : entity.eid is
    # modified from creation mark (eg 'X') to its actual eid (eg 123), and then
    # `field.input_name()` won't return the right key anymore if not cached
    # (first call to input_name done *before* eventual eid affectation).
    @cached
    def input_name(self, form, suffix=None):
        """return 'qualified name' for this field"""
        name = self.role_name()
        if suffix is not None:
            name += suffix
        if self.eidparam:
            return eid_param(name, form.edited_entity.eid)
        return name

    def role_name(self):
        """return <field.name>-<field.role> if role is specified, else field.name"""
        if self.role is not None:
            return '%s-%s' % (self.name, self.role)
        return self.name

    def dom_id(self, form, suffix=None):
        """return an html dom identifier for this field"""
        id = self.id or self.role_name()
        if suffix is not None:
            id += suffix
        if self.eidparam:
            return eid_param(id, form.edited_entity.eid)
        return id

    def typed_value(self, form, load_bytes=False):
        if self.eidparam and self.role is not None:
            entity = form.edited_entity
            if form._cw.vreg.schema.rschema(self.name).final:
                if entity.has_eid() or self.name in entity:
                    return getattr(entity, self.name)
            elif entity.has_eid() or entity.relation_cached(self.name, self.role):
                return [r[0] for r in entity.related(self.name, self.role)]
        return self.initial_typed_value(form, load_bytes)

    def initial_typed_value(self, form, load_bytes):
        if self.value is not _MARKER:
            if callable(self.value):
                return self.value(form)
            return self.value
        formattr = '%s_%s_default' % (self.role, self.name)
        if hasattr(form, formattr):
            warn('[3.6] %s.%s deprecated, use field.value' % (
                form.__class__.__name__, formattr), DeprecationWarning)
            return getattr(form, formattr)()
        if self.eidparam and self.role is not None:
            if form._cw.vreg.schema.rschema(self.name).final:
                return form.edited_entity.e_schema.default(self.name)
            return ()
        return None

    def example_format(self, req):
        """return a sample string describing what can be given as input for this
        field
        """
        return u''

    def render(self, form, renderer):
        """render this field, which is part of form, using the given form
        renderer
        """
        widget = self.get_widget(form)
        return widget.render(form, self, renderer)

    def vocabulary(self, form):
        """return vocabulary for this field. This method will be called by
        widgets which requires a vocabulary.
        """
        assert self.choices is not None
        if callable(self.choices):
            try:
                if getattr(self.choices, 'im_self', None) is self:
                    vocab = self.choices(form=form)
                else:
                    vocab = self.choices(form=form, field=self)
            except TypeError:
                warn('[3.6]  %s: choices should now take '
                     'the form and field as named arguments' % self,
                     DeprecationWarning)
                try:
                    vocab = self.choices(form=form)
                except TypeError:
                    warn('[3.3]  %s: choices should now take '
                         'the form and field as named arguments' % self,
                         DeprecationWarning)
                    vocab = self.choices(req=form._cw)
        else:
            vocab = self.choices
        if vocab and not isinstance(vocab[0], (list, tuple)):
            vocab = [(x, x) for x in vocab]
        if self.internationalizable:
            # the short-cirtcuit 'and' boolean operator is used here to permit
            # a valid empty string in vocabulary without attempting to translate
            # it by gettext (which can lead to weird strings display)
            vocab = [(label and form._cw._(label), value) for label, value in vocab]
        if self.sort:
            vocab = vocab_sort(vocab)
        return vocab

    def format(self, form):
        """return MIME type used for the given (text or bytes) field"""
        if self.eidparam and self.role == 'subject':
            entity = form.edited_entity
            if entity.e_schema.has_metadata(self.name, 'format') and (
                entity.has_eid() or '%s_format' % self.name in entity):
                return form.edited_entity.attr_metadata(self.name, 'format')
        return form._cw.property_value('ui.default-text-format')

    def encoding(self, form):
        """return encoding used for the given (text) field"""
        if self.eidparam:
            entity = form.edited_entity
            if entity.e_schema.has_metadata(self.name, 'encoding') and (
                entity.has_eid() or '%s_encoding' % self.name in entity):
                return form.edited_entity.attr_metadata(self.name, 'encoding')
        return form._cw.encoding

    def form_init(self, form):
        """method called before by build_context to trigger potential field
        initialization requiring the form instance
        """
        pass

    def has_been_modified(self, form):
        if self.is_visible():
            # fields not corresponding to an entity attribute / relations
            # are considered modified
            if not self.eidparam or not self.role or not form.edited_entity.has_eid():
                return True # XXX
            try:
                if self.role == 'subject':
                    previous_value = getattr(form.edited_entity, self.name)
                else:
                    previous_value = getattr(form.edited_entity,
                                             'reverse_%s' % self.name)
            except AttributeError:
                # fields with eidparam=True but not corresponding to an actual
                # attribute or relation
                return True
            # if it's a non final relation, we need the eids
            if isinstance(previous_value, tuple):
                # widget should return a set of untyped eids
                previous_value = set(unicode(e.eid) for e in previous_value)
            try:
                new_value = self.process_form_value(form)
            except ProcessFormError:
                return True
            except UnmodifiedField:
                return False
            if form.edited_entity.has_eid() and previous_value == new_value:
                return False # not modified
            return True
        return False

    def process_form_value(self, form):
        """process posted form and return correctly typed value"""
        try:
            return form.formvalues[self]
        except KeyError:
            value = form.formvalues[self] = self._process_form_value(form)
            return value

    def _process_form_value(self, form):
        widget = self.get_widget(form)
        value = widget.process_field_data(form, self)
        return self._ensure_correctly_typed(form, value)

    def _ensure_correctly_typed(self, form, value):
        """widget might to return date as a correctly formatted string or as
        correctly typed objects, but process_for_value must return a typed value.
        Override this method to type the value if necessary
        """
        return value

    def process_posted(self, form):
        for field in self.actual_fields(form):
            if field is self:
                try:
                    yield field, field.process_form_value(form)
                except UnmodifiedField:
                    continue
            else:
                # recursive function: we might have compound fields
                # of compound fields (of compound fields of ...)
                for field, value in field.process_posted(form):
                    yield field, value


class StringField(Field):
    widget = fw.TextArea
    size = 45

    def __init__(self, name=None, max_length=None, **kwargs):
        self.max_length = max_length # must be set before super call
        super(StringField, self).__init__(name=name, **kwargs)

    def init_widget(self, widget):
        if widget is None:
            if self.choices:
                widget = fw.Select()
            elif self.max_length and self.max_length < 257:
                widget = fw.TextInput()

        super(StringField, self).init_widget(widget)
        if isinstance(self.widget, fw.TextArea):
            self.init_text_area(self.widget)
        elif isinstance(self.widget, fw.TextInput):
            self.init_text_input(self.widget)

    def init_text_input(self, widget):
        if self.max_length:
            widget.attrs.setdefault('size', min(self.size, self.max_length))
            widget.attrs.setdefault('maxlength', self.max_length)

    def init_text_area(self, widget):
        if self.max_length < 513:
            widget.attrs.setdefault('cols', 60)
            widget.attrs.setdefault('rows', 5)


class PasswordField(StringField):
    widget = fw.PasswordInput

    def typed_value(self, form, load_bytes=False):
        if self.eidparam:
            # no way to fetch actual password value with cw
            if form.edited_entity.has_eid():
                return INTERNAL_FIELD_VALUE
            return self.initial_typed_value(form, load_bytes)
        return super(PasswordField, self).typed_value(form, load_bytes)


class RichTextField(StringField):
    widget = None
    def __init__(self, format_field=None, **kwargs):
        super(RichTextField, self).__init__(**kwargs)
        self.format_field = format_field

    def init_text_area(self, widget):
        pass

    def get_widget(self, form):
        if self.widget is None:
            if self.use_fckeditor(form):
                return fw.FCKEditor()
            widget = fw.TextArea()
            self.init_text_area(widget)
            return widget
        return self.widget

    def get_format_field(self, form):
        if self.format_field:
            return self.format_field
        # we have to cache generated field since it's use as key in the
        # context dictionnary
        req = form._cw
        try:
            return req.data[self]
        except KeyError:
            fkwargs = {'eidparam': self.eidparam, 'role': self.role}
            if self.use_fckeditor(form):
                # if fckeditor is used and format field isn't explicitly
                # deactivated, we want an hidden field for the format
                fkwargs['widget'] = fw.HiddenInput()
                fkwargs['value'] = 'text/html'
            else:
                # else we want a format selector
                fkwargs['widget'] = fw.Select()
                fcstr = FormatConstraint()
                fkwargs['choices'] = fcstr.vocabulary(form=form)
                fkwargs['internationalizable'] = True
                fkwargs['value'] = self.format
            fkwargs['eidparam'] = self.eidparam
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
        if form._cw.use_fckeditor():
            return self.format(form) == 'text/html'
        return False

    def render(self, form, renderer):
        format_field = self.get_format_field(form)
        if format_field:
            # XXX we want both fields to remain vertically aligned
            if format_field.is_visible():
                format_field.widget.attrs['style'] = 'display: block'
            result = format_field.render(form, renderer)
        else:
            result = u''
        return result + self.get_widget(form).render(form, self, renderer)


class FileField(StringField):
    widget = fw.FileInput
    needs_multipart = True

    def __init__(self, format_field=None, encoding_field=None, name_field=None,
                 **kwargs):
        super(FileField, self).__init__(**kwargs)
        self.format_field = format_field
        self.encoding_field = encoding_field
        self.name_field = name_field

    def actual_fields(self, form):
        yield self
        if self.format_field:
            yield self.format_field
        if self.encoding_field:
            yield self.encoding_field
        if self.name_field:
            yield self.name_field

    def typed_value(self, form, load_bytes=False):
        if self.eidparam and self.role is not None:
            if form.edited_entity.has_eid():
                if load_bytes:
                    return getattr(form.edited_entity, self.name)
                # don't actually load data
                # XXX value should reflect if some file is already attached
                # * try to display name metadata
                # * check length(data) / data != null
                return True
            return False
        return super(FileField, self).typed_value(form, load_bytes)

    def render(self, form, renderer):
        wdgs = [self.get_widget(form).render(form, self, renderer)]
        if self.format_field or self.encoding_field:
            divid = '%s-advanced' % self.input_name(form)
            wdgs.append(u'<a href="%s" title="%s"><img src="%s" alt="%s"/></a>' %
                        (xml_escape(uilib.toggle_action(divid)),
                         form._cw._('show advanced fields'),
                         xml_escape(form._cw.build_url('data/puce_down.png')),
                         form._cw._('show advanced fields')))
            wdgs.append(u'<div id="%s" class="hidden">' % divid)
            if self.name_field:
                wdgs.append(self.render_subfield(form, self.name_field, renderer))
            if self.format_field:
                wdgs.append(self.render_subfield(form, self.format_field, renderer))
            if self.encoding_field:
                wdgs.append(self.render_subfield(form, self.encoding_field, renderer))
            wdgs.append(u'</div>')
        if not self.required and self.typed_value(form):
            # trick to be able to delete an uploaded file
            wdgs.append(u'<br/>')
            wdgs.append(tags.input(name=self.input_name(form, u'__detach'),
                                   type=u'checkbox'))
            wdgs.append(form._cw._('detach attached file'))
        return u'\n'.join(wdgs)

    def render_subfield(self, form, field, renderer):
        return (renderer.render_label(form, field)
                + field.render(form, renderer)
                + renderer.render_help(form, field)
                + u'<br/>')

    def _process_form_value(self, form):
        posted = form._cw.form
        if self.input_name(form, u'__detach') in posted:
            # drop current file value on explictily asked to detach
            return None
        try:
            value = posted[self.input_name(form)]
        except KeyError:
            # raise UnmodifiedField instead of returning None, since the later
            # will try to remove already attached file if any
            raise UnmodifiedField()
        # skip browser submitted mime type
        filename, _, stream = value
        # value is a  3-uple (filename, mimetype, stream)
        value = Binary(stream.read())
        if not value.getvalue(): # usually an unexistant file
            value = None
        else:
            # set filename on the Binary instance, may be used later in hooks
            value.filename = filename
        return value


class EditableFileField(FileField):
    editable_formats = ('text/plain', 'text/html', 'text/rest')

    def render(self, form, renderer):
        wdgs = [super(EditableFileField, self).render(form, renderer)]
        if self.format(form) in self.editable_formats:
            data = self.typed_value(form, load_bytes=True)
            if data:
                encoding = self.encoding(form)
                try:
                    form.formvalues[self] = unicode(data.getvalue(), encoding)
                except UnicodeError:
                    pass
                else:
                    if not self.required:
                        msg = form._cw._(
                            'You can either submit a new file using the browse button above'
                            ', or choose to remove already uploaded file by checking the '
                            '"detach attached file" check-box, or edit file content online '
                            'with the widget below.')
                    else:
                        msg = form._cw._(
                            'You can either submit a new file using the browse button above'
                            ', or edit file content online with the widget below.')
                    wdgs.append(u'<p><b>%s</b></p>' % msg)
                    wdgs.append(fw.TextArea(setdomid=False).render(form, self, renderer))
                    # XXX restore form context?
        return '\n'.join(wdgs)

    def _process_form_value(self, form):
        value = form._cw.form.get(self.input_name(form))
        if isinstance(value, unicode):
            # file modified using a text widget
            return Binary(value.encode(self.encoding(form)))
        return super(EditableFileField, self)._process_form_value(form)


class IntField(Field):
    def __init__(self, min=None, max=None, **kwargs):
        super(IntField, self).__init__(**kwargs)
        self.min = min
        self.max = max
        if isinstance(self.widget, fw.TextInput):
            self.widget.attrs.setdefault('size', 5)
            self.widget.attrs.setdefault('maxlength', 15)

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            try:
                return int(value)
            except ValueError:
                raise ProcessFormError(form._cw._('an integer is expected'))
        return value


class BooleanField(Field):
    widget = fw.Radio

    def vocabulary(self, form):
        if self.choices:
            return super(BooleanField, self).vocabulary(form)
        return [(form._cw._('yes'), '1'), (form._cw._('no'), '')]

    def _ensure_correctly_typed(self, form, value):
        if value is not None:
            return bool(value)
        return value


class FloatField(IntField):
    def format_single_value(self, req, value):
        formatstr = req.property_value('ui.float-format')
        if value is None:
            return u''
        return formatstr % float(value)

    def render_example(self, req):
        return self.format_single_value(req, 1.234)

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            try:
                return float(value)
            except ValueError:
                raise ProcessFormError(form._cw._('a float is expected'))
        return None


class DateField(StringField):
    widget = fw.JQueryDatePicker
    format_prop = 'ui.date-format'
    etype = 'Date'

    def format_single_value(self, req, value):
        if value:
            return utils.ustrftime(value, req.property_value(self.format_prop))
        return u''

    def render_example(self, req):
        return self.format_single_value(req, datetime.now())

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            try:
                value = form._cw.parse_datetime(value, self.etype)
            except ValueError, ex:
                raise ProcessFormError(unicode(ex))
        return value


class DateTimeField(DateField):
    widget = fw.JQueryDateTimePicker
    format_prop = 'ui.datetime-format'
    etype = 'Datetime'


class TimeField(DateField):
    widget = fw.JQueryTimePicker
    format_prop = 'ui.time-format'
    etype = 'Time'


# relation vocabulary helper functions #########################################

def relvoc_linkedto(entity, rtype, role):
    # first see if its specified by __linkto form parameters
    linkedto = entity.linked_to(rtype, role)
    if linkedto:
        buildent = entity._cw.entity_from_eid
        return [(buildent(eid).view('combobox'), eid) for eid in linkedto]
    return []

def relvoc_init(entity, rtype, role, required=False):
    # it isn't, check if the entity provides a method to get correct values
    vocab = []
    if not required:
        vocab.append(('', INTERNAL_FIELD_VALUE))
    # vocabulary doesn't include current values, add them
    if entity.has_eid():
        rset = entity.related(rtype, role)
        vocab += [(e.view('combobox'), e.eid) for e in rset.entities()]
    return vocab

def relvoc_unrelated(entity, rtype, role, limit=None):
    if isinstance(rtype, basestring):
        rtype = entity._cw.vreg.schema.rschema(rtype)
    if entity.has_eid():
        done = set(row[0] for row in entity.related(rtype, role))
    else:
        done = None
    result = []
    rsetsize = None
    for objtype in rtype.targets(entity.e_schema, role):
        if limit is not None:
            rsetsize = limit - len(result)
        result += _relvoc_unrelated(entity, rtype, objtype, role, rsetsize, done)
        if limit is not None and len(result) >= limit:
            break
    return result

def _relvoc_unrelated(entity, rtype, targettype, role, limit, done):
    """return unrelated entities for a given relation and target entity type
    for use in vocabulary
    """
    if done is None:
        done = set()
    res = []
    for entity in entity.unrelated(rtype, targettype, role, limit).entities():
        if entity.eid in done:
            continue
        done.add(entity.eid)
        res.append((entity.view('combobox'), entity.eid))
    return res


class RelationField(Field):

    @staticmethod
    def fromcardinality(card, **kwargs):
        kwargs.setdefault('widget', fw.Select(multiple=card in '*+'))
        return RelationField(**kwargs)

    def choices(self, form, limit=None):
        entity = form.edited_entity
        # first see if its specified by __linkto form parameters
        linkedto = relvoc_linkedto(entity, self.name, self.role)
        if linkedto:
            return linkedto
        # it isn't, check if the entity provides a method to get correct values
        vocab = relvoc_init(entity, self.name, self.role, self.required)
        method = '%s_%s_vocabulary' % (self.role, self.name)
        try:
            vocab += getattr(form, method)(self.name, limit)
            warn('[3.6] found %s on %s, should override field.choices instead (need tweaks)'
                 % (method, form), DeprecationWarning)
        except AttributeError:
            vocab += relvoc_unrelated(entity, self.name, self.role, limit)
        if self.sort:
            vocab = vocab_sort(vocab)
        return vocab

    def form_init(self, form):
        #if not self.display_value(form):
        value = form.edited_entity.linked_to(self.name, self.role)
        if value:
            searchedvalues = ['%s:%s:%s' % (self.name, eid, self.role)
                              for eid in value]
            # remove associated __linkto hidden fields
            for field in form.root_form.fields_by_name('__linkto'):
                if field.value in searchedvalues:
                    form.root_form.remove_field(field)
            form.formvalues[self] = value

    def format_single_value(self, req, value):
        return value

    def _process_form_value(self, form):
        """process posted form and return correctly typed value"""
        widget = self.get_widget(form)
        values = widget.process_field_data(form, self)
        if values is None:
            values = ()
        elif not isinstance(values, list):
            values = (values,)
        eids = set()
        for eid in values:
            # XXX 'not eid' for AutoCompletionWidget, deal with this in the widget
            if not eid or eid == INTERNAL_FIELD_VALUE:
                continue
            typed_eid = form.actual_eid(eid)
            if typed_eid is None:
                form._cw.data['pendingfields'].add( (form, self) )
                return None
            eids.add(typed_eid)
        return eids


class CompoundField(Field):
    def __init__(self, fields, *args, **kwargs):
        super(CompoundField, self).__init__(*args, **kwargs)
        self.fields = fields

    def subfields(self, form):
        return self.fields

    def actual_fields(self, form):
        return [self] + list(self.fields)


def guess_field(eschema, rschema, role='subject', skip_meta_attr=True, **kwargs):
    """return the most adapated widget to edit the relation
    'subjschema rschema objschema' according to information found in the schema
    """
    fieldclass = None
    rdef = eschema.rdef(rschema, role)
    if role == 'subject':
        targetschema = rdef.object
        if rschema.final:
            if rdef.get('internationalizable'):
                kwargs.setdefault('internationalizable', True)
    else:
        targetschema = rdef.subject
    card = rdef.role_cardinality(role)
    kwargs['required'] = card in '1+'
    kwargs['name'] = rschema.type
    kwargs['role'] = role
    if role == 'object':
        kwargs.setdefault('label', (eschema.type, rschema.type + '_object'))
    else:
        kwargs.setdefault('label', (eschema.type, rschema.type))
    kwargs['eidparam'] = True
    kwargs.setdefault('help', rdef.description)
    if rschema.final:
        if skip_meta_attr and rschema in eschema.meta_attributes():
            return None
        fieldclass = FIELDS[targetschema]
        if fieldclass is StringField:
            if eschema.has_metadata(rschema, 'format'):
                # use RichTextField instead of StringField if the attribute has
                # a "format" metadata. But getting information from constraints
                # may be useful anyway...
                for cstr in rdef.constraints:
                    if isinstance(cstr, StaticVocabularyConstraint):
                        raise Exception('rich text field with static vocabulary')
                return RichTextField(**kwargs)
            # init StringField parameters according to constraints
            for cstr in rdef.constraints:
                if isinstance(cstr, StaticVocabularyConstraint):
                    kwargs.setdefault('choices', cstr.vocabulary)
                    break
            for cstr in rdef.constraints:
                if isinstance(cstr, SizeConstraint) and cstr.max is not None:
                    kwargs['max_length'] = cstr.max
            return StringField(**kwargs)
        if fieldclass is FileField:
            for metadata in KNOWN_METAATTRIBUTES:
                metaschema = eschema.has_metadata(rschema, metadata)
                if metaschema is not None:
                    kwargs['%s_field' % metadata] = guess_field(eschema, metaschema,
                                                                skip_meta_attr=False)
        return fieldclass(**kwargs)
    return RelationField.fromcardinality(card, **kwargs)


FIELDS = {
    'Boolean':  BooleanField,
    'Bytes':    FileField,
    'Date':     DateField,
    'Datetime': DateTimeField,
    'Int':      IntField,
    'Float':    FloatField,
    'Decimal':  StringField,
    'Password': PasswordField,
    'String' :  StringField,
    'Time':     TimeField,
    }
