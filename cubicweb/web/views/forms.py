# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

Besides the automagic form we'll see later, there are roughly two main
form classes in |cubicweb|:

.. autoclass:: cubicweb.web.views.forms.FieldsForm
.. autoclass:: cubicweb.web.views.forms.EntityFieldsForm

As you have probably guessed, choosing between them is easy. Simply ask you the
question 'I am editing an entity or not?'. If the answer is yes, use
:class:`EntityFieldsForm`, else use :class:`FieldsForm`.

Actually there exists a third form class:

.. autoclass:: cubicweb.web.views.forms.CompositeForm

but you'll use this one rarely.
"""

import time
import inspect

from logilab.common import dictattr, tempattr
from logilab.common.decorators import iclassmethod, cached
from logilab.common.textutils import splitstrip

from cubicweb import ValidationError, neg_role
from cubicweb.predicates import non_final_entity, match_kwargs, one_line_rset
from cubicweb.web import RequestError, ProcessFormError
from cubicweb.web import form
from cubicweb.web.views import uicfg
from cubicweb.web.formfields import guess_field


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
      value for the "target" attribute of the <form> tag

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

    :attr:`autocomplete`
      set to False to add 'autocomplete=off' in the form open tag

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

    **Form posting methods**

    Once a form is posted, you can retrieve the form on the controller side and
    use the following methods to ease processing. For "simple" forms, this
    should looks like :

    .. sourcecode :: python

        form = self._cw.vreg['forms'].select('myformid', self._cw)
        posted = form.process_posted()
        # do something with the returned dictionary

    Notice that form related to entity edition should usually use the
    `edit` controller which will handle all the logic for you.

    .. automethod:: cubicweb.web.views.forms.FieldsForm.process_posted
    .. automethod:: cubicweb.web.views.forms.FieldsForm.iter_modified_fields
    """
    __regid__ = 'base'


    # attributes overrideable by subclasses or through __init__
    needs_js = ('cubicweb.ajax.js', 'cubicweb.edition.js',)
    needs_css = ('cubicweb.form.css',)
    action = None
    cssclass = None
    cssstyle = None
    cwtarget = None
    redirect_path = None
    form_buttons = None
    form_renderer_id = 'default'
    fieldsets_in_order = None
    autocomplete = True

    @property
    def needs_multipart(self):
        """true if the form needs enctype=multipart/form-data"""
        return any(field.needs_multipart for field in self.fields)

    def _get_onsubmit(self):
        try:
            return self._onsubmit
        except AttributeError:
            return "return freezeFormButtons('%(domid)s');" % dictattr(self)

    def _set_onsubmit(self, value):
        self._onsubmit = value

    onsubmit = property(_get_onsubmit, _set_onsubmit)

    def add_media(self):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            self._cw.add_js(self.needs_js)
        if self.needs_css:
            self._cw.add_css(self.needs_css)

    def render(self, formvalues=None, renderer=None, **kwargs):
        """Render this form, using the `renderer` given as argument or the
        default according to :attr:`form_renderer_id`. The rendered form is
        returned as a unicode string.

        `formvalues` is an optional dictionary containing values that will be
        considered as field's value.

        Extra keyword arguments will be given to renderer's :meth:`render` method.
        """
        w = kwargs.pop('w', None)
        self.build_context(formvalues)
        if renderer is None:
            renderer = self.default_renderer()
        renderer.render(w, self, kwargs)

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
            return  # already built
        self.formvalues = formvalues or {}
        # use a copy in case fields are modified while context is built (eg
        # __linkto handling for instance)
        for field in self.fields[:]:
            for field in field.actual_fields(self):
                field.form_init(self)
        # store used field in an hidden input for later usage by a controller
        fields = set()
        eidfields = set()
        for field in self.fields:
            if field.eidparam:
                eidfields.add(field.role_name())
            elif field.name not in self.control_fields:
                fields.add(field.role_name())
        if fields:
            self.add_hidden('_cw_fields', u','.join(fields))
        if eidfields:
            self.add_hidden('_cw_entity_fields', u','.join(eidfields),
                            eidparam=True)

    _default_form_action_path = 'edit'

    def form_action(self):
        action = self.action
        if action is None:
            return self._cw.build_url(self._default_form_action_path)
        return action

    # controller form processing methods #######################################

    def iter_modified_fields(self, editedfields=None, entity=None):
        """return a generator on field that has been modified by the posted
        form.
        """
        if editedfields is None:
            try:
                editedfields = self._cw.form['_cw_fields']
            except KeyError:
                raise RequestError(self._cw._('no edited fields specified'))
        entityform = entity and len(inspect.getargspec(self.field_by_name)) == 4  # XXX
        for editedfield in splitstrip(editedfields):
            try:
                name, role = editedfield.split('-')
            except Exception:
                name = editedfield
                role = None
            if entityform:
                field = self.field_by_name(name, role, eschema=entity.e_schema)
            else:
                field = self.field_by_name(name, role)
            if field.has_been_modified(self):
                yield field

    def process_posted(self):
        """use this method to process the content posted by a simple form.  it
        will return a dictionary with field names as key and typed value as
        associated value.
        """
        with tempattr(self, 'formvalues', {}):  # init fields value cache
            errors = []
            processed = {}
            for field in self.iter_modified_fields():
                try:
                    for field, value in field.process_posted(self):
                        processed[field.role_name()] = value
                except ProcessFormError as exc:
                    errors.append((field, exc))
            if errors:
                errors = dict((f.role_name(), str(ex)) for f, ex in errors)
                raise ValidationError(None, errors)
            return processed


