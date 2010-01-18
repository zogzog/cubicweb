"""some base form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.decorators import iclassmethod
from logilab.common.compat import any
from logilab.common.deprecation import deprecated

from cubicweb import typed_eid
from cubicweb.selectors import non_final_entity, match_kwargs, one_line_rset
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param
from cubicweb.web import uicfg, form, formwidgets as fwdgs
from cubicweb.web.controller import NAV_FORM_PARAMETERS
from cubicweb.web.formfields import StringField, relvoc_unrelated, guess_field


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
                self.add_hidden(key, val)
            elif hasattr(self.__class__, key) and not key[0] == '_':
                setattr(self, key, val)
            else:
                self.cw_extra_kwargs[key] = val
            # skip other parameters, usually given for selection
            # (else write a custom class to handle them)
        if mainform:
            self.add_hidden('__errorurl', self.session_key())
            self.add_hidden('__domid', self.domid)
            self.restore_previous_post(self.session_key())

        # XXX why do we need two different variables (mainform and copy_nav_params ?)
        if self.copy_nav_params:
            for param in NAV_FORM_PARAMETERS:
                if not param in kwargs:
                    value = req.form.get(param)
                    if value:
                        self.add_hidden(param, value)
        if submitmsg is not None:
            self.add_hidden('__message', submitmsg)
        if 'domid' in kwargs:# session key changed
            self.restore_previous_post(self.session_key())

    @property
    def needs_multipart(self):
        """true if the form needs enctype=multipart/form-data"""
        return any(field.needs_multipart for field in self.fields)

    def add_hidden(self, name, value=None, **kwargs):
        """add an hidden field to the form"""
        kwargs.setdefault('widget', fwdgs.HiddenInput)
        field = StringField(name=name, value=value, **kwargs)
        if 'id' in kwargs:
            # by default, hidden input don't set id attribute. If one is
            # explicitly specified, ensure it will be set
            field.widget.setdomid = True
        self.append_field(field)
        return field

    def add_media(self):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            self._cw.add_js(self.needs_js)
        if self.needs_css:
            self._cw.add_css(self.needs_css)

    def render(self, formvalues=None, rendervalues=None, renderer=None, **kwargs):
        """render this form, using the renderer given in args or the default
        FormRenderer()
        """
        if rendervalues is not None:
            warn('[3.6] rendervalues argument is deprecated, all named arguments will be given instead',
                 DeprecationWarning, stacklevel=1)
            kwargs = rendervalues
        self.build_context(formvalues)
        if renderer is None:
            renderer = self.default_renderer()
        return renderer.render(self, kwargs)

    def default_renderer(self):
        return self._cw.vreg['formrenderers'].select(
            self.form_renderer_id, self._cw,
            rset=self.cw_rset, row=self.cw_row, col=self.cw_col)

    formvalues = None
    def build_context(self, formvalues=None):
        """build form context values (the .context attribute which is a
        dictionary with field instance as key associated to a dictionary
        containing field 'name' (qualified), 'id', 'value' (for display, always
        a string).
        """
        if self.formvalues is not None:
            return # already built
        self.formvalues = formvalues or {}
        # use a copy in case fields are modified while context is build (eg
        # __linkto handling for instance)
        for field in self.fields[:]:
            for field in field.actual_fields(self):
                field.form_init(self)

    @deprecated('[3.6] use .add_hidden(name, value, **kwargs)')
    def form_add_hidden(self, name, value=None, **kwargs):
        return self.add_hidden(name, value, **kwargs)

    @deprecated('[3.6] use .render(formvalues, **rendervalues)')
    def form_render(self, **values):
        """render this form, using the renderer given in args or the default
        FormRenderer()
        """
        self.build_context(values)
        renderer = values.pop('renderer', None)
        if renderer is None:
            renderer = self.form_default_renderer()
        return renderer.render(self, values)

_AFF = uicfg.autoform_field
_AFF_KWARGS = uicfg.autoform_field_kwargs

class EntityFieldsForm(FieldsForm):
    __regid__ = 'base'
    __select__ = (match_kwargs('entity')
                  | (one_line_rset() & non_final_entity()))

    internal_fields = FieldsForm.internal_fields + ('__type', 'eid', '__maineid')
    domid = 'entityForm'

    @iclassmethod
    def field_by_name(cls_or_self, name, role=None, eschema=None):
        """return field with the given name and role. If field is not explicitly
        defined for the form but `eclass` is specified, guess_field will be
        called.
        """
        try:
            return super(EntityFieldsForm, cls_or_self).field_by_name(name, role)
        except form.FieldNotFound:
            if eschema is None or role is None or not name in eschema.schema:
                raise
            rschema = eschema.schema.rschema(name)
            # XXX use a sample target type. Document this.
            tschemas = rschema.targets(eschema, role)
            fieldcls = _AFF.etype_get(eschema, rschema, role, tschemas[0])
            kwargs = _AFF_KWARGS.etype_get(eschema, rschema, role, tschemas[0])
            if kwargs is None:
                kwargs = {}
            if fieldcls:
                if not isinstance(fieldcls, type):
                    return fieldcls # already and instance
                return fieldcls(name=name, role=role, eidparam=True, **kwargs)
            field = guess_field(eschema, rschema, role, eidparam=True, **kwargs)
            if field is None:
                raise
            return field

    def __init__(self, *args, **kwargs):
        self.edited_entity = kwargs.pop('entity', None)
        msg = kwargs.pop('submitmsg', None)
        super(EntityFieldsForm, self).__init__(*args, **kwargs)
        if self.edited_entity is None:
            self.edited_entity = self.cw_rset.complete_entity(self.cw_row or 0, self.cw_col or 0)
        self.add_hidden('__type', self.edited_entity.__regid__, eidparam=True)
        self.add_hidden('eid', self.edited_entity.eid)
        if kwargs.get('mainform', True): # mainform default to true in parent
            self.add_hidden(u'__maineid', self.edited_entity.eid)
            # If we need to directly attach the new object to another one
            if self._cw.list_form_param('__linkto'):
                for linkto in self._cw.list_form_param('__linkto'):
                    self.add_hidden('__linkto', linkto)
                if msg:
                    msg = '%s %s' % (msg, self._cw._('and linked'))
                else:
                    msg = self._cw._('entity linked')
        if msg:
            self.add_hidden('__message', msg)

    def session_key(self):
        """return the key that may be used to store / retreive data about a
        previous post which failed because of a validation error
        """
        if self.force_session_key is not None:
            return self.force_session_key
        # XXX if this is a json request, suppose we should redirect to the
        # entity primary view
        if self._cw.json_request and self.edited_entity.has_eid():
            return '%s#%s' % (self.edited_entity.absolute_url(), self.domid)
        return '%s#%s' % (self._cw.url(), self.domid)

    def build_context(self, formvalues=None):
        if self.formvalues is not None:
            return # already built
        super(EntityFieldsForm, self).build_context(formvalues)
        edited = set()
        for field in self.fields:
            if field.eidparam:
                edited.add(field.role_name())
        self.add_hidden('_cw_edited_fields', u','.join(edited),
                        eidparam=True)

    def default_renderer(self):
        return self._cw.vreg['formrenderers'].select(
            self.form_renderer_id, self._cw, rset=self.cw_rset, row=self.cw_row,
            col=self.cw_col, entity=self.edited_entity)

    # controller side method (eg POST reception handling)

    def actual_eid(self, eid):
        # should be either an int (existant entity) or a variable (to be
        # created entity)
        assert eid or eid == 0, repr(eid) # 0 is a valid eid
        try:
            return typed_eid(eid)
        except ValueError:
            try:
                return self._cw.data['eidmap'][eid]
            except KeyError:
                self._cw.data['eidmap'][eid] = None
                return None

    def editable_relations(self):
        return ()

    def should_display_add_new_relation_link(self, rschema, existant, card):
        return False

    @deprecated('[3.6] use cw.web.formfields.relvoc_unrelated function')
    def subject_relation_vocabulary(self, rtype, limit=None):
        """defaut vocabulary method for the given relation, looking for
        relation's object entities (i.e. self is the subject)
        """
        return relvoc_unrelated(self.edited_entity, rtype, 'subject', limit=None)

    @deprecated('[3.6] use cw.web.formfields.relvoc_unrelated function')
    def object_relation_vocabulary(self, rtype, limit=None):
        return relvoc_unrelated(self.edited_entity, rtype, 'object', limit=None)


class CompositeFormMixIn(object):
    """form composed of sub-forms"""
    __regid__ = 'composite'
    form_renderer_id = __regid__

    def __init__(self, *args, **kwargs):
        super(CompositeFormMixIn, self).__init__(*args, **kwargs)
        self.forms = []

    def add_subform(self, subform):
        """mark given form as a subform and append it"""
        subform.parent_form = self
        self.forms.append(subform)

    def build_context(self, formvalues=None):
        super(CompositeFormMixIn, self).build_context(formvalues)
        for form in self.forms:
            form.build_context(formvalues)


class CompositeForm(CompositeFormMixIn, FieldsForm):
    pass

class CompositeEntityForm(CompositeFormMixIn, EntityFieldsForm):
    pass # XXX why is this class necessary?
