"""widgets for entity edition

those are in cubicweb.common since we need to know available widgets at schema
serialization time

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps
from mx.DateTime import now, today

from logilab.mtconverter import html_escape

from yams.constraints import SizeConstraint, StaticVocabularyConstraint

from cubicweb.common.uilib import toggle_action
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param

def _format_attrs(kwattrs):
    """kwattrs is the dictionary of the html attributes available for
    the edited element
    """
    # sort for predictability (required for tests)
    return u' '.join(sorted(u'%s="%s"' % item for item in kwattrs.iteritems()))

def _value_from_values(values):
    # take care, value may be 0, 0.0...
    if values:
        value = values[0]
        if value is None:
            value = u''
    else:
        value = u''
    return value

def _eclass_eschema(eschema_or_eclass):
    try:
        return eschema_or_eclass, eschema_or_eclass.e_schema
    except AttributeError:
        return None, eschema_or_eclass

def checkbox(name, value, attrs='', checked=None):
    if checked is None:
        checked = value
    checked = checked and 'checked="checked"' or ''
    return u'<input type="checkbox" name="%s" value="%s" %s %s />' % (
        name, value, checked, attrs)

def widget(vreg, subjschema, rschema, objschema, role='object'):
    """get a widget to edit the given relation"""
    if rschema == 'eid':
        # return HiddenWidget(vreg, subjschema, rschema, objschema)
        return EidWidget(vreg, _eclass_eschema(subjschema)[1], rschema, objschema)
    return widget_factory(vreg, subjschema, rschema, objschema, role=role)


class Widget(object):
    """abstract widget class"""
    need_multipart = False
    # generate the "id" attribute with the same value as the "name" (html) attribute
    autoid = True
    html_attributes = set(('id', 'class', 'tabindex', 'accesskey', 'onchange', 'onkeypress'))
    cubicwebns_attributes = set()
    
    def __init__(self, vreg, subjschema, rschema, objschema,
                 role='subject', description=None,
                 **kwattrs):
        self.vreg = vreg
        self.rschema = rschema
        self.subjtype = subjschema
        self.objtype = objschema
        self.role = role
        self.name = rschema.type
        self.description = description
        self.attrs = kwattrs
        # XXX accesskey may not be unique
        kwattrs['accesskey'] = self.name[0]

    def copy(self):
        """shallow copy (useful when you need to modify self.attrs
        because widget instances are cached)
        """
        # brute force copy (subclasses don't have the
        # same __init__ prototype) 
        widget = self.__new__(self.__class__)
        widget.__dict__ = dict(self.__dict__)
        widget.attrs = dict(widget.attrs)
        return widget
    
    @staticmethod
    def size_constraint_attrs(attrs, maxsize):
        """set html attributes in the attrs dict to consider maxsize"""
        pass

    def format_attrs(self):
        """return a string with html attributes available for the edit input"""
        # sort for predictability (required for tests)
        attrs = []
        for name, value in self.attrs.iteritems():
            # namespace attributes have priority over standard xhtml ones
            if name in self.cubicwebns_attributes:
                attrs.append(u'cubicweb:%s="%s"' % (name, value))
            elif name in self.html_attributes:
                attrs.append(u'%s="%s"' % (name, value))
        return u' '.join(sorted(attrs))
        
    def required(self, entity):
        """indicates if the widget needs a value to be filled in"""
        card = self.rschema.cardinality(self.subjtype, self.objtype, self.role)
        return card in '1+'

    def input_id(self, entity):
        try:
            return self.rname
        except AttributeError:
            return eid_param(self.name, entity.eid)
    
    def render_label(self, entity, label=None):
        """render widget's label"""
        label = label or self.rschema.display_name(entity.req, self.role)
        forid = self.input_id(entity)
        if forid:
            forattr =  ' for="%s"' % forid
        else:
            forattr = ''
        if self.required(entity):
            label = u'<label class="required"%s>%s</label>' % (forattr, label)
        else:
            label = u'<label%s>%s</label>' % (forattr, label)
        return label
    
    def render_error(self, entity):
        """return validation error for widget's field of the given entity, if
        any
        """
        errex = entity.req.data.get('formerrors')
        if errex and errex.eid == entity.eid and self.name in errex.errors:
            entity.req.data['displayederrors'].add(self.name)
            return u'<span class="error">%s</span>' % errex.errors[self.name]
        return u''

    def render_help(self, entity):
        """render a help message about the (edited) field"""
        req = entity.req
        help = [u'<br/>']
        descr = self.description or self.rschema.rproperty(self.subjtype, self.objtype, 'description')
        if descr:
            help.append(u'<span class="helper">%s</span>' % req._(descr))
        example = self.render_example(req)
        if example:
            help.append(u'<span class="helper">(%s: %s)</span>'
                        % (req._('sample format'), example))
        return u'&nbsp;'.join(help)
    
    def render_example(self, req):
        return u''
        
    def render(self, entity):
        """render the widget for a simple view"""
        if not entity.has_eid():
            return u''
        return entity.printable_value(self.name)
    
    def edit_render(self, entity, tabindex=None,
                    includehelp=False, useid=None, **kwargs):
        """render the widget for edition"""
        # this is necessary to handle multiple edition
        self.rname = eid_param(self.name, entity.eid)
        if useid:
            self.attrs['id'] = useid
        elif self.autoid:
            self.attrs['id'] = self.rname
        if tabindex is not None:
            self.attrs['tabindex'] = tabindex
        else:
            self.attrs['tabindex'] = entity.req.next_tabindex()
        output = self._edit_render(entity, **kwargs)
        if includehelp:
            output += self.render_help(entity)
        return output
    
    def _edit_render(self, entity):
        """do the actual job to render the widget for edition"""
        raise NotImplementedError

    def current_values(self, entity):
        """return the value of the field associated to this widget on the given
        entity. always return a list of values, which'll have size equal to 1
        if the field is monovalued (like all attribute fields, but not all non
        final relation fields
        """
        if self.rschema.is_final():
            return entity.attribute_values(self.name)
        elif entity.has_eid():
            return [row[0] for row in entity.related(self.name, self.role)]
        return ()
            
    def current_value(self, entity):
        return _value_from_values(self.current_values(entity))

    def current_display_values(self, entity):
        """same as .current_values but consider values stored in session in case
        of validation error
        """
        values = entity.req.data.get('formvalues')
        if values is None:
            return self.current_values(entity)
        cdvalues = values.get(self.rname)
        if cdvalues is None:
            return self.current_values(entity)
        if not isinstance(cdvalues, (list, tuple)):
            cdvalues = (cdvalues,)
        return cdvalues
    
    def current_display_value(self, entity):
        """same as .current_value but consider values stored in session in case
        of validation error
        """
        return _value_from_values(self.current_display_values(entity))
    
    def hidden_input(self, entity, qvalue):
        """return an hidden field which
        1. indicates that a field is edited
        2. hold the old value to easily detect if the field has been modified

        `qvalue` is the html quoted old value
        """
        if self.role == 'subject':
            editmark = 'edits'
        else:
            editmark = 'edito'
        if qvalue is None or not entity.has_eid():
            qvalue = INTERNAL_FIELD_VALUE
        return u'<input type="hidden" name="%s-%s" value="%s"/>\n' % (
            editmark, self.rname, qvalue)

