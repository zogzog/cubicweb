"""Set of HTML automatic forms to create, delete, copy or edit a single entity
or a list of entities of the same type

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from copy import copy

from simplejson import dumps

from logilab.mtconverter import html_escape
from logilab.common.decorators import cached

from cubicweb.selectors import (specified_etype_implements, accepts_etype_compat,
                                non_final_entity, match_kwargs, one_line_rset)
from cubicweb.view import View, EntityView
from cubicweb.web import INTERNAL_FIELD_VALUE, eid_param
from cubicweb.web.controller import NAV_FORM_PARAMETERS
from cubicweb.web.widgets import checkbox, InputWidget, ComboBoxWidget
from cubicweb.web.form import FormMixIn

_ = unicode
    
    
class EditionForm(FormMixIn, EntityView):
    """primary entity edition form

    When generating a new attribute_input, the editor will look for a method
    named 'default_ATTRNAME' on the entity instance, where ATTRNAME is the
    name of the attribute being edited. You may use this feature to compute
    dynamic default values such as the 'tomorrow' date or the user's login
    being connected
    """    
    id = 'edition'
    __select__ = one_line_rset() & non_final_entity()

    title = _('edition')
    controller = 'edit'
    skip_relations = FormMixIn.skip_relations.copy()
    
    EDITION_BODY = u'''\
 %(errormsg)s
<form id="%(formid)s" class="entityForm" cubicweb:target="eformframe"
      method="post" onsubmit="%(onsubmit)s" enctype="%(enctype)s" action="%(action)s">
 %(title)s
 <div id="progress">%(inprogress)s</div>
 <div class="iformTitle"><span>%(mainattrs_label)s</span></div>
 <div class="formBody"><fieldset>
 %(base)s
 %(attrform)s
 %(relattrform)s
</fieldset>
 %(relform)s
 </div>
 <table width="100%%">
  <tbody>
   <tr><td align="center">
     %(validate)s
   </td><td style="align: right; width: 50%%;">
     %(apply)s
     %(cancel)s
   </td></tr>
  </tbody>
 </table>
</form>
'''

    def initialize_varmaker(self):
        varmaker = self.req.get_page_data('rql_varmaker')
        if varmaker is None:
            varmaker = self.req.varmaker
            self.req.set_page_data('rql_varmaker', varmaker)
        self.varmaker = varmaker

    def cell_call(self, row, col, **kwargs):
        self.req.add_js( ('cubicweb.ajax.js', ) )
        entity = self.complete_entity(row, col)
        self.edit_form(entity, kwargs)

    def edit_form(self, entity, kwargs):
        varmaker = self.req.get_page_data('rql_varmaker')
        if varmaker is None:
            varmaker = self.req.varmaker
            self.req.set_page_data('rql_varmaker', varmaker)
        self.varmaker = varmaker
        self.w(self.EDITION_BODY % self.form_context(entity, kwargs))

    def form_context(self, entity, kwargs):
        """returns the dictionnary used to fill the EDITION_BODY template

        If you create your own edition form, you can probably just override
        `EDITION_BODY` and `form_context`
        """
        if self.need_multipart(entity):
            enctype = 'multipart/form-data'
        else:
            enctype = 'application/x-www-form-urlencoded'
        self._hiddens = []
        if entity.eid is None:
            entity.eid = self.varmaker.next()
        # XXX (hack) action_title might need __linkto req's original value
        #            and widgets such as DynamicComboWidget might change it
        #            so we need to compute title before calling atttributes_form
        formtitle = self.action_title(entity)
        # be sure to call .*_form first so tabindexes are correct and inlined
        # fields errors are consumed
        if not entity.has_eid() or entity.has_perm('update'):
            attrform = self.attributes_form(entity, kwargs)
        else:
            attrform = ''
        inlineform = self.inline_entities_form(entity, kwargs)
        relform = self.relations_form(entity, kwargs)
        vindex = self.req.next_tabindex()
        aindex = self.req.next_tabindex()
        cindex = self.req.next_tabindex()
        self.add_hidden_web_behaviour_params(entity)
        _ = self.req._
        return {
            'formid'   : self.domid,
            'onsubmit' : self.on_submit(entity),
            'enctype'  : enctype,
            'errormsg' : self.error_message(),
            'action'   : self.build_url('validateform'),
            'eids'     : entity.has_eid() and [entity.eid] or [],
            'inprogress': _('validating...'),
            'title'    : formtitle,
            'mainattrs_label' : _('main informations'),
            'reseturl' : self.redirect_url(entity),
            'attrform' : attrform,
            'relform'  : relform,
            'relattrform': inlineform,
            'base'     : self.base_form(entity, kwargs),
            'validate' : self.button_ok(tabindex=vindex),
            'apply'    : self.button_apply(tabindex=aindex),
            'cancel'   : self.button_cancel(tabindex=cindex),
            }

    @property
    def formid(self):
        return self.id
    
    def action_title(self, entity):
        """form's title"""
        ptitle = self.req._(self.title)
        return u'<div class="formTitle"><span>%s %s</span></div>' % (
            entity.dc_type(), ptitle and '(%s)' % ptitle)


    def base_form(self, entity, kwargs):
        output = []
        for name, value, iid in self._hiddens:
            if isinstance(value, basestring):
                value = html_escape(value)
            if iid:
                output.append(u'<input id="%s" type="hidden" name="%s" value="%s" />'
                              % (iid, name, value))
            else:
                output.append(u'<input type="hidden" name="%s" value="%s" />'
                              % (name, value))
        return u'\n'.join(output)
                
    def add_hidden_web_behaviour_params(self, entity):
        """inserts hidden params controlling how errors and redirection
        should be handled
        """
        req = self.req
        self._hiddens.append( (u'__maineid', entity.eid, u'') )
        self._hiddens.append( (u'__errorurl', req.url(), u'errorurl') )
        self._hiddens.append( (u'__form_id', self.formid, u'') )
        for param in NAV_FORM_PARAMETERS:
            value = req.form.get(param)
            if value:
                self._hiddens.append( (param, value, u'') )
        msg = self.submited_message()
        # If we need to directly attach the new object to another one
        for linkto in req.list_form_param('__linkto'):
            self._hiddens.append( ('__linkto', linkto, '') )
            msg = '%s %s' % (msg, self.req._('and linked'))
        self._hiddens.append( ('__message', msg, '') )
        
    
    def attributes_form(self, entity, kwargs, include_eid=True):
        """create a form to edit entity's attributes"""
        html = []
        w = html.append
        eid = entity.eid
        wdg = entity.get_widget
        lines = (wdg(rschema, x) for rschema, x in self.editable_attributes(entity))
        if include_eid:
            self._hiddens.append( ('eid', entity.eid, '') )
        self._hiddens.append( (eid_param('__type', eid), entity.e_schema, '') )
        w(u'<table id="%s" class="%s" style="width:100%%;">' %
          (kwargs.get('tab_id', 'entityForm%s' % eid),
           kwargs.get('tab_class', 'attributeForm')))
        for widget in lines:
            w(u'<tr>\n<th class="labelCol">%s</th>' % widget.render_label(entity))
            error = widget.render_error(entity)
            if error:
                w(u'<td class="error" style="width:100%;">')
            else:
                w(u'<td style="width:100%;">')
            if error:
                w(error)
            w(widget.edit_render(entity))
            w(widget.render_help(entity))
            w(u'</td>\n</tr>')
        w(u'</table>')
        return u'\n'.join(html)

    def editable_attributes(self, entity):
        # XXX both (add, delete)
        return [(rschema, x) for rschema, _, x in entity.relations_by_category(('primary', 'secondary'), 'add')
                if rschema != 'eid']
    
    def relations_form(self, entity, kwargs):
        srels_by_cat = entity.srelations_by_category(('generic', 'metadata'), 'add')
        if not srels_by_cat:
            return u''
        req = self.req
        _ = self.req._
        label = u'%s :' % _('This %s' % entity.e_schema).capitalize()
        eid = entity.eid
        html = []
        w = html.append
        w(u'<fieldset class="subentity">')
        w(u'<legend class="iformTitle">%s</legend>' % label)
        w(u'<table id="relatedEntities">')
        for row in self.relations_table(entity):
            # already linked entities
            if row[2]:
                w(u'<tr><th class="labelCol">%s</th>' % row[0].display_name(req, row[1]))
                w(u'<td>')
                w(u'<ul>')
                for viewparams in row[2]:
                    w(u'<li class="invisible">%s<div id="span%s" class="%s">%s</div></li>'
                      % (viewparams[1], viewparams[0], viewparams[2], viewparams[3]))
                if not self.force_display and self.maxrelitems < len(row[2]):
                    w(u'<li class="invisible">%s</li>' % self.force_display_link())
                w(u'</ul>')
                w(u'</td>')
                w(u'</tr>')
        pendings = list(self.restore_pending_inserts(entity))
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
        w(u'<select id="relationSelector_%s" tabindex="%s" onchange="javascript:showMatchingSelect(this.options[this.selectedIndex].value,%s);">'
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
        return '\n'.join(html)
        
    def inline_entities_form(self, entity, kwargs):
        """create a form to edit entity's inlined relations"""
        result = []
        _ = self.req._
        for rschema, targettypes, x in entity.relations_by_category('inlineview', 'add'):
            # show inline forms only if there's one possible target type
            # for rschema
            if len(targettypes) != 1:
                self.warning('entity related by the %s relation should have '
                             'inlined form but there is multiple target types, '
                             'dunno what to do', rschema)
                continue
            targettype = targettypes[0].type
            if self.should_inline_relation_form(entity, rschema, targettype, x):
                result.append(u'<div id="inline%sslot">' % rschema)
                existant = entity.has_eid() and entity.related(rschema)
                if existant:
                    # display inline-edition view for all existing related entities
                    result.append(self.view('inline-edition', existant, 
                                            ptype=entity.e_schema, peid=entity.eid,
                                            rtype=rschema, role=x, **kwargs))
                if x == 'subject':
                    card = rschema.rproperty(entity.e_schema, targettype, 'cardinality')[0]
                else:
                    card = rschema.rproperty(targettype, entity.e_schema, 'cardinality')[1]
                # there is no related entity and we need at least one : we need to
                # display one explicit inline-creation view
                if self.should_display_inline_relation_form(rschema, existant, card):
                    result.append(self.view('inline-creation', None, etype=targettype,
                                            peid=entity.eid, ptype=entity.e_schema,
                                            rtype=rschema, role=x, **kwargs))
                # we can create more than one related entity, we thus display a link
                # to add new related entities
                if self.should_display_add_inline_relation_link(rschema, existant, card):
                    divid = "addNew%s%s%s:%s" % (targettype, rschema, x, entity.eid)
                    result.append(u'<div class="inlinedform" id="%s" cubicweb:limit="true">'
                                  % divid)
                    js = "addInlineCreationForm('%s', '%s', '%s', '%s', '%s')" % (
                        entity.eid, entity.e_schema, targettype, rschema, x)
                    if card in '1?':
                        js = "toggleVisibility('%s'); %s" % (divid, js)
                    result.append(u'<a class="addEntity" id="add%s:%slink" href="javascript: %s" >+ %s.</a>'
                                  % (rschema, entity.eid, js,
                                     self.req.__('add a %s' % targettype)))
                    result.append(u'</div>')
                    result.append(u'<div class="trame_grise">&nbsp;</div>')
                result.append(u'</div>')
        return '\n'.join(result)

    # should_* method extracted to allow overriding
    
    def should_inline_relation_form(self, entity, rschema, targettype, role):
        return entity.rtags.is_inlined(rschema, targettype, role)

    def should_display_inline_relation_form(self, rschema, existant, card):
        return not existant and card in '1+'

    def should_display_add_inline_relation_link(self, rschema, existant, card):
        return not existant or card in '+*'
    
    def reset_url(self, entity):
        return entity.absolute_url()
    
    def on_submit(self, entity):
        return u'return freezeFormButtons(\'%s\')' % (self.domid)

    def submited_message(self):
        return self.req._('element edited')


    
class CreationForm(EditionForm):
    __select__ = specified_etype_implements('Any')
    # XXX bw compat, use View.registered since we don't want accept_compat
    #    wrapper set in EntityView
    registered = accepts_etype_compat(View.registered)
    id = 'creation'
    title = _('creation')
    
    def call(self, **kwargs):
        """creation view for an entity"""
        self.req.add_js( ('cubicweb.ajax.js',) )
        self.initialize_varmaker()
        etype = kwargs.pop('etype', self.req.form.get('etype'))
        try:
            entity = self.vreg.etype_class(etype)(self.req, None, None)
        except:
            self.w(self.req._('no such entity type %s') % etype)
        else:
            entity.eid = self.varmaker.next()
            self.edit_form(entity, kwargs)

    def action_title(self, entity):
        """custom form title if creating a entity with __linkto"""
        if '__linkto' in self.req.form:
            if isinstance(self.req.form['__linkto'], list):
                # XXX which one should be considered (case: add a ticket to a version in jpl)
                rtype, linkto_eid, role = self.req.form['__linkto'][0].split(':')
            else:
                rtype, linkto_eid, role = self.req.form['__linkto'].split(':')
            linkto_rset = self.req.eid_rset(linkto_eid)
            linkto_type = linkto_rset.description[0][0]
            if role == 'subject':
                title = self.req.__('creating %s (%s %s %s %%(linkto)s)' % (
                    entity.e_schema, entity.e_schema, rtype, linkto_type))
            else:
                title = self.req.__('creating %s (%s %%(linkto)s %s %s)' % (
                    entity.e_schema, linkto_type, rtype, entity.e_schema))
            msg = title % {'linkto' : self.view('incontext', linkto_rset)}
            return u'<div class="formTitle notransform"><span>%s</span></div>' % msg
        else:
            return super(CreationForm, self).action_title(entity)

    @property
    def formid(self):
        return 'edition'
    
    def relations_form(self, entity, kwargs):
        return u''

    def reset_url(self, entity=None):
        return self.build_url(self.req.form.get('etype', '').lower())
    
    def submited_message(self):
        return self.req._('element created')
    
    def url(self):
        """return the url associated with this view"""
        return self.create_url(self.req.form.get('etype'))


class InlineFormMixIn(object):

    @cached
    def card(self, etype):
        return self.rschema.rproperty(self.parent_schema, etype, 'cardinality')[0]
    
    def action_title(self, entity):
        return self.rschema.display_name(self.req, self.role)
        
    def add_hidden_web_behaviour_params(self, entity):
        pass
    
    def edit_form(self, entity, ptype, peid, rtype,
                  role='subject', **kwargs):
        self.rschema = self.schema.rschema(rtype)
        self.role = role        
        self.parent_schema = self.schema.eschema(ptype)
        self.parent_eid = peid
        super(InlineFormMixIn, self).edit_form(entity, kwargs)
    
    def should_inline_relation_form(self, entity, rschema, targettype, role):
        if rschema == self.rschema:
            return False
        return entity.rtags.is_inlined(rschema, targettype, role)

    @cached
    def keep_entity(self, entity):
        req = self.req
        # are we regenerating form because of a validation error ?
        erroneous_post = req.data.get('formvalues')
        if erroneous_post:
            cdvalues = req.list_form_param('%s:%s' % (self.rschema,
                                                      self.parent_eid),
                                           erroneous_post)
            if unicode(entity.eid) not in cdvalues:
                return False
        return True

    def form_context(self, entity, kwargs):
        ctx = super(InlineFormMixIn, self).form_context(entity, kwargs)
        _ = self.req._
        local_ctx = {'createmsg' : self.req.__('add a %s' % entity.e_schema),
                     'so': self.role[0], # 's' for subject, 'o' for object
                     'eid' : entity.eid,
                     'rtype' : self.rschema,
                     'parenteid' : self.parent_eid,
                     'parenttype' : self.parent_schema,
                     'etype' : entity.e_schema,
                     'novalue' : INTERNAL_FIELD_VALUE,
                     'removemsg' : self.req.__('remove this %s' % entity.e_schema),
                     'notice' : self.req._('click on the box to cancel the deletion'),
                     }
        ctx.update(local_ctx)
        return ctx


class InlineEntityCreationForm(InlineFormMixIn, CreationForm):
    id = 'inline-creation'
    __select__ = (match_kwargs('ptype', 'peid', 'rtype')
                  & specified_etype_implements('Any'))
    
    EDITION_BODY = u'''\
<div id="div-%(parenteid)s-%(rtype)s-%(eid)s" class="inlinedform">
 <div class="iformBody">
 <div class="iformTitle"><span>%(title)s</span> #<span class="icounter">1</span> [<a href="javascript: removeInlineForm('%(parenteid)s', '%(rtype)s', '%(eid)s'); noop();">%(removemsg)s</a>]</div>
 <fieldset class="subentity">
 %(attrform)s
 %(relattrform)s
 </fieldset>
 </div>
 <fieldset class="hidden" id="fs-%(parenteid)s-%(rtype)s-%(eid)s">
%(base)s
 <input type="hidden" value="%(novalue)s" name="edit%(so)s-%(rtype)s:%(parenteid)s" />
 <input id="rel-%(parenteid)s-%(rtype)s-%(eid)s" type="hidden" value="%(eid)s" name="%(rtype)s:%(parenteid)s" />
 </fieldset>
</div>''' # do not insert trailing space or \n here !

    def call(self, etype, ptype, peid, rtype, role='subject', **kwargs):
        """
        :param etype: the entity type being created in the inline form
        :param parent: the parent entity hosting the inline form
        :param rtype: the relation bridging `etype` and `parent`
        :param role: the role played by the `parent` in the relation
        """
        try:
            entity = self.vreg.etype_class(etype)(self.req, None, None)
        except:
            self.w(self.req._('no such entity type %s') % etype)
            return
        self.edit_form(entity, ptype, peid, rtype, role, **kwargs)


class InlineEntityEditionForm(InlineFormMixIn, EditionForm):
    id = 'inline-edition'
    __select__ = non_final_entity() & match_kwargs('ptype', 'peid', 'rtype')
    
    EDITION_BODY = u'''\
<div onclick="restoreInlinedEntity('%(parenteid)s', '%(rtype)s', '%(eid)s')" id="div-%(parenteid)s-%(rtype)s-%(eid)s" class="inlinedform">   
<div id="notice-%(parenteid)s-%(rtype)s-%(eid)s" class="notice">%(notice)s</div>
<div class="iformTitle"><span>%(title)s</span>  #<span class="icounter">%(count)s</span> [<a href="javascript: removeInlinedEntity('%(parenteid)s', '%(rtype)s', '%(eid)s'); noop();">%(removemsg)s</a>]</div>
 <div class="iformBody">
 <fieldset class="subentity">
 %(attrform)s
 </fieldset>
 %(relattrform)s
 </div>
 <fieldset id="fs-%(parenteid)s-%(rtype)s-%(eid)s">
%(base)s
 <input type="hidden" value="%(eid)s" name="edit%(so)s-%(rtype)s:%(parenteid)s" />
 %(rinput)s
 </fieldset>
</div>''' # do not insert trailing space or \n here !

    rel_input = u'''<input id="rel-%(parenteid)s-%(rtype)s-%(eid)s" type="hidden" value="%(eid)s" name="%(rtype)s:%(parenteid)s" />'''
 
    def call(self, **kwargs):
        """redefine default View.call() method to avoid automatic
        insertions of <div class="section"> between each row of
        the resultset
        """
        rset = self.rset
        for i in xrange(len(rset)):
            self.wview(self.id, rset, row=i, **kwargs)

    def cell_call(self, row, col, ptype, peid, rtype, role='subject', **kwargs):
        """
        :param parent: the parent entity hosting the inline form
        :param rtype: the relation bridging `etype` and `parent`
        :param role: the role played by the `parent` in the relation
        """
        entity = self.entity(row, col)
        self.edit_form(entity, ptype, peid, rtype, role, **kwargs)


    def form_context(self, entity, kwargs):
        ctx = super(InlineEntityEditionForm, self).form_context(entity, kwargs)
        if self.keep_entity(entity):
            ctx['rinput'] = self.rel_input % ctx
            ctx['todelete'] = u''
        else:
            ctx['rinput'] = u''
            ctx['todelete'] = u'checked="checked"'
        ctx['count'] = entity.row + 1
        return ctx
    

class CopyEditionForm(EditionForm):
    id = 'copy'
    title = _('copy edition')

    def cell_call(self, row, col, **kwargs):
        self.req.add_js(('cubicweb.ajax.js',))
        entity = self.complete_entity(row, col, skip_bytes=True)
        # make a copy of entity to avoid altering the entity in the
        # request's cache. 
        self.newentity = copy(entity)
        self.copying = self.newentity.eid
        self.newentity.eid = None
        self.edit_form(self.newentity, kwargs)
        del self.newentity

    def action_title(self, entity):
        """form's title"""
        msg = super(CopyEditionForm, self).action_title(entity)
        return msg + (u'<script type="text/javascript">updateMessage("%s");</script>\n'
                      % self.req._('Please note that this is only a shallow copy'))
        # XXX above message should have style of a warning

    @property
    def formid(self):
        return 'edition'
        
    def relations_form(self, entity, kwargs):
        return u''

    def reset_url(self, entity):
        return self.build_url('view', rql='Any X WHERE X eid %s' % self.copying)
    
    def attributes_form(self, entity, kwargs, include_eid=True):
        # we don't want __clone_eid on inlined edited entities
        if entity.eid == self.newentity.eid:
            self._hiddens.append((eid_param('__cloned_eid', entity.eid), self.copying, ''))
        return EditionForm.attributes_form(self, entity, kwargs, include_eid)
    
    def submited_message(self):
        return self.req._('element copied')
       
    
class TableEditForm(FormMixIn, EntityView):
    id = 'muledit'
    title = _('multiple edit')

    EDITION_BODY = u'''<form method="post" id="entityForm" onsubmit="return validateForm('entityForm', null);" action="%(action)s">
  %(error)s
  <div id="progress">%(progress)s</div>
  <fieldset>
  <input type="hidden" name="__errorurl" value="%(url)s" />
  <input type="hidden" name="__form_id" value="%(formid)s" />
  <input type="hidden" name="__redirectvid" value="%(redirectvid)s" />
  <input type="hidden" name="__redirectrql" value="%(redirectrql)s" />
  <table class="listing">
    <tr class="header">
      <th align="left"><input type="checkbox" onclick="setCheckboxesState('eid', this.checked)" value="" title="toggle check boxes" /></th>
      %(attrheaders)s
    </tr>
    %(lines)s
  </table>
  <table width="100%%">
    <tr>
      <td align="left">
        <input class="validateButton" type="submit"  value="%(okvalue)s" title="%(oktitle)s" />
        <input class="validateButton" type="reset" name="__action_cancel" value="%(cancelvalue)s" title="%(canceltitle)s" />
      </td>
    </tr>
  </table>
  </fieldset>    
</form>
'''

    WIDGET_CELL = u'''\
<td%(csscls)s>
  %(error)s
  <div>%(widget)s</div>
</td>'''
    
    def call(self, **kwargs):
        """a view to edit multiple entities of the same type
        the first column should be the eid
        """
        req = self.req
        form = req.form
        _ = req._
        sampleentity = self.complete_entity(0)
        attrheaders = [u'<th>%s</th>' % rdef[0].display_name(req, rdef[-1])
                       for rdef in sampleentity.relations_by_category('primary', 'add')
                       if rdef[0].type != 'eid']
        ctx = {'action' : self.build_url('edit'),
               'error': self.error_message(),
               'progress': _('validating...'),
               'url': html_escape(req.url()),
               'formid': self.id,
               'redirectvid': html_escape(form.get('__redirectvid', 'list')),
               'redirectrql': html_escape(form.get('__redirectrql', self.rset.printable_rql())),
               'attrheaders': u'\n'.join(attrheaders),
               'lines': u'\n'.join(self.edit_form(ent) for ent in self.rset.entities()),
               'okvalue': _('button_ok').capitalize(),
               'oktitle': _('validate modifications on selected items').capitalize(),
               'cancelvalue': _('button_reset').capitalize(),
               'canceltitle': _('revert changes').capitalize(),
               }        
        self.w(self.EDITION_BODY % ctx)
        
        
    def reset_url(self, entity=None):
        self.build_url('view', rql=self.rset.printable_rql())
        
    def edit_form(self, entity):
        html = []
        w = html.append
        entity.complete()
        eid = entity.eid
        values = self.req.data.get('formvalues', ())
        qeid = eid_param('eid', eid)
        checked = qeid in values
        w(u'<tr class="%s">' % (entity.row % 2 and u'even' or u'odd'))
        w(u'<td>%s<input type="hidden" name="__type:%s" value="%s" /></td>'
          % (checkbox('eid', eid, checked=checked), eid, entity.e_schema))
        # attribute relations (skip eid which is handled by the checkbox
        wdg = entity.get_widget
        wdgfactories = [wdg(rschema, x) for rschema, _, x in entity.relations_by_category('primary', 'add')
                        if rschema.type != 'eid'] # XXX both (add, delete)
        seid = html_escape(dumps(eid))
        for wobj in wdgfactories:
            if isinstance(wobj, ComboBoxWidget):
                wobj.attrs['onchange'] = "setCheckboxesState2('eid', %s, 'checked')" % seid
            elif isinstance(wobj, InputWidget):
                wobj.attrs['onkeypress'] = "setCheckboxesState2('eid', %s, 'checked')" % seid
            error = wobj.render_error(entity)
            if error:
                csscls = u' class="error"'
            else:
                csscls = u''
            w(self.WIDGET_CELL % {'csscls': csscls, 'error': error,
                                  'widget': wobj.edit_render(entity)})
        w(u'</tr>')
        return '\n'.join(html)


# XXX bw compat

from logilab.common.deprecation import class_moved
from cubicweb.web.views import editviews
ComboboxView = class_moved(editviews.ComboboxView)
