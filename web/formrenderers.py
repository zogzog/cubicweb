"""form renderers, responsible to layout a form to html

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common import dictattr
from logilab.mtconverter import html_escape

from simplejson import dumps

from cubicweb.common import tags
from cubicweb.web import eid_param
from cubicweb.web import formwidgets as fwdgs
from cubicweb.web.widgets import checkbox


class FormRenderer(object):
    """basic renderer displaying fields in a two columns table label | value
    """
    display_fields = None # None -> all fields
    display_label = True
    display_help = True
    display_progress_div = True
    button_bar_class = u'formButtonBar'
    
    def __init__(self, **kwargs):
        if self._set_options(kwargs):
            raise ValueError('unconsumed arguments %s' % kwargs)

    def _set_options(self, kwargs):
        for key in ('display_fields', 'display_label', 'display_help',
                    'display_progress_div', 'button_bar_class'):
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
            w(u'<div id="progress">%s</div>' % form.req._('validating...'))
        w(u'<fieldset>')
        w(tags.input(type=u'hidden', name=u'__form_id',
                     value=values.get('formvid', form.id)))
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
        label = form.req._(field.label)
        attrs = {'for': form.context[field]['id']}
        if field.required:
            attrs['class'] = 'required'
        return tags.label(label, **attrs)

    def render_help(self, form, field):
        help = [ u'<br/>' ]
        descr = field.help
        if descr:
            help.append('<span class="helper">%s</span>' % form.req._(descr))
        example = field.example_format(form.req)
        if example:
            help.append('<span class="helper">(%s: %s)</span>'
                        % (form.req._('sample format'), example))
        return u'&nbsp;'.join(help)

    # specific methods (mostly to ease overriding) #############################

    def error_message(self, form):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        req = form.req
        errex = req.data.get('formerrors')
        # get extra errors
        if errex is not None:
            errormsg = req._('please correct the following errors:')
            displayed = req.data['displayederrors']
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
            action = form.req.build_url('edit')
        else:
            action = form.action
        tag = ('<form action="%s" method="post" enctype="%s"' % (
            html_escape(action or '#'), enctype))
        if form.domid:
            tag += ' id="%s"' % form.domid
        if form.onsubmit:
            tag += ' onsubmit="%s"' % html_escape(form.onsubmit % dictattr(form))
        if form.cssstyle:
            tag += ' style="%s"' % html_escape(form.cssstyle)
        if form.cssclass:
            tag += ' class="%s"' % html_escape(form.cssclass)
        if form.cwtarget:
            tag += ' cubicweb:target="%s"' % html_escape(form.cwtarget)
        return tag + '>'
    
    def display_field(self, form, field):
        return (self.display_fields is None
                or field.name in self.display_fields
                or field.name in form.internal_fields)
    
    def render_fields(self, w, form, values):
        form.form_build_context(values)
        fields = self._render_hidden_fields(w, form)
        if fields:
            self._render_fields(fields, w, form, values)
        self.render_child_forms(w, form, values)
        
    def render_child_forms(self, w, form, values):
        # render 
        for childform in getattr(form, 'forms', []):
            self.render_fields(w, childform, values)

    def _render_hidden_fields(self, w, form):
        fields = form.fields[:]
        for field in form.fields:
            if not self.display_field(form, field):
                fields.remove(field)
            elif not field.is_visible():
                w(field.render(form, self))
                fields.remove(field)
        return fields
    
    def _render_fields(self, fields, w, form, values):
        w(u'<table class="attributeForm" style="width:100%;">')
        for field in fields:
            w(u'<tr>')
            if self.display_label:
                w(u'<th class="labelCol">%s</th>' % self.render_label(form, field))
            error = form.form_field_error(field)
            if error:
                w(u'<td class="error" style="width:100%;">')
                w(error)
            else:
                w(u'<td style="width:100%;">')
            w(field.render(form, self))
            if self.display_help:
                w(self.render_help(form, field))
            w(u'</td></tr>')
        w(u'</table>')

    def render_buttons(self, w, form):
        w(u'<table class="%s">\n<tr>\n' % self.button_bar_class)
        for button in form.form_buttons:
            w(u'<td>%s</td>\n' % button.render(form))
        w(u'</tr></table>')


    
class EntityCompositeFormRenderer(FormRenderer):
    """specific renderer for multiple entities edition form (muledit)"""
    def render_fields(self, w, form, values):
        if not form.is_subform:
            w(u'<table class="listing">')
        super(EntityCompositeFormRenderer, self).render_fields(w, form, values)
        if not form.is_subform:
            w(u'</table>')
        
    def _render_fields(self, fields, w, form, values):
        if form.is_subform:
            entity = form.edited_entity
            values = form.req.data.get('formvalues', ())
            qeid = eid_param('eid', entity.eid)
            cbsetstate = "setCheckboxesState2('eid', %s, 'checked')" % html_escape(dumps(entity.eid))
            w(u'<tr class="%s">' % (entity.row % 2 and u'even' or u'odd'))
            # XXX turn this into a widget used on the eid field
            w(u'<td>%s</td>' % checkbox('eid', entity.eid, checked=qeid in values))
            for field in fields:
                error = form.form_field_error(field)
                if error:
                    w(u'<td class="error">')
                    w(error)
                else:
                    w(u'<td>')
                if isinstance(field.widget, (fwdgs.Select, fwdgs.CheckBox, fwdgs.Radio)):
                    field.widget.attrs['onchange'] = cbsetstate
                elif isinstance(field.widget, fwdgs.Input):
                    field.widget.attrs['onkeypress'] = cbsetstate
                w(u'<div>%s</div>' % field.render(form, self))
                w(u'/<td>')
        else:
            # main form, display table headers
            w(u'<tr class="header">')
            w(u'<th align="left">%s</th>'
              % tags.input(type='checkbox', title=form.req._('toggle check boxes'),
                           onclick="setCheckboxesState('eid', this.checked)"))
            for field in self.forms[0].fields:
                if self.display_field(form, field) and field.is_visible():
                    w(u'<th>%s</th>' % form.req._(field.label))
        w(u'</tr>')
            

            
class EntityFormRenderer(FormRenderer):
    """specific renderer for entity edition form (edition)"""
        
    def render(self, form, values):
        rendered = super(EntityFormRenderer, self).render(form, values)
        return rendered + u'</div>' # close extra div introducted by open_form
        
    def open_form(self, form, values):
        attrs_fs_label = ('<div class="iformTitle"><span>%s</span></div>'
                          % form.req._('main informations'))
        attrs_fs_label += '<div class="formBody">'
        return attrs_fs_label + super(EntityFormRenderer, self).open_form(form, values)

    def render_fields(self, w, form, values):
        super(EntityFormRenderer, self).render_fields(w, form, values)
        self.inline_entities_form(w, form)
        if form.edited_entity.has_eid():
            self.relations_form(w, form)

    def _render_fields(self, fields, w, form, values):
        if not form.edited_entity.has_eid() or form.edited_entity.has_perm('update'):
            super(EntityFormRenderer, self)._render_fields(fields, w, form, values)
            
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
        srels_by_cat = form.srelations_by_category(('generic', 'metadata'), 'add')
        if not srels_by_cat:
            return u''
        req = form.req
        _ = req._
        label = u'%s :' % _('This %s' % form.edited_entity.e_schema).capitalize()
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
                            '</span>' % form.req._('view all'))
                    w(u'<li class="invisible">%s</li>' % link)
                w(u'</ul>')
                w(u'</td>')
                w(u'</tr>')
        pendings = list(form.restore_pending_inserts())
        if not pendings:
            w(u'<tr><th>&nbsp;</th><td>&nbsp;</td></tr>')
        else:
            for row in pendings:
                # soon to be linked to entities
                w(u'<tr id="tr%s">' % row[1])
                w(u'<th>%s</th>' % row[3])
                w(u'<td>')
                w(u'<a class="handle" title="%s" href="%s">[x]</a>' %
                  (_('cancel this insert'), row[2]))
                w(u'<a id="a%s" class="editionPending" href="%s">%s</a>'
                  % (row[1], row[4], html_escape(row[5])))
                w(u'</td>')
                w(u'</tr>')
        w(u'<tr id="relationSelectorRow_%s" class="separator">' % eid)
        w(u'<th class="labelCol">')
        w(u'<span>%s</span>' % _('add relation'))
        w(u'<select id="relationSelector_%s" tabindex="%s" '
          'onchange="javascript:showMatchingSelect(this.options[this.selectedIndex].value,%s);">'
          % (eid, req.next_tabindex(), html_escape(dumps(eid))))
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
        
    def inline_entities_form(self, w, form):
        """create a form to edit entity's inlined relations"""
        entity = form.edited_entity
        __ = form.req.__
        for rschema, targettypes, role in form.inlined_relations():
            # show inline forms only if there's one possible target type
            # for rschema
            if len(targettypes) != 1:
                self.warning('entity related by the %s relation should have '
                             'inlined form but there is multiple target types, '
                             'dunno what to do', rschema)
                continue
            targettype = targettypes[0].type
            if form.should_inline_relation_form(rschema, targettype, role):
                w(u'<div id="inline%sslot">' % rschema)
                existant = entity.has_eid() and entity.related(rschema)
                if existant:
                    # display inline-edition view for all existing related entities
                    w(form.view('inline-edition', existant, rtype=rschema, role=role, 
                                ptype=entity.e_schema, peid=entity.eid))
                if role == 'subject':
                    card = rschema.rproperty(entity.e_schema, targettype, 'cardinality')[0]
                else:
                    card = rschema.rproperty(targettype, entity.e_schema, 'cardinality')[1]
                # there is no related entity and we need at least one: we need to
                # display one explicit inline-creation view
                if form.should_display_inline_creation_form(rschema, existant, card):
                    w(form.view('inline-creation', None, etype=targettype,
                                peid=entity.eid, ptype=entity.e_schema,
                                rtype=rschema, role=role))
                # we can create more than one related entity, we thus display a link
                # to add new related entities
                if form.should_display_add_new_relation_link(rschema, existant, card):
                    divid = "addNew%s%s%s:%s" % (targettype, rschema, role, entity.eid)
                    w(u'<div class="inlinedform" id="%s" cubicweb:limit="true">'
                      % divid)
                    js = "addInlineCreationForm('%s', '%s', '%s', '%s')" % (
                        entity.eid, targettype, rschema, role)
                    if card in '1?':
                        js = "toggleVisibility('%s'); %s" % (divid, js)
                    w(u'<a class="addEntity" id="add%s:%slink" href="javascript: %s" >+ %s.</a>'
                      % (rschema, entity.eid, js, __('add a %s' % targettype)))
                    w(u'</div>')
                    w(u'<div class="trame_grise">&nbsp;</div>')
                w(u'</div>')

    
class EntityInlinedFormRenderer(EntityFormRenderer):
    """specific renderer for entity inlined edition form
    (inline-[creation|edition])
    """
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
                values['divid'], form.req._('click on the box to cancel the deletion')))
        w(u'<div class="iformBody">')
        values['removemsg'] = form.req.__('remove this %s' % form.edited_entity.e_schema)
        w(u'<div class="iformTitle"><span>%(title)s</span> '
          '#<span class="icounter">1</span> '
          '[<a href="javascript: %(removejs)s;noop();">%(removemsg)s</a>]</div>'
          % values)
        self.render_fields(w, form, values)
        w(u'</div></div>')
        return '\n'.join(data)
    
    def render_fields(self, w, form, values):
        form.form_build_context(values)
        w(u'<fieldset id="fs-%(divid)s">' % values)
        fields = self._render_hidden_fields(w, form)
        w(u'</fieldset>')
        w(u'<fieldset class="subentity">')
        if fields:
            self._render_fields(fields, w, form, values)
        self.render_child_forms(w, form, values)
        self.inline_entities_form(w, form)
        w(u'</fieldset>')
    
