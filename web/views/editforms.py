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
"""Set of HTML automatic forms to create, delete, copy or edit a single entity
or a list of entities of the same type

"""
__docformat__ = "restructuredtext en"
_ = unicode

from copy import copy

from logilab.mtconverter import xml_escape
from logilab.common.decorators import cached

from cubicweb.selectors import (match_kwargs, one_line_rset, non_final_entity,
                                specified_etype_implements, implements, yes)
from cubicweb.view import EntityView
from cubicweb import tags
from cubicweb.web import uicfg, stdmsgs, eid_param, dumps, \
     formfields as ff, formwidgets as fw
from cubicweb.web.form import FormViewMixIn, FieldNotFound
from cubicweb.web.views import forms

_pvdc = uicfg.primaryview_display_ctrl


class DeleteConfForm(forms.CompositeForm):
    __regid__ = 'deleteconf'
    # XXX non_final_entity does not implement eclass_selector
    __select__ = implements('Any')

    domid = 'deleteconf'
    copy_nav_params = True
    form_buttons = [fw.Button(stdmsgs.BUTTON_DELETE, cwaction='delete'),
                    fw.Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]

    def __init__(self, *args, **kwargs):
        super(DeleteConfForm, self).__init__(*args, **kwargs)
        done = set()
        for entity in self.cw_rset.entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            subform = self._cw.vreg['forms'].select('base', self._cw,
                                                    entity=entity,
                                                    mainform=False)
            self.add_subform(subform)


class DeleteConfFormView(FormViewMixIn, EntityView):
    """form used to confirm deletion of some entities"""
    __regid__ = 'deleteconf'
    title = _('delete')
    # don't use navigation, all entities asked to be deleted should be displayed
    # else we will only delete the displayed page
    paginable = False

    def call(self, onsubmit=None):
        """ask for confirmation before real deletion"""
        req, w = self._cw, self.w
        _ = req._
        w(u'<script type="text/javascript">updateMessage(\'%s\');</script>\n'
          % _('this action is not reversible!'))
        # XXX above message should have style of a warning
        w(u'<h4>%s</h4>\n' % _('Do you want to delete the following element(s) ?'))
        form = self._cw.vreg['forms'].select(self.__regid__, req,
                                             rset=self.cw_rset,
                                             onsubmit=onsubmit)
        w(u'<ul>\n')
        for entity in self.cw_rset.entities():
            # don't use outofcontext view or any other that may contain inline
            # edition form
            w(u'<li>%s</li>' % tags.a(entity.view('textoutofcontext'),
                                      href=entity.absolute_url()))
        w(u'</ul>\n')
        w(form.render())


class EditionFormView(FormViewMixIn, EntityView):
    """display primary entity edition form"""
    __regid__ = 'edition'
    # add yes() so it takes precedence over deprecated views in baseforms,
    # though not baseforms based customized view
    __select__ = one_line_rset() & non_final_entity() & yes()

    title = _('edition')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.complete_entity(row, col)
        self.render_form(entity)

    def render_form(self, entity):
        """fetch and render the form"""
        self.form_title(entity)
        form = self._cw.vreg['forms'].select('edition', self._cw, entity=entity,
                                             submitmsg=self.submited_message())
        self.init_form(form, entity)
        self.w(form.render())

    def init_form(self, form, entity):
        """customize your form before rendering here"""
        pass

    def form_title(self, entity):
        """the form view title"""
        ptitle = self._cw._(self.title)
        self.w(u'<div class="formTitle"><span>%s %s</span></div>' % (
            entity.dc_type(), ptitle and '(%s)' % ptitle))

    def submited_message(self):
        """return the message that will be displayed on successful edition"""
        return self._cw._('entity edited')