class InputWidget(Widget):
    """abstract class for input generating a <input> tag"""
    input_type = None
    html_attributes = Widget.html_attributes | set(('type', 'name', 'value'))

    def _edit_render(self, entity):
        value = self.current_value(entity)
        dvalue = self.current_display_value(entity)
        if isinstance(value, basestring):
            value = html_escape(value)
        if isinstance(dvalue, basestring):
            dvalue = html_escape(dvalue)
        return u'%s<input type="%s" name="%s" value="%s" %s/>' % (
            self.hidden_input(entity, value), self.input_type,
            self.rname, dvalue, self.format_attrs())

class HiddenWidget(InputWidget):
    input_type = 'hidden'
    autoid = False
    def __init__(self, vreg, subjschema, rschema, objschema,
                 role='subject', **kwattrs):
        InputWidget.__init__(self, vreg, subjschema, rschema, objschema,
                             role='subject', 
                             **kwattrs)
        # disable access key
        del self.attrs['accesskey']

    def current_value(self, entity):
        value = InputWidget.current_value(self, entity)
        return value or INTERNAL_FIELD_VALUE

    def current_display_value(self, entity):
        value = InputWidget.current_display_value(self, entity)
        return value or INTERNAL_FIELD_VALUE
    
    def render_label(self, entity, label=None):
        """render widget's label"""
        return u''
    
    def render_help(self, entity):
        return u''
    
    def hidden_input(self, entity, value):
        """no hidden input for hidden input"""
        return ''
    

class EidWidget(HiddenWidget):

    def _edit_render(self, entity):
        return u'<input type="hidden" name="eid" value="%s" />' % entity.eid


