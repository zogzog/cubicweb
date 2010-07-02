import copy

from logilab.mtconverter import xml_escape

from cubicweb import neg_role
from cubicweb.schema import display_name
from cubicweb.utils import json
from cubicweb.selectors import non_final_entity, match_kwargs
from cubicweb.view import EntityView
from cubicweb.web import uicfg, stdmsgs
from cubicweb.web.form import FormViewMixIn, FieldNotFound
from cubicweb.web.formwidgets import Button, SubmitButton

class DummyForm(object):
    __slots__ = ('event_args',)
    def form_render(self, **_args):
        return u''
    def render(self, *_args, **_kwargs):
        return u''
    def append_field(self, *args):
        pass
    def field_by_name(self, rtype, role, eschema=None):
        return None

class ClickAndEditFormView(FormViewMixIn, EntityView):
    __regid__ = 'doreledit'
    __select__ = non_final_entity() & match_kwargs('rtype')

    # ui side continuations
    _onclick = (u"cw.reledit.loadInlineEditionForm('%(formid)s', %(eid)s, '%(rtype)s', '%(role)s', "
                "'%(divid)s', %(reload)s, '%(vid)s', '%(default_value)s');")
    _cancelclick = "cw.reledit.cleanupAfterCancel('%s')"

    # ui side actions/buttons
    _addzone = (u'<img title="%(msg)s" src="data/plus.png" '
                u'alt="%(msg)s"/>')
    _addmsg = _('click to add a value')
    _deletezone = (u'<img title="%(msg)s" src="data/cancel.png" alt="%(msg)s"/>')
    _deletemsg = _('click to delete this value')
    _editzone = (u'<img title="%(msg)s" src="data/pen_icon.png" alt="%(msg)s"/>')
    _editzonemsg = _('click to edit this field')

    # default relation vids according to cardinality
    _one_rvid = 'incontext'
    _many_rvid = 'csv'

    def cell_call(self, row, col, rtype=None, role='subject',
                  reload=False, # controls reloading the whole page after change
                                # boolean, eid (to redirect), or
                                # function taking the subject entity & returning a boolean or an eid
                  rvid=None,    # vid to be applied to other side of rtype (non final relations only)
                  default_value=None,
                  formid=None
                  ):
        """display field to edit entity's `rtype` relation on click"""
        assert rtype
        assert role in ('subject', 'object'), '%s is not an acceptable role value' % role
        if self.__regid__ == 'doreledit':
            assert formid
        self._cw.add_js('cubicweb.reledit.js')
        if formid:
            self._cw.add_js('cubicweb.edition.js')
        self._cw.add_css('cubicweb.form.css')
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema[rtype]
        reload = self._compute_reload(entity, rschema, role, reload)
        default_value = self._compute_default_value(entity, rschema, role, default_value)
        # compute value, checking perms, build & display form
        divid = self._build_divid(rtype, role, entity.eid)
        if rschema.final:
            value = entity.printable_value(rtype)
            form, renderer = self._build_form(entity, rtype, role, divid, 'base',
                                              default_value, reload)
            if not self._should_edit_attribute(entity, rschema, form):
                self.w(value)
                return
            value = value or default_value
            field = form.field_by_name(rtype, role, entity.e_schema)
            form.append_field(field)
            self.view_form(divid, value, form, renderer)
        else:
            rvid = self._compute_best_vid(entity.e_schema, rschema, role)
            related_rset = entity.related(rtype, role)
            if related_rset:
                value = self._cw.view(rvid, related_rset)
            else:
                value = default_value
            ttypes = self._compute_ttypes(rschema, role)

            if not self._should_edit_relation(entity, rschema, role):
                self.w(value)
                return
            # this is for attribute-like composites (1 target type, 1 related entity at most)
            edit_related = self._may_edit_related_entity(related_rset, entity, rschema, role, ttypes)
            delete_related = edit_related and self._may_delete_related(related_rset, entity, rschema, role)
            add_related = self._may_add_related(related_rset, entity, rschema, role, ttypes)
            # compute formid
            if len(ttypes) > 1: # redundant safety belt
                formid = 'base'
            else:
                afs = uicfg.autoform_section.etype_get(entity.e_schema, rschema, role, ttypes[0])
                # is there an afs spec that says we should edit
                # the rschema as an attribute ?
                if afs and 'main_attributes' in afs:
                    formid = 'base'

            form, renderer = self._build_form(entity, rtype, role, divid, formid, default_value,
                                              reload, dict(vid=rvid),
                                              edit_related, add_related and ttypes[0])
            self.view_form(divid, value, form, renderer, edit_related,
                           delete_related, add_related)

    def _compute_best_vid(self, eschema, rschema, role):
        if eschema.rdef(rschema, role).role_cardinality(role) in '+*':
            return self._many_rvid
        return self._one_rvid

    def _compute_ttypes(self, rschema, role):
        dual_role = neg_role(role)
        return getattr(rschema, '%ss' % dual_role)()

    def _compute_reload(self, entity, rschema, role, reload):
        rule = uicfg.reledit_ctrl.etype_get(entity.e_schema.type, rschema.type, role, '*')
        ctrl_reload = rule.get('reload', reload)
        if callable(ctrl_reload):
            ctrl_reload = ctrl_reload(entity)
        if isinstance(ctrl_reload, int) and ctrl_reload > 1: # not True/False
            ctrl_reload = self._cw.build_url(ctrl_reload)
        return ctrl_reload

    def _compute_default_value(self, entity, rschema, role, default_value):
        etype = entity.e_schema.type
        rule = uicfg.reledit_ctrl.etype_get(etype, rschema.type, role, '*')
        ctrl_default = rule.get('default_value', default_value)
        if ctrl_default:
            return ctrl_default
        if default_value is None:
            return xml_escape(self._cw._('<%s not specified>') %
                              display_name(self._cw, rschema.type, role))
        return default_value

    def _is_composite(self, eschema, rschema, role):
        return eschema.rdef(rschema, role).composite == role

    def _may_add_related(self, rset, entity, rschema, role, ttypes):
        """ ok for attribute-like composite entities """
        if self._is_composite(entity.e_schema, rschema, role):
            if len(ttypes) > 1: # wrong cardinality: do not handle
                return False
            ttype = ttypes[0]
            if rset:
                eschema = entity.e_schema
                if role == 'subject':
                    source, target = eschema.type, ttype
                else:
                    source, target = ttype, eschema.type
                card = rschema.rdef(source, target).role_cardinality(role)
                if card in '1?':
                    return False
            if rschema.has_perm(self._cw, 'add', toetype=ttype):
                return True
        return False

    def _may_edit_related_entity(self, related_rset, entity, rschema, role, ttypes):
        """ controls the edition of the related entity """
        if len(ttypes) > 1:
            return False
        if not self._is_composite(entity.e_schema, rschema, role):
            return False
        if len(related_rset.rows) != 1:
            return False
        return related_rset.get_entity(0, 0).cw_has_perm('update')

    def _may_delete_related(self, related_rset, entity, rschema, role):
        # we assume may_edit_related
        assert len(related_rset.rows) == 1
        kwargs = {'fromeid': entity.eid} if role == 'subject' else {'toeid': entity.eid}
        if not rschema.has_perm(self._cw, 'delete', **kwargs):
            return False
        for related_entity in related_rset.entities():
            if not related_entity.cw_has_perm('delete'):
                return False
        return True

    def _build_edit_zone(self):
        return self._editzone % {'msg' : xml_escape(_(self._cw._(self._editzonemsg)))}

    def _build_delete_zone(self):
        return self._deletezone % {'msg': xml_escape(self._cw._(self._deletemsg))}

    def _build_add_zone(self):
        return self._addzone % {'msg': xml_escape(self._cw._(self._addmsg))}

    def _build_divid(self, rtype, role, entity_eid):
        """ builds an id for the root div of a reledit widget """
        return '%s-%s-%s' % (rtype, role, entity_eid)

    def _build_args(self, entity, rtype, role, formid, default_value, reload,
                    extradata=None):
        divid = self._build_divid(rtype, role, entity.eid)
        event_args = {'divid' : divid, 'eid' : entity.eid, 'rtype' : rtype, 'formid': formid,
                      'reload' : json.dumps(reload), 'default_value' : default_value,
                      'role' : role, 'vid' : u''}
        if extradata:
            event_args.update(extradata)
        return event_args

    def _build_form(self, entity, rtype, role, divid, formid, default_value, reload,
                    extradata=None, edit_related=False, add_related=False, **formargs):
        event_args = self._build_args(entity, rtype, role, formid, default_value,
                                      reload, extradata)
        cancelclick = self._cancelclick % divid
        if edit_related:
            display_fields = None
            display_label = True
            related_entity = entity.related(rtype, role).get_entity(0, 0)
            self._cw.form['eid'] = related_entity.eid
        elif add_related:
            display_fields = None
            display_label = True
            _new_entity = self._cw.vreg['etypes'].etype_class(add_related)(self._cw)
            _new_entity.eid = self._cw.varmaker.next()
            related_entity = _new_entity
            self._cw.form['__linkto'] = '%s:%s:%s' % (rtype, entity.eid, neg_role(role))
        else: # base case: edition/attribute relation
            display_fields = [(rtype, role)]
            display_label = False
            related_entity = entity
        form = self._cw.vreg['forms'].select(
            formid, self._cw, rset=related_entity.as_rset(), entity=related_entity, domid='%s-form' % divid,
            display_fields=display_fields, formtype='inlined',
            action=self._cw.build_url('validateform?__onsuccess=window.parent.cw.reledit.onSuccess'),
            cwtarget='eformframe', cssstyle='display: none',
            **formargs)
        # pass reledit arguments
        for pname, pvalue in event_args.iteritems():
            form.add_hidden('__reledit|' + pname, pvalue)
        # handle buttons
        if form.form_buttons: # edition, delete
            form_buttons = []
            for button in form.form_buttons:
                if not button.label.endswith('apply'):
                    if button.label.endswith('cancel'):
                        button = copy.deepcopy(button)
                        button.cwaction = None
                        button.onclick = cancelclick
                    form_buttons.append(button)
            form.form_buttons = form_buttons
        else: # base
            form.form_buttons = [SubmitButton(),
                                 Button(stdmsgs.BUTTON_CANCEL, onclick=cancelclick)]
        form.event_args = event_args
        renderer = self._cw.vreg['formrenderers'].select(
            'base', self._cw, entity=related_entity, display_label=display_label,
            display_help=False, table_class='',
            button_bar_class='buttonbar', display_progress_div=False)
        return form, renderer

    def _should_edit_attribute(self, entity, rschema, form):
        # examine rtags
        noedit = uicfg.reledit_ctrl.etype_get(entity.e_schema, rschema.type, 'subject').get('noedit', False)
        if noedit:
            return False
        rdef = entity.e_schema.rdef(rschema)
        afs = uicfg.autoform_section.etype_get(entity.__regid__, rschema, 'subject', rdef.object)
        if 'main_hidden' in  afs:
            return False
        # check permissions
        if not entity.cw_has_perm('update'):
            return False
        rdef = entity.e_schema.rdef(rschema)
        if not rdef.has_perm(self._cw, 'update', eid=entity.eid):
            return False
        # XXX ?
        try:
            form.field_by_name(str(rschema), 'subject', entity.e_schema)
        except FieldNotFound:
            return False
        return True

    def _should_edit_relation(self, entity, rschema, role):
        # examine rtags
        rtype = rschema.type
        noedit = uicfg.reledit_ctrl.etype_get(entity.e_schema, rtype, role).get('noedit', False)
        if noedit:
            return False
        rdef = entity.e_schema.rdef(rschema, role)
        afs = uicfg.autoform_section.etype_get(
            entity.__regid__, rschema, role, rdef.object)
        if 'main_hidden' in afs:
            return False
        perm_args = {'fromeid': entity.eid} if role == 'subject' else {'toeid': entity.eid}
        return rschema.has_perm(self._cw, 'add', **perm_args)

    def view_form(self, divid, value, form=None, renderer=None,
                  edit_related=False, delete_related=False, add_related=False):
        w = self.w
        w(u'<div id="%(id)s-reledit" onmouseout="%(out)s" onmouseover="%(over)s">' %
          {'id': divid,
           'out': "jQuery('#%s').addClass('hidden')" % divid,
           'over': "jQuery('#%s').removeClass('hidden')" % divid})
        w(u'<div id="%s-value" class="editableFieldValue">' % divid)
        w(value)
        w(u'</div>')
        w(form.render(renderer=renderer))
        w(u'<div id="%s" class="editableField hidden">' % divid)
        args = form.event_args.copy()
        if not add_related: # excludes edition
            args['formid'] = 'edition'
            w(u'<div id="%s-update" class="editableField" onclick="%s" title="%s">' %
              (divid, xml_escape(self._onclick % args), self._cw._(self._editzonemsg)))
            w(self._build_edit_zone())
            w(u'</div>')
        else:
            args['formid'] = 'edition'
            w(u'<div id="%s-add" class="editableField" onclick="%s" title="%s">' %
              (divid, xml_escape(self._onclick % args), self._cw._(self._addmsg)))
            w(self._build_add_zone())
            w(u'</div>')
        if delete_related:
            args['formid'] = 'deleteconf'
            w(u'<div id="%s-add" class="editableField" onclick="%s" title="%s">' %
              (divid, xml_escape(self._onclick % args), self._cw._(self._deletemsg)))
            w(self._build_delete_zone())
            w(u'</div>')
        w(u'</div>')
        w(u'</div>')

class AutoClickAndEditFormView(ClickAndEditFormView):
    __regid__ = 'reledit'

    def _build_form(self, entity, rtype, role, divid, formid, default_value, reload,
                  extradata=None, edit_related=False, add_related=False, **formargs):
        event_args = self._build_args(entity, rtype, role, 'base', default_value,
                                      reload, extradata)
        form = DummyForm()
        form.event_args = event_args
        return form, None
