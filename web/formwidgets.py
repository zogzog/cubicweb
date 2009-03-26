"""widget classes for form construction

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from datetime import date

from cubicweb.common import tags

class FieldWidget(object):
    needs_js = ()
    needs_css = ()
    setdomid = True
    settabindex = True
    
    def __init__(self, attrs=None, setdomid=None, settabindex=None):
        self.attrs = attrs or {}
        if setdomid is not None:
            # override class's default value
            self.setdomid = setdomid
        if settabindex is not None:
            # override class's default value
            self.settabindex = settabindex

    def add_media(self, form):
        """adds media (CSS & JS) required by this widget"""
        if self.needs_js:
            form.req.add_js(self.needs_js)
        if self.needs_css:
            form.req.add_css(self.needs_css)
        
    def render(self, form, field):
        raise NotImplementedError

    def _render_attrs(self, form, field):
        name = form.context[field]['name']
        values = form.context[field]['value']
        if not isinstance(values, (tuple, list)):
            values = (values,)
        attrs = dict(self.attrs)
        if self.setdomid:
            attrs['id'] = form.context[field]['id']
        if self.settabindex:
            attrs['tabindex'] = form.req.next_tabindex()
        return name, values, attrs


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
    
    def render(self, form, field):
        self.add_media(form)
        name, values, attrs = self._render_attrs(form, field)
        assert len(values) == 1
        id = attrs.pop('id')
        confirmname = '%s-confirm:%s' % tuple(name.rsplit(':', 1))
        inputs = [tags.input(name=name, value=values[0], type=self.type, id=id, **attrs),
                  '<br/>',
                  tags.input(name=confirmname, type=self.type, **attrs),
                  '&nbsp;', tags.span(form.req._('confirm password'),
                                      **{'class': 'emphasis'})]
        return u'\n'.join(inputs)


class FileInput(Input):
    type = 'file'
    
    def _render_attrs(self, form, field):
        # ignore value which makes no sense here (XXX even on form validation error?)
        name, values, attrs = super(FileInput, self)._render_attrs(form, field)
        return name, ('',), attrs

        
class HiddenInput(Input):
    type = 'hidden'
    setdomid = False # by default, don't set id attribute on hidden input
    settabindex = False

    
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
    def __init__(self, *args, **kwargs):
        super(FCKEditor, self).__init__(*args, **kwargs)
        self.attrs['cubicweb:type'] = 'wysiwyg'
    
    def render(self, form, field):
        form.req.fckeditor_config()
        return super(FCKEditor, self).render(form, field)


class Select(FieldWidget):
    def __init__(self, attrs=None, multiple=False):
        super(Select, self).__init__(attrs)
        self.multiple = multiple
        
    def render(self, form, field):
        name, curvalues, attrs = self._render_attrs(form, field)
        options = []
        for label, value in field.vocabulary(form):
            if value in curvalues:
                options.append(tags.option(label, value=value, selected='selected'))
            else:
                options.append(tags.option(label, value=value))
        return tags.select(name=name, multiple=self.multiple,
                           options=options, **attrs)


class CheckBox(Input):
    type = 'checkbox'
    
    def render(self, form, field):
        name, curvalues, attrs = self._render_attrs(form, field)
        options = []
        for label, value in field.vocabulary(form):
            if value in curvalues:
                tag = tags.input(name=name, value=value, type=self.type,
                                 checked='checked', **attrs)
            else:
                tag = tags.input(name=name, value=value, type=self.type,
                                 **attrs)
            options.append(tag + label)
        return '<br/>\n'.join(options)

        
class Radio(Input):
    type = 'radio'
    setdomid = False
    
    def render(self, form, field):
        name, curvalues, attrs = self._render_attrs(form, field)
        options = []
        for label, value in field.vocabulary(form):
            if value in curvalues:
                options.append(tags.input(name=name, type=self.type, value=value, checked='checked', **attrs))
            else:
                options.append(tags.option(name=name, type=self.type, value=value, **attrs))
            options[-1] += label + '<br/>'
        return '\n'.join(options)


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
        self.add_localized_infos(form.req)
        cal_button = self._render_calendar_popup(form, field)
        return txtwidget + cal_button
    
    def _render_calendar_popup(self, form, field):
        req = form.req
        value = form.context[field]['rawvalue']
        inputid = form.context[field]['id']
        helperid = '%shelper' % inputid
        if not value:
            value = date.today()
        year, month = value.year, value.month
        return (u"""<a onclick="toggleCalendar('%s', '%s', %s, %s);" class="calhelper">
<img src="%s" title="%s" alt="" /></a><div class="calpopup hidden" id="%s"></div>"""
                % (helperid, inputid, year, month,
                   req.external_resource('CALENDAR_ICON'),
                   req._('calendar'), helperid) )


class AjaxWidget(FieldWidget):
    def __init__(self, wdgtype, inputid=None, **kwargs):
        super(AjaxWidget, self).__init__(**kwargs)
        self.attrs.setdefault('class', 'widget')
        self.attrs.setdefault('cubicweb:loadtype', 'auto')
        self.attrs['cubicweb:wdgtype'] = wdgtype
        if inputid is not None:
            self.attrs['cubicweb:inputid'] = inputid
            
    def render(self, form, field):
        self.add_media(form)
        attrs = self._render_attrs(form, field)[-1]
        return tags.div(**attrs)