class CreationFormView(EditionFormView):
    """display primary entity creation form"""
    __regid__ = 'creation'
    __select__ = specified_etype_implements('Any') & yes()

    title = _('creation')

    def call(self, **kwargs):
        """creation view for an entity"""
        # at this point we know etype is a valid entity type, thanks to our
        # selector
        etype = kwargs.pop('etype', self._cw.form.get('etype'))
        entity = self._cw.vreg['etypes'].etype_class(etype)(self._cw)
        entity.eid = self._cw.varmaker.next()
        self.render_form(entity)

    def form_title(self, entity):
        """the form view title"""
        if '__linkto' in self._cw.form:
            if isinstance(self._cw.form['__linkto'], list):
                # XXX which one should be considered (case: add a ticket to a
                # version in jpl)
                rtype, linkto_eid, role = self._cw.form['__linkto'][0].split(':')
            else:
                rtype, linkto_eid, role = self._cw.form['__linkto'].split(':')
            linkto_rset = self._cw.eid_rset(linkto_eid)
            linkto_type = linkto_rset.description[0][0]
            if role == 'subject':
                title = self._cw.__('creating %s (%s %s %s %%(linkto)s)' % (
                    entity.e_schema, entity.e_schema, rtype, linkto_type))
            else:
                title = self._cw.__('creating %s (%s %%(linkto)s %s %s)' % (
                    entity.e_schema, linkto_type, rtype, entity.e_schema))
            msg = title % {'linkto' : self._cw.view('incontext', linkto_rset)}
            self.w(u'<div class="formTitle notransform"><span>%s</span></div>' % msg)
        else:
            super(CreationFormView, self).form_title(entity)

    def url(self):
        """return the url associated with this view"""
        return self.create_url(self._cw.form.get('etype'))

    def submited_message(self):
        """return the message that will be displayed on successful edition"""
        return self._cw._('entity created')


class CopyFormView(EditionFormView):
    """display primary entity creation form initialized with values from another
    entity
    """
    __regid__ = 'copy'

    title = _('copy')
    warning_message = _('Please note that this is only a shallow copy')

    def render_form(self, entity):
        """fetch and render the form"""
        # make a copy of entity to avoid altering the entity in the
        # request's cache.
        entity.complete()
        self.newentity = copy(entity)
        self.copying = entity
        self.newentity.eid = self._cw.varmaker.next()
        self.w(u'<script type="text/javascript">updateMessage("%s");</script>\n'
               % self._cw._(self.warning_message))
        super(CopyFormView, self).render_form(self.newentity)
        del self.newentity

    def init_form(self, form, entity):
        """customize your form before rendering here"""
        super(CopyFormView, self).init_form(form, entity)
        if entity.eid == self.newentity.eid:
            form.add_hidden(eid_param('__cloned_eid', entity.eid),
                            self.copying.eid)
        for rschema, role in form.editable_attributes():
            if not rschema.final:
                # ensure relation cache is filed
                rset = self.copying.related(rschema, role)
                self.newentity.set_related_cache(rschema, role, rset)

    def submited_message(self):
        """return the message that will be displayed on successful edition"""
        return self._cw._('entity copied')


class TableEditForm(forms.CompositeForm):
    __regid__ = 'muledit'
    domid = 'entityForm'
    onsubmit = "return validateForm('%s', null);" % domid
    form_buttons = [fw.SubmitButton(_('validate modifications on selected items')),
                    fw.ResetButton(_('revert changes'))]

    def __init__(self, req, rset, **kwargs):
        kwargs.setdefault('__redirectrql', rset.printable_rql())
        super(TableEditForm, self).__init__(req, rset=rset, **kwargs)
        for row in xrange(len(self.cw_rset)):
            form = self._cw.vreg['forms'].select('edition', self._cw,
                                                 rset=self.cw_rset, row=row,
                                                 formtype='muledit',
                                                 copy_nav_params=False,
                                                 mainform=False)
            # XXX rely on the EntityCompositeFormRenderer to put the eid input
            form.remove_field(form.field_by_name('eid'))
            self.add_subform(form)


class TableEditFormView(FormViewMixIn, EntityView):
    __regid__ = 'muledit'
    __select__ = EntityView.__select__ & yes()
    title = _('multiple edit')

    def call(self, **kwargs):
        """a view to edit multiple entities of the same type the first column
        should be the eid
        """
        # XXX overriding formvid (eg __form_id) necessary to make work edition:
        # the edit controller try to select the form with no rset but
        # entity=entity, and use this form to edit the entity. So we want
        # edition form there but specifying formvid may have other undesired
        # side effect. Maybe we should provide another variable optionally
        # telling which form the edit controller should select (eg difffers
        # between html generation / post handling form)
        form = self._cw.vreg['forms'].select(self.__regid__, self._cw,
                                             rset=self.cw_rset,
                                             copy_nav_params=True,
                                             formvid='edition')
        self.w(form.render())