class StringWidget(InputWidget):
    input_type = 'text'
    html_attributes = InputWidget.html_attributes | set(('size', 'maxlength'))
    @staticmethod
    def size_constraint_attrs(attrs, maxsize):
        """set html attributes in the attrs dict to consider maxsize"""
        attrs['size'] = min(maxsize, 40)
        attrs['maxlength'] = maxsize
        
        
class AutoCompletionWidget(StringWidget):
    cubicwebns_attributes = (StringWidget.cubicwebns_attributes |
                          set(('accesskey', 'size', 'maxlength')))
    attrs = ()
    
    wdgtype = 'SuggestField'
    
    def current_value(self, entity):
        value = StringWidget.current_value(self, entity)
        return value or INTERNAL_FIELD_VALUE

    def _get_url(self, entity):
        return entity.req.build_url('json', fname=entity.autocomplete_initfuncs[self.rschema],
                                pageid=entity.req.pageid, mode='remote')

    def _edit_render(self, entity):
        req = entity.req
        req.add_js( ('cubicweb.widgets.js', 'jquery.autocomplete.js') )
        req.add_css('jquery.autocomplete.css')
        value = self.current_value(entity)
        dvalue = self.current_display_value(entity)
        if isinstance(value, basestring):
            value = html_escape(value)
        if isinstance(dvalue, basestring):
            dvalue = html_escape(dvalue)
        iid = self.attrs.pop('id')
        if self.required(entity):
            cssclass = u' required'
        else:
            cssclass = u''
        dataurl = self._get_url(entity)
        return (u'%(hidden)s<input type="text" name="%(iid)s" value="%(value)s" cubicweb:dataurl="%(url)s" class="widget%(required)s" id="%(iid)s" '
                u'tabindex="%(tabindex)s" cubicweb:loadtype="auto" cubicweb:wdgtype="%(wdgtype)s"  %(attrs)s />' % {
                    'iid': iid,
                    'hidden': self.hidden_input(entity, value),
                    'wdgtype': self.wdgtype,
                    'url': html_escape(dataurl),
                    'tabindex': self.attrs.pop('tabindex'),
                    'value': dvalue,
                    'attrs': self.format_attrs(),
                    'required' : cssclass,
                    })

class StaticFileAutoCompletionWidget(AutoCompletionWidget):
    wdgtype = 'StaticFileSuggestField'
    
    def _get_url(self, entity):
        return entity.req.datadir_url + entity.autocomplete_initfuncs[self.rschema]

class RestrictedAutoCompletionWidget(AutoCompletionWidget):
    wdgtype = 'RestrictedSuggestField'    

    
class PasswordWidget(InputWidget):
    input_type = 'password'
    
    def required(self, entity):
        if InputWidget.required(self, entity) and not entity.has_eid():
            return True
        return False
    
    def current_values(self, entity):
        # on existant entity, show password field has non empty (we don't have
        # the actual value
        if entity.has_eid():
            return (INTERNAL_FIELD_VALUE,)
        return super(PasswordWidget, self).current_values(entity)

    def _edit_render(self, entity):
        html = super(PasswordWidget, self)._edit_render(entity)
        name = eid_param(self.name + '-confirm', entity.eid)
        return u'%s<br/>\n<input type="%s" name="%s" id="%s" tabindex="%s"/>&nbsp;<span class="emphasis">(%s)</span>' % (
            html, self.input_type, name, name, entity.req.next_tabindex(),
            entity.req._('confirm password'))

    
