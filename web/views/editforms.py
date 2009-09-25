"""Set of HTML automatic forms to create, delete, copy or edit a single entity
or a list of entities of the same type

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from copy import copy

from simplejson import dumps

from logilab.mtconverter import xml_escape

from cubicweb.selectors import (match_kwargs, one_line_rset, non_final_entity,
                                specified_etype_implements, yes)
from cubicweb.utils import make_uid
from cubicweb.view import EntityView
from cubicweb.common import tags
from cubicweb.web import INTERNAL_FIELD_VALUE, RequestError, stdmsgs, eid_param
from cubicweb.web import uicfg
from cubicweb.web.form import FormViewMixIn, FieldNotFound
from cubicweb.web.formfields import guess_field
from cubicweb.web.formwidgets import Button, SubmitButton, ResetButton
from cubicweb.web.views import forms


def relation_id(eid, rtype, role, reid):
    """return an identifier for a relation between two entities"""
    if role == 'subject':
        return u'%s:%s:%s' % (eid, rtype, reid)
    return u'%s:%s:%s' % (reid, rtype, eid)

def toggleable_relation_link(eid, nodeid, label='x'):
    """return javascript snippet to delete/undelete a relation between two
    entities
    """
    js = u"javascript: togglePendingDelete('%s', %s);" % (
        nodeid, xml_escape(dumps(eid)))
    return u'[<a class="handle" href="%s" id="handle%s">%s</a>]' % (
        js, nodeid, label)


class DeleteConfForm(forms.CompositeForm):
    __regid__ = 'deleteconf'
    __select__ = non_final_entity()

    domid = 'deleteconf'
    copy_nav_params = True
    form_buttons = [Button(stdmsgs.YES, cwaction='delete'),
                    Button(stdmsgs.NO, cwaction='cancel')]
    @property
    def action(self):
        return self._cw.build_url('edit')

    def __init__(self, *args, **kwargs):
        super(DeleteConfForm, self).__init__(*args, **kwargs)
        done = set()
        for entity in self.cw_rset.entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            subform = self._cw.vreg['forms'].select('base', self._cw, entity=entity,
                                                mainform=False)
            self.form_add_subform(subform)


class DeleteConfFormView(FormViewMixIn, EntityView):
    """form used to confirm deletion of some entities"""
    __regid__ = 'deleteconf'
    title = _('delete')
    # don't use navigation, all entities asked to be deleted should be displayed
    # else we will only delete the displayed page
    need_navigation = False

    def call(self, onsubmit=None):
        """ask for confirmation before real deletion"""
        req, w = self._cw, self.w
        _ = req._
        w(u'<script type="text/javascript">updateMessage(\'%s\');</script>\n'
          % _('this action is not reversible!'))
        # XXX above message should have style of a warning
        w(u'<h4>%s</h4>\n' % _('Do you want to delete the following element(s) ?'))
        form = self._cw.vreg['forms'].select(self.__regid__, req, rset=self.cw_rset,
                                         onsubmit=onsubmit)
        w(u'<ul>\n')
        for entity in self.cw_rset.entities():
            # don't use outofcontext view or any other that may contain inline edition form
            w(u'<li>%s</li>' % tags.a(entity.view('textoutofcontext'),
                                      href=entity.absolute_url()))
        w(u'</ul>\n')
        w(form.form_render())


class ClickAndEditFormView(FormViewMixIn, EntityView):
    """form used to permit ajax edition of a relation or attribute of an entity
    in a view, if logged user have the permission to edit it.

    (double-click on the field to see an appropriate edition widget).
    """
    __regid__ = 'doreledit'
    __select__ = non_final_entity() & match_kwargs('rtype')
    # FIXME editableField class could be toggleable from userprefs

    _onclick = u"showInlineEditionForm(%(eid)s, '%(rtype)s', '%(divid)s')"
    _defaultlandingzone = (u'<img title="%(msg)s" '
                           'src="data/accessories-text-editor.png" '
                           'alt="%(msg)s"/>')
    _landingzonemsg = _('click to edit this field')
    # default relation vids according to cardinality
    _one_rvid = 'incontext'
    _many_rvid = 'csv'

    def _compute_best_vid(self, eschema, rschema, role):
        if eschema.cardinality(rschema, role) in '+*':
            return self._many_rvid
        return self._one_rvid

    def _build_landing_zone(self, lzone):
        return lzone or self._defaultlandingzone % {'msg' : xml_escape(self._cw._(self._landingzonemsg))}

    def _build_renderer(self, entity, rtype, role):
        return self._cw.vreg['formrenderers'].select(
            'base', self._cw, entity=entity, display_label=False,
            display_help=False, table_class='',
            button_bar_class='buttonbar', display_progress_div=False)

    def _build_form(self, entity, rtype, role, formid, default, onsubmit, reload,
                  extradata=None, **formargs):
        divid = 'd%s' % make_uid('%s-%s' % (rtype, entity.eid))
        event_data = {'divid' : divid, 'eid' : entity.eid, 'rtype' : rtype,
                      'reload' : dumps(reload), 'default' : default}
        if extradata:
            event_data.update(extradata)
        onsubmit %= event_data
        cancelclick = "hideInlineEdit(%s,\'%s\',\'%s\')" % (entity.eid, rtype,
                                                            divid)
        form = self._cw.vreg['forms'].select(
            formid, self._cw, entity=entity, domid='%s-form' % divid,
            cssstyle='display: none', onsubmit=onsubmit, action='#',
            display_fields=[(rtype, role)],
            form_buttons=[SubmitButton(), Button(stdmsgs.BUTTON_CANCEL,
                                                 onclick=cancelclick)],
            **formargs)
        form.event_data = event_data
        return form

    def cell_call(self, row, col, rtype=None, role='subject',
                  reload=False,      # controls reloading the whole page after change
                  rvid=None,         # vid to be applied to other side of rtype (non final relations only)
                  default=None,      # default value
                  landing_zone=None  # prepend value with a separate html element to click onto
                                     # (esp. needed when values are links)
                  ):
        """display field to edit entity's `rtype` relation on click"""
        assert rtype
        assert role in ('subject', 'object')
        if default is None:
            default = xml_escape(self._cw._('<no value>'))
        schema = self._cw.vreg.schema
        entity = self.cw_rset.get_entity(row, col)
        rschema = schema.rschema(rtype)
        lzone = self._build_landing_zone(landing_zone)
        # compute value, checking perms, build form
        if rschema.is_final():
            onsubmit = ("return inlineValidateAttributeForm('%(rtype)s', '%(eid)s', '%(divid)s', "
                        "%(reload)s, '%(default)s');")
            form = self._build_form(
                entity, rtype, role, default, onsubmit, reload)
            if not self.should_edit_attribute(entity, rschema, role, form):
                return
            value = entity.printable_value(rtype) or default
            self.attribute_form(lzone, value, form,
                                 self._build_renderer(entity, rtype, role))
        else:
            if rvid is None:
                rvid = self._compute_best_vid(entity.e_schema, rschema, role)
            if not self.should_edit_relation(entity, rschema, role, rvid):
                return
            rset = entity.related(rtype, role)
            if rset:
                value = self._cw.view(rvid, rset)
            else:
                value = default
            onsubmit = ("return inlineValidateRelationForm('%(rtype)s', '%(role)s', '%(eid)s', "
                        "'%(divid)s', %(reload)s, '%(vid)s', '%(default)s', '%(lzone)s');")
            form = self._build_form(
                entity, rtype, role, 'base', default, onsubmit, reload,
                dict(vid=rvid, role=role, lzone=lzone))
            field = guess_field(entity.e_schema, schema.rschema(rtype), role)
            form.append_field(field)
            self.relation_form(lzone, value, form,
                               self._build_renderer(entity, rtype, role))

    def should_edit_attribute(self, entity, rschema, role, form):
        rtype = str(rschema)
        ttype = rschema.targets(entity.__regid__, role)[0]
        afs = uicfg.autoform_section.etype_get(entity.__regid__, rtype, role, ttype)
        if 'main_hidden' in afs or not entity.has_perm('update'):
            self.w(entity.printable_value(rtype))
            return False
        try:
            field = form.field_by_name(rtype, role)
        except FieldNotFound:
            self.w(entity.printable_value(rtype))
            return False
        return True

    def should_edit_relation(self, entity, rschema, role, rvid):
        if ((role == 'subject' and not rschema.has_perm(self._cw, 'add',
                                                        fromeid=entity.eid))
            or
            (role == 'object' and not rschema.has_perm(self._cw, 'add',
                                                       toeid=entity.eid))):
            self.wview(rvid, entity.related(str(rschema), role), 'null')
            return False
        return True

    def attribute_form(self, lzone, value, form, renderer):
        """div (class=field)
              +-xxx div
              |  +-xxx div (class=editableField)
              |  |  +-landing zone
              |  +-value-xxx div
              |     +-value
              +-form-xxx div
        """
        w = self.w
        w(u'<div class="field">')
        w(u'<div id="%s" style="display: inline">' % form.event_data['divid'])
        w(tags.div(lzone, klass='editableField',
                   onclick=self._onclick % form.event_data))
        w(u'<div id="value-%s" style="display: inline">%s</div>' %
               (form.event_data['divid'], value))
        w(u'</div>')
        w(form.form_render(renderer=renderer))
        w(u'</div>')

    def relation_form(self, lzone, value, form, renderer):
        """xxx-reledit div (class=field)
              +-xxx div (class="editableField")
              |   +-landing zone
              +-value
              +-form-xxx div
        """
        w = self.w
        w(u'<div id="%s-reledit" class="field">' % form.event_data['divid'])
        w(tags.div(lzone, klass='editableField', id=form.event_data['divid'],
                   onclick=self._onclick % form.event_data))
        w(value)
        w(form.form_render(renderer=renderer))
        w(u'</div>')


