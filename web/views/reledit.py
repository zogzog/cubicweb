# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""the 'reedit' feature (eg edit attribute/relation from primary view"""

__docformat__ = "restructuredtext en"
_ = unicode

import copy
from warnings import warn

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import deprecated

from cubicweb import neg_role
from cubicweb.schema import display_name
from cubicweb.utils import json_dumps
from cubicweb.selectors import non_final_entity, match_kwargs
from cubicweb.view import EntityView
from cubicweb.web import uicfg, stdmsgs
from cubicweb.web.form import FieldNotFound
from cubicweb.web.formwidgets import Button, SubmitButton

class _DummyForm(object):
    __slots__ = ('event_args',)
    def form_render(self, **_args):
        return u''
    def render(self, *_args, **_kwargs):
        return u''
    def append_field(self, *args):
        pass

rctrl = uicfg.reledit_ctrl

class ClickAndEditFormView(EntityView):
    __regid__ = 'doreledit'
    __select__ = non_final_entity() & match_kwargs('rtype')

    # ui side continuations
    _onclick = (u"cw.reledit.loadInlineEditionForm('%(formid)s', %(eid)s, '%(rtype)s', '%(role)s', "
                "'%(divid)s', %(reload)s, '%(vid)s');")
    _cancelclick = "cw.reledit.cleanupAfterCancel('%s')"

    # ui side actions/buttons
    _addzone = u'<img title="%(msg)s" src="data/plus.png" alt="%(msg)s"/>'
    _addmsg = _('click to add a value')
    _deletezone = u'<img title="%(msg)s" src="data/cancel.png" alt="%(msg)s"/>'
    _deletemsg = _('click to delete this value')
    _editzone = u'<img title="%(msg)s" src="data/pen_icon.png" alt="%(msg)s"/>'
    _editzonemsg = _('click to edit this field')

    # renderer
    _form_renderer_id = 'base'

    def cell_call(self, row, col, rtype=None, role='subject',
                  reload=False, # controls reloading the whole page after change
                                # boolean, eid (to redirect), or
                                # function taking the subject entity & returning a boolean or an eid
                  rvid=None,    # vid to be applied to other side of rtype (non final relations only)
                  default_value=None,
                  formid='base'
                  ):
        """display field to edit entity's `rtype` relation on click"""
        assert rtype
        assert role in ('subject', 'object'), '%s is not an acceptable role value' % role
        self._cw.add_css('cubicweb.form.css')
        self._cw.add_js(('cubicweb.reledit.js', 'cubicweb.edition.js', 'cubicweb.ajax.js'))
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema[rtype]
        self._rules = rctrl.etype_get(entity.e_schema.type, rschema.type, role, '*')
        if rvid is not None or default_value is not None:
            warn('[3.9] specifying rvid/default_value on select is deprecated, '
                 'reledit_ctrl rtag to control this' % self, DeprecationWarning)
        reload = self._compute_reload(entity, rschema, role, reload)
        divid = self._build_divid(rtype, role, entity.eid)
        if rschema.final:
            self._handle_attribute(entity, rschema, role, divid, reload)
        else:
            if self._is_composite():
                self._handle_composite(entity, rschema, role, divid, reload, formid)
            else:
                self._handle_relation(entity, rschema, role, divid, reload, formid)

    def _handle_attribute(self, entity, rschema, role, divid, reload):
        rtype = rschema.type
        value = entity.printable_value(rtype)
        if not self._should_edit_attribute(entity, rschema):
            self.w(value)
            return
        display_label, related_entity = self._prepare_form(entity, rtype, role)
        form, renderer = self._build_form(entity, rtype, role, divid, 'base',
                                          reload, display_label, related_entity)
        value = value or self._compute_default_value(rschema, role)
        self.view_form(divid, value, form, renderer)

    def _compute_formid_value(self, entity, rschema, role, rvid, formid):
        related_rset = entity.related(rschema.type, role)
        if related_rset:
            value = self._cw.view(rvid, related_rset)
        else:
            value = self._compute_default_value(rschema, role)
        if not self._should_edit_relation(entity, rschema, role):
            return None, value
        return formid, value

    def _handle_relation(self, entity, rschema, role, divid, reload, formid):
        rvid = self._rules.get('rvid', 'autolimited')
        formid, value = self._compute_formid_value(entity, rschema, role, rvid, formid)
        if formid is None:
            return self.w(value)
        rtype = rschema.type
        display_label, related_entity = self._prepare_form(entity, rtype, role)
        form, renderer = self._build_form(entity, rtype, role, divid, formid, reload,
                                          display_label, related_entity, dict(vid=rvid))
        self.view_form(divid, value, form, renderer)

    def _handle_composite(self, entity, rschema, role, divid, reload, formid):
        # this is for attribute-like composites (1 target type, 1 related entity at most, for now)
        ttypes = self._compute_ttypes(rschema, role)
        related_rset = entity.related(rschema.type, role)
        add_related = self._may_add_related(related_rset, entity, rschema, role, ttypes)
        edit_related = self._may_edit_related_entity(related_rset, entity, rschema, role, ttypes)
        delete_related = edit_related and self._may_delete_related(related_rset, entity, rschema, role)
        rvid = self._rules.get('rvid', 'autolimited')
        formid, value = self._compute_formid_value(entity, rschema, role, rvid, formid)
        if formid is None or not (edit_related or add_related):
            # till we learn to handle cases where not (edit_related or add_related)
            self.w(value)
            return
        rtype = rschema.type
        ttype = ttypes[0]
        _fdata = self._prepare_composite_form(entity, rtype, role, edit_related,
                                              add_related and ttype)
        display_label, related_entity = _fdata
        form, renderer = self._build_form(entity, rtype, role, divid, formid, reload,
                                          display_label, related_entity, dict(vid=rvid))
        self.view_form(divid, value, form, renderer,
                       edit_related, add_related, delete_related)

    def _compute_ttypes(self, rschema, role):
        dual_role = neg_role(role)
        return getattr(rschema, '%ss' % dual_role)()

    def _compute_reload(self, entity, rschema, role, reload):
        ctrl_reload = self._rules.get('reload', reload)
        if callable(ctrl_reload):
            ctrl_reload = ctrl_reload(entity)
        if isinstance(ctrl_reload, int) and ctrl_reload > 1: # not True/False
            ctrl_reload = self._cw.build_url(ctrl_reload)
        return ctrl_reload

    def _compute_default_value(self, rschema, role):
        default = self._rules.get('novalue_label')
        if default is None:
            if self._rules.get('novalue_include_rtype'):
                default = self._cw._('<%s not specified>') % display_name(
                    self._cw, rschema.type, role)
            else:
                default = self._cw._('<not specified>')
        return xml_escape(default)

    def _is_composite(self):
        return self._rules.get('edit_target') == 'related'

    def _may_add_related(self, related_rset, entity, rschema, role, ttypes):
        """ ok for attribute-like composite entities """
        if len(ttypes) > 1: # many etypes: learn how to do it
            return False
        rdef = rschema.role_rdef(entity.e_schema, ttypes[0], role)
        card = rdef.role_cardinality(role)
        if related_rset or card not in '?1':
            return False
        if role == 'subject':
            kwargs = {'fromeid': entity.eid}
        else:
            kwargs = {'toeid': entity.eid}
        return rdef.has_perm(self._cw, 'add', **kwargs)

    def _may_edit_related_entity(self, related_rset, entity, rschema, role, ttypes):
        """ controls the edition of the related entity """
        if len(ttypes) > 1 or len(related_rset.rows) != 1:
            return False
        if entity.e_schema.rdef(rschema, role).role_cardinality(role) not in '?1':
            return False
        return related_rset.get_entity(0, 0).cw_has_perm('update')

    def _may_delete_related(self, related_rset, entity, rschema, role):
        # we assume may_edit_related, only 1 related entity
        if not related_rset:
            return False
        rentity = related_rset.get_entity(0, 0)
        if role == 'subject':
            kwargs = {'fromeid': entity.eid, 'toeid': rentity.eid}
        else:
            kwargs = {'fromeid': rentity.eid, 'toeid': entity.eid}
        # NOTE: should be sufficient given a well built schema/security
        return rschema.has_perm(self._cw, 'delete', **kwargs)

    def _build_edit_zone(self):
        return self._editzone % {'msg' : xml_escape(self._cw._(self._editzonemsg))}

    def _build_delete_zone(self):
        return self._deletezone % {'msg': xml_escape(self._cw._(self._deletemsg))}

    def _build_add_zone(self):
        return self._addzone % {'msg': xml_escape(self._cw._(self._addmsg))}

    def _build_divid(self, rtype, role, entity_eid):
        """ builds an id for the root div of a reledit widget """
        return '%s-%s-%s' % (rtype, role, entity_eid)

    def _build_args(self, entity, rtype, role, formid, reload,
                    extradata=None):
        divid = self._build_divid(rtype, role, entity.eid)
        event_args = {'divid' : divid, 'eid' : entity.eid, 'rtype' : rtype, 'formid': formid,
                      'reload' : json_dumps(reload),
                      'role' : role, 'vid' : u''}
        if extradata:
            event_args.update(extradata)
        return event_args

    def _prepare_form(self, entity, _rtype, role):
        display_label = False
        related_entity = entity
        return display_label, related_entity

    def _prepare_composite_form(self, entity, rtype, role, edit_related, add_related):
        display_label = True
        if edit_related and not add_related:
            related_entity = entity.related(rtype, role).get_entity(0, 0)
        elif add_related:
            _new_entity = self._cw.vreg['etypes'].etype_class(add_related)(self._cw)
            _new_entity.eid = self._cw.varmaker.next()
            related_entity = _new_entity
            # XXX see forms.py ~ 276 and entities.linked_to method
            #     is there another way ?
            self._cw.form['__linkto'] = '%s:%s:%s' % (rtype, entity.eid, neg_role(role))
        return display_label, related_entity

    def _build_renderer(self, related_entity, display_label):
        return self._cw.vreg['formrenderers'].select(
            self._form_renderer_id, self._cw, entity=related_entity,
            display_label=display_label,
            table_class='attributeForm' if display_label else '',
            display_help=False, button_bar_class='buttonbar',
            display_progress_div=False)

    def _build_form(self, entity, rtype, role, divid, formid, reload,
                    display_label, related_entity, extradata=None, **formargs):
        event_args = self._build_args(entity, rtype, role, formid,
                                      reload, extradata)
        cancelclick = self._cancelclick % divid
        form = self._cw.vreg['forms'].select(
            formid, self._cw, rset=related_entity.as_rset(), entity=related_entity,
            domid='%s-form' % divid, formtype='inlined',
            action=self._cw.build_url('validateform', __onsuccess='window.parent.cw.reledit.onSuccess'),
            cwtarget='eformframe', cssclass='releditForm',
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
        if formid == 'base':
            field = form.field_by_name(rtype, role, entity.e_schema)
            form.append_field(field)
        return form, self._build_renderer(related_entity, display_label)

    def _should_edit_attribute(self, entity, rschema):
        rdef = entity.e_schema.rdef(rschema)
        # check permissions
        if not entity.cw_has_perm('update'):
            return False
        rdef = entity.e_schema.rdef(rschema)
        return rdef.has_perm(self._cw, 'update', eid=entity.eid)

    should_edit_attributes = deprecated('[3.9] should_edit_attributes is deprecated,'
                                        ' use _should_edit_attribute instead',
                                        _should_edit_attribute)

    def _should_edit_relation(self, entity, rschema, role):
        eeid = entity.eid
        perm_args = {'fromeid': eeid} if role == 'subject' else {'toeid': eeid}
        return rschema.has_perm(self._cw, 'add', **perm_args)

    should_edit_relations = deprecated('[3.9] should_edit_relations is deprecated,'
                                       ' use _should_edit_relation instead',
                                       _should_edit_relation)

    def _open_form_wrapper(self, divid, value, form, renderer,
                           _edit_related, _add_related, _delete_related):
        w = self.w
        w(u'<div id="%(id)s-reledit" onmouseout="%(out)s" onmouseover="%(over)s" class="%(css)s">' %
          {'id': divid, 'css': 'releditField',
           'out': "jQuery('#%s').addClass('hidden')" % divid,
           'over': "jQuery('#%s').removeClass('hidden')" % divid})
        w(u'<div id="%s-value" class="editableFieldValue">' % divid)
        w(value)
        w(u'</div>')
        form.render(w=w, renderer=renderer)
        w(u'<div id="%s" class="editableField hidden">' % divid)

    def _edit_action(self, divid, args, edit_related, add_related, _delete_related):
        if not add_related: # currently, excludes edition
            w = self.w
            args['formid'] = 'edition' if edit_related else 'base'
            w(u'<div id="%s-update" class="editableField" onclick="%s" title="%s">' %
              (divid, xml_escape(self._onclick % args), self._cw._(self._editzonemsg)))
            w(self._build_edit_zone())
            w(u'</div>')

    def _add_action(self, divid, args, _edit_related, add_related, _delete_related):
        if add_related:
            w = self.w
            args['formid'] = 'edition' if add_related else 'base'
            w(u'<div id="%s-add" class="editableField" onclick="%s" title="%s">' %
              (divid, xml_escape(self._onclick % args), self._cw._(self._addmsg)))
            w(self._build_add_zone())
            w(u'</div>')

    def _del_action(self, divid, args, _edit_related, _add_related, delete_related):
        if delete_related:
            w = self.w
            args['formid'] = 'deleteconf'
            w(u'<div id="%s-delete" class="editableField" onclick="%s" title="%s">' %
              (divid, xml_escape(self._onclick % args), self._cw._(self._deletemsg)))
            w(self._build_delete_zone())
            w(u'</div>')

    def _close_form_wrapper(self):
        self.w(u'</div>')
        self.w(u'</div>')

    def view_form(self, divid, value, form=None, renderer=None,
                  edit_related=False, add_related=False, delete_related=False):
        self._open_form_wrapper(divid, value, form, renderer,
                                edit_related, add_related, delete_related)
        args = form.event_args.copy()
        self._edit_action(divid, args, edit_related, add_related, delete_related)
        self._add_action(divid, args, edit_related, add_related, delete_related)
        self._del_action(divid, args, edit_related, add_related, delete_related)
        self._close_form_wrapper()


class AutoClickAndEditFormView(ClickAndEditFormView):
    __regid__ = 'reledit'

    def _build_form(self, entity, rtype, role, divid, formid, reload,
                    display_label, related_entity, extradata=None, **formargs):
        event_args = self._build_args(entity, rtype, role, 'base',
                                      reload, extradata)
        form = _DummyForm()
        form.event_args = event_args
        return form, None