class TextWidget(Widget):
    html_attributes = Widget.html_attributes | set(('rows', 'cols'))
    
    @staticmethod
    def size_constraint_attrs(attrs, maxsize):
        """set html attributes in the attrs dict to consider maxsize"""
        if 256 < maxsize < 513:
            attrs['cols'], attrs['rows'] = 60, 5
        else:
            attrs['cols'], attrs['rows'] = 80, 10
    
    def render(self, entity):
        if not entity.has_eid():
            return u''
        return entity.printable_value(self.name)
    
    def add_fckeditor_info(self, req):
        req.add_js('fckeditor.js')
        req.fckeditor_config()
    
    def _edit_render(self, entity, with_format=True):
        req = entity.req
        editor = self._edit_render_textarea(entity, with_format)
        value = self.current_value(entity)
        if isinstance(value, basestring):
            value = html_escape(value)
        return u'%s%s' % (self.hidden_input(entity, value), editor)
    
    def _edit_render_textarea(self, entity, with_format):
        self.attrs.setdefault('cols', 80)
        self.attrs.setdefault('rows', 20)
        dvalue = self.current_display_value(entity)
        if isinstance(dvalue, basestring):
            dvalue = html_escape(dvalue)
        if entity.use_fckeditor(self.name):
            self.add_fckeditor_info(entity.req)
            if with_format:
                if entity.has_eid():
                    format = entity.format(self.name)
                else:
                    format = ''
                frname = eid_param(self.name + '_format', entity.eid)
                hidden = u'<input type="hidden" name="edits-%s" value="%s"/>\n'\
                         '<input type="hidden" name="%s" value="text/html"/>\n' % (
                    frname, format, frname)
            return u'%s<textarea cubicweb:type="wysiwyg" onkeypress="autogrow(this)" name="%s" %s>%s</textarea>' % (
                hidden, self.rname, self.format_attrs(), dvalue)
        if with_format and entity.has_format(self.name):
            fmtwdg = entity.get_widget(self.name + '_format')
            fmtwdgstr = fmtwdg.edit_render(entity, tabindex=self.attrs['tabindex'])
            self.attrs['tabindex'] = entity.req.next_tabindex()
        else:
            fmtwdgstr = ''
        return u'%s<br/><textarea onkeypress="autogrow(this)" name="%s" %s>%s</textarea>' % (
            fmtwdgstr, self.rname, self.format_attrs(), dvalue)
            
    
class CheckBoxWidget(Widget):
    html_attributes = Widget.html_attributes | set(('checked', ))
    def _edit_render(self, entity):
        value = self.current_value(entity)
        dvalue = self.current_display_value(entity)
        return self.hidden_input(entity, value) + checkbox(self.rname, 'checked', self.format_attrs(), dvalue)

    def render(self, entity):
        if not entity.has_eid():
            return u''
        if getattr(entity, self.name):
            return entity.req._('yes')
        return entity.req._('no')


class YesNoRadioWidget(CheckBoxWidget):
    html_attributes = Widget.html_attributes | set(('disabled',))
    def _edit_render(self, entity):
        value = self.current_value(entity)
        dvalue = self.current_display_value(entity)
        attrs1 = self.format_attrs()
        del self.attrs['id'] # avoid duplicate id for xhtml compliance
        attrs2 = self.format_attrs()
        if dvalue:
            attrs1 += ' checked="checked"'
        else:
            attrs2 += ' checked="checked"'
        wdgs = [self.hidden_input(entity, value),
                u'<input type="radio" name="%s" value="1" %s/>%s<br/>' % (self.rname, attrs1, entity.req._('yes')),
                u'<input type="radio" name="%s" value="" %s/>%s<br/>' % (self.rname, attrs2, entity.req._('no'))]
        return '\n'.join(wdgs)

    
class FileWidget(Widget):
    need_multipart = True
    def _file_wdg(self, entity):
        wdgs = [u'<input type="file" name="%s" %s/>' % (self.rname, self.format_attrs())]
        req = entity.req
        if entity.has_format(self.name) or entity.has_text_encoding(self.name):
            divid = '%s-%s-advanced' % (self.name, entity.eid)
            wdgs.append(u'<a href="%s" title="%s"><img src="%s" alt="%s"/></a>' %
                        (html_escape(toggle_action(divid)),
                         req._('show advanced fields'),
                         html_escape(req.build_url('data/puce_down.png')),
                         req._('show advanced fields')))
            wdgs.append(u'<div id="%s" class="hidden">' % divid)
            for extraattr in ('_format', '_encoding'):
                if entity.e_schema.has_subject_relation('%s%s' % (self.name, extraattr)):
                    ewdg = entity.get_widget(self.name + extraattr)
                    wdgs.append(ewdg.render_label(entity))
                    wdgs.append(ewdg.edit_render(entity, includehelp=True))
                    wdgs.append(u'<br/>')
            wdgs.append(u'</div>')
        if entity.has_eid():
            if not self.required(entity):
                # trick to be able to delete an uploaded file
                wdgs.append(u'<br/>')
                wdgs.append(checkbox(eid_param('__%s_detach' % self.rname, entity.eid), False))
                wdgs.append(req._('detach attached file %s' % entity.dc_title()))
            else:
                wdgs.append(u'<br/>')
                wdgs.append(req._('currently attached file: %s' % entity.dc_title()))
        return '\n'.join(wdgs)
    
    def _edit_render(self, entity):
        return self.hidden_input(entity, None) + self._file_wdg(entity)


