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
The Field class and basic fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. Note::
  Fields are used to control what's edited in forms. They makes the link between
  something to edit and its display in the form. Actual display is handled by a
  widget associated to the field.

Let first see the base class for fields:

.. autoclass:: cubicweb.web.formfields.Field

Now, you usually don't use that class but one of the concrete field classes
described below, according to what you want to edit.

Basic fields
''''''''''''

.. autoclass:: cubicweb.web.formfields.StringField()
.. autoclass:: cubicweb.web.formfields.PasswordField()
.. autoclass:: cubicweb.web.formfields.IntField()
.. autoclass:: cubicweb.web.formfields.BigIntField()
.. autoclass:: cubicweb.web.formfields.FloatField()
.. autoclass:: cubicweb.web.formfields.BooleanField()
.. autoclass:: cubicweb.web.formfields.DateField()
.. autoclass:: cubicweb.web.formfields.DateTimeField()
.. autoclass:: cubicweb.web.formfields.TimeField()
.. autoclass:: cubicweb.web.formfields.TimeIntervalField()

Compound fields
''''''''''''''''

.. autoclass:: cubicweb.web.formfields.RichTextField()
.. autoclass:: cubicweb.web.formfields.FileField()
.. autoclass:: cubicweb.web.formfields.CompoundField()

.. autoclass cubicweb.web.formfields.EditableFileField() XXX should be a widget

Entity specific fields and function
'''''''''''''''''''''''''''''''''''

.. autoclass:: cubicweb.web.formfields.RelationField()
.. autofunction:: cubicweb.web.formfields.guess_field