class AutoClickAndEditFormView(ClickAndEditFormView):
    """same as ClickAndEditFormView but checking if the view *should* be applied
    by checking uicfg configuration and composite relation property.
    """
    __regid__ = 'reledit'

    def should_edit_relation(self, entity, rschema, role, rvid):
        eschema = entity.e_schema
        rtype = str(rschema)
        # XXX check autoform_section. what if 'generic'?
        dispctrl = uicfg.primaryview_display_ctrl.etype_get(eschema, rtype, role)
        vid = dispctrl.get('vid', 'reledit')
        if vid != 'reledit': # reledit explicitly disabled
            self.wview(vid, entity.related(rtype, role), 'null')
            return False
        if eschema.role_rproperty(role, rschema, 'composite') == role:
            self.wview(rvid, entity.related(rtype, role), 'null')
            return False
        return super(AutoClickAndEditFormView, self).should_edit_relation(
            entity, rschema, role, rvid)


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
        form = self._cw.vreg['forms'].select('edition', self._cw, rset=entity.cw_rset,
                                             row=entity.cw_row, col=entity.cw_col,
                                             entity=entity,
                                             submitmsg=self.submited_message())
        self.init_form(form, entity)
        self.w(form.form_render(formvid=u'edition'))

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
            form.form_add_hidden(eid_param('__cloned_eid', entity.eid),
                                 self.copying.eid)
        for rschema, role in form.editable_attributes():
            if not rschema.is_final():
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
    form_buttons = [SubmitButton(_('validate modifications on selected items')),
                    ResetButton(_('revert changes'))]

    def __init__(self, req, rset, **kwargs):
        kwargs.setdefault('__redirectrql', rset.printable_rql())
        super(TableEditForm, self).__init__(req, rset=rset, **kwargs)
        for row in xrange(len(self.cw_rset)):
            form = self._cw.vreg['forms'].select('edition', self._cw,
                                                 rset=self.cw_rset, row=row,
                                                 formtype='muledit',
                                                 mainform=False)
            # XXX rely on the EntityCompositeFormRenderer to put the eid input
            form.remove_field(form.field_by_name('eid'))
            self.form_add_subform(form)