class TextFileWidget(FileWidget):
    def _edit_msg(self, entity):
        if entity.has_eid() and not self.required(entity):
            msg = entity.req._(
                'You can either submit a new file using the browse button above'
                ', or choose to remove already uploaded file by checking the '
                '"detach attached file" check-box, or edit file content online '
                'with the widget below.')
        else:
            msg = entity.req._(
                'You can either submit a new file using the browse button above'
                ', or edit file content online with the widget below.')
        return msg
    
    def _edit_render(self, entity):
        wdgs = [self._file_wdg(entity)]
        if entity.format(self.name) in ('text/plain', 'text/html', 'text/rest'):
            msg = self._edit_msg(entity)
            wdgs.append(u'<p><b>%s</b></p>' % msg)
            twdg = TextWidget(self.vreg, self.subjtype, self.rschema, self.objtype)
            twdg.rname = self.rname
            data = getattr(entity, self.name)
            if data:
                encoding = entity.text_encoding(self.name)
                try:
                    entity[self.name] = unicode(data.getvalue(), encoding)
                except UnicodeError:
                    pass
                else:
                    wdgs.append(twdg.edit_render(entity, with_format=False))
                    entity[self.name] = data # restore Binary value
            wdgs.append(u'<br/>')
        return '\n'.join(wdgs)


class ComboBoxWidget(Widget):
    html_attributes = Widget.html_attributes | set(('multiple', 'size'))
    
    def __init__(self, vreg, subjschema, rschema, objschema,
                 multiple=False, **kwattrs):
        super(ComboBoxWidget, self).__init__(vreg, subjschema, rschema, objschema,
                                             **kwattrs)
        if multiple:
            self.attrs['multiple'] = 'multiple'
            if not 'size' in self.attrs:
                self.attrs['size'] = '5'
        # disable access key (dunno why but this is not allowed by xhtml 1.0)
        del self.attrs['accesskey']
        
    def vocabulary(self, entity):
        raise NotImplementedError()
    
    def form_value(self, entity, value, values):
        if value in values:
            flag = 'selected="selected"'
        else:
            flag = ''
        return value, flag

    def _edit_render(self, entity):
        values = self.current_values(entity)
        if values:
            res = [self.hidden_input(entity, v) for v in values]
        else:
            res = [self.hidden_input(entity, INTERNAL_FIELD_VALUE)]
        dvalues = self.current_display_values(entity)
        res.append(u'<select name="%s" %s>' % (self.rname, self.format_attrs()))
        for label, value in self.vocabulary(entity):
            if value is None:
                # handle separator
                res.append(u'<optgroup label="%s"/>' % (label or ''))
            else:
                value, flag = self.form_value(entity, value, dvalues)
                res.append(u'<option value="%s" %s>%s</option>' % (value, flag, html_escape(label)))
        res.append(u'</select>')
        return '\n'.join(res)

 
class StaticComboBoxWidget(ComboBoxWidget):
    
    def __init__(self, vreg, subjschema, rschema, objschema,
                 vocabfunc, multiple=False, sort=False, **kwattrs):
        super(StaticComboBoxWidget, self).__init__(vreg, subjschema, rschema, objschema,
                                                   multiple, **kwattrs)
        self.sort = sort
        self.vocabfunc = vocabfunc

    def vocabulary(self, entity):
        choices = self.vocabfunc(entity)
        if self.sort:
            choices = sorted(choices)
        if self.rschema.rproperty(self.subjtype, self.objtype, 'internationalizable'):
            return zip((entity.req._(v) for v in choices), choices)
        return zip(choices, choices)
    

class EntityLinkComboBoxWidget(ComboBoxWidget):
    """to be used be specific forms"""
    
    def current_values(self, entity):
        if entity.has_eid():
            return [r[0] for r in entity.related(self.name, self.role)]
        defaultmeth = 'default_%s_%s' % (self.role, self.name)
        if hasattr(entity, defaultmeth):
            return getattr(entity, defaultmeth)()
        return ()
    
    def vocabulary(self, entity):
        return [('', INTERNAL_FIELD_VALUE)] + entity.vocabulary(self.rschema, self.role)


class RawDynamicComboBoxWidget(EntityLinkComboBoxWidget):
    
    def vocabulary(self, entity, limit=None):
        req = entity.req
        # first see if its specified by __linkto form parameters
        linkedto = entity.linked_to(self.name, self.role)
        if linkedto:
            entities = (req.eid_rset(eid).get_entity(0, 0) for eid in linkedto)
            return [(entity.view('combobox'), entity.eid) for entity in entities]
        # it isn't, check if the entity provides a method to get correct values
        if not self.required(entity):
            res = [('', INTERNAL_FIELD_VALUE)]
        else:
            res = []
        # vocabulary doesn't include current values, add them
        if entity.has_eid():
            rset = entity.related(self.name, self.role)
            relatedvocab = [(e.view('combobox'), e.eid) for e in rset.entities()]
        else:
            relatedvocab = []
        return res + entity.vocabulary(self.rschema, self.role) + relatedvocab