class EntityFieldsForm(FieldsForm):
    """This class is designed for forms used to edit some entities. It should
    handle for you all the underlying stuff necessary to properly work with the
    generic :class:`~cubicweb.web.views.editcontroller.EditController`.
    """

    __regid__ = 'base'
    __select__ = (match_kwargs('entity')
                  | (one_line_rset() & non_final_entity()))
    domid = 'entityForm'
    uicfg_aff = uicfg.autoform_field
    uicfg_affk = uicfg.autoform_field_kwargs

    @iclassmethod
    def field_by_name(cls_or_self, name, role=None, eschema=None):
        """return field with the given name and role. If field is not explicitly
        defined for the form but `eclass` is specified, guess_field will be
        called.
        """
        try:
            return super(EntityFieldsForm, cls_or_self).field_by_name(name, role)
        except form.FieldNotFound:
            if eschema is None or role is None or name not in eschema.schema:
                raise
            rschema = eschema.schema.rschema(name)
            # XXX use a sample target type. Document this.
            tschemas = rschema.targets(eschema, role)
            fieldclass = cls_or_self.uicfg_aff.etype_get(
                eschema, rschema, role, tschemas[0])
            kwargs = cls_or_self.uicfg_affk.etype_get(
                eschema, rschema, role, tschemas[0])
            if kwargs is None:
                kwargs = {}
            if fieldclass:
                if not isinstance(fieldclass, type):
                    return fieldclass  # already an instance
                kwargs['fieldclass'] = fieldclass
            if isinstance(cls_or_self, type):
                req = None
            else:
                req = cls_or_self._cw
            field = guess_field(eschema, rschema, role, req=req, eidparam=True, **kwargs)
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
        self.uicfg_aff = self._cw.vreg['uicfg'].select(
            'autoform_field', self._cw, entity=self.edited_entity)
        self.uicfg_affk = self._cw.vreg['uicfg'].select(
            'autoform_field_kwargs', self._cw, entity=self.edited_entity)
        self.add_hidden('__type', self.edited_entity.cw_etype, eidparam=True)

        self.add_hidden('eid', self.edited_entity.eid)
        self.add_generation_time()
        # mainform default to true in parent, hence default to True
        if kwargs.get('mainform', True) or kwargs.get('mainentity', False):
            self.add_hidden(u'__maineid', self.edited_entity.eid)
            # If we need to directly attach the new object to another one
            if '__linkto' in self._cw.form:
                if msg:
                    msg = '%s %s' % (msg, self._cw._('and linked'))
                else:
                    msg = self._cw._('entity linked')
        if msg:
            msgid = self._cw.set_redirect_message(msg)
            self.add_hidden('_cwmsgid', msgid)

    def add_generation_time(self):
        # use %f to prevent (unlikely) display in exponential format
        self.add_hidden('__form_generation_time', '%.6f' % time.time(),
                        eidparam=True)

    def add_linkto_hidden(self):
        """add the __linkto hidden field used to directly attach the new object
        to an existing other one when the relation between those two is not
        already present in the form.

        Warning: this method must be called only when all form fields are setup
        """
        for (rtype, role), eids in self.linked_to.items():
            # if the relation is already setup by a form field, do not add it
            # in a __linkto hidden to avoid setting it twice in the controller
            try:
                self.field_by_name(rtype, role)
            except form.FieldNotFound:
                for eid in eids:
                    self.add_hidden('__linkto', '%s:%s:%s' % (rtype, eid, role))

    def render(self, *args, **kwargs):
        self.add_linkto_hidden()
        return super(EntityFieldsForm, self).render(*args, **kwargs)

    @property
    @cached
    def linked_to(self):
        linked_to = {}
        # case where this is an embeded creation form
        try:
            eid = int(self.cw_extra_kwargs['peid'])
        except (KeyError, ValueError):
            # When parent is being created, its eid is not numeric (e.g. 'A')
            # hence ValueError.
            pass
        else:
            ltrtype = self.cw_extra_kwargs['rtype']
            ltrole = neg_role(self.cw_extra_kwargs['role'])
            linked_to[(ltrtype, ltrole)] = [eid]
        # now consider __linkto if the current form is the main form
        try:
            self.field_by_name('__maineid')
        except form.FieldNotFound:
            return linked_to
        for linkto in self._cw.list_form_param('__linkto'):
            ltrtype, eid, ltrole = linkto.split(':')
            linked_to.setdefault((ltrtype, ltrole), []).append(int(eid))
        return linked_to

    def session_key(self):
        """return the key that may be used to store / retreive data about a
        previous post which failed because of a validation error
        """
        if self.force_session_key is not None:
            return self.force_session_key
        # XXX if this is a json request, suppose we should redirect to the
        # entity primary view
        if self._cw.ajax_request and self.edited_entity.has_eid():
            return '%s#%s' % (self.edited_entity.absolute_url(), self.domid)
        # XXX we should not consider some url parameters that may lead to
        # different url after a validation error
        return '%s#%s' % (self._cw.url(), self.domid)

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
        assert eid or eid == 0, repr(eid)  # 0 is a valid eid
        try:
            return int(eid)
        except ValueError:
            try:
                return self._cw.data['eidmap'][eid]
            except KeyError:
                self._cw.data['eidmap'][eid] = None
                return None

    def editable_relations(self):
        return ()


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
        for form_ in self.forms:
            form_.build_context(formvalues)


class CompositeForm(CompositeFormMixIn, FieldsForm):
    """Form composed of sub-forms. Typical usage is edition of multiple entities
    at once.
    """


class CompositeEntityForm(CompositeFormMixIn, EntityFieldsForm):
    pass  # XXX why is this class necessary?