# click and edit handling ('reledit') ##########################################

class DummyForm(object):
    __slots__ = ('event_args',)
    def form_render(self, **_args):
        return u''
    def render(self, **_args):
        return u''
    def append_field(self, *args):
        pass
    def field_by_name(self, rtype, role, eschema=None):
        return None


class ClickAndEditFormView(FormViewMixIn, EntityView):
    """form used to permit ajax edition of a relation or attribute of an entity
    in a view, if logged user have the permission to edit it.

    (double-click on the field to see an appropriate edition widget).
    """
    __regid__ = 'doreledit'
    __select__ = non_final_entity() & match_kwargs('rtype')
    # FIXME editableField class could be toggleable from userprefs

    _onclick = u"showInlineEditionForm(%(eid)s, '%(rtype)s', '%(divid)s')"
    _onsubmit = ("return inlineValidateRelationForm('%(rtype)s', '%(role)s', '%(eid)s', "
                 "'%(divid)s', %(reload)s, '%(vid)s', '%(default)s', '%(lzone)s');")
    _cancelclick = "hideInlineEdit(%s,\'%s\',\'%s\')"
    _defaultlandingzone = (u'<img title="%(msg)s" src="data/pen_icon.png" '
                           'alt="%(msg)s"/>')
    _landingzonemsg = _('click to edit this field')
    # default relation vids according to cardinality
    _one_rvid = 'incontext'
    _many_rvid = 'csv'


    def cell_call(self, row, col, rtype=None, role='subject',
                  reload=False,      # controls reloading the whole page after change
                  rvid=None,         # vid to be applied to other side of rtype (non final relations only)
                  default=None,      # default value
                  landing_zone=None  # prepend value with a separate html element to click onto
                                     # (esp. needed when values are links)
                  ):
        """display field to edit entity's `rtype` relation on click"""
        assert rtype
        assert role in ('subject', 'object'), '%s is not an acceptable role value' % role
        self._cw.add_js('cubicweb.edition.js')
        self._cw.add_css('cubicweb.form.css')
        if default is None:
            default = xml_escape(self._cw._('<no value>'))
        schema = self._cw.vreg.schema
        entity = self.cw_rset.get_entity(row, col)
        rschema = schema.rschema(rtype)
        lzone = self._build_landing_zone(landing_zone)
        # compute value, checking perms, build form
        if rschema.final:
            form = self._build_form(entity, rtype, role, 'base', default, reload, lzone)
            if not self.should_edit_attribute(entity, rschema, form):
                self.w(entity.printable_value(rtype))
                return
            value = entity.printable_value(rtype) or default
        else:
            rvid = self._compute_best_vid(entity.e_schema, rschema, role)
            rset = entity.related(rtype, role)
            if rset:
                value = self._cw.view(rvid, rset)
            else:
                value = default
            if not self.should_edit_relation(entity, rschema, role, rvid):
                if rset:
                    self.w(value)
                return
            # XXX do we really have to give lzone twice?
            form = self._build_form(entity, rtype, role, 'base', default, reload, lzone,
                                    dict(vid=rvid, lzone=lzone))
        field = form.field_by_name(rtype, role, entity.e_schema)
        form.append_field(field)
        self.relation_form(lzone, value, form,
                           self._build_renderer(entity, rtype, role))

    def should_edit_attribute(self, entity, rschema, form):
        rtype = str(rschema)
        rdef = entity.e_schema.rdef(rtype)
        afs = uicfg.autoform_section.etype_get(
            entity.__regid__, rtype, 'subject', rdef.object)
        if 'main_hidden' in afs or not entity.has_perm('update'):
            return False
        if not rdef.has_perm(self._cw, 'update', eid=entity.eid):
            return False
        try:
            form.field_by_name(rtype, 'subject', entity.e_schema)
        except FieldNotFound:
            return False
        return True

    def should_edit_relation(self, entity, rschema, role, rvid):
        if ((role == 'subject' and not rschema.has_perm(self._cw, 'add',
                                                        fromeid=entity.eid))
            or
            (role == 'object' and not rschema.has_perm(self._cw, 'add',
                                                       toeid=entity.eid))):
            return False
        return True

    def relation_form(self, lzone, value, form, renderer):
        """xxx-reledit div (class=field)
              +-xxx div (class="editableField")
              |   +-landing zone
              +-xxx-value div
              +-xxx-form div
        """
        w = self.w
        divid = form.event_args['divid']
        w(u'<div id="%s-reledit" class="field" '
          u'onmouseout="addElementClass(jQuery(\'#%s\'), \'hidden\')" '
          u'onmouseover="removeElementClass(jQuery(\'#%s\'), \'hidden\')">'
          % (divid, divid, divid))
        w(u'<div id="%s-value" class="editableFieldValue">%s</div>' % (divid, value))
        w(form.render(renderer=renderer))
        w(u'<div id="%s" class="editableField hidden" onclick="%s" title="%s">' % (
                divid, xml_escape(self._onclick % form.event_args),
                self._cw._(self._landingzonemsg)))
        w(lzone)
        w(u'</div>')
        w(u'</div>')

    def _compute_best_vid(self, eschema, rschema, role):
        dispctrl = _pvdc.etype_get(eschema, rschema, role)
        if dispctrl.get('rvid'):
            return dispctrl['rvid']
        if eschema.rdef(rschema, role).role_cardinality(role) in '+*':
            return self._many_rvid
        return self._one_rvid

    def _build_landing_zone(self, lzone):
        return lzone or self._defaultlandingzone % {
            'msg': xml_escape(self._cw._(self._landingzonemsg))}

    def _build_renderer(self, entity, rtype, role):
        return self._cw.vreg['formrenderers'].select(
            'base', self._cw, entity=entity, display_label=False,
            display_help=False, table_class='',
            button_bar_class='buttonbar', display_progress_div=False)

    def _build_args(self, entity, rtype, role, formid, default, reload, lzone,
                    extradata=None):
        divid = '%s-%s-%s' % (rtype, role, entity.eid)
        event_args = {'divid' : divid, 'eid' : entity.eid, 'rtype' : rtype,
                      'reload' : dumps(reload), 'default' : default, 'role' : role, 'vid' : u'',
                      'lzone' : lzone}
        if extradata:
            event_args.update(extradata)
        return divid, event_args

    def _build_form(self, entity, rtype, role, formid, default, reload, lzone,
                  extradata=None, **formargs):
        divid, event_args = self._build_args(entity, rtype, role, formid, default,
                                      reload, lzone, extradata)
        onsubmit = self._onsubmit % event_args
        cancelclick = self._cancelclick % (entity.eid, rtype, divid)
        form = self._cw.vreg['forms'].select(
            formid, self._cw, entity=entity, domid='%s-form' % divid,
            cssstyle='display: none', onsubmit=onsubmit, action='#',
            form_buttons=[fw.SubmitButton(),
                          fw.Button(stdmsgs.BUTTON_CANCEL, onclick=cancelclick)],
            **formargs)
        form.event_args = event_args
        return form