class DynamicComboBoxWidget(RawDynamicComboBoxWidget):
    
    def vocabulary(self, entity, limit=None):
        return sorted(super(DynamicComboBoxWidget, self).vocabulary(entity, limit))


class AddComboBoxWidget(DynamicComboBoxWidget):
    def _edit_render(self, entity):
        req = entity.req
        req.add_js( ('cubicweb.ajax.js', 'jquery.js', 'cubicweb.widgets.js') )
        values = self.current_values(entity)
        if values:
            res = [self.hidden_input(entity, v) for v in values]
        else:
            res = [self.hidden_input(entity, INTERNAL_FIELD_VALUE)]
        dvalues = self.current_display_values(entity)
        etype_from = entity.e_schema.subject_relation(self.name).objects(entity.e_schema)[0]
        res.append(u'<select class="widget" cubicweb:etype_to="%s" cubicweb:etype_from="%s" cubicweb:loadtype="auto" cubicweb:wdgtype="AddComboBox" name="%s" %s>'
                   % (entity.e_schema, etype_from, self.rname, self.format_attrs()))
        for label, value in self.vocabulary(entity):
            if value is None:
                # handle separator
                res.append(u'<optgroup label="%s"/>' % (label or ''))
            else:
                value, flag = self.form_value(entity, value, dvalues)
                res.append(u'<option value="%s" %s>%s</option>' % (value, flag, html_escape(label)))
        res.append(u'</select>')
        res.append(u'<div id="newvalue">')
        res.append(u'<input type="text" id="newopt" />')
        res.append(u'<a href="javascript:noop()" id="add_newopt">&nbsp;</a></div>')
        return '\n'.join(res)

class IntegerWidget(StringWidget):
    def __init__(self, vreg, subjschema, rschema, objschema, **kwattrs):
        kwattrs['size'] = 5
        kwattrs['maxlength'] = 15
        StringWidget.__init__(self, vreg, subjschema, rschema, objschema, **kwattrs)
        
    def render_example(self, req):
        return '23'
    

        
class FloatWidget(StringWidget):
    def __init__(self, vreg, subjschema, rschema, objschema, **kwattrs):
        kwattrs['size'] = 5
        kwattrs['maxlength'] = 15
        StringWidget.__init__(self, vreg, subjschema, rschema, objschema, **kwattrs)

    def render_example(self, req):
        formatstr = req.property_value('ui.float-format')
        return formatstr % 1.23
    
    def current_values(self, entity):
        values = entity.attribute_values(self.name)
        if values:
            formatstr = entity.req.property_value('ui.float-format')
            value = values[0]
            if value is not None:
                value = float(value)
            else:
                return ()
            return [formatstr % value]
        return ()

class DecimalWidget(StringWidget):
    def __init__(self, vreg, subjschema, rschema, objschema, **kwattrs):
        kwattrs['size'] = 5
        kwattrs['maxlength'] = 15
        StringWidget.__init__(self, vreg, subjschema, rschema, objschema, **kwattrs)
        
    def render_example(self, req):
        return '345.0300'
    


