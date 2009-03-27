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
from cubicweb.web.formrenderers import FormRenderer
from cubicweb.web import formwidgets as fwdgs



# XXX should disappear 
class FormMixIn(object):
    """abstract form mix-in
    XXX: you should inherit from this FIRST (obscure pb with super call)"""
    category = 'form'
    controller = 'edit'
    domid = 'entityForm'
    
    http_cache_manager = NoHTTPCacheManager
    add_to_breadcrumbs = False
    skip_relations = set()
    
    def __init__(self, req, rset, **kwargs):
        super(FormMixIn, self).__init__(req, rset, **kwargs)
        self.maxrelitems = self.req.property_value('navigation.related-limit')
        self.maxcomboitems = self.req.property_value('navigation.combobox-limit')
        self.force_display = not not req.form.get('__force_display')
        # get validation session data which may have been previously set.
        # deleting validation errors here breaks form reloading (errors are
        # no more available), they have to be deleted by application's publish
        # method on successful commit
        formurl = req.url()
        forminfo = req.get_session_data(formurl)
        if forminfo:
            req.data['formvalues'] = forminfo['values']
            req.data['formerrors'] = errex = forminfo['errors']
            req.data['displayederrors'] = set()
            # if some validation error occured on entity creation, we have to
            # get the original variable name from its attributed eid
            foreid = errex.entity
            for var, eid in forminfo['eidmap'].items():
                if foreid == eid:
                    errex.eid = var
                    break
            else:
                errex.eid = foreid
        
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

    @property
    def limit(self):
        if self.force_display:
            return None
        return self.maxrelitems + 1

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

    # XXX deprecated with new form system
    def error_message(self):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        errex = self.req.data.get('formerrors')
        # get extra errors
        if errex is not None:
            errormsg = self.req._('please correct the following errors:')
            displayed = self.req.data['displayederrors']
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
    

class FieldsForm(FormMixIn, AppRsetObject):
    __metaclass__ = metafieldsform
    __registry__ = 'forms'
    __select__ = yes()
    
    is_subform = False
    
    # attributes overrideable through __init__
    internal_fields = ('__errorurl',) + NAV_FORM_PARAMETERS
    needs_js = ('cubicweb.edition.js',)
    needs_css = ('cubicweb.form.css',)
    domid = 'form'
    title = None
    action = None
    onsubmit = "return freezeFormButtons('%(domid)s');"
    cssclass = None
    cssstyle = None
    cwtarget = None
    buttons = None
    redirect_path = None
    set_error_url = True
    copy_nav_params = False
                 
    def __init__(self, req, rset=None, row=None, col=None, **kwargs):
        super(FieldsForm, self).__init__(req, rset, row=row, col=col)
        self.buttons = kwargs.pop('buttons', [])
        for key, val in kwargs.items():
            assert hasattr(self.__class__, key) and not key[0] == '_', key
            setattr(self, key, val)
        self.fields = list(self.__class__._fields_)
        if self.set_error_url:
            self.form_add_hidden('__errorurl', req.url())
        if self.copy_nav_params:
            for param in NAV_FORM_PARAMETERS:
                value = kwargs.get(param, req.form.get(param))
                if value:
                    self.form_add_hidden(param, initial=value)
        self.context = None

    @iclassmethod
    def field_by_name(cls_or_self, name, role='subject'):
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        for field in fields:
            if field.name == name and field.role == role:
                return field
        raise Exception('field %s not found' % name)
    
    @iclassmethod
    def remove_field(cls_or_self, field):
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        fields.remove(field)
    
    @property
    def form_needs_multipart(self):
        return any(field.needs_multipart for field in self.fields) 

    def form_add_hidden(self, name, value=None, **kwargs):
        field = StringField(name=name, widget=fwdgs.HiddenInput, initial=value,
                            **kwargs)
        self.fields.append(field)
        return field
    
    def add_media(self):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            self.req.add_js(self.needs_js)
        if self.needs_css:
            self.req.add_css(self.needs_css)

    def form_render(self, **values):
        renderer = values.pop('renderer', FormRenderer())
        return renderer.render(self, values)

    def form_build_context(self, values):
        self.context = context = {}
        # on validation error, we get a dictionnary of previously submitted values
        previous_values = self.req.data.get('formvalues')
        if previous_values:
            values.update(previous_values)
        for field in self.fields:
            for field in field.actual_fields(self):
                value = self.form_field_value(field, values)
                context[field] = {'value': field.format_value(self.req, value),
                                  'rawvalue': value,
                                  'name': self.form_field_name(field),
                                  'id': self.form_field_id(field),
                                  }

    def form_field_value(self, field, values, load_bytes=False):
        """looks for field's value in
        1. kw args given to render_form (including previously submitted form
           values if any)
        2. req.form
        3. field's initial value
        """
        if field.name in values:
            value = values[field.name]
        elif field.name in self.req.form:
            value = self.req.form[field.name]
        else:
            value = field.initial
        return value
    
    def form_field_error(self, field):
        """return validation error for widget's field, if any"""
        errex = self.req.data.get('formerrors')
        if errex and field.name in errex.errors:
            self.req.data['displayederrors'].add(field.name)
            return u'<span class="error">%s</span>' % errex.errors[field.name]
        return u''

    def form_field_format(self, field):
        return self.req.property_value('ui.default-text-format')
    
    def form_field_encoding(self, field):
        return self.req.encoding
    
    def form_field_name(self, field):
        return field.name

    def form_field_id(self, field):
        return field.id
   
    def form_field_vocabulary(self, field, limit=None):
        raise NotImplementedError

    def form_buttons(self):
        return self.buttons

   
