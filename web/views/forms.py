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
Base form classes
-----------------

.. Note:

   Form is the glue that bind a context to a set of fields, and is rendered
   using a form renderer. No display is actually done here, though you'll find
   some attributes of form that are used to control the rendering process.

Besides the automagic form we'll see later, they are barely two form
classes in |cubicweb|:

.. autoclass:: cubicweb.web.views.forms.FieldsForm
.. autoclass:: cubicweb.web.views.forms.EntityFieldsForm

As you have probably guessed, choosing between them is easy. Simply ask you the
question 'I am editing an entity or not?'. If the answer is yes, use
:class:`EntityFieldsForm`, else use :class:`FieldsForm`.

Actually there exists a third form class:

.. autoclass:: cubicweb.web.views.forms.CompositeForm

but you'll use this one rarely.
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.decorators import iclassmethod
from logilab.common.compat import any
from logilab.common.deprecation import deprecated

from cubicweb import typed_eid
from cubicweb.selectors import non_final_entity, match_kwargs, one_line_rset
from cubicweb.web import uicfg, form, formwidgets as fwdgs
from cubicweb.web.formfields import relvoc_unrelated, guess_field


class FieldsForm(form.Form):
    """This is the base class for fields based forms.

    **Attributes**

    The following attributes may be either set on subclasses or given on
    form selection to customize the generated form:

    :attr:`needs_js`
      sequence of javascript files that should be added to handle this form
      (through :meth:`~cubicweb.web.request.Request.add_js`)

    :attr:`needs_css`
      sequence of css files that should be added to handle this form (through
      :meth:`~cubicweb.web.request.Request.add_css`)

    :attr:`domid`
      value for the "id" attribute of the <form> tag

    :attr:`action`
      value for the "action" attribute of the <form> tag

    :attr:`onsubmit`
      value for the "onsubmit" attribute of the <form> tag

    :attr:`cssclass`
      value for the "class" attribute of the <form> tag

    :attr:`cssstyle`
      value for the "style" attribute of the <form> tag

    :attr:`cwtarget`
      value for the "cubicweb:target" attribute of the <form> tag

    :attr:`redirect_path`
      relative to redirect to after submitting the form

    :attr:`copy_nav_params`
      flag telling if navigation parameters should be copied back in hidden
      inputs

    :attr:`form_buttons`
      sequence of form control (:class:`~cubicweb.web.formwidgets.Button`
      widgets instances)

    :attr:`form_renderer_id`
      identifier of the form renderer to use to render the form

    :attr:`fieldsets_in_order`
      sequence of fieldset names , to control order

    **Generic methods**

    .. automethod:: cubicweb.web.form.Form.field_by_name(name, role=None)
    .. automethod:: cubicweb.web.form.Form.fields_by_name(name, role=None)

    **Form construction methods**

    .. automethod:: cubicweb.web.form.Form.remove_field(field)
    .. automethod:: cubicweb.web.form.Form.append_field(field)
    .. automethod:: cubicweb.web.form.Form.insert_field_before(field, name, role=None)
    .. automethod:: cubicweb.web.form.Form.insert_field_after(field, name, role=None)
    .. automethod:: cubicweb.web.form.Form.add_hidden(name, value=None, **kwargs)

    **Form rendering methods**

    .. automethod:: cubicweb.web.views.forms.FieldsForm.render

    """
    __regid__ = 'base'


    # attributes overrideable by subclasses or through __init__
    needs_js = ('cubicweb.ajax.js', 'cubicweb.edition.js',)
    needs_css = ('cubicweb.form.css',)
    action = None
    onsubmit = "return freezeFormButtons('%(domid)s');"
    cssclass = None
    cssstyle = None
    cwtarget = None
    redirect_path = None
    form_buttons = None
    form_renderer_id = 'default'
    fieldsets_in_order = None

    @property
    def needs_multipart(self):
        """true if the form needs enctype=multipart/form-data"""
        return any(field.needs_multipart for field in self.fields)

    def add_media(self):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            self._cw.add_js(self.needs_js)
        if self.needs_css:
            self._cw.add_css(self.needs_css)

    def render(self, formvalues=None, rendervalues=None, renderer=None, **kwargs):
        """Render this form, using the `renderer` given as argument or the
        default according to :attr:`form_renderer_id`. The rendered form is
        returned as an unicode string.

        `formvalues` is an optional dictionary containing values that will be
        considered as field's value.

        Extra keyword arguments will be given to renderer's :meth:`render` method.

        `rendervalues` is deprecated.
        """
        if rendervalues is not None:
            warn('[3.6] rendervalues argument is deprecated, all named arguments will be given instead',
                 DeprecationWarning, stacklevel=2)
            kwargs = rendervalues
        self.build_context(formvalues)
        if renderer is None:
            renderer = self.default_renderer()
        return renderer.render(self, kwargs)

    def default_renderer(self):
        return self._cw.vreg['formrenderers'].select(
            self.form_renderer_id, self._cw,
            rset=self.cw_rset, row=self.cw_row, col=self.cw_col or 0)

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
            renderer = self.default_renderer()
        return renderer.render(self, values)


_AFF = uicfg.autoform_field
_AFF_KWARGS = uicfg.autoform_field_kwargs

class EntityFieldsForm(FieldsForm):
    """This class is designed for forms used to edit some entities. It should
    handle for you all the underlying stuff necessary to properly work with the
    generic :class:`~cubicweb.web.views.editcontroller.EditController`.
    """

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

    def __init__(self, _cw, rset=None, row=None, col=None, **kwargs):
        try:
            self.edited_entity = kwargs.pop('entity')
        except KeyError:
            self.edited_entity = rset.complete_entity(row or 0, col or 0)
        msg = kwargs.pop('submitmsg', None)
        super(EntityFieldsForm, self).__init__(_cw, rset, row, col, **kwargs)
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
        # XXX we should not consider some url parameters that may lead to
        # different url after a validation error
        return '%s#%s' % (self._cw.url(), self.domid)

    def build_context(self, formvalues=None):
        if self.formvalues is not None:
            return # already built
        super(EntityFieldsForm, self).build_context(formvalues)
        edited = set()
        for field in self.fields:
            if field.eidparam:
                edited.add(field.role_name())
        self.add_hidden('_cw_edited_fields', u','.join(edited), eidparam=True)

    def default_renderer(self):
        return self._cw.vreg['formrenderers'].select(
            self.form_renderer_id, self._cw, rset=self.cw_rset, row=self.cw_row,
            col=self.cw_col, entity=self.edited_entity)

    def should_display_add_new_relation_link(self, rschema, existant, card):
        return False

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
    """Form composed of sub-forms. Typical usage is edition of multiple entities
    at once.
    """

class CompositeEntityForm(CompositeFormMixIn, EntityFieldsForm):
    pass # XXX why is this class necessary?
