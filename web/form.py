"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.compat import any
from logilab.common.decorators import iclassmethod

from cubicweb.appobject import AppRsetObject
from cubicweb.selectors import yes, non_final_entity, match_kwargs, one_line_rset
from cubicweb.view import NOINDEX, NOFOLLOW
from cubicweb.common import tags
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param, stdmsgs
from cubicweb.web.httpcache import NoHTTPCacheManager
from cubicweb.web.controller import NAV_FORM_PARAMETERS
from cubicweb.web.formfields import (Field, StringField, RelationField,
                                     HiddenInitialValueField)
from cubicweb.web import formrenderers
from cubicweb.web import formwidgets as fwdgs

class FormViewMixIn(object):
    """abstract form view mix-in"""
    category = 'form'
    controller = 'edit'
    http_cache_manager = NoHTTPCacheManager
    add_to_breadcrumbs = False

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default forms are neither indexed nor followed
        """
        return [NOINDEX, NOFOLLOW]

    def linkable(self):
        """override since forms are usually linked by an action,
        so we don't want them to be listed by appli.possible_views
        """
        return False


# XXX should disappear
class FormMixIn(object):
    """abstract form mix-in
    XXX: you should inherit from this FIRST (obscure pb with super call)
    """

    def initialize_varmaker(self):
        varmaker = self.req.get_page_data('rql_varmaker')
        if varmaker is None:
            varmaker = self.req.varmaker
            self.req.set_page_data('rql_varmaker', varmaker)
        self.varmaker = varmaker

    def session_key(self):
        """return the key that may be used to store / retreive data about a
        previous post which failed because of a validation error
        """
        return '%s#%s' % (self.req.url(), self.domid)

    def __init__(self, req, rset, **kwargs):
        super(FormMixIn, self).__init__(req, rset, **kwargs)
        self.restore_previous_post(self.session_key())

    def restore_previous_post(self, sessionkey):
        # get validation session data which may have been previously set.
        # deleting validation errors here breaks form reloading (errors are
        # no more available), they have to be deleted by application's publish
        # method on successful commit
        forminfo = self.req.get_session_data(sessionkey, pop=True)
        if forminfo:
            # XXX remove req.data assigment once cw.web.widget is killed
            self.req.data['formvalues'] = self.form_previous_values = forminfo['values']
            self.req.data['formerrors'] = self.form_valerror = forminfo['errors']
            self.req.data['displayederrors'] = self.form_displayed_errors = set()
            # if some validation error occured on entity creation, we have to
            # get the original variable name from its attributed eid
            foreid = self.form_valerror.entity
            for var, eid in forminfo['eidmap'].items():
                if foreid == eid:
                    self.form_valerror.eid = var
                    break
            else:
                self.form_valerror.eid = foreid
        else:
            self.form_previous_values = {}
            self.form_valerror = None

    # XXX deprecated with new form system. Should disappear

    domid = 'entityForm'
    category = 'form'
    controller = 'edit'
    http_cache_manager = NoHTTPCacheManager
    add_to_breadcrumbs = False

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default forms are neither indexed nor followed
        """
        return [NOINDEX, NOFOLLOW]

    def linkable(self):
        """override since forms are usually linked by an action,
        so we don't want them to be listed by appli.possible_views
        """
        return False


    def button(self, label, klass='validateButton', tabindex=None, **kwargs):
        if tabindex is None:
            tabindex = self.req.next_tabindex()
        return tags.input(value=label, klass=klass, **kwargs)

    def action_button(self, label, onclick=None, __action=None, **kwargs):
        if onclick is None:
            onclick = "postForm('__action_%s', \'%s\', \'%s\')" % (
                __action, label, self.domid)
        return self.button(label, onclick=onclick, **kwargs)

    def button_ok(self, label=None, type='submit', name='defaultsubmit',
                  **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_OK).capitalize()
        return self.button(label, name=name, type=type, **kwargs)

    def button_apply(self, label=None, type='button', **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_APPLY).capitalize()
        return self.action_button(label, __action='apply', type=type, **kwargs)

    def button_delete(self, label=None, type='button', **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_DELETE).capitalize()
        return self.action_button(label, __action='delete', type=type, **kwargs)

    def button_cancel(self, label=None, type='button', **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.action_button(label, __action='cancel', type=type, **kwargs)

    def button_reset(self, label=None, type='reset', name='__action_cancel',
                     **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.button(label, type=type, **kwargs)

    def need_multipart(self, entity, categories=('primary', 'secondary')):
        """return a boolean indicating if form's enctype should be multipart
        """
        for rschema, _, x in entity.relations_by_category(categories):
            if entity.get_widget(rschema, x).need_multipart:
                return True
        # let's find if any of our inlined entities needs multipart
        for rschema, targettypes, x in entity.relations_by_category('inlineview'):
            assert len(targettypes) == 1, \
                   "I'm not able to deal with several targets and inlineview"
            ttype = targettypes[0]
            inlined_entity = self.vreg.etype_class(ttype)(self.req, None, None)
            for irschema, _, x in inlined_entity.relations_by_category(categories):
                if inlined_entity.get_widget(irschema, x).need_multipart:
                    return True
        return False

    def error_message(self):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        errex = self.req.data.get('formerrors') or self.form_valerror
        # get extra errors
        if errex is not None:
            errormsg = self.req._('please correct the following errors:')
            displayed = self.req.data.get('displayederrors') or self.form_displayed_errors
            errors = sorted((field, err) for field, err in errex.errors.items()
                            if not field in displayed)
            if errors:
                if len(errors) > 1:
                    templstr = '<li>%s</li>\n'
                else:
                    templstr = '&nbsp;%s\n'
                for field, err in errors:
                    if field is None:
                        errormsg += templstr % err
                    else:
                        errormsg += templstr % '%s: %s' % (self.req._(field), err)
                if len(errors) > 1:
                    errormsg = '<ul>%s</ul>' % errormsg
            return u'<div class="errorMessage">%s</div>' % errormsg
        return u''


###############################################################################

class metafieldsform(type):
    """metaclass for FieldsForm to retrieve fields defined as class attributes
    and put them into a single ordered list: '_fields_'.
    """
    def __new__(mcs, name, bases, classdict):
        allfields = []
        for base in bases:
            if hasattr(base, '_fields_'):
                allfields += base._fields_
        clsfields = (item for item in classdict.items()
                     if isinstance(item[1], Field))
        for fieldname, field in sorted(clsfields, key=lambda x: x[1].creation_rank):
            if not field.name:
                field.set_name(fieldname)
            allfields.append(field)
        classdict['_fields_'] = allfields
        return super(metafieldsform, mcs).__new__(mcs, name, bases, classdict)


class FieldNotFound(Exception):
    """raised by field_by_name when a field with the given name has not been
    found
    """

class FieldsForm(FormMixIn, AppRsetObject):
    __metaclass__ = metafieldsform
    __registry__ = 'forms'
    __select__ = yes()

    renderer_cls = formrenderers.FormRenderer
    is_subform = False

    # attributes overrideable through __init__
    internal_fields = ('__errorurl',) + NAV_FORM_PARAMETERS
    needs_js = ('cubicweb.ajax.js', 'cubicweb.edition.js',)
    needs_css = ('cubicweb.form.css',)
    domid = 'form'
    title = None
    action = None
    onsubmit = "return freezeFormButtons('%(domid)s');"
    cssclass = None
    cssstyle = None
    cwtarget = None
    redirect_path = None
    set_error_url = True
    copy_nav_params = False
    form_buttons = None # form buttons (button widgets instances)

    def __init__(self, req, rset=None, row=None, col=None, submitmsg=None,
                 **kwargs):
        super(FieldsForm, self).__init__(req, rset, row=row, col=col)
        self.fields = list(self.__class__._fields_)
        for key, val in kwargs.items():
            if key in NAV_FORM_PARAMETERS:
                self.form_add_hidden(key, val)
            else:
                assert hasattr(self.__class__, key) and not key[0] == '_', key
                setattr(self, key, val)
        if self.set_error_url:
            self.form_add_hidden('__errorurl', self.session_key())
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
    def field_by_name(cls_or_self, name, role='subject'):
        """return field with the given name and role"""
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        for field in fields:
            if field.name == name and field.role == role:
                return field
        raise FieldNotFound(name)

    @iclassmethod
    def remove_field(cls_or_self, field):
        """remove a field from form class or instance"""
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        fields.remove(field)

    @iclassmethod
    def append_field(cls_or_self, field):
        """append a field to form class or instance"""
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        fields.append(field)

    @property
    def form_needs_multipart(self):
        """true if the form needs enctype=multipart/form-data"""
        return any(field.needs_multipart for field in self.fields)

    def form_add_hidden(self, name, value=None, **kwargs):
        """add an hidden field to the form"""
        field = StringField(name=name, widget=fwdgs.HiddenInput, initial=value,
                            **kwargs)
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
        renderer = values.pop('renderer', self.renderer_cls())
        return renderer.render(self, values)

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
        for field in self.fields:
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
        qname = self.form_field_name(field)
        if qname in self.form_previous_values:
            value = self.form_previous_values[qname]
        elif qname in self.req.form:
            value = self.req.form[qname]
        else:
            if field.name in rendervalues:
                value = rendervalues[field.name]
            else:
                value = self.form_field_value(field, load_bytes)
                if callable(value):
                    value = value(self)
            if value != INTERNAL_FIELD_VALUE:
                value = field.format_value(self.req, value)
        return value

    def form_field_value(self, field, load_bytes=False):
        """return field's *typed* value"""
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
    __select__ = (match_kwargs('entity') | (one_line_rset & non_final_entity()))

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
        if msg is not None:
            # If we need to directly attach the new object to another one
            for linkto in self.req.list_form_param('__linkto'):
                self.form_add_hidden('__linkto', linkto)
                msg = '%s %s' % (msg, self.req._('and linked'))
            self.form_add_hidden('__message', msg)
        # in case of direct instanciation
        self.schema = self.edited_entity.schema
        self.vreg = self.edited_entity.vreg

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

    def subject_in_state_vocabulary(self, rtype, limit=None):
        """vocabulary method for the in_state relation, looking for relation's
        object entities (i.e. self is the subject) according to initial_state,
        state_of and next_state relation
        """
        entity = self.edited_entity
        if not entity.has_eid() or not entity.in_state:
            # get the initial state
            rql = 'Any S where S state_of ET, ET name %(etype)s, ET initial_state S'
            rset = self.req.execute(rql, {'etype': str(entity.e_schema)})
            if rset:
                return [(rset.get_entity(0, 0).view('combobox'), rset[0][0])]
            return []
        results = []
        for tr in entity.in_state[0].transitions(entity):
            state = tr.destination_state[0]
            results.append((state.view('combobox'), state.eid))
        return sorted(results)


class CompositeForm(FieldsForm):
    """form composed for sub-forms"""

    def __init__(self, *args, **kwargs):
        super(CompositeForm, self).__init__(*args, **kwargs)
        self.forms = []

    def form_add_subform(self, subform):
        """mark given form as a subform and append it"""
        subform.is_subform = True
        self.forms.append(subform)