"""
__docformat__ = "restructuredtext en"

from warnings import warn
from datetime import datetime, timedelta

from logilab.mtconverter import xml_escape
from logilab.common import nullobject
from logilab.common.date import ustrftime
from logilab.common.configuration import format_time
from logilab.common.textutils import apply_units, TIME_UNITS

from yams.schema import KNOWN_METAATTRIBUTES, role_name
from yams.constraints import (SizeConstraint, StaticVocabularyConstraint,
                              FormatConstraint)

from cubicweb import Binary, tags, uilib
from cubicweb.utils import support_args
from cubicweb.web import INTERNAL_FIELD_VALUE, ProcessFormError, eid_param, \
     formwidgets as fw
from cubicweb.web.views import uicfg

class UnmodifiedField(Exception):
    """raise this when a field has not actually been edited and you want to skip
    it
    """

def normalize_filename(filename):
    return filename.split('\\')[-1]

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

_MARKER = nullobject()

class Field(object):
    """This class is the abstract base class for all fields. It hold a bunch
    of attributes which may be used for fine control of the behaviour of a
    concrete field.

    **Attributes**

    All the attributes described below have sensible default value which may be
    overriden by named arguments given to field's constructor.

    :attr:`name`
       base name of the field (basestring). The actual input name is returned by
       the :meth:`input_name` method and may differ from that name (for instance
       if `eidparam` is true).
    :attr:`id`
       DOM identifier (default to the same value as `name`), should be unique in
       a form.
    :attr:`label`
       label of the field (default to the same value as `name`).
    :attr:`help`
       help message about this field.
    :attr:`widget`
       widget associated to the field. Each field class has a default widget
       class which may be overriden per instance.
    :attr:`value`
       field value. May be an actual value or a callable which should take the
       form as argument and return a value.
    :attr:`choices`
       static vocabulary for this field. May be a list of values, a list of
       (label, value) tuples or a callable which should take the form and field
       as arguments and return a list of values or a list of (label, value).
    :attr:`required`
       bool flag telling if the field is required or not.
    :attr:`sort`
       bool flag telling if the vocabulary (either static vocabulary specified
       in `choices` or dynamic vocabulary fetched from the form) should be
       sorted on label.
    :attr:`internationalizable`
       bool flag telling if the vocabulary labels should be translated using the
       current request language.
    :attr:`eidparam`
       bool flag telling if this field is linked to a specific entity
    :attr:`role`
       when the field is linked to an entity attribute or relation, tells the
       role of the entity in the relation (eg 'subject' or 'object'). If this is
       not an attribute or relation of the edited entity, `role` should be
       `None`.
    :attr:`fieldset`
       optional fieldset to which this field belongs to
    :attr:`order`
       key used by automatic forms to sort fields
    :attr:`ignore_req_params`
       when true, this field won't consider value potentialy specified using
       request's form parameters (eg you won't be able to specify a value using for
       instance url like http://mywebsite.com/form?field=value)

    .. currentmodule:: cubicweb.web.formfields

    **Generic methods**

    .. automethod:: Field.input_name
    .. automethod:: Field.dom_id
    .. automethod:: Field.actual_fields

    **Form generation methods**

    .. automethod:: form_init
    .. automethod:: typed_value

    **Post handling methods**

    .. automethod:: process_posted
    .. automethod:: process_form_value

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
    fallback_on_none_attribute = False
    ignore_req_params = False

    def __init__(self, name=None, label=_MARKER, widget=None, **kwargs):
        for key, val in kwargs.items():
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

    def as_string(self, repr=True):
        l = [u'<%s' % self.__class__.__name__]
        for attr in ('name', 'eidparam', 'role', 'id', 'value'):
            value = getattr(self, attr)
            if value is not None and value is not _MARKER:
                l.append('%s=%r' % (attr, value))
        if repr:
            l.append('@%#x' % id(self))
        return u'%s>' % ' '.join(l)

    def __unicode__(self):
        return self.as_string(False)

    def __str__(self):
        return self.as_string(False).encode('UTF8')

    def __repr__(self):
        return self.as_string(True).encode('UTF8')

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
        """Fields may be composed of other fields. For instance the
        :class:`~cubicweb.web.formfields.RichTextField` is containing a format
        field to define the text format. This method returns actual fields that
        should be considered for display / edition. It usually simply return
        self.
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

    def input_name(self, form, suffix=None):
        """Return the 'qualified name' for this field, e.g. something suitable
        to use as HTML input name. You can specify a suffix that will be
        included in the name when widget needs several inputs.
        """
        # caching is necessary else we get some pb on entity creation :
        # entity.eid is modified from creation mark (eg 'X') to its actual eid
        # (eg 123), and then `field.input_name()` won't return the right key
        # anymore if not cached (first call to input_name done *before* eventual
        # eid affectation).
        #
        # note that you should NOT use @cached else it will create a memory leak
        # on persistent fields (eg created once for all on a form class) because
        # of the 'form' appobject argument: the cache will keep growing as new
        # form are created...
        try:
            return form.formvalues[(self, 'input_name', suffix)]
        except KeyError:
            name = self.role_name()
            if suffix is not None:
                name += suffix
            if self.eidparam:
                name = eid_param(name, form.edited_entity.eid)
            form.formvalues[(self, 'input_name', suffix)] = name
            return name

    def role_name(self):
        """return <field.name>-<field.role> if role is specified, else field.name"""
        assert self.name, 'field without a name (give it to constructor for explicitly built fields)'
        if self.role is not None:
            return role_name(self.name, self.role)
        return self.name

    def dom_id(self, form, suffix=None):
        """Return the HTML DOM identifier for this field, e.g. something
        suitable to use as HTML input id. You can specify a suffix that will be
        included in the name when widget needs several inputs.
        """
        id = self.id or self.role_name()
        if suffix is not None:
            id += suffix
        if self.eidparam:
            return eid_param(id, form.edited_entity.eid)
        return id

    def typed_value(self, form, load_bytes=False):
        """Return the correctly typed value for this field in the form context.
        """
        if self.eidparam and self.role is not None:
            entity = form.edited_entity
            if form._cw.vreg.schema.rschema(self.name).final:
                if entity.has_eid() or self.name in entity.cw_attr_cache:
                    value = getattr(entity, self.name)
                    if value is not None or not self.fallback_on_none_attribute:
                        return value
            elif entity.has_eid() or entity.cw_relation_cached(self.name, self.role):
                value = [r[0] for r in entity.related(self.name, self.role)]
                if value or not self.fallback_on_none_attribute:
                    return value
        return self.initial_typed_value(form, load_bytes)

    def initial_typed_value(self, form, load_bytes):
        if self.value is not _MARKER:
            if callable(self.value):
                # pylint: disable=E1102
                if support_args(self.value, 'form', 'field'):
                    return self.value(form, self)
                else:
                    warn("[3.10] field's value callback must now take form and "
                         "field as argument (%s)" % self, DeprecationWarning)
                    return self.value(form)
            return self.value
        formattr = '%s_%s_default' % (self.role, self.name)
        if self.eidparam and self.role is not None:
            if form._cw.vreg.schema.rschema(self.name).final:
                return form.edited_entity.e_schema.default(self.name)
            return form.linked_to.get((self.name, self.role), ())
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

    def vocabulary(self, form, **kwargs):
        """return vocabulary for this field. This method will be
        called by widgets which requires a vocabulary.

        It should return a list of tuple (label, value), where value
        *must be an unicode string*, not a typed value.
        """
        assert self.choices is not None
        if callable(self.choices):
            # pylint: disable=E1102
            if getattr(self.choices, 'im_self', None) is self:
                vocab = self.choices(form=form, **kwargs)
            else:
                vocab = self.choices(form=form, field=self, **kwargs)
        else:
            vocab = self.choices
        if vocab and not isinstance(vocab[0], (list, tuple)):
            vocab = [(x, x) for x in vocab]
        if self.internationalizable:
            # the short-cirtcuit 'and' boolean operator is used here
            # to permit a valid empty string in vocabulary without
            # attempting to translate it by gettext (which can lead to
            # weird strings display)
            vocab = [(label and form._cw._(label), value)
                     for label, value in vocab]
        if self.sort:
            vocab = vocab_sort(vocab)
        return vocab

    # support field as argument to avoid warning when used as format field value
    # callback
    def format(self, form, field=None):
        """return MIME type used for the given (text or bytes) field"""
        if self.eidparam and self.role == 'subject':
            entity = form.edited_entity
            if entity.e_schema.has_metadata(self.name, 'format') and (
                entity.has_eid() or '%s_format' % self.name in entity.cw_attr_cache):
                return form.edited_entity.cw_attr_metadata(self.name, 'format')
        return form._cw.property_value('ui.default-text-format')

    def encoding(self, form):
        """return encoding used for the given (text) field"""
        if self.eidparam:
            entity = form.edited_entity
            if entity.e_schema.has_metadata(self.name, 'encoding') and (
                entity.has_eid() or '%s_encoding' % self.name in entity):
                return form.edited_entity.cw_attr_metadata(self.name, 'encoding')
        return form._cw.encoding

    def form_init(self, form):
        """Method called at form initialization to trigger potential field
        initialization requiring the form instance. Do nothing by default.
        """
        pass

    def has_been_modified(self, form):
        for field in self.actual_fields(form):
            if field._has_been_modified(form):
                return True # XXX
        return False # not modified

    def _has_been_modified(self, form):
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
        if isinstance(previous_value, (list, tuple)):
            # widget should return a set of untyped eids
            previous_value = set(e.eid for e in previous_value)
        try:
            new_value = self.process_form_value(form)
        except ProcessFormError:
            return True
        except UnmodifiedField:
            return False # not modified
        if previous_value == new_value:
            return False # not modified
        return True

    def process_form_value(self, form):
        """Return the correctly typed value posted for this field."""
        try:
            return form.formvalues[(self, form)]
        except KeyError:
            value = form.formvalues[(self, form)] = self._process_form_value(form)
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
        return value or None

    def process_posted(self, form):
        """Return an iterator on (field, value) that has been posted for
        field returned by :meth:`~cubicweb.web.formfields.Field.actual_fields`.
        """
        for field in self.actual_fields(form):
            if field is self:
                try:
                    value = field.process_form_value(form)
                    if field.no_value(value) and field.required:
                        raise ProcessFormError(form._cw._("required field"))
                    yield field, value
                except UnmodifiedField:
                    continue
            else:
                # recursive function: we might have compound fields
                # of compound fields (of compound fields of ...)
                for field, value in field.process_posted(form):
                    yield field, value

    @staticmethod
    def no_value(value):
        """return True if the value can be considered as no value for the field"""
        return value is None


class StringField(Field):
    """Use this field to edit unicode string (`String` yams type). This field
    additionaly support a `max_length` attribute that specify a maximum size for
    the string (`None` meaning no limit).

    Unless explicitly specified, the widget for this field will be:

    * :class:`~cubicweb.web.formwidgets.Select` if some vocabulary is specified
      using `choices` attribute

    * :class:`~cubicweb.web.formwidgets.TextInput` if maximum size is specified
      using `max_length` attribute and this length is inferior to 257.

    * :class:`~cubicweb.web.formwidgets.TextArea` in all other cases
    """
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
        if self.max_length and self.max_length < 513:
            widget.attrs.setdefault('cols', 60)
            widget.attrs.setdefault('rows', 5)


class PasswordField(StringField):
    """Use this field to edit password (`Password` yams type, encoded python
    string).

    Unless explicitly specified, the widget for this field will be
    a :class:`~cubicweb.web.formwidgets.PasswordInput`.
    """
    widget = fw.PasswordInput
    def form_init(self, form):
        if self.eidparam and form.edited_entity.has_eid():
            # see below: value is probably set but we can't retreive it. Ensure
            # the field isn't show as a required field on modification
            self.required = False

    def typed_value(self, form, load_bytes=False):
        if self.eidparam:
            # no way to fetch actual password value with cw
            if form.edited_entity.has_eid():
                return ''
            return self.initial_typed_value(form, load_bytes)
        return super(PasswordField, self).typed_value(form, load_bytes)


class RichTextField(StringField):
    """This compound field allow edition of text (unicode string) in
    a particular format. It has an inner field holding the text format,
    that can be specified using `format_field` argument. If not specified
    one will be automaticall generated.

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.FCKEditor` or a
    :class:`~cubicweb.web.formwidgets.TextArea`. according to the field's
    format and to user's preferences.
    """

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
        # context dictionary
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
    """This compound field allow edition of binary stream (`Bytes` yams
    type). Three inner fields may be specified:

    * `format_field`, holding the file's format.
    * `encoding_field`, holding the file's content encoding.
    * `name_field`, holding the file's name.

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.FileInput`. Inner fields, if any,
    will be added to a drop down menu at the right of the file input.
    """
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
                         xml_escape(form._cw.data_url('puce_down.png')),
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
        # value is a 2-uple (filename, stream) or a list of such
        # tuples (multiple files)
        try:
            if isinstance(value, list):
                value = value[0]
                form.warning('mutiple files provided, however '
                             'only the first will be picked')
            filename, stream = value
        except ValueError:
            raise UnmodifiedField()
        # XXX avoid in memory loading of posted files. Requires Binary handling changes...
        value = Binary(stream.read())
        if not value.getvalue(): # usually an unexistant file
            value = None
        else:
            # set filename on the Binary instance, may be used later in hooks
            value.filename = normalize_filename(filename)
        return value


# XXX turn into a widget
class EditableFileField(FileField):
    """This compound field allow edition of binary stream as
    :class:`~cubicweb.web.formfields.FileField` but expect that stream to
    actually contains some text.

    If the stream format is one of text/plain, text/html, text/rest,
    then a :class:`~cubicweb.web.formwidgets.TextArea` will be additionaly
    displayed, allowing to directly the file's content when desired, instead
    of choosing a file from user's file system.
    """
    editable_formats = ('text/plain', 'text/html', 'text/rest')

    def render(self, form, renderer):
        wdgs = [super(EditableFileField, self).render(form, renderer)]
        if self.format(form) in self.editable_formats:
            data = self.typed_value(form, load_bytes=True)
            if data:
                encoding = self.encoding(form)
                try:
                    form.formvalues[(self, form)] = unicode(data.getvalue(), encoding)
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


class BigIntField(Field):
    """Use this field to edit big integers (`BigInt` yams type). This field
    additionaly support `min` and `max` attributes that specify a minimum and/or
    maximum value for the integer (`None` meaning no boundary).

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.TextInput`.
    """
    default_text_input_size = 10

    def __init__(self, min=None, max=None, **kwargs):
        super(BigIntField, self).__init__(**kwargs)
        self.min = min
        self.max = max

    def init_widget(self, widget):
        super(BigIntField, self).init_widget(widget)
        if isinstance(self.widget, fw.TextInput):
            self.widget.attrs.setdefault('size', self.default_text_input_size)

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            value = value.strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                raise ProcessFormError(form._cw._('an integer is expected'))
        return value


class IntField(BigIntField):
    """Use this field to edit integers (`Int` yams type). Similar to
    :class:`~cubicweb.web.formfields.BigIntField` but set max length when text
    input widget is used (the default).
    """
    default_text_input_size = 5

    def init_widget(self, widget):
        super(IntField, self).init_widget(widget)
        if isinstance(self.widget, fw.TextInput):
            self.widget.attrs.setdefault('maxlength', 15)


class BooleanField(Field):
    """Use this field to edit booleans (`Boolean` yams type).

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.Radio` with yes/no values. You
    can change that values by specifing `choices`.
    """
    widget = fw.Radio

    def __init__(self, allow_none=False, **kwargs):
        super(BooleanField, self).__init__(**kwargs)
        self.allow_none = allow_none

    def vocabulary(self, form):
        if self.choices:
            return super(BooleanField, self).vocabulary(form)
        if self.allow_none:
            return [(form._cw._('indifferent'), ''),
                    (form._cw._('yes'), '1'),
                    (form._cw._('no'), '0')]
        # XXX empty string for 'no' in that case for bw compat
        return [(form._cw._('yes'), '1'), (form._cw._('no'), '')]

    def format_single_value(self, req, value):
        """return value suitable for display"""
        if self.allow_none:
            if value is None:
                return u''
            if value is False:
                return '0'
        return super(BooleanField, self).format_single_value(req, value)

    def _ensure_correctly_typed(self, form, value):
        if self.allow_none:
            if value:
                return bool(int(value))
            return None
        return bool(value)


class FloatField(IntField):
    """Use this field to edit floats (`Float` yams type). This field additionaly
    support `min` and `max` attributes as the
    :class:`~cubicweb.web.formfields.IntField`.

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.TextInput`.
    """
    def format_single_value(self, req, value):
        formatstr = req.property_value('ui.float-format')
        if value is None:
            return u''
        return formatstr % float(value)

    def render_example(self, req):
        return self.format_single_value(req, 1.234)

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            value = value.strip()
            if not value:
                return None
            try:
                return float(value)
            except ValueError:
                raise ProcessFormError(form._cw._('a float is expected'))
        return None


class TimeIntervalField(StringField):
    """Use this field to edit time interval (`Interval` yams type).

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.TextInput`.
    """
    widget = fw.TextInput

    def format_single_value(self, req, value):
        if value:
            value = format_time(value.days * 24 * 3600 + value.seconds)
            return unicode(value)
        return u''

    def example_format(self, req):
        """return a sample string describing what can be given as input for this
        field
        """
        return u'20s, 10min, 24h, 4d'

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            value = value.strip()
            if not value:
                return None
            try:
                value = apply_units(value, TIME_UNITS)
            except ValueError:
                raise ProcessFormError(form._cw._('a number (in seconds) or 20s, 10min, 24h or 4d are expected'))
        return timedelta(0, value)


class DateField(StringField):
    """Use this field to edit date (`Date` yams type).

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.JQueryDatePicker`.
    """
    widget = fw.JQueryDatePicker
    format_prop = 'ui.date-format'
    etype = 'Date'

    def format_single_value(self, req, value):
        if value:
            return ustrftime(value, req.property_value(self.format_prop))
        return u''

    def render_example(self, req):
        return self.format_single_value(req, datetime.now())

    def _ensure_correctly_typed(self, form, value):
        if isinstance(value, basestring):
            value = value.strip()
            if not value:
                return None
            try:
                value = form._cw.parse_datetime(value, self.etype)
            except ValueError as ex:
                raise ProcessFormError(unicode(ex))
        return value


class DateTimeField(DateField):
    """Use this field to edit datetime (`Datetime` yams type).

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.JQueryDateTimePicker`.
    """
    widget = fw.JQueryDateTimePicker
    format_prop = 'ui.datetime-format'
    etype = 'Datetime'


class TimeField(DateField):
    """Use this field to edit time (`Time` yams type).

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.JQueryTimePicker`.
    """
    widget = fw.JQueryTimePicker
    format_prop = 'ui.time-format'
    etype = 'Time'


# XXX use cases where we don't actually want a better widget?
class CompoundField(Field):
    """This field shouldn't be used directly, it's designed to hold inner
    fields that should be conceptually groupped together.
    """
    def __init__(self, fields, *args, **kwargs):
        super(CompoundField, self).__init__(*args, **kwargs)
        self.fields = fields

    def subfields(self, form):
        return self.fields

    def actual_fields(self, form):
        # don't add [self] to actual fields, compound field is usually kinda
        # virtual, all interesting values are in subfield. Skipping it may avoid
        # error when processed by the editcontroller : it may be marked as required
        # while it has no value, hence generating a false error.
        return list(self.fields)

    @property
    def needs_multipart(self):
        return any(f.needs_multipart for f in self.fields)


class RelationField(Field):
    """Use this field to edit a relation of an entity.

    Unless explicitly specified, the widget for this field will be a
    :class:`~cubicweb.web.formwidgets.Select`.
    """

    @staticmethod
    def fromcardinality(card, **kwargs):
        kwargs.setdefault('widget', fw.Select(multiple=card in '*+'))
        return RelationField(**kwargs)

    def choices(self, form, limit=None):
        """Take care, choices function for relation field instance should take
        an extra 'limit' argument, with default to None.

        This argument is used by the 'unrelateddivs' view (see in autoform) and
        when it's specified (eg not None), vocabulary returned should:
        * not include already related entities
        * have a max size of `limit` entities
        """
        entity = form.edited_entity
        # first see if its specified by __linkto form parameters
        if limit is None:
            linkedto = self.relvoc_linkedto(form)
            if linkedto:
                return linkedto
            # it isn't, search more vocabulary
            vocab = self.relvoc_init(form)
        else:
            vocab = []
        vocab += self.relvoc_unrelated(form, limit)
        if self.sort:
            vocab = vocab_sort(vocab)
        return vocab

    def relvoc_linkedto(self, form):
        linkedto = form.linked_to.get((self.name, self.role))
        if linkedto:
            buildent = form._cw.entity_from_eid
            return [(buildent(eid).view('combobox'), unicode(eid))
                    for eid in linkedto]
        return []

    def relvoc_init(self, form):
        entity, rtype, role = form.edited_entity, self.name, self.role
        vocab = []
        if not self.required:
            vocab.append(('', INTERNAL_FIELD_VALUE))
        # vocabulary doesn't include current values, add them
        if form.edited_entity.has_eid():
            rset = form.edited_entity.related(self.name, self.role)
            vocab += [(e.view('combobox'), unicode(e.eid))
                      for e in rset.entities()]
        return vocab

    def relvoc_unrelated(self, form, limit=None):
        entity = form.edited_entity
        rtype = entity._cw.vreg.schema.rschema(self.name)
        if entity.has_eid():
            done = set(row[0] for row in entity.related(rtype, self.role))
        else:
            done = None
        result = []
        rsetsize = None
        for objtype in rtype.targets(entity.e_schema, self.role):
            if limit is not None:
                rsetsize = limit - len(result)
            result += self._relvoc_unrelated(form, objtype, rsetsize, done)
            if limit is not None and len(result) >= limit:
                break
        return result

    def _relvoc_unrelated(self, form, targettype, limit, done):
        """return unrelated entities for a given relation and target entity type
        for use in vocabulary
        """
        if done is None:
            done = set()
        res = []
        entity = form.edited_entity
        for entity in entity.unrelated(self.name, targettype, self.role, limit,
                                       lt_infos=form.linked_to).entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            res.append((entity.view('combobox'), unicode(entity.eid)))
        return res

    def format_single_value(self, req, value):
        return unicode(value)

    def process_form_value(self, form):
        """process posted form and return correctly typed value"""
        try:
            return form.formvalues[(self, form)]
        except KeyError:
            value = self._process_form_value(form)
            # if value is None, there are some remaining pending fields, we'll
            # have to recompute this later -> don't cache in formvalues
            if value is not None:
                form.formvalues[(self, form)] = value
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
        rschema = form._cw.vreg.schema.rschema(self.name)
        for eid in values:
            if not eid or eid == INTERNAL_FIELD_VALUE:
                continue
            typed_eid = form.actual_eid(eid)
            # if entity doesn't exist yet
            if typed_eid is None:
                # inlined relations of to-be-created **subject entities** have
                # to be handled separatly
                if self.role == 'object' and rschema.inlined:
                    form._cw.data['pending_inlined'][eid].add( (form, self) )
                else:
                    form._cw.data['pending_others'].add( (form, self) )
                return None
            eids.add(typed_eid)
        return eids

    @staticmethod
    def no_value(value):
        """return True if the value can be considered as no value for the field"""
        # value is None is the 'not yet ready value, consider the empty set
        return value is not None and not value


_AFF_KWARGS = uicfg.autoform_field_kwargs

def guess_field(eschema, rschema, role='subject', req=None, **kwargs):
    """This function return the most adapted field to edit the given relation
    (`rschema`) where the given entity type (`eschema`) is the subject or object
    (`role`).

    The field is initialized according to information found in the schema,
    though any value can be explicitly specified using `kwargs`.
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
    kwargs['name'] = rschema.type
    kwargs['role'] = role
    kwargs['eidparam'] = True
    kwargs.setdefault('required', card in '1+')
    if role == 'object':
        kwargs.setdefault('label', (eschema.type, rschema.type + '_object'))
    else:
        kwargs.setdefault('label', (eschema.type, rschema.type))
    kwargs.setdefault('help', rdef.description)
    if rschema.final:
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
            if req:
                aff_kwargs = req.vreg['uicfg'].select('autoform_field_kwargs', req)
            else:
                aff_kwargs = _AFF_KWARGS
            for metadata in KNOWN_METAATTRIBUTES:
                metaschema = eschema.has_metadata(rschema, metadata)
                if metaschema is not None:
                    metakwargs = aff_kwargs.etype_get(eschema, metaschema, 'subject')
                    kwargs['%s_field' % metadata] = guess_field(eschema, metaschema,
                                                                req=req, **metakwargs)
        return fieldclass(**kwargs)
    return RelationField.fromcardinality(card, **kwargs)


FIELDS = {
    'String' :  StringField,
    'Bytes':    FileField,
    'Password': PasswordField,

    'Boolean':  BooleanField,
    'Int':      IntField,
    'BigInt':   BigIntField,
    'Float':    FloatField,
    'Decimal':  StringField,

    'Date':       DateField,
    'Datetime':   DateTimeField,
    'TZDatetime': DateTimeField,
    'Time':       TimeField,
    'TZTime':     TimeField,
    'Interval':   TimeIntervalField,
    }
