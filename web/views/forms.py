"""some base form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.compat import any
from logilab.common.decorators import iclassmethod

from cubicweb.selectors import non_final_entity, match_kwargs, one_line_rset
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param
from cubicweb.web import form, formwidgets as fwdgs
from cubicweb.web.controller import NAV_FORM_PARAMETERS
from cubicweb.web.formfields import HiddenInitialValueField, StringField


class FieldsForm(form.Form):
    """base class for fields based forms.

    The following attributes may be either set on subclasses or given on
    form selection to customize the generated form:

    * `needs_js`: sequence of javascript files that should be added to handle
      this form (through `req.add_js`)

    * `needs_css`: sequence of css files that should be added to handle this
      form (through `req.add_css`)

    * `domid`: value for the "id" attribute of the <form> tag

    * `action`: value for the "action" attribute of the <form> tag

    * `onsubmit`: value for the "onsubmit" attribute of the <form> tag

    * `cssclass`: value for the "class" attribute of the <form> tag

    * `cssstyle`: value for the "style" attribute of the <form> tag

    * `cwtarget`: value for the "cubicweb:target" attribute of the <form> tag

    * `redirect_path`: relative to redirect to after submitting the form

    * `copy_nav_params`: flag telling if navigation paramenters should be copied
      back in hidden input

    * `form_buttons`:  form buttons sequence (button widgets instances)

    * `form_renderer_id`: id of the form renderer to use to render the form

    * `fieldsets_in_order`: fieldset name sequence, to control order
    """
    __regid__ = 'base'

    is_subform = False
    internal_fields = ('__errorurl',) + NAV_FORM_PARAMETERS

    # attributes overrideable by subclasses or through __init__
    needs_js = ('cubicweb.ajax.js', 'cubicweb.edition.js',)
    needs_css = ('cubicweb.form.css',)
    domid = 'form'
    action = None
    onsubmit = "return freezeFormButtons('%(domid)s');"
    cssclass = None
    cssstyle = None
    cwtarget = None
    redirect_path = None
    copy_nav_params = False
    form_buttons = None
    form_renderer_id = 'default'
    fieldsets_in_order = None

    def __init__(self, req, rset=None, row=None, col=None,
                 submitmsg=None, mainform=True,
                 **kwargs):
        super(FieldsForm, self).__init__(req, rset=rset, row=row, col=col)
        self.fields = list(self.__class__._fields_)
        for key, val in kwargs.items():
            if key in NAV_FORM_PARAMETERS:
                self.form_add_hidden(key, val)
            elif hasattr(self.__class__, key) and not key[0] == '_':
                setattr(self, key, val)
            # skip other parameters, usually given for selection
            # (else write a custom class to handle them)
        if mainform:
            self.form_add_hidden('__errorurl', self.session_key())
            self.form_add_hidden('__domid', self.domid)
        if self.copy_nav_params:
            for param in NAV_FORM_PARAMETERS:
                if not param in kwargs:
                    value = req.form.get(param)
                    if value:
                        self.form_add_hidden(param, value)
        if submitmsg is not None:
            self.form_add_hidden('__message', submitmsg)
        self.context = None
        if 'domid' in kwargs:# session key changed
            self.restore_previous_post(self.session_key())

    @iclassmethod
    def _fieldsattr(cls_or_self):
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        return fields

    @iclassmethod
    def field_by_name(cls_or_self, name, role='subject'):
        """return field with the given name and role.
        Raise FieldNotFound if the field can't be found.
        """
        for field in cls_or_self._fieldsattr():
            if field.name == name and field.role == role:
                return field
        raise form.FieldNotFound(name)

    @iclassmethod
    def fields_by_name(cls_or_self, name, role='subject'):
        """return a list of fields with the given name and role"""
        return [field for field in cls_or_self._fieldsattr()
                if field.name == name and field.role == role]

    @iclassmethod
    def remove_field(cls_or_self, field):
        """remove a field from form class or instance"""
        cls_or_self._fieldsattr().remove(field)

    @iclassmethod
    def append_field(cls_or_self, field):
        """append a field to form class or instance"""
        cls_or_self._fieldsattr().append(field)

    @iclassmethod
    def insert_field_before(cls_or_self, new_field, name, role='subject'):
        field = cls_or_self.field_by_name(name, role)
        fields = cls_or_self._fieldsattr()
        fields.insert(fields.index(field), new_field)

    @iclassmethod
    def insert_field_after(cls_or_self, new_field, name, role='subject'):
        field = cls_or_self.field_by_name(name, role)
        fields = cls_or_self._fieldsattr()
        fields.insert(fields.index(field)+1, new_field)

    @property
    def form_needs_multipart(self):
        """true if the form needs enctype=multipart/form-data"""
        return any(field.needs_multipart for field in self.fields)

    def form_add_hidden(self, name, value=None, **kwargs):
        """add an hidden field to the form"""
        kwargs.setdefault('widget', fwdgs.HiddenInput)
        field = StringField(name=name, initial=value, **kwargs)
        if 'id' in kwargs:
            # by default, hidden input don't set id attribute. If one is
            # explicitly specified, ensure it will be set
            field.widget.setdomid = True
        self.append_field(field)
        return field

    def add_media(self):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            self.req.add_js(self.needs_js)
        if self.needs_css:
            self.req.add_css(self.needs_css)

    def form_render(self, **values):
        """render this form, using the renderer given in args or the default
        FormRenderer()
        """
        renderer = values.pop('renderer', None)
        if renderer is None:
            renderer = self.form_default_renderer()
        return renderer.render(self, values)

    def form_default_renderer(self):
        return self.vreg['formrenderers'].select(self.form_renderer_id,
                                                self.req, rset=self.rset,
                                                row=self.row, col=self.col)

    def form_build_context(self, rendervalues=None):
        """build form context values (the .context attribute which is a
        dictionary with field instance as key associated to a dictionary
        containing field 'name' (qualified), 'id', 'value' (for display, always
        a string).

        rendervalues is an optional dictionary containing extra kwargs given to
        form_render()
        """
        self.context = context = {}
        # ensure rendervalues is a dict
        if rendervalues is None:
            rendervalues = {}
        # use a copy in case fields are modified while context is build (eg
        # __linkto handling for instance)
        for field in self.fields[:]:
            for field in field.actual_fields(self):
                field.form_init(self)
                value = self.form_field_display_value(field, rendervalues)
                context[field] = {'value': value,
                                  'name': self.form_field_name(field),
                                  'id': self.form_field_id(field),
                                  }

    def form_field_display_value(self, field, rendervalues, load_bytes=False):
        """return field's *string* value to use for display

        looks in
        1. previously submitted form values if any (eg on validation error)
        2. req.form
        3. extra kw args given to render_form
        4. field's typed value

        values found in 1. and 2. are expected te be already some 'display'
        value while those found in 3. and 4. are expected to be correctly typed.
        """
        value = self._req_display_value(field)
        if value is None:
            if field.name in rendervalues:
                value = rendervalues[field.name]
            else:
                value = self.form_field_value(field, load_bytes)
                if callable(value):
                    value = value(self)
            if value != INTERNAL_FIELD_VALUE:
                value = field.format_value(self.req, value)
        return value

    def _req_display_value(self, field):
        qname = self.form_field_name(field)
        if qname in self.form_previous_values:
            return self.form_previous_values[qname]
        if qname in self.req.form:
            return self.req.form[qname]
        if field.name in self.req.form:
            return self.req.form[field.name]
        return None

    def form_field_value(self, field, load_bytes=False):
        """return field's *typed* value"""
        myattr = '%s_%s_default' % (field.role, field.name)
        if hasattr(self, myattr):
            return getattr(self, myattr)()
        value = field.initial
        if callable(value):
            value = value(self)
        return value

    def form_field_error(self, field):
        """return validation error for widget's field, if any"""
        if self._field_has_error(field):
            self.form_displayed_errors.add(field.name)
            return u'<span class="error">%s</span>' % self.form_valerror.errors[field.name]
        return u''

    def form_field_format(self, field):
        """return MIME type used for the given (text or bytes) field"""
        return self.req.property_value('ui.default-text-format')

    def form_field_encoding(self, field):
        """return encoding used for the given (text) field"""
        return self.req.encoding

    def form_field_name(self, field):
        """return qualified name for the given field"""
        return field.name

    def form_field_id(self, field):
        """return dom id for the given field"""
        return field.id

    def form_field_vocabulary(self, field, limit=None):
        """return vocabulary for the given field. Should be overriden in
        specific forms using fields which requires some vocabulary
        """
        raise NotImplementedError

    def _field_has_error(self, field):
        """return true if the field has some error in given validation exception
        """
        return self.form_valerror and field.name in self.form_valerror.errors


class EntityFieldsForm(FieldsForm):
    __regid__ = 'base'
    __select__ = (match_kwargs('entity')
                  | (one_line_rset() & non_final_entity()))

    internal_fields = FieldsForm.internal_fields + ('__type', 'eid', '__maineid')
    domid = 'entityForm'

    def __init__(self, *args, **kwargs):
        self.edited_entity = kwargs.pop('entity', None)
        msg = kwargs.pop('submitmsg', None)
        super(EntityFieldsForm, self).__init__(*args, **kwargs)
        if self.edited_entity is None:
            self.edited_entity = self.complete_entity(self.row or 0, self.col or 0)
        self.form_add_hidden('__type', eidparam=True)
        self.form_add_hidden('eid')
        if kwargs.get('mainform', True): # mainform default to true in parent
            self.form_add_hidden(u'__maineid', self.edited_entity.eid)
            # If we need to directly attach the new object to another one
            if self.req.list_form_param('__linkto'):
                for linkto in self.req.list_form_param('__linkto'):
                    self.form_add_hidden('__linkto', linkto)
                if msg:
                    msg = '%s %s' % (msg, self.req._('and linked'))
                else:
                    msg = self.req._('entity linked')
        if msg:
            self.form_add_hidden('__message', msg)

    def _field_has_error(self, field):
        """return true if the field has some error in given validation exception
        """
        return super(EntityFieldsForm, self)._field_has_error(field) \
               and self.form_valerror.eid == self.edited_entity.eid

    def _relation_vocabulary(self, rtype, targettype, role,
                            limit=None, done=None):
        """return unrelated entities for a given relation and target entity type
        for use in vocabulary
        """
        if done is None:
            done = set()
        rset = self.edited_entity.unrelated(rtype, targettype, role, limit)
        res = []
        for entity in rset.entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            res.append((entity.view('combobox'), entity.eid))
        return res

    def _req_display_value(self, field):
        value = super(EntityFieldsForm, self)._req_display_value(field)
        if value is None:
            value = self.edited_entity.linked_to(field.name, field.role)
            if value:
                searchedvalues = ['%s:%s:%s' % (field.name, eid, field.role)
                                  for eid in value]
                # remove associated __linkto hidden fields
                for field in self.fields_by_name('__linkto'):
                    if field.initial in searchedvalues:
                        self.remove_field(field)
            else:
                value = None
        return value

    def _form_field_default_value(self, field, load_bytes):
        defaultattr = 'default_%s' % field.name
        if hasattr(self.edited_entity, defaultattr):
            # XXX bw compat, default_<field name> on the entity
            warn('found %s on %s, should be set on a specific form'
                 % (defaultattr, self.edited_entity.id), DeprecationWarning)
            value = getattr(self.edited_entity, defaultattr)
            if callable(value):
                value = value()
        else:
            value = super(EntityFieldsForm, self).form_field_value(field,
                                                                   load_bytes)
        return value

    def form_default_renderer(self):
        return self.vreg['formrenderers'].select(
            self.form_renderer_id, self.req, rset=self.rset, row=self.row,
            col=self.col, entity=self.edited_entity)

    def form_build_context(self, values=None):
        """overriden to add edit[s|o] hidden fields and to ensure schema fields
        have eidparam set to True

        edit[s|o] hidden fields are used to indicate the value for the
        associated field before the (potential) modification made when
        submitting the form.
        """
        eschema = self.edited_entity.e_schema
        for field in self.fields[:]:
            for field in field.actual_fields(self):
                fieldname = field.name
                if fieldname != 'eid' and (
                    (eschema.has_subject_relation(fieldname) or
                     eschema.has_object_relation(fieldname))):
                    field.eidparam = True
                    self.fields.append(HiddenInitialValueField(field))
        return super(EntityFieldsForm, self).form_build_context(values)

    def form_field_value(self, field, load_bytes=False):
        """return field's *typed* value

        overriden to deal with
        * special eid / __type / edits- / edito- fields
        * lookup for values on edited entities
        """
        attr = field.name
        entity = self.edited_entity
        if attr == 'eid':
            return entity.eid
        if not field.eidparam:
            return super(EntityFieldsForm, self).form_field_value(field, load_bytes)
        if attr.startswith('edits-') or attr.startswith('edito-'):
            # edit[s|o]- fieds must have the actual value stored on the entity
            assert hasattr(field, 'visible_field')
            vfield = field.visible_field
            assert vfield.eidparam
            if entity.has_eid():
                return self.form_field_value(vfield)
            return INTERNAL_FIELD_VALUE
        if attr == '__type':
            return entity.id
        if self.schema.rschema(attr).is_final():
            attrtype = entity.e_schema.destination(attr)
            if attrtype == 'Password':
                return entity.has_eid() and INTERNAL_FIELD_VALUE or ''
            if attrtype == 'Bytes':
                if entity.has_eid():
                    if load_bytes:
                        return getattr(entity, attr)
                    # XXX value should reflect if some file is already attached
                    return True
                return False
            if entity.has_eid() or attr in entity:
                value = getattr(entity, attr)
            else:
                value = self._form_field_default_value(field, load_bytes)
            return value
        # non final relation field
        if entity.has_eid() or entity.relation_cached(attr, field.role):
            value = [r[0] for r in entity.related(attr, field.role)]
        else:
            value = self._form_field_default_value(field, load_bytes)
        return value

    def form_field_format(self, field):
        """return MIME type used for the given (text or bytes) field"""
        entity = self.edited_entity
        if field.eidparam and entity.e_schema.has_metadata(field.name, 'format') and (
            entity.has_eid() or '%s_format' % field.name in entity):
            return self.edited_entity.attr_metadata(field.name, 'format')
        return self.req.property_value('ui.default-text-format')

    def form_field_encoding(self, field):
        """return encoding used for the given (text) field"""
        entity = self.edited_entity
        if field.eidparam and entity.e_schema.has_metadata(field.name, 'encoding') and (
            entity.has_eid() or '%s_encoding' % field.name in entity):
            return self.edited_entity.attr_metadata(field.name, 'encoding')
        return super(EntityFieldsForm, self).form_field_encoding(field)

    def form_field_name(self, field):
        """return qualified name for the given field"""
        if field.eidparam:
            return eid_param(field.name, self.edited_entity.eid)
        return field.name

    def form_field_id(self, field):
        """return dom id for the given field"""
        if field.eidparam:
            return eid_param(field.id, self.edited_entity.eid)
        return field.id

    def form_field_vocabulary(self, field, limit=None):
        """return vocabulary for the given field"""
        role, rtype = field.role, field.name
        method = '%s_%s_vocabulary' % (role, rtype)
        try:
            vocabfunc = getattr(self, method)
        except AttributeError:
            try:
                # XXX bw compat, <role>_<rtype>_vocabulary on the entity
                vocabfunc = getattr(self.edited_entity, method)
            except AttributeError:
                vocabfunc = getattr(self, '%s_relation_vocabulary' % role)
            else:
                warn('found %s on %s, should be set on a specific form'
                     % (method, self.edited_entity.id), DeprecationWarning)
        # NOTE: it is the responsibility of `vocabfunc` to sort the result
        #       (direclty through RQL or via a python sort). This is also
        #       important because `vocabfunc` might return a list with
        #       couples (label, None) which act as separators. In these
        #       cases, it doesn't make sense to sort results afterwards.
        return vocabfunc(rtype, limit)

    # XXX should be on the field, no?
    def subject_relation_vocabulary(self, rtype, limit=None):
        """defaut vocabulary method for the given relation, looking for
        relation's object entities (i.e. self is the subject)
        """
        entity = self.edited_entity
        if isinstance(rtype, basestring):
            rtype = entity.schema.rschema(rtype)
        done = None
        assert not rtype.is_final(), rtype
        if entity.has_eid():
            done = set(e.eid for e in getattr(entity, str(rtype)))
        result = []
        rsetsize = None
        for objtype in rtype.objects(entity.e_schema):
            if limit is not None:
                rsetsize = limit - len(result)
            result += self._relation_vocabulary(rtype, objtype, 'subject',
                                                rsetsize, done)
            if limit is not None and len(result) >= limit:
                break
        return result

    def object_relation_vocabulary(self, rtype, limit=None):
        """defaut vocabulary method for the given relation, looking for
        relation's subject entities (i.e. self is the object)
        """
        entity = self.edited_entity
        if isinstance(rtype, basestring):
            rtype = entity.schema.rschema(rtype)
        done = None
        if entity.has_eid():
            done = set(e.eid for e in getattr(entity, 'reverse_%s' % rtype))
        result = []
        rsetsize = None
        for subjtype in rtype.subjects(entity.e_schema):
            if limit is not None:
                rsetsize = limit - len(result)
            result += self._relation_vocabulary(rtype, subjtype, 'object',
                                                rsetsize, done)
            if limit is not None and len(result) >= limit:
                break
        return result

    def srelations_by_category(self, categories=None, permission=None,
                               strict=False):
        return ()

    def should_display_add_new_relation_link(self, rschema, existant, card):
        return False


class CompositeForm(FieldsForm):
    """form composed of sub-forms"""
    __regid__ = 'composite'
    form_renderer_id = id

    def __init__(self, *args, **kwargs):
        super(CompositeForm, self).__init__(*args, **kwargs)
        self.forms = []

    def form_add_subform(self, subform):
        """mark given form as a subform and append it"""
        subform.is_subform = True
        self.forms.append(subform)


class CompositeEntityForm(EntityFieldsForm):
    """form composed of sub-forms"""
    __regid__ = 'composite'
    form_renderer_id = id

    def __init__(self, *args, **kwargs):
        super(CompositeEntityForm, self).__init__(*args, **kwargs)
        self.forms = []

    def form_add_subform(self, subform):
        """mark given form as a subform and append it"""
        subform.is_subform = True
        self.forms.append(subform)
