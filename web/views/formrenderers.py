"""form renderers, responsible to layout a form to html

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common import dictattr
from logilab.mtconverter import xml_escape

from simplejson import dumps

from cubicweb import tags
from cubicweb.appobject import AppObject
from cubicweb.selectors import implements, yes
from cubicweb.web import eid_param, formwidgets as fwdgs


def checkbox(name, value, attrs='', checked=None):
    if checked is None:
        checked = value
    checked = checked and 'checked="checked"' or ''
    return u'<input type="checkbox" name="%s" value="%s" %s %s />' % (
        name, value, checked, attrs)


class FormRenderer(AppObject):
    """basic renderer displaying fields in a two columns table label | value

    +--------------+--------------+
    | field1 label | field1 input |
    +--------------+--------------+
    | field1 label | field2 input |
    +--------------+--------------+
    +---------+
    | buttons |
    +---------+
    """
    __registry__ = 'formrenderers'
    __regid__ = 'default'

    _options = ('display_label', 'display_help',
                'display_progress_div', 'table_class', 'button_bar_class',
                # add entity since it may be given to select the renderer
                'entity')
    display_label = True
    display_help = True
    display_progress_div = True
    table_class = u'attributeForm'
    button_bar_class = u'formButtonBar'

    def __init__(self, req=None, rset=None, row=None, col=None, **kwargs):
        super(FormRenderer, self).__init__(req, rset=rset, row=row, col=col)
        if self._set_options(kwargs):
            raise ValueError('unconsumed arguments %s' % kwargs)

    def _set_options(self, kwargs):
        for key in self._options:
            try:
                setattr(self, key, kwargs.pop(key))
            except KeyError:
                continue
        return kwargs

    # renderer interface ######################################################

    def render(self, form, values):
        self._set_options(values)
        form.add_media()
        data = []
        w = data.append
        w(self.open_form(form, values))
        if self.display_progress_div:
            w(u'<div id="progress">%s</div>' % self._cw._('validating...'))
        w(u'<fieldset>')
        w(tags.input(type=u'hidden', name=u'__form_id',
                     value=values.get('formvid', form.__regid__)))
        if form.redirect_path:
            w(tags.input(type='hidden', name='__redirectpath', value=form.redirect_path))
        self.render_fields(w, form, values)
        self.render_buttons(w, form)
        w(u'</fieldset>')
        w(u'</form>')
        errormsg = self.error_message(form)
        if errormsg:
            data.insert(0, errormsg)
        return '\n'.join(data)

    def render_label(self, form, field):
        if field.label is None:
            return u''
        if isinstance(field.label, tuple): # i.e. needs contextual translation
            label = self._cw.pgettext(*field.label)
        else:
            label = self._cw._(field.label)
        attrs = {'for': form.context[field]['id']}
        if field.required:
            attrs['class'] = 'required'
        return tags.label(label, **attrs)

    def render_help(self, form, field):
        help = []
        descr = field.help
        if callable(descr):
            descr = descr(form)
        if descr:
            help.append('<div class="helper">%s</div>' % self._cw._(descr))
        example = field.example_format(self._cw)
        if example:
            help.append('<div class="helper">(%s: %s)</div>'
                        % (self._cw._('sample format'), example))
        return u'&#160;'.join(help)

    # specific methods (mostly to ease overriding) #############################

    def error_message(self, form):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        req = self._cw
        errex = form.form_valerror
        # get extra errors
        if errex is not None:
            errormsg = req._('please correct the following errors:')
            displayed = form.form_displayed_errors
            errors = sorted((field, err) for field, err in errex.errors.items()
                            if not field in displayed)
            if errors:
                if len(errors) > 1:
                    templstr = '<li>%s</li>\n'
                else:
                    templstr = '&#160;%s\n'
                for field, err in errors:
                    if field is None:
                        errormsg += templstr % err
                    else:
                        errormsg += templstr % '%s: %s' % (req._(field), err)
                if len(errors) > 1:
                    errormsg = '<ul>%s</ul>' % errormsg
            return u'<div class="errorMessage">%s</div>' % errormsg
        return u''

    def open_form(self, form, values):
        if form.form_needs_multipart:
            enctype = 'multipart/form-data'
        else:
            enctype = 'application/x-www-form-urlencoded'
        if form.action is None:
            action = self._cw.build_url('edit')
        else:
            action = form.action
        tag = ('<form action="%s" method="post" enctype="%s"' % (
            xml_escape(action or '#'), enctype))
        if form.domid:
            tag += ' id="%s"' % form.domid
        if form.onsubmit:
            tag += ' onsubmit="%s"' % xml_escape(form.onsubmit % dictattr(form))
        if form.cssstyle:
            tag += ' style="%s"' % xml_escape(form.cssstyle)
        if form.cssclass:
            tag += ' class="%s"' % xml_escape(form.cssclass)
        if form.cwtarget:
            tag += ' cubicweb:target="%s"' % xml_escape(form.cwtarget)
        return tag + '>'

    def render_fields(self, w, form, values):
        fields = self._render_hidden_fields(w, form)
        if fields:
            self._render_fields(fields, w, form)
        self.render_child_forms(w, form, values)

    def render_child_forms(self, w, form, values):
        # render
        for childform in getattr(form, 'forms', []):
            self.render_fields(w, childform, values)

    def _render_hidden_fields(self, w, form):
        fields = form.fields[:]
        for field in form.fields:
            if not field.is_visible():
                w(field.render(form, self))
                fields.remove(field)
        return fields

    def _render_fields(self, fields, w, form):
        byfieldset = {}
        for field in fields:
            byfieldset.setdefault(field.fieldset, []).append(field)
        if form.fieldsets_in_order:
            fieldsets = form.fieldsets_in_order
        else:
            fieldsets = byfieldset.keys()
        for fieldset in fieldsets:
            try:
                fields = byfieldset.pop(fieldset)
            except KeyError:
                self.warning('no such fieldset: %s (%s)', fieldset, form)
                continue
            w(u'<fieldset class="%s">' % (fieldset or u'default'))
            if fieldset:
                w(u'<legend>%s</legend>' % self._cw._(fieldset))
            w(u'<table class="%s">' % self.table_class)
            for field in fields:
                w(u'<tr class="%s_%s_row">' % (field.name, field.role))
                if self.display_label:
                    w(u'<th class="labelCol">%s</th>' % self.render_label(form, field))
                error = form.form_field_error(field)
                if error:
                    w(u'<td class="error">')
                    w(error)
                else:
                    w(u'<td>')
                w(field.render(form, self))
                if self.display_help:
                    w(self.render_help(form, field))
                w(u'</td></tr>')
            w(u'</table></fieldset>')
        if byfieldset:
            self.warning('unused fieldsets: %s', ', '.join(byfieldset))

    def render_buttons(self, w, form):
        if not form.form_buttons:
            return
        w(u'<table class="%s">\n<tr>\n' % self.button_bar_class)
        for button in form.form_buttons:
            w(u'<td>%s</td>\n' % button.render(form))
        w(u'</tr></table>')


class BaseFormRenderer(FormRenderer):
    """use form_renderer_id = 'base' if you want base FormRenderer layout even
    when selected for an entity
    """
    __regid__ = 'base'



class HTableFormRenderer(FormRenderer):
    """display fields horizontally in a table

    +--------------+--------------+---------+
    | field1 label | field2 label |         |
    +--------------+--------------+---------+
    | field1 input | field2 input | buttons
    +--------------+--------------+---------+
    """
    __regid__ = 'htable'

    display_help = False
    def _render_fields(self, fields, w, form):
        w(u'<table border="0" class="htableForm">')
        w(u'<tr>')
        for field in fields:
            if self.display_label:
                w(u'<th class="labelCol">%s</th>' % self.render_label(form, field))
            if self.display_help:
                w(self.render_help(form, field))
        # empty slot for buttons
        w(u'<th class="labelCol">&#160;</th>')
        w(u'</tr>')
        w(u'<tr>')
        for field in fields:
            error = form.form_field_error(field)
            if error:
                w(u'<td class="error">')
                w(error)
            else:
                w(u'<td>')
            w(field.render(form, self))
            w(u'</td>')
        w(u'<td>')
        for button in form.form_buttons:
            w(button.render(form))
        w(u'</td>')
        w(u'</tr>')
        w(u'</table>')

    def render_buttons(self, w, form):
        pass


class EntityCompositeFormRenderer(FormRenderer):
    """specific renderer for multiple entities edition form (muledit)"""
    __regid__ = 'composite'

    _main_display_fields = None

    def render_fields(self, w, form, values):
        if form.parent_form is None:
            w(u'<table class="listing">')
            subfields = [field for field in form.forms[0].fields
                         if self.display_field(form, field)
                         and field.is_visible()]
            if subfields:
                # main form, display table headers
                w(u'<tr class="header">')
                w(u'<th align="left">%s</th>' %
                  tags.input(type='checkbox',
                             title=self._cw._('toggle check boxes'),
                             onclick="setCheckboxesState('eid', this.checked)"))
                for field in subfields:
                    w(u'<th>%s</th>' % self._cw._(field.label))
                w(u'</tr>')
        super(EntityCompositeFormRenderer, self).render_fields(w, form, values)
        if form.parent_form is None:
            w(u'</table>')
            if self._main_display_fields:
                super(EntityCompositeFormRenderer, self)._render_fields(
                    self._main_display_fields, w, form)

    def _render_fields(self, fields, w, form):
        if form.parent_form is not None:
            entity = form.edited_entity
            values = form.form_previous_values
            qeid = eid_param('eid', entity.eid)
            cbsetstate = "setCheckboxesState2('eid', %s, 'checked')" % \
                         xml_escape(dumps(entity.eid))
            w(u'<tr class="%s">' % (entity.cw_row % 2 and u'even' or u'odd'))
            # XXX turn this into a widget used on the eid field
            w(u'<td>%s</td>' % checkbox('eid', entity.eid,
                                        checked=qeid in values))
            for field in fields:
                error = form.form_field_error(field)
                if error:
                    w(u'<td class="error">')
                    w(error)
                else:
                    w(u'<td>')
                if isinstance(field.widget, (fwdgs.Select, fwdgs.CheckBox,
                                             fwdgs.Radio)):
                    field.widget.attrs['onchange'] = cbsetstate
                elif isinstance(field.widget, fwdgs.Input):
                    field.widget.attrs['onkeypress'] = cbsetstate
                # XXX else
                w(u'<div>%s</div>' % field.render(form, self))
                w(u'</td>\n')
            w(u'</tr>')
        else:
            self._main_display_fields = fields


class EntityFormRenderer(BaseFormRenderer):
    """specific renderer for entity edition form (edition)"""
    __regid__ = 'default'
    # needs some additional points in some case (XXX explain cases)
    __select__ = implements('Any') & yes()

    _options = FormRenderer._options + ('display_relations_form', 'main_form_title')
    display_relations_form = True
    main_form_title = _('main informations')

    def render(self, form, values):
        rendered = super(EntityFormRenderer, self).render(form, values)
        return rendered + u'</div>' # close extra div introducted by open_form

    def open_form(self, form, values):
        attrs_fs_label = ''
        if self.main_form_title:
            attrs_fs_label += ('<div class="iformTitle"><span>%s</span></div>'
                               % self._cw._(self.main_form_title))
        attrs_fs_label += '<div class="formBody">'
        return attrs_fs_label + super(EntityFormRenderer, self).open_form(form, values)

    def render_fields(self, w, form, values):
        super(EntityFormRenderer, self).render_fields(w, form, values)
        self.inline_entities_form(w, form)
        if form.edited_entity.has_eid() and self.display_relations_form:
            self.relations_form(w, form)

    def _render_fields(self, fields, w, form):
        if not form.edited_entity.has_eid() or form.edited_entity.has_perm('update'):
            super(EntityFormRenderer, self)._render_fields(fields, w, form)

    def render_buttons(self, w, form):
        if len(form.form_buttons) == 3:
            w("""<table width="100%%">
  <tbody>
   <tr><td align="center">
     %s
   </td><td style="align: right; width: 50%%;">
     %s
     %s
   </td></tr>
  </tbody>
 </table>""" % tuple(button.render(form) for button in form.form_buttons))
        else:
            super(EntityFormRenderer, self).render_buttons(w, form)

    def relations_form(self, w, form):
        try:
            srels_by_cat = form.srelations_by_category('generic', 'add', strict=True)
            warn('[3.6] %s: srelations_by_category is deprecated, override '
                 'editable_relations instead' % classid(form), DeprecationWarning)
        except AttributeError:
            srels_by_cat = form.editable_relations()
        if not srels_by_cat:
            return u''
        req = self._cw
        _ = req._
        __ = _
        label = u'%s :' % __('This %s' % form.edited_entity.e_schema).capitalize()
        eid = form.edited_entity.eid
        w(u'<fieldset class="subentity">')
        w(u'<legend class="iformTitle">%s</legend>' % label)
        w(u'<table id="relatedEntities">')
        for rschema, target, related in form.relations_table():
            # already linked entities
            if related:
                w(u'<tr><th class="labelCol">%s</th>' % rschema.display_name(req, target))
                w(u'<td>')
                w(u'<ul>')
                for viewparams in related:
                    w(u'<li class="invisible">%s<div id="span%s" class="%s">%s</div></li>'
                      % (viewparams[1], viewparams[0], viewparams[2], viewparams[3]))
                if not form.force_display and form.maxrelitems < len(related):
                    link = (u'<span class="invisible">'
                            '[<a href="javascript: window.location.href+=\'&amp;__force_display=1\'">%s</a>]'
                            '</span>' % self._cw._('view all'))
                    w(u'<li class="invisible">%s</li>' % link)
                w(u'</ul>')
                w(u'</td>')
                w(u'</tr>')
        pendings = list(form.restore_pending_inserts())
        if not pendings:
            w(u'<tr><th>&#160;</th><td>&#160;</td></tr>')
        else:
            for row in pendings:
                # soon to be linked to entities
                w(u'<tr id="tr%s">' % row[1])
                w(u'<th>%s</th>' % row[3])
                w(u'<td>')
                w(u'<a class="handle" title="%s" href="%s">[x]</a>' %
                  (_('cancel this insert'), row[2]))
                w(u'<a id="a%s" class="editionPending" href="%s">%s</a>'
                  % (row[1], row[4], xml_escape(row[5])))
                w(u'</td>')
                w(u'</tr>')
        w(u'<tr id="relationSelectorRow_%s" class="separator">' % eid)
        w(u'<th class="labelCol">')
        w(u'<span>%s</span>' % _('add relation'))
        w(u'<select id="relationSelector_%s" tabindex="%s" '
          'onchange="javascript:showMatchingSelect(this.options[this.selectedIndex].value,%s);">'
          % (eid, req.next_tabindex(), xml_escape(dumps(eid))))
        w(u'<option value="">%s</option>' % _('select a relation'))
        for i18nrtype, rschema, target in srels_by_cat:
            # more entities to link to
            w(u'<option value="%s_%s">%s</option>' % (rschema, target, i18nrtype))
        w(u'</select>')
        w(u'</th>')
        w(u'<td id="unrelatedDivs_%s"></td>' % eid)
        w(u'</tr>')
        w(u'</table>')
        w(u'</fieldset>')

    # NOTE: should_* and display_* method extracted and moved to the form to
    # ease overriding

    def inline_entities_form(self, w, form):
        """create a form to edit entity's inlined relations"""
        if not hasattr(form, 'inlined_form_views'):
            return
        keysinorder = []
        formviews = form.inlined_form_views()
        for formview in formviews:
            if not (formview.rtype, formview.role) in keysinorder:
                keysinorder.append( (formview.rtype, formview.role) )
        for key in keysinorder:
            self.inline_relation_form(w, form, [fv for fv in formviews
                                                if (fv.rtype, fv.role) == key])

    def inline_relation_form(self, w, form, formviews):
        i18nctx = 'inlined:%s.%s.%s' % (form.edited_entity.e_schema,
                                        formviews[0].rtype, formviews[0].role)
        w(u'<div id="inline%sslot">' % formviews[0].rtype)
        for formview in formviews:
            w(formview.render(i18nctx=i18nctx, row=formview.row, col=formview.col))
        w(u'</div>')


