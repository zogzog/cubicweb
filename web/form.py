"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn
from simplejson import dumps
from mx.DateTime import today, now

from logilab.common.compat import any
from logilab.mtconverter import html_escape

from yams.constraints import SizeConstraint, StaticVocabularyConstraint

from cubicweb import typed_eid
from cubicweb.utils import ustrftime
from cubicweb.selectors import match_form_params
from cubicweb.view import NOINDEX, NOFOLLOW, View, EntityView, AnyRsetView
from cubicweb.common.registerers import accepts_registerer
from cubicweb.common.uilib import toggle_action
from cubicweb.web import stdmsgs
from cubicweb.web.httpcache import NoHTTPCacheManager
from cubicweb.web.controller import NAV_FORM_PARAMETERS, redirect_params
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param


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
        return self.ACTION_SUBMIT_STR % ('__action_apply', label, self.domid,
                                         label, tabindex or 3)

    def button_delete(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_DELETE).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_delete', label, self.domid,
                                         label, tabindex or 3)
    
    def button_cancel(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_cancel', label, self.domid,
                                         label, tabindex or 4)
    
    def button_reset(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return u'<input class="validateButton" type="reset" value="%s" tabindex="%s"/>' % (
            label, tabindex or 4)


###############################################################################

from cubicweb.common import tags

# widgets ############

class FieldWidget(object):
    needs_js = ()
    needs_css = ()
    
    def __init__(self, attrs=None):
        self.attrs = attrs or {}

    def add_media(self, form):
        """adds media (CSS & JS) required by this widget"""
        req = form.req
        if self.needs_js:
            req.add_js(self.needs_js)
        if self.needs_css:
            req.add_css(self.needs_css)
        
    def render(self, form, field):
        raise NotImplementedError

    def _render_attrs(self, form, field):
        name = form.context[field]['name']
        values = form.context[field]['value']
        if not isinstance(values, (tuple, list)):
            values = (values,)
        attrs = dict(self.attrs)
        attrs['id'] = form.context[field]['id']
        return name, values, dict(self.attrs)

class Input(FieldWidget):
    type = None
    
    def render(self, form, field):
        self.add_media(form)
        name, values, attrs = self._render_attrs(form, field)
        inputs = [tags.input(name=name, value=value, type=self.type, **attrs)
                  for value in values]
        return u'\n'.join(inputs)

class TextInput(Input):
    type = 'text'

class PasswordInput(Input):
    type = 'password'
    # XXX password validation

class FileInput(Input):
    type = 'file'
    
    def _render_attrs(self, form, field):
        # ignore value which makes no sense here (XXX even on form validation error?)
        name, values, attrs = super(FileInput, self)._render_attrs(form, field)
        return name, ('',), attrs
        
class HiddenInput(Input):
    type = 'hidden'
    
class ButtonInput(Input):
    type = 'button'

class TextArea(FieldWidget):
    def render(self, form, field):
        name, values, attrs = self._render_attrs(form, field)
        attrs.setdefault('onkeypress', 'autogrow(this)')
        if not values:
            value = u''
        elif len(values) == 1:
            value = values[0]
        else:
            raise ValueError('a textarea is not supposed to be multivalued')
        return tags.textarea(value, name=name, **attrs)


class FCKEditor(TextArea):
    def __init__(self, attrs):
        super(FCKEditor, self).__init__(attrs)
        self.attrs['cubicweb:type'] = 'wysiwyg'
    
    def render(self, form, field):
        form.req.fckeditor_config()
        return super(self, FCKEditor, self).render(form, field)


#class EditableFile(Widget):
#    # XXX
#    pass

class Select(FieldWidget):
    def __init__(self, attrs=None, multiple=False):
        super(Select, self).__init__(attrs)
        self.multiple = multiple
        
    def render(self, form, field):
        name, curvalues, attrs = self._render_attrs(form, field)
        vocab = field.vocabulary(form)
        options = []
        for label, value in vocab:
            if value in curvalues:
                options.append(tags.option(label, value=value, selected='selected'))
            else:
                options.append(tags.option(label, value=value))
        if attrs is None:
            return tags.select(name=name, options=options)
        return tags.select(name=name, multiple=self.multiple,
                           options=options, **attrs)


class CheckBox(Input):
    type = 'checkbox'
    
    def _render_attrs(self, form, field):
        name, values, attrs = super(CheckBox, self)._render_attrs(form, field)
        if values and values[0]:
            attrs['checked'] = u'checked'
        return name, values, attrs

        
class Radio(FieldWidget):
    pass


class DateTimePicker(TextInput):
    monthnames = ('january', 'february', 'march', 'april',
                  'may', 'june', 'july', 'august',
                  'september', 'october', 'november', 'december')
    daynames = ('monday', 'tuesday', 'wednesday', 'thursday',
                'friday', 'saturday', 'sunday')

    needs_js = ('cubicweb.ajax.js', 'cubicweb.calendar.js')
    needs_css = ('cubicweb.calendar_popup.css',)
    
    @classmethod
    def add_localized_infos(cls, req):
        """inserts JS variables defining localized months and days"""
        # import here to avoid dependancy from cubicweb-common to simplejson
        _ = req._
        monthnames = [_(mname) for mname in cls.monthnames]
        daynames = [_(dname) for dname in cls.daynames]
        req.html_headers.define_var('MONTHNAMES', monthnames)
        req.html_headers.define_var('DAYNAMES', daynames)
    
    def render(self, form, field):
        txtwidget = super(DateTimePicker, self).render(form, field)
        cal_button = self._render_calendar_popup(form, field)
        return txtwidget + cal_button
    
    def _render_calendar_popup(self, form, field):
        req = form.req
        value = form.context[field]['rawvalue']
        inputid = form.context[field]['id']
        helperid = '%shelper' % inputid
        if not value:
            value = today()
        year, month = value.year, value.month
        onclick = "toggleCalendar('%s', '%s', %s, %s);" % (
            helperid, inputid, year, month)
        return (u"""<a onclick="toggleCalendar('%s', '%s', %s, %s);" class="calhelper">
<img src="%s" title="%s" alt="" /></a><div class="calpopup hidden" id="%s"></div>"""
                % (helperid, inputid, year, month,
                   req.external_resource('CALENDAR_ICON'),
                   req._('calendar'), helperid) )


# fields ############

class Field(object):
    """field class is introduced to control what's displayed in edition form
    """
    widget = TextInput
    needs_multipart = False
    creation_rank = 0

    def __init__(self, name=None, id=None, label=None,
                 widget=None, required=False, initial=None,
                 choices=None, help=None, eidparam=False):
        self.required = required
        if widget is not None:
            self.widget = widget
        if isinstance(self.widget, type):
            self.widget = self.widget()
        self.name = name
        self.label = label or name
        self.id = id or name
        self.initial = initial
        self.choices = choices or ()
        self.help = help
        self.eidparam = eidparam
        self.role = 'subject'
        # global fields ordering in forms
        Field.creation_rank += 1

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

    def __unicode__(self):
        return u'<%s name=%r label=%r id=%r initial=%r>' % (
            self.__class__.__name__, self.name, self.label,
            self.id, self.initial)

    def __repr__(self):
        return self.__unicode__().encode('utf-8')
    
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
        return self.choices

    
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
        try:
            return form.req.data[self]
        except KeyError:
            if self.use_fckeditor(form):
                # if fckeditor is used and format field isn't explicitly
                # deactivated, we want an hidden field for the format
                widget = HiddenInput()
            else:
                # else we want a format selector
                # XXX compute vocabulary
                widget = Select
            field = StringField(name=self.name + '_format', widget=widget)
            form.req.data[self] = field
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
        if form.config.fckeditor_installed() and form.req.property_value('ui.fckeditor'):
            return form.form_format_field_value(self) == 'text/html'
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
                        (html_escape(toggle_action(divid)),
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
        
    
class IntField(Field):
    def __init__(self, min=None, max=None, **kwargs):
        super(IntField, self).__init__(**kwargs)
        self.min = min
        self.max = max


class BooleanField(Field):
    widget = Radio


class FloatField(IntField):    
    def format_single_value(self, req, value):
        formatstr = entity.req.property_value('ui.float-format')
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
        return self.format_value(req, now())


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
    def fromcardinality(card, role, **kwargs):
        return RelationField(widget=Select(multiple=card in '*+'),
                             **kwargs)
        
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
    
# forms ############
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
    

class FieldsForm(FormMixIn):
    __metaclass__ = metafieldsform
    
    def __init__(self, req, domid=None, title=None, action='edit',
                 onsubmit="return freezeFormButtons('%s');",
                 cssclass=None, cssstyle=None, cwtarget=None, buttons=None,
                 redirect_path=None, set_error_url=True, copy_nav_params=False):
        self.req = req
        self.config = req.vreg.config
        self.domid = domid or 'form'
        self.title = title
        self.action = action
        self.onsubmit = onsubmit
        self.cssclass = cssclass
        self.cssstyle = cssstyle
        self.cwtarget = cwtarget
        self.redirect_path = redirect_path
        self.fields = list(self.__class__._fields_)
        if set_error_url:
            self.form_add_hidden('__errorurl', req.url())
        if copy_nav_params:
            for param in NAV_FORM_PARAMETERS:
                value = req.form.get(param)
                if value:
                    self.form_add_hidden(param, initial=value)
        self.buttons = buttons or []
        self.context = {}
        
    @property
    def form_needs_multipart(self):
        return any(field.needs_multipart for field in self.fields) 

    def form_add_hidden(self, name, value=None, **kwargs):
        self.fields.append(StringField(name=name, widget=HiddenInput,
                                       initial=value, **kwargs))

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
        return value

    def form_format_field_value(self, field, values):
        return self.req.property_value('ui.default-text-format')
    
    def form_field_name(self, field):
        return field.name

    def form_field_id(self, field):
        return field.id
   
    def form_field_vocabulary(self, field):
        raise NotImplementedError

    def form_buttons(self):
        return self.buttons

   
class EntityFieldsForm(FieldsForm):
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('domid', 'entityForm')
        self.entity = kwargs.pop('entity', None)
        super(EntityFieldsForm, self).__init__(*args, **kwargs)
        self.form_add_hidden('__type', eidparam=True)
        self.form_add_hidden('eid')
        
    def form_render(self, **values):
        self.form_add_entity_hiddens(self.entity.e_schema)
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
        fieldname = field.name
        if fieldname.startswith('edits-') or fieldname.startswith('edito-'):
            # edit[s|o]- fieds must have the actual value stored on the entity
            if self.entity.has_eid():
                value = self.form_field_entity_value(field.visible_field, default_initial=False)
            else:
                value = INTERNAL_FIELD_VALUE
        elif fieldname == '__type':
            value = self.entity.id
        elif fieldname == 'eid':
            value = self.entity.eid
        elif fieldname in values:
            value = values[fieldname]
        elif fieldname in self.req.form:
            value = self.req.form[fieldname]
        else:
            if self.entity.has_eid() and field.eidparam:
                # use value found on the entity or field's initial value if it's
                # not an attribute of the entity (XXX may conflicts and get
                # undesired value)
                value = self.form_field_entity_value(field, default_initial=True)
            else:
                defaultattr = 'default_%s' % fieldname
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
        return value
    
    def form_format_field_value(self, field, values):
        entity = self.entity
        if field.eidparam and entity.has_format(field.name) and (
            entity.has_eid() or '%s_format' % field.name in entity):
            return self.entity.format(field.name) == 'text/html'
        return self.req.property_value('ui.default-text-format')

    def form_field_entity_value(self, field, default_initial=True):
        attr = field.name 
        if field.role == 'object':
            attr += '_object'
        else:
            attrtype = self.entity.e_schema.destination(attr)
            if attrtype == 'Password':
                return self.entity.has_eid() and INTERNAL_FIELD_VALUE or ''
            if attrtype == 'Bytes':
                # XXX value should reflect if some file is already attached
                return self.entity.has_eid()
        if default_initial:
            value = getattr(self.entity, attr, field.initial)
        else:
            value = getattr(self.entity, attr)
        if isinstance(field, RelationField):
            # in this case, value is the list of related entities
            value = [ent.eid for ent in value]
        return value
    
    def form_field_name(self, field):
        if field.eidparam:
            return eid_param(field.name, self.entity.eid)
        return field.name

    def form_field_id(self, field):
        if field.eidparam:
            return eid_param(field.id, self.entity.eid)
        return field.id
        
    def form_field_vocabulary(self, field):
        role, rtype = field.role, field.name
        try:
            vocabfunc = getattr(self.entity, '%s_%s_vocabulary' % (role, rtype))
        except AttributeError:
            vocabfunc = getattr(self, '%s_relation_vocabulary' % role)
        else:
            # XXX bw compat, default_<field name> on the entity
            warn('found %s_%s_vocabulary on %s, should be set on a specific form'
                 % (role, rtype, self.entity.id), DeprecationWarning)
        return vocabfunc(rtype)
## XXX BACKPORT ME
##         if self.sort:
##             choices = sorted(choices)
##         if self.rschema.rproperty(self.subjtype, self.objtype, 'internationalizable'):
##             return zip((entity.req._(v) for v in choices), choices)

    def subject_relation_vocabulary(self, rtype, limit=None):
        """defaut vocabulary method for the given relation, looking for
        relation's object entities (i.e. self is the subject)
        """
        entity = self.entity
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
        entity = self.entity
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
        req = self.req
        rset = entity.unrelated(rtype, targettype, role, limit)
        res = []
        for entity in rset.entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            res.append((entity.view('combobox'), entity.eid))
        return res


class MultipleFieldsForm(FieldsForm):
    def __init__(self, *args, **kwargs):
        super(MultipleFieldsForm, self).__init__(*args, **kwargs)
        self.forms = []

    def form_add_subform(self, subform):
        self.forms.append(subform)


# form renderers ############
class FormRenderer(object):

    # renderer interface ######################################################
    
    def render(self, form, values, display_help=True):
        data = []
        w = data.append
        w(self.open_form(form))
        w(u'<div id="progress">%s</div>' % form.req._('validating...'))
        w(u'<fieldset>')
        w(tags.input(type='hidden', name='__form_id', value=form.domid))
        if form.redirect_path:
            w(tags.input(type='hidden', name='__redirectpath', value=form.redirect_path))
        self.render_fields(w, form, values, display_help)
        self.render_buttons(w, form)
        w(u'</fieldset>')
        w(u'</form>')
        return '\n'.join(data)
        
    def render_label(self, form, field):
        label = form.req._(field.label)
        attrs = {'for': form.context[field]['id']}
        if field.required:
            attrs['class'] = 'required'
        return tags.label(label, **attrs)

    def render_help(self, form, field):
        help = [ u'<br/>' ]
        descr = field.help
        if descr:
            help.append('<span class="helper">%s</span>' % req._(descr))
        example = field.example_format(form.req)
        if example:
            help.append('<span class="helper">(%s: %s)</span>'
                        % (req._('sample format'), example))
        return u'&nbsp;'.join(help)

    # specific methods (mostly to ease overriding) #############################
    
    def open_form(self, form):
        if form.form_needs_multipart:
            enctype = 'multipart/form-data'
        else:
            enctype = 'application/x-www-form-urlencoded'
        tag = ('<form action="%s" methody="post" id="%s" enctype="%s"' % (
            html_escape(form.action or '#'), form.domid, enctype))
        if form.onsubmit:
            tag += ' onsubmit="%s"' % html_escape(form.onsubmit)
        if form.cssstyle:
            tag += ' style="%s"' % html_escape(form.cssstyle)
        if form.cssclass:
            tag += ' class="%s"' % html_escape(form.cssclass)
        if form.cwtarget:
            tag += ' cubicweb:target="%s"' % html_escape(form.cwtarget)
        return tag + '>'
        
    def render_fields(self, w, form, values, display_help=True):
        form.form_build_context(values)
        fields = form.fields[:]
        for field in form.fields:
            if not field.is_visible():
                w(field.render(form, self))
                fields.remove(field)
        if fields:
            w(u'<table>')
            for field in fields:
                w(u'<tr>')
                w('<th>%s</th>' % self.render_label(form, field))
                w(u'<td style="width:100%;">')
                w(field.render(form, self))
                if display_help == True:
                    w(self.render_help(form, field))
                w(u'</td></tr>')
            w(u'</table>')
        for childform in getattr(form, 'forms', []):
            self.render_fields(w, childform, values)
        
    def render_buttons(self, w, form):
        w(u'<table class="formButtonBar">\n<tr>\n')
        for button in form.form_buttons():
            w(u'<td>%s</td>\n' % button)
        w(u'</tr></table>')


def stringfield_from_constraints(constraints, **kwargs):
    field = None
    for cstr in constraints:
        if isinstance(cstr, StaticVocabularyConstraint):
            return StringField(widget=Select(vocabulary=cstr.vocabulary),
                               **kwargs)
        if isinstance(cstr, SizeConstraint) and cstr.max is not None:
            if cstr.max > 257:
                field = textfield_from_constraint(cstr, **kwargs)
            else:
                field = StringField(max_length=cstr.max, **kwargs)
    return field or TextField(**kwargs)
        

def textfield_from_constraint(constraint, **kwargs):
    if 256 < constraint.max < 513:
        rows, cols = 5, 60
    else:
        rows, cols = 10, 80
    return TextField(rows, cols, **kwargs)


def find_field(eclass, subjschema, rschema, role='subject'):
    """return the most adapated widget to edit the relation
    'subjschema rschema objschema' according to information found in the schema
    """
    fieldclass = None
    if role == 'subject':
        objschema = rschema.objects(subjschema)[0]
        cardidx = 0
    else:
        objschema = rschema.subjects(subjschema)[0]
        cardidx = 1
    card = rschema.rproperty(subjschema, objschema, 'cardinality')[cardidx]
    required = card in '1+'
    if rschema in eclass.widgets:
        fieldclass = eclass.widgets[rschema]
        if isinstance(fieldclass, basestring):
            return StringField(name=rschema.type)
    elif not rschema.is_final():
        return RelationField.fromcardinality(card, role,name=rschema.type,
                                             required=required)
    else:
        fieldclass = FIELDS[objschema]
    if fieldclass is StringField:
        constraints = rschema.rproperty(subjschema, objschema, 'constraints')
        return stringfield_from_constraints(constraints, name=rschema.type,
                                            required=required)
    return fieldclass(name=rschema.type, required=required)

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