class DateWidget(StringWidget):
    format_key = 'ui.date-format'
    monthnames = ("january", "february", "march", "april",
                  "may", "june", "july", "august",
                  "september", "october", "november", "december")
    
    daynames = ("monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday")
    
    def __init__(self, vreg, subjschema, rschema, objschema, **kwattrs):
        kwattrs.setdefault('size', 10)
        kwattrs.setdefault('maxlength', 10)
        StringWidget.__init__(self, vreg, subjschema, rschema, objschema, **kwattrs)

    def current_values(self, entity):
        values = entity.attribute_values(self.name)
        if values and hasattr(values[0], 'strftime'):
            formatstr = entity.req.property_value(self.format_key)
            return [values[0].strftime(formatstr)]
        return values

    def render_example(self, req):
        formatstr = req.property_value(self.format_key)
        return now().strftime(formatstr)

    @classmethod
    def add_localized_infos(cls, req):
        """inserts JS variables defining localized months and days"""
        # import here to avoid dependancy from cubicweb-common to simplejson
        _ = req._
        monthnames = [_(mname) for mname in cls.monthnames]
        daynames = [_(dname) for dname in cls.daynames]
        req.html_headers.define_var('MONTHNAMES', monthnames)
        req.html_headers.define_var('DAYNAMES', daynames)


    def _edit_render(self, entity):
        wdg = super(DateWidget, self)._edit_render(entity)
        cal_button = self.render_calendar_popup(entity)
        return wdg+cal_button

    def render_help(self, entity):
        """calendar popup widget"""
        req = entity.req
        help = [ u'<br/>' ]
        descr = self.rschema.rproperty(self.subjtype, self.objtype, 'description')
        if descr:
            help.append('<span class="helper">%s</span>' % req._(descr))
        example = self.render_example(req)
        if example:
            help.append('<span class="helper">(%s: %s)</span>'
                        % (req._('sample format'), example))
        return u'&nbsp;'.join(help)

    def render_calendar_popup(self, entity):
        """calendar popup widget"""
        req = entity.req
        self.add_localized_infos(req)
        req.add_js(('cubicweb.ajax.js', 'cubicweb.calendar.js',))
        req.add_css(('cubicweb.calendar_popup.css',))
        inputid = self.attrs.get('id', self.rname)
        helperid = "%shelper" % inputid
        _today = today()
        year = int(req.form.get('year', _today.year))
        month = int(req.form.get('month', _today.month))

        return (u"""<a onclick="toggleCalendar('%s', '%s', %s, %s);" class="calhelper">
<img src="%s" title="%s" alt="" /></a><div class="calpopup hidden" id="%s"></div>"""
                % (helperid, inputid, year, month,
                   req.external_resource('CALENDAR_ICON'), req._('calendar'), helperid) )

class DateTimeWidget(DateWidget):
    format_key = 'ui.datetime-format'
    
    def render_example(self, req):
        formatstr1 = req.property_value('ui.datetime-format')
        formatstr2 = req.property_value('ui.date-format')
        return req._('%(fmt1)s, or without time: %(fmt2)s') % {
            'fmt1': now().strftime(formatstr1),
            'fmt2': now().strftime(formatstr2),
            }




    def __init__(self, vreg, subjschema, rschema, objschema, **kwattrs):
        kwattrs['size'] = 16
        kwattrs['maxlength'] = 16
        DateWidget.__init__(self, vreg, subjschema, rschema, objschema, **kwattrs)


class TimeWidget(StringWidget):
    format_key = 'ui.time-format'
    def __init__(self, vreg, subjschema, rschema, objschema, **kwattrs):
        kwattrs['size'] = 5
        kwattrs['maxlength'] = 5
        StringWidget.__init__(self, vreg, subjschema, rschema, objschema, **kwattrs)

        
class EmailWidget(StringWidget):
    
    def render(self, entity):
        email = getattr(entity, self.name)
        if not email:
            return u''
        return u'<a href="mailto:%s">%s</a>' % (email, email)
        
class URLWidget(StringWidget):
    
    def render(self, entity):
        url = getattr(entity, self.name)
        if not url:
            return u''
        url = html_escape(url)
        return u'<a href="%s">%s</a>' % (url, url)
    
class EmbededURLWidget(StringWidget):
    
    def render(self, entity):
        url = getattr(entity, self.name)
        if not url:
            return u''
        aurl = html_escape(entity.build_url('embed', url=url))
        return u'<a href="%s">%s</a>' % (aurl, url)



class PropertyKeyWidget(ComboBoxWidget):
    """specific widget for EProperty.pkey field to set the value widget according to
    the selected key
    """
    
    def _edit_render(self, entity):
        entity.req.add_js( ('cubicweb.ajax.js', 'cubicweb.edition.js') )
        vtabindex = self.attrs.get('tabindex', 0) + 1
        self.attrs['onchange'] = "javascript:setPropValueWidget('%s', %s)" % (
            entity.eid, vtabindex)
        # limit size
        if not entity.has_eid():
            self.attrs['size'] = 10
        else:
            self.attrs['size'] = 1
        return super(PropertyKeyWidget, self)._edit_render(entity)
    
    def vocabulary(self, entity):
        _ = entity.req._
        if entity.has_eid():
            return [(_(entity.pkey), entity.pkey)]
        # key beginning with 'system.' should usually not be edited by hand
        choices = entity.vreg.user_property_keys()
        return sorted(zip((_(v) for v in choices), choices))