class TableEditFormView(FormViewMixIn, EntityView):
    __regid__ = 'muledit'
    __select__ = EntityView.__select__ & yes()
    title = _('multiple edit')

    def call(self, **kwargs):
        """a view to edit multiple entities of the same type the first column
        should be the eid
        """
        #self.form_title(entity)
        form = self._cw.vreg['forms'].select(self.__regid__, self._cw, rset=self.cw_rset)
        self.w(form.form_render())


class InlineEntityEditionFormView(FormViewMixIn, EntityView):
    __regid__ = 'inline-edition'
    __select__ = non_final_entity() & match_kwargs('peid', 'rtype')
    removejs = "removeInlinedEntity('%s', '%s', '%s')"

    def call(self, **kwargs):
        """redefine default call() method to avoid automatic
        insertions of <div class="section"> between each row of
        the resultset
        """
        rset = self.cw_rset
        for i in xrange(len(rset)):
            self.wview(self.__regid__, rset, row=i, **kwargs)

    def cell_call(self, row, col, peid, rtype, role, i18nctx, **kwargs):
        """
        :param peid: the parent entity's eid hosting the inline form
        :param rtype: the relation bridging `etype` and `peid`
        :param role: the role played by the `peid` in the relation
        """
        entity = self.cw_rset.get_entity(row, col)
        divonclick = "restoreInlinedEntity('%s', '%s', '%s')" % (peid, rtype,
                                                                 entity.eid)
        self.render_form(entity, peid, rtype, role, i18nctx,
                         divonclick=divonclick)

    def render_form(self, entity, peid, rtype, role, i18nctx, **kwargs):
        """fetch and render the form"""
        form = self._cw.vreg['forms'].select('edition', self._cw, entity=entity,
                                             form_renderer_id='inline',
                                             formtype='inlined',
                                             mainform=False,
                                             copy_nav_params=False)
        self.add_hiddens(form, entity, peid, rtype, role)
        divid = '%s-%s-%s' % (peid, rtype, entity.eid)
        title = self._cw.pgettext(i18nctx, 'This %s' % entity.e_schema)
        removejs = self.removejs % (peid, rtype, entity.eid)
        countkey = '%s_count' % rtype
        try:
            self._cw.data[countkey] += 1
        except:
            self._cw.data[countkey] = 1
        self.w(form.form_render(divid=divid, title=title, removejs=removejs,
                                i18nctx=i18nctx,
                                counter=self._cw.data[countkey], **kwargs))

    def add_hiddens(self, form, entity, peid, rtype, role):
        # to ease overriding (see cubes.vcsfile.views.forms for instance)
        form.form_add_hidden(name='%s:%s' % (rtype, peid), value=entity.eid,
                             id='rel-%s-%s-%s'  % (peid, rtype, entity.eid))

    def keep_entity(self, form, entity, peid, rtype):
        if not entity.has_eid():
            return True
        # are we regenerating form because of a validation error ?
        if form.form_previous_values:
            cdvalues = self._cw.list_form_param(eid_param(rtype, peid),
                                                form.form_previous_values)
            if unicode(entity.eid) not in cdvalues:
                return False
        return True


class InlineEntityCreationFormView(InlineEntityEditionFormView):
    __regid__ = 'inline-creation'
    __select__ = (match_kwargs('peid', 'rtype')
                  & specified_etype_implements('Any'))
    removejs = "removeInlineForm('%s', '%s', '%s')"

    def call(self, etype, peid, rtype, role, i18nctx, **kwargs):
        """
        :param etype: the entity type being created in the inline form
        :param peid: the parent entity's eid hosting the inline form
        :param rtype: the relation bridging `etype` and `peid`
        :param role: the role played by the `peid` in the relation
        """
        try:
            cls = self._cw.vreg['etypes'].etype_class(etype)
        except:
            self.w(self._cw._('no such entity type %s') % etype)
            return
        entity = cls(self._cw)
        entity.eid = self._cw.varmaker.next()
        self.render_form(entity, peid, rtype, role, i18nctx, **kwargs)
