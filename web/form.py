"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn
from simplejson import dumps

from logilab.common.compat import any
from logilab.mtconverter import html_escape

from cubicweb import typed_eid
from cubicweb.selectors import match_form_params
from cubicweb.view import NOINDEX, NOFOLLOW, View, EntityView, AnyRsetView
from cubicweb.common.registerers import accepts_registerer
from cubicweb.web import stdmsgs
from cubicweb.web.httpcache import NoHTTPCacheManager
from cubicweb.web.controller import redirect_params
from cubicweb.web import eid_param


def relation_id(eid, rtype, target, reid):
    if target == 'subject':
        return u'%s:%s:%s' % (eid, rtype, reid)
    return u'%s:%s:%s' % (reid, rtype, eid)
        
def toggable_relation_link(eid, nodeid, label='x'):
    js = u"javascript: togglePendingDelete('%s', %s);" % (nodeid, html_escape(dumps(eid)))
    return u'[<a class="handle" href="%s" id="handle%s">%s</a>]' % (js, nodeid, label)


class FormMixIn(object):
    """abstract form mix-in"""
    category = 'form'
    controller = 'edit'
    domid = 'entityForm'
    
    http_cache_manager = NoHTTPCacheManager
    add_to_breadcrumbs = False
    skip_relations = set()
    
    def __init__(self, req, rset):
        super(FormMixIn, self).__init__(req, rset)
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
    
    def restore_pending_inserts(self, entity, cell=False):
        """used to restore edition page as it was before clicking on
        'search for <some entity type>'
        
        """
        eid = entity.eid
        cell = cell and "div_insert_" or "tr"
        pending_inserts = set(self.req.get_pending_inserts(eid))
        for pendingid in pending_inserts:
            eidfrom, rtype, eidto = pendingid.split(':')
            if typed_eid(eidfrom) == entity.eid: # subject
                label = display_name(self.req, rtype, 'subject')
                reid = eidto
            else:
                label = display_name(self.req, rtype, 'object')
                reid = eidfrom
            jscall = "javascript: cancelPendingInsert('%s', '%s', null, %s);" \
                     % (pendingid, cell, eid)
            rset = self.req.eid_rset(reid)
            eview = self.view('text', rset, row=0)
            # XXX find a clean way to handle baskets
            if rset.description[0][0] == 'Basket':
                eview = '%s (%s)' % (eview, display_name(self.req, 'Basket'))
            yield rtype, pendingid, jscall, label, reid, eview
        
    
    def force_display_link(self):
        return (u'<span class="invisible">' 
                u'[<a href="javascript: window.location.href+=\'&amp;__force_display=1\'">%s</a>]'
                u'</span>' % self.req._('view all'))
    
    def relations_table(self, entity):
        """yiels 3-tuples (rtype, target, related_list)
        where <related_list> itself a list of :
          - node_id (will be the entity element's DOM id)
          - appropriate javascript's togglePendingDelete() function call
          - status 'pendingdelete' or ''
          - oneline view of related entity
        """
        eid = entity.eid
        pending_deletes = self.req.get_pending_deletes(eid)
        # XXX (adim) : quick fix to get Folder relations
        for label, rschema, target in entity.srelations_by_category(('generic', 'metadata'), 'add'):
            if rschema in self.skip_relations:
                continue
            relatedrset = entity.related(rschema, target, limit=self.limit)
            toggable_rel_link = self.toggable_relation_link_func(rschema)
            related = []
            for row in xrange(relatedrset.rowcount):
                nodeid = relation_id(eid, rschema, target, relatedrset[row][0])
                if nodeid in pending_deletes:
                    status = u'pendingDelete'
                    label = '+'
                else:
                    status = u''
                    label = 'x'
                dellink = toggable_rel_link(eid, nodeid, label)
                eview = self.view('oneline', relatedrset, row=row)
                related.append((nodeid, dellink, status, eview))
            yield (rschema, target, related)
        
    def toggable_relation_link_func(self, rschema):
        if not rschema.has_perm(self.req, 'delete'):
            return lambda x, y, z: u''
        return toggable_relation_link


    def redirect_url(self, entity=None):
        """return a url to use as next direction if there are some information
        specified in current form params, else return the result the reset_url
        method which should be defined in concrete classes
        """
        rparams = redirect_params(self.req.form)
        if rparams:
            return self.build_url('view', **rparams)
        return self.reset_url(entity)

    def reset_url(self, entity):
        raise NotImplementedError('implement me in concrete classes')

    BUTTON_STR = u'<input class="validateButton" type="submit" name="%s" value="%s" tabindex="%s"/>'
    ACTION_SUBMIT_STR = u'<input class="validateButton" type="button" onclick="postForm(\'%s\', \'%s\', \'%s\')" value="%s" tabindex="%s"/>'

    def button_ok(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_OK).capitalize()
        return self.BUTTON_STR % ('defaultsubmit', label, tabindex or 2)
    
    def button_apply(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_APPLY).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_apply', label, self.domid, label, tabindex or 3)

    def button_delete(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_DELETE).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_delete', label, self.domid, label, tabindex or 3)
    
    def button_cancel(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_cancel', label, self.domid, label, tabindex or 4)
    
    def button_reset(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return u'<input class="validateButton" type="reset" value="%s" tabindex="%s"/>' % (
            label, tabindex or 4)


###############################################################################

from cubicweb.common import tags

# widgets ############

class FieldWidget(object):
    def __init__(self, attrs=None):
        self.attrs = attrs or {}
    
    def render(self, form, field):
        raise NotImplementedError
    
class Input(FieldWidget):
    type = None
    
    def render(self, form, field):
        name, value, attrs = self._render_attrs(form, field)
        if attrs is None:
            return tags.input(name=name, value=value)
        return tags.input(name=name, value=value, type=self.type, **attrs)

    def _render_attrs(self, form, field):
        name = form.context[field]['name'] # qualified name
        value = form.context[field]['value']
        #fattrs = field.widget_attributes(self)
        attrs = self.attrs.copy()
        #attrs.update(fattrs)
        # XXX id
        return name, value, attrs
    
class TextInput(Input):
    type = 'text'

class PasswordInput(Input):
    type = 'password'

class FileInput(Input):
    type = 'file'

class HiddenInput(Input):
    type = 'hidden'

class Button(Input):
    type = 'button'

class TextArea(FieldWidget):
    def render(self, form, field):
        name, value, attrs = self._render_attrs(form, field)
        if attrs is None:
            return tags.textarea(value, name=name)
        return tags.textarea(value, name=name, **attrs)

class Select: 
    def render(self, form, field):
        name, value, attrs = self._render_attrs(form, field)
        if self.vocabulary:
            # static vocabulary defined in form definition
            vocab = self.vocabulary
        else:
            vocab = form.get_vocabulary(field)
        options = []
        for label, value in vocab:
            options.append(tags.option(label, value=value))
        if attrs is None:
            return tags.select(name=name, options=options)
        return tags.select(name=name, options=options, **attrs)

class CheckBox: pass

class Radio: pass

class DateTimePicker: pass


# fields ############

class Field(object):
    """field class is introduced to control what's displayed in edition form
    """
    widget = TextInput
    needs_multipart = False
    creation_rank = 0
    
    def __init__(self, name=None, id=None, label=None,
                 widget=None, required=False, initial=None, help=None,
                 eidparam=True):
        self.required = required
        if widget is not None:
            self.widget = widget
        if isinstance(self.widget, type):
            self.widget = self.widget()
        self.name = name
        self.label = label or name
        self.id = id or name
        self.initial = initial
        self.help = help
        self.eidparam = eidparam
        # global fields ordering in forms
        Field.creation_rank += 1

    def set_name(self, name):
        self.name = name
        if not self.id:
            self.id = name
        if not self.label:
            self.label = name

    def format_value(self, req, value):
        return unicode(value)

    def render(self, form):
        return self.widget.render(form, self)


class StringField(Field):
    def __init__(self, max_length=None, **kwargs):
        super(StringField, self).__init__(**kwargs)
        self.max_length = max_length
        
class TextField(Field):
    widget = TextArea
    def __init__(self, row=None, col=None, **kwargs):
        super(TextField, self).__init__(**kwargs)
        self.row = row
        self.col = col

class RichTextField(Field):
    pass

class IntField(Field):
    def __init__(self, min=None, max=None, **kwargs):
        super(IntField, self).__init__(**kwargs)
        self.min = min
        self.max = max

class FloatField(IntField):
    
    def format_value(self, req, value):
        if value is not None:
            return ustrftime(value, req.property_value('ui.float-format'))
        return u''

class DateField(IntField):
    
    def format_value(self, req, value):
        return value and ustrftime(value, req.property_value('ui.date-format')) or u''

class DateTimeField(IntField):

    def format_value(self, req, value):
        return value and ustrftime(value, req.property_value('ui.datetime-format')) or u''

class FileField(IntField):
    needs_multipart = True
                 
# forms ############
class metafieldsform(type):
    def __new__(mcs, name, bases, classdict):
        allfields = []
        for base in bases:
            if hasattr(base, '_fields_'):
                allfields += base._fields_
        clsfields = (item for item in classdict.items()
                     if isinstance(item[1], Field))
        for name, field in sorted(clsfields, key=lambda x: x[1].creation_rank):
            if not field.name:
                field.set_name(name)
            allfields.append(field)
        classdict['_fields_'] = allfields
        return super(metafieldsform, mcs).__new__(mcs, name, bases, classdict)
    

class FieldsForm(object):
    __metaclass__ = metafieldsform
    
    def __init__(self, req, id=None, title=None, action='edit',
                 redirect_path=None):
        self.req = req
        self.id = id or 'form'
        self.title = title
        self.action = action
        self.redirect_path = None
        self.fields = list(self.__class__._fields_)
        self.fields.append(TextField(name='__errorurl', widget=HiddenInput,
                                     initial=req.url()))
        self.context = {}
        
    @property
    def form_needs_multipart(self):
        return any(field.needs_multipart for field in self.fields) 

    def form_render(self, **values):
        renderer = values.pop('renderer', FormRenderer())
        self.form_build_context(values)
        return renderer.render(self)

    def form_build_context(self, values):
        self.context = context = {}
        # on validation error, we get a dictionnary of previously submitted values
        previous_values = self.req.data.get('formvalues')
        if previous_values:
            values.update(previous_values)
        for field in self.fields:
            context[field] = {'value': self.form_field_value(field, field_values),
                              'name': self.form_field_name(field),
                              'id': self.form_field_id(field),
                              }

    def form_field_value(self, field, values):
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
        return field.format_value(self.req, value) 

    def form_field_name(self, field):
        return field.name

    def form_field_id(self, field):
        return field.id
   
    def form_field_vocabulary(self, field):
        raise NotImplementedError
    
    BUTTON_STR = u'<input class="validateButton" type="submit" name="%s" value="%s" tabindex="%s"/>'
    ACTION_SUBMIT_STR = u'<input class="validateButton" type="button" onclick="postForm(\'%s\', \'%s\', \'%s\')" value="%s" tabindex="%s"/>'

    def button_ok(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_OK).capitalize()
        return self.BUTTON_STR % ('defaultsubmit', label, tabindex or 2)
    
    def button_apply(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_APPLY).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_apply', label, self.id, label, tabindex or 3)

    def button_delete(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_DELETE).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_delete', label, self.id, label, tabindex or 3)
    
    def button_cancel(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_cancel', label, self.id, label, tabindex or 4)
    
    def button_reset(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return u'<input class="validateButton" type="reset" value="%s" tabindex="%s"/>' % (
            label, tabindex or 4)

    
class EntityFieldsForm(FieldsForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('id', 'entityForm')
        super(EntityFieldsForm, self).__init__(*args, **kwargs)
        self.fields.append(TextField(name='__type', widget=HiddenInput))
        self.fields.append(TextField(name='eid', widget=HiddenInput))
        
    def form_render(self, entity, **values):
        self.entity = entity
        return super(EntityFieldsForm, self).form_render(**values)
        
    def form_field_value(self, field, values):
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
        if field.name == '__type':
            value = self.entity.id
        elif field.name == 'eid':
            value = self.entity.eid
        elif field.name in values:
            value = values[field.name]
        elif field.name in self.req.form:
            value = self.req.form[field.name]
        else:
            if self.entity.has_eid():
                # use value found on the entity or field's initial value if it's
                # not an attribute of the entity (XXX may conflicts and get
                # undesired value)
                value = getattr(self.entity, field.name, field.initial)
            else:
                defaultattr = 'default_%s' % field.name
                if hasattr(self.entity, defaultattr):
                    # XXX bw compat, default_<field name> on the entity
                    warn('found %s on %s, should be set on a specific form'
                         % (defaultattr, self.entity.id), DeprecationWarning)
                    value = getattr(self.entity, defaultattr)
                elif hasattr(self, defaultattr):
                    # search for default_<field name> on the form instance
                    value = getattr(self, defaultattr)
                else:
                    # use field's initial value
                    value = field.initial
            if callable(value):
                values = value()
        return field.format_value(self.req, value) 

    def form_field_name(self, field):
        if field.eidparam:
            return eid_param(field.name, self.entity.eid)
        return field.name

    def form_field_id(self, field):
        if field.eidparam:
            return eid_param(field.id, self.entity.eid)
        return field.id
        
    def form_field_vocabulary(self, field):
        choices = self.vocabfunc(entity)
        if self.sort:
            choices = sorted(choices)
        if self.rschema.rproperty(self.subjtype, self.objtype, 'internationalizable'):
            return zip((entity.req._(v) for v in choices), choices)
        return zip(choices, choices)

    
# form renderers ############

class FormRenderer(object):
    
    def render(self, form):
        data = []
        w = data.append
        # XXX form_needs_multipart
        w(u'<form action="%s" onsubmit="return freezeFormButtons(\'%s\');" method="post" id="%s">'
          % (form.req.build_url(form.action), form.id, form.id))
        w(u'<div id="progress">%s</div>' % _('validating...'))
        w(u'<fieldset>')
        w(tags.input(type='hidden', name='__form_id', value=form.id))
        if form.redirect_path:
            w(tags.input(type='hidden', name='__redirect_path', value=form.redirect_path))
        self.render_fields(w, form)
        self.render_buttons(w, form)
        w(u'</fieldset>')
        w(u'</form>')
        return '\n'.join(data)

    def render_fields(self, w, form):
        w(u'<table>')
        for field in form.fields:
            w(u'<tr>')
            w('<th>%s</th>' % self.render_label(form, field))
            w(u'<td style="width:100%;">')
            w(field.render(form))
            w(u'</td></tr>')
        w(u'</table>')

    def render_buttons(self, w, form):
        for button in form.buttons():
            w(button)
        
    def render_label(self, form, field):
        label = form.req._(field.label)
        attrs = {'for': form.context[field]['id']}
        if field.required:
            attrs['class'] = 'required'
        return tags.label(label, **attrs)
        