class PropertyValueWidget(Widget):
    """specific widget for EProperty.value field which will be different according to
    the selected key type and vocabulary information
    """
    
    def render_help(self, entity):
        return u''
        
    def render(self, entity):
        assert entity.has_eid()
        w = self.vreg.property_value_widget(entity.pkey, req=entity.req, **self.attrs)
        return w.render(entity)
        
    def _edit_render(self, entity):
        if not entity.has_eid():
            # no key set yet, just include an empty div which will be filled
            # on key selection
            # empty span as well else html validation fail (label is refering to this id)
            return u'<div id="div:%s"><span id="%s"/></div>' % (self.rname, self.attrs.get('id'))
        w = self.vreg.property_value_widget(entity.pkey, req=entity.req, **self.attrs)
        if entity.pkey.startswith('system.'):
            value = '<span class="value" id="%s">%s</span>' % (self.attrs.get('id'), w.render(entity))
            msg = entity.req._('value associated to this key is not editable manually')
            return value + '<div>%s</div>' % msg
        return w.edit_render(entity, self.attrs.get('tabindex'), includehelp=True)
    

def widget_factory(vreg, subjschema, rschema, objschema, role='subject',
                   **kwargs):
    """return the most adapated widget to edit the relation
    'subjschema rschema objschema' according to information found in the schema
    """
    if role == 'subject':
        eclass, subjschema = _eclass_eschema(subjschema)
    else:
        eclass, objschema = _eclass_eschema(objschema)
    if eclass is not None and rschema in eclass.widgets:
        wcls = WIDGETS[eclass.widgets[rschema]]
    elif not rschema.is_final():
        card = rschema.rproperty(subjschema, objschema, 'cardinality')
        if role == 'object':
            multiple = card[1] in '+*'
        else: #if role == 'subject':
            multiple = card[0] in '+*'
        return DynamicComboBoxWidget(vreg, subjschema, rschema, objschema,
                                     role=role, multiple=multiple)
    else:
        wcls = None
    factory = FACTORIES.get(objschema, _default_widget_factory)
    return factory(vreg, subjschema, rschema, objschema, wcls=wcls,
                   role=role, **kwargs)


# factories to find the most adapated widget according to a type and other constraints
                
def _string_widget_factory(vreg, subjschema, rschema, objschema, wcls=None, **kwargs):
    w = None
    for c in rschema.rproperty(subjschema, objschema, 'constraints'):
        if isinstance(c, StaticVocabularyConstraint):
            # may have been set by a previous SizeConstraint but doesn't make sense
            # here (even doesn't have the same meaning on a combobox actually)
            kwargs.pop('size', None) 
            return (wcls or StaticComboBoxWidget)(vreg, subjschema, rschema, objschema,
                                                  vocabfunc=c.vocabulary, **kwargs)
        if isinstance(c, SizeConstraint) and c.max is not None:
            # don't return here since a StaticVocabularyConstraint may
            # follow
            if wcls is None:
                if c.max < 257:
                    _wcls = StringWidget
                else:
                    _wcls = TextWidget
            else:
                _wcls = wcls
            _wcls.size_constraint_attrs(kwargs, c.max)
            w = _wcls(vreg, subjschema, rschema, objschema, **kwargs)
    if w is None:
        w = (wcls or TextWidget)(vreg, subjschema, rschema, objschema, **kwargs)
    return w

def _default_widget_factory(vreg, subjschema, rschema, objschema, wcls=None, **kwargs):
    if wcls is None:
        wcls = _WFACTORIES[objschema]
    return wcls(vreg, subjschema, rschema, objschema, **kwargs)

FACTORIES = {
    'String' :  _string_widget_factory,
    'Boolean':  _default_widget_factory,
    'Bytes':    _default_widget_factory,
    'Date':     _default_widget_factory,
    'Datetime': _default_widget_factory,
    'Float':    _default_widget_factory,
    'Decimal':    _default_widget_factory,
    'Int':      _default_widget_factory,
    'Password': _default_widget_factory,
    'Time':     _default_widget_factory,
    }

# default widget by entity's type
_WFACTORIES = {
    'Boolean':  YesNoRadioWidget,
    'Bytes':    FileWidget,
    'Date':     DateWidget,
    'Datetime': DateTimeWidget,
    'Int':      IntegerWidget,
    'Float':    FloatWidget,
    'Decimal':  DecimalWidget,
    'Password': PasswordWidget,
    'String' :  StringWidget,
    'Time':     TimeWidget,
    }
    
# widgets registry
WIDGETS = {}
def register(widget_list):
    for obj in widget_list:
        if isinstance(obj, type) and issubclass(obj, Widget):
            if obj is Widget or obj is ComboBoxWidget:
                continue
            WIDGETS[obj.__name__] = obj

register(globals().values())