class AutoClickAndEditFormView(ClickAndEditFormView):
    """same as ClickAndEditFormView but checking if the view *should* be applied
    by checking uicfg configuration and composite relation property.
    """
    __regid__ = 'reledit'
    _onclick = (u"loadInlineEditionForm(%(eid)s, '%(rtype)s', '%(role)s', "
                "'%(divid)s', %(reload)s, '%(vid)s', '%(default)s', '%(lzone)s');")

    def should_edit_relation(self, entity, rschema, role, rvid):
        eschema = entity.e_schema
        rtype = str(rschema)
        # XXX check autoform_section. what if 'generic'?
        dispctrl = _pvdc.etype_get(eschema, rtype, role)
        vid = dispctrl.get('vid', 'reledit')
        if vid != 'reledit': # reledit explicitly disabled
            return False
        if eschema.rdef(rschema, role).composite == role:
            return False
        return super(AutoClickAndEditFormView, self).should_edit_relation(
            entity, rschema, role, rvid)

    def _build_form(self, entity, rtype, role, formid, default, reload, lzone,
                  extradata=None, **formargs):
        _divid, event_args = self._build_args(entity, rtype, role, formid, default,
                                              reload, lzone, extradata)
        form = DummyForm()
        form.event_args = event_args
        return form

    def _build_renderer(self, entity, rtype, role):
        pass