class EntityInlinedFormRenderer(EntityFormRenderer):
    """specific renderer for entity inlined edition form
    (inline-[creation|edition])
    """
    __regid__ = 'inline'

    def render(self, form, values):
        form.add_media()
        data = []
        w = data.append
        try:
            w(u'<div id="div-%(divid)s" onclick="%(divonclick)s">' % values)
        except KeyError:
            w(u'<div id="div-%(divid)s">' % values)
        else:
            w(u'<div id="notice-%s" class="notice">%s</div>' % (
                values['divid'], self._cw._('click on the box to cancel the deletion')))
        w(u'<div class="iformBody">')
        eschema = form.edited_entity.e_schema
        ctx = values.pop('i18nctx')
        values['removemsg'] = self._cw.pgettext(ctx, 'remove this %s' % eschema)
        w(u'<div class="iformTitle"><span>%(title)s</span> '
          '#<span class="icounter">%(counter)s</span> '
          '[<a href="javascript: %(removejs)s;noop();">%(removemsg)s</a>]</div>'
          % values)
        # cleanup values
        for key in ('title', 'removejs', 'removemsg'):
            values.pop(key)
        self.render_fields(w, form, values)
        w(u'</div></div>')
        return '\n'.join(data)

    def render_fields(self, w, form, values):
        w(u'<fieldset id="fs-%(divid)s">' % values)
        fields = self._render_hidden_fields(w, form)
        w(u'</fieldset>')
        w(u'<fieldset class="subentity">')
        if fields:
            self._render_fields(fields, w, form)
        self.render_child_forms(w, form, values)
        self.inline_entities_form(w, form)
        w(u'</fieldset>')