class EntityFieldsForm(FieldsForm):
    __select__ = (match_kwargs('entity') | (one_line_rset & non_final_entity()))
    
    internal_fields = FieldsForm.internal_fields + ('__type', 'eid')
    domid = 'entityForm'
    
    def __init__(self, *args, **kwargs):
        self.edited_entity = kwargs.pop('entity', None)
        msg = kwargs.pop('submitmsg', None)
        super(EntityFieldsForm, self).__init__(*args, **kwargs)
        if self.edited_entity is None:
            self.edited_entity = self.complete_entity(self.row)
        self.form_add_hidden('__type', eidparam=True)
        self.form_add_hidden('eid')
        if msg is not None:
            # If we need to directly attach the new object to another one
            for linkto in self.req.list_form_param('__linkto'):
                self.form_add_hidden('__linkto', linkto)
                msg = '%s %s' % (msg, self.req._('and linked'))
            self.form_add_hidden('__message', msg)
        
    def form_render(self, **values):
        self.form_add_entity_hiddens(self.edited_entity.e_schema)
        return super(EntityFieldsForm, self).form_render(**values)

    def form_add_entity_hiddens(self, eschema):
        for field in self.fields[:]:
            for field in field.actual_fields(self):
                fieldname = field.name
                if fieldname != 'eid' and (
                    (eschema.has_subject_relation(fieldname) or
                     eschema.has_object_relation(fieldname))):
                    field.eidparam = True
                    self.fields.append(self.form_entity_hidden_field(field))

    def form_entity_hidden_field(self, field):
        """returns the hidden field which will indicate the value
        before the modification
        """
        # Only RelationField has a `role` attribute, others are used
        # to describe attribute fields => role is 'subject'
        if getattr(field, 'role', 'subject') == 'subject':
            name = 'edits-%s' % field.name
        else:
            name = 'edito-%s' % field.name
        return HiddenInitialValueField(field, name=name)
        
    def form_field_value(self, field, values, load_bytes=False):
        """look for field's value with the following rules:
        1. handle special __type and eid fields
        2. looks in kw args given to render_form (including previously submitted
           form values if any)
        3. looks in req.form
        4. if entity has an eid:
             1. looks for an associated attribute / method
             2. use field's initial value
           else:
             1. looks for a default_<fieldname> attribute / method on the form
             2. use field's initial value
             
        values found in step 4 may be a callable which'll then be called.
        """
        fieldname = field.name
        if fieldname.startswith('edits-') or fieldname.startswith('edito-'):
            # edit[s|o]- fieds must have the actual value stored on the entity
            if hasattr(field, 'visible_field'):
                if self.edited_entity.has_eid():
                    value = self._form_field_entity_value(field.visible_field,
                                                          default_initial=False)
                else:
                    value = INTERNAL_FIELD_VALUE
            else:
                value = field.initial
        elif fieldname == '__type':
            value = self.edited_entity.id
        elif fieldname == 'eid':
            value = self.edited_entity.eid
        elif fieldname in values:
            value = values[fieldname]
        elif fieldname in self.req.form:
            value = self.req.form[fieldname]
        else:
            if self.edited_entity.has_eid() and field.eidparam:
                # use value found on the entity or field's initial value if it's
                # not an attribute of the entity (XXX may conflicts and get
                # undesired value)
                value = self._form_field_entity_value(field, default_initial=True,
                                                      load_bytes=load_bytes)
            else:
                defaultattr = 'default_%s' % fieldname
                if hasattr(self.edited_entity, defaultattr):
                    # XXX bw compat, default_<field name> on the entity
                    warn('found %s on %s, should be set on a specific form'
                         % (defaultattr, self.edited_entity.id), DeprecationWarning)
                    value = getattr(self.edited_entity, defaultattr)
                elif hasattr(self, defaultattr):
                    # search for default_<field name> on the form instance
                    value = getattr(self, defaultattr)
                else:
                    # use field's initial value
                    value = field.initial
            if callable(value):
                value = value()
        return value
    
    def form_field_format(self, field):
        entity = self.edited_entity
        if field.eidparam and entity.e_schema.has_metadata(field.name, 'format') and (
            entity.has_eid() or '%s_format' % field.name in entity):
            return self.edited_entity.attribute_metadata(field.name, 'format')
        return self.req.property_value('ui.default-text-format')

    def form_field_encoding(self, field):
        entity = self.edited_entity
        if field.eidparam and entity.e_schema.has_metadata(field.name, 'encoding') and (
            entity.has_eid() or '%s_encoding' % field.name in entity):
            return self.edited_entity.attribute_metadata(field.name, 'encoding')
        return super(EntityFieldsForm, self).form_field_encoding(field)
    
    def form_field_error(self, field):
        """return validation error for widget's field, if any"""
        errex = self.req.data.get('formerrors')
        if errex and errex.eid == self.edited_entity.eid and field.name in errex.errors:
            self.req.data['displayederrors'].add(field.name)
            return u'<span class="error">%s</span>' % errex.errors[field.name]
        return u''

    def _form_field_entity_value(self, field, default_initial=True, load_bytes=False):
        attr = field.name
        entity = self.edited_entity
        if field.role == 'object':
            attr = 'reverse_' + attr
        elif entity.e_schema.subject_relation(attr).is_final():
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
        if default_initial:
            value = getattr(entity, attr, field.initial)
        else:
            value = getattr(entity, attr)
        if isinstance(field, RelationField):
            # in this case, value is the list of related entities
            value = [ent.eid for ent in value]
        return value
    
    def form_field_name(self, field):
        if field.eidparam:
            return eid_param(field.name, self.edited_entity.eid)
        return field.name

    def form_field_id(self, field):
        if field.eidparam:
            return eid_param(field.id, self.edited_entity.eid)
        return field.id
        
    def form_field_vocabulary(self, field, limit=None):
        role, rtype = field.role, field.name
        try:
            vocabfunc = getattr(self.edited_entity, '%s_%s_vocabulary' % (role, rtype))
        except AttributeError:
            vocabfunc = getattr(self, '%s_relation_vocabulary' % role)
        else:
            # XXX bw compat, default_<field name> on the entity
            warn('found %s_%s_vocabulary on %s, should be set on a specific form'
                 % (role, rtype, self.edited_entity.id), DeprecationWarning)
        # NOTE: it is the responsibility of `vocabfunc` to sort the result
        #       (direclty through RQL or via a python sort). This is also
        #       important because `vocabfunc` might return a list with
        #       couples (label, None) which act as separators. In these
        #       cases, it doesn't make sense to sort results afterwards.
        return vocabfunc(rtype, limit)
## XXX BACKPORT ME
##         if self.sort:
##             choices = sorted(choices)
##         if self.rschema.rproperty(self.subjtype, self.objtype, 'internationalizable'):
##             return zip((entity.req._(v) for v in choices), choices)

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
            result += self.relation_vocabulary(rtype, objtype, 'subject',
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
            result += self.relation_vocabulary(rtype, subjtype, 'object',
                                               rsetsize, done)
            if limit is not None and len(result) >= limit:
                break
        return result

    def relation_vocabulary(self, rtype, targettype, role,
                            limit=None, done=None):
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

    def subject_in_state_vocabulary(self, rschema, limit=None):
        """vocabulary method for the in_state relation, looking for
        relation's object entities (i.e. self is the subject) according
        to initial_state, state_of and next_state relation
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
        subform.is_subform = True
        self.forms.append(subform)
