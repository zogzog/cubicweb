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
from cubicweb.utils import make_uid, compute_cardinality, get_schema_property
from cubicweb.view import EntityView
from cubicweb.common import tags
from cubicweb.web import INTERNAL_FIELD_VALUE, stdmsgs, eid_param, uicfg
from cubicweb.web.form import FormViewMixIn
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


class DeleteConfForm(FormViewMixIn, EntityView):
    """form used to confirm deletion of some entities"""
    id = 'deleteconf'
    title = _('delete')
    # don't use navigation, all entities asked to be deleted should be displayed
    # else we will only delete the displayed page
    need_navigation = False

    def call(self, onsubmit=None):
        """ask for confirmation before real deletion"""
        req, w = self.req, self.w
        _ = req._
        w(u'<script type="text/javascript">updateMessage(\'%s\');</script>\n'
          % _('this action is not reversible!'))
        # XXX above message should have style of a warning
        w(u'<h4>%s</h4>\n' % _('Do you want to delete the following element(s) ?'))
        form = self.vreg.select('forms', 'composite', req, domid='deleteconf',
                                copy_nav_params=True,
                                action=self.build_url('edit'), onsubmit=onsubmit,
                                form_buttons=[Button(stdmsgs.YES, cwaction='delete'),
                                              Button(stdmsgs.NO, cwaction='cancel')])
        done = set()
        w(u'<ul>\n')
        for entity in self.rset.entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            subform = self.vreg.select('forms', 'base', req, entity=entity,
                                       mainform=False)
            form.form_add_subform(subform)
            # don't use outofcontext view or any other that may contain inline edition form
            w(u'<li>%s</li>' % tags.a(entity.view('textoutofcontext'),
                                      href=entity.absolute_url()))
        w(u'</ul>\n')
        w(form.form_render())


class ClickAndEditFormView(FormViewMixIn, EntityView):
    """form used to permit ajax edition of an attribute of an entity in a view

    (double-click on the field to see an appropriate edition widget)
    """
    id = 'reledit'
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

    def _compute_best_vid(self, entity, rtype, role):
        if compute_cardinality(entity.e_schema,
                               entity.schema.rschema(rtype),
                               role) in '+*':
            return self._many_rvid
        return self._one_rvid

    def _build_landing_zone(self, lzone):
        return lzone or self._defaultlandingzone % {'msg' : xml_escape(self.req._(self._landingzonemsg))}

    def _build_renderer(self, entity, rtype, role):
        return self.vreg.select_object('formrenderers', 'base', self.req,
                                       entity=entity,
                                       display_label=False, display_help=False,
                                       display_fields=[(rtype, role)],
                                       table_class='', button_bar_class='buttonbar',
                                       display_progress_div=False)

    def cell_call(self, row, col, rtype=None, role='subject',
                  reload=False,      # controls reloading the whole page after change
                  rvid=None,         # vid to be applied to other side of rtype
                  default=None,      # default value
                  landing_zone=None  # prepend value with a separate html element to click onto
                                     # (esp. needed when values are links)
                  ):
        """display field to edit entity's `rtype` relation on click"""
        assert rtype
        assert role in ('subject', 'object')
        if default is None:
            default = xml_escape(self.req._('<no value>'))
        entity = self.entity(row, col)
        rschema = entity.schema.rschema(rtype)
        lzone = self._build_landing_zone(landing_zone)
        # compute value, checking perms, build form
        if rschema.is_final():
            value = entity.printable_value(rtype) or default
            if not entity.has_perm('update'):
                self.w(value)
                return
            self._attribute_form(entity, value, rtype, role, reload,
                                 row, col, default, lzone)
        else:
            dispctrl = uicfg.primaryview_display_ctrl.etype_get(entity.e_schema,
                                                                rtype, role)
            vid = dispctrl.get('vid', 'reledit')
            if vid != 'reledit': # reledit explicitly disabled
                self.wview(vid, entity.related(rtype, role))
                return
            if rvid is None:
                rvid = self._compute_best_vid(entity, rtype, role)
            rset = entity.related(rtype, role)
            candidate = self.view(rvid, rset, 'null')
            value = candidate or default
            if role == 'subject' and not rschema.has_perm(self.req, 'add',
                                                          fromeid=entity.eid):
                return self.w(value)
            elif role == 'object' and not rschema.has_perm(self.req, 'add',
                                                           toeid=entity.eid):
                return self.w(value)
            elif get_schema_property(entity.e_schema, rschema,
                                     role, 'composite') == role:
                self.warning('reledit cannot be applied : (... %s %s [composite])'
                             % (rtype, entity.e_schema))
                return self.w(value)
            self._relation_form(entity, value, rtype, role, reload, rvid,
                                default, lzone)


    def _relation_form(self, entity, value, rtype, role, reload, rvid, default, lzone):
        """xxx-reledit div (class=field)
              +-xxx div (class="editableField")
              |   +-landing zone
              +-value
              +-form-xxx div
        """
        divid = 'd%s' % make_uid('%s-%s' % (rtype, entity.eid))
        event_data = {'divid' : divid, 'eid' : entity.eid, 'rtype' : rtype, 'vid' : rvid,
                      'reload' : dumps(reload), 'default' : default, 'role' : role,
                      'lzone' : lzone}
        onsubmit = ("return inlineValidateRelationForm('%(rtype)s', '%(role)s', '%(eid)s', "
                    "'%(divid)s', %(reload)s, '%(vid)s', '%(default)s', '%(lzone)s');"
                    % event_data)
        cancelclick = "hideInlineEdit(%s,\'%s\',\'%s\')" % (
            entity.eid, rtype, divid)
        form = self.vreg.select_object('forms', 'base', self.req, entity=entity,
                                       domid='%s-form' % divid, cssstyle='display: none',
                                       onsubmit=onsubmit, action='#',
                                       form_buttons=[SubmitButton(),
                                                     Button(stdmsgs.BUTTON_CANCEL,
                                                            onclick=cancelclick)])
        field = guess_field(entity.e_schema, entity.schema.rschema(rtype), role)
        form.append_field(field)
        w = self.w
        w(u'<div id="%s-reledit" class="field">' % divid)
        w(tags.div(lzone, klass='editableField', id=divid,
                   onclick=self._onclick % event_data))
        w(value)
        renderer = self._build_renderer(entity, rtype, role)
        w(form.form_render(renderer=renderer))
        w(u'</div>')

    def _attribute_form(self, entity, value, rtype, role, reload, row, col, default, lzone):
        """div (class=field)
              +-xxx div
              |  +-xxx div (class=editableField)
              |  |  +-landing zone
              |  +-value-xxx div
              |     +-value
              +-form-xxx div
        """
        eid = entity.eid
        divid = 'd%s' % make_uid('%s-%s' % (rtype, eid))
        event_data = {'divid' : divid, 'eid' : eid, 'rtype' : rtype,
                      'reload' : dumps(reload), 'default' : default}
        onsubmit = ("return inlineValidateAttributeForm('%(rtype)s', '%(eid)s', '%(divid)s', "
                    "%(reload)s, '%(default)s');")
        buttons = [SubmitButton(stdmsgs.BUTTON_OK),
                   Button(stdmsgs.BUTTON_CANCEL,
                          onclick="hideInlineEdit(%s,\'%s\',\'%s\')" % (
                              eid, rtype, divid))]
        form = self.vreg.select_object('forms', 'edition', self.req, self.rset,
                                       row=row, col=col, form_buttons=buttons,
                                       domid='%s-form' % divid, action='#',
                                       cssstyle='display: none',
                                       onsubmit=onsubmit % event_data)
        w = self.w
        w(u'<div class="field">')
        w(u'<div id="%s" style="display: inline">' % divid)
        w(tags.div(lzone, klass='editableField',
                   onclick=self._onclick % event_data))
        w(u'<div id="value-%s" style="display: inline">%s</div>' %
               (divid, value))
        w(u'</div>')
        renderer = self._build_renderer(entity, rtype, role)
        w(form.form_render(renderer=renderer))
        w(u'</div>')


class EditionFormView(FormViewMixIn, EntityView):
    """display primary entity edition form"""
    id = 'edition'
    # add yes() so it takes precedence over deprecated views in baseforms,
    # though not baseforms based customized view
    __select__ = one_line_rset() & non_final_entity() & yes()

    title = _('edition')

    def cell_call(self, row, col, **kwargs):
        entity = self.complete_entity(row, col)
        self.render_form(entity)

    def render_form(self, entity):
        """fetch and render the form"""
        self.form_title(entity)
        form = self.vreg.select('forms', 'edition', self.req, rset=entity.rset,
                                row=entity.row, col=entity.col, entity=entity,
                                submitmsg=self.submited_message())
        self.init_form(form, entity)
        self.w(form.form_render(formvid=u'edition'))

    def init_form(self, form, entity):
        """customize your form before rendering here"""
        pass

    def form_title(self, entity):
        """the form view title"""
        ptitle = self.req._(self.title)
        self.w(u'<div class="formTitle"><span>%s %s</span></div>' % (
            entity.dc_type(), ptitle and '(%s)' % ptitle))

    def submited_message(self):
        """return the message that will be displayed on successful edition"""
        return self.req._('entity edited')


class CreationFormView(EditionFormView):
    """display primary entity creation form"""
    id = 'creation'
    __select__ = specified_etype_implements('Any') & yes()

    title = _('creation')

    def call(self, **kwargs):
        """creation view for an entity"""
        etype = kwargs.pop('etype', self.req.form.get('etype'))
        try:
            entity = self.vreg.etype_class(etype)(self.req)
        except:
            self.w(self.req._('no such entity type %s') % etype)
        else:
            self.initialize_varmaker()
            entity.eid = self.varmaker.next()
            self.render_form(entity)

    def form_title(self, entity):
        """the form view title"""
        if '__linkto' in self.req.form:
            if isinstance(self.req.form['__linkto'], list):
                # XXX which one should be considered (case: add a ticket to a
                # version in jpl)
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
            self.w(u'<div class="formTitle notransform"><span>%s</span></div>' % msg)
        else:
            super(CreationFormView, self).form_title(entity)

    def url(self):
        """return the url associated with this view"""
        return self.create_url(self.req.form.get('etype'))

    def submited_message(self):
        """return the message that will be displayed on successful edition"""
        return self.req._('entity created')


class CopyFormView(EditionFormView):
    """display primary entity creation form initialized with values from another
    entity
    """
    id = 'copy'
    def render_form(self, entity):
        """fetch and render the form"""
        # make a copy of entity to avoid altering the entity in the
        # request's cache.
        entity.complete()
        self.newentity = copy(entity)
        self.copying = entity
        self.initialize_varmaker()
        self.newentity.eid = self.varmaker.next()
        self.w(u'<script type="text/javascript">updateMessage("%s");</script>\n'
               % self.req._('Please note that this is only a shallow copy'))
        super(CopyFormView, self).render_form(self.newentity)
        del self.newentity

    def init_form(self, form, entity):
        """customize your form before rendering here"""
        super(CopyFormView, self).init_form(form, entity)
        if entity.eid == self.newentity.eid:
            form.form_add_hidden(eid_param('__cloned_eid', entity.eid),
                                 self.copying.eid)
        for rschema, _, role in form.relations_by_category(form.attrcategories,
                                                           'add'):
            if not rschema.is_final():
                # ensure relation cache is filed
                rset = self.copying.related(rschema, role)
                self.newentity.set_related_cache(rschema, role, rset)

    def submited_message(self):
        """return the message that will be displayed on successful edition"""
        return self.req._('entity copied')


class TableEditForm(forms.CompositeForm):
    id = 'muledit'
    domid = 'entityForm'
    onsubmit = "return validateForm('%s', null);" % domid
    form_buttons = [SubmitButton(_('validate modifications on selected items')),
                    ResetButton(_('revert changes'))]

    def __init__(self, req, rset, **kwargs):
        kwargs.setdefault('__redirectrql', rset.printable_rql())
        super(TableEditForm, self).__init__(req, rset, **kwargs)
        for row in xrange(len(self.rset)):
            form = self.vreg.select('forms', 'edition', self.req, rset=self.rset,
                                    row=row, attrcategories=('primary',),
                                    mainform=False)
            # XXX rely on the EntityCompositeFormRenderer to put the eid input
            form.remove_field(form.field_by_name('eid'))
            self.form_add_subform(form)


class TableEditFormView(FormViewMixIn, EntityView):
    id = 'muledit'
    __select__ = EntityView.__select__ & yes()
    title = _('multiple edit')

    def call(self, **kwargs):
        """a view to edit multiple entities of the same type the first column
        should be the eid
        """
        #self.form_title(entity)
        form = self.vreg.select('forms', self.id, self.req, rset=self.rset)
        self.w(form.form_render())


class InlineEntityEditionFormView(FormViewMixIn, EntityView):
    id = 'inline-edition'
    __select__ = non_final_entity() & match_kwargs('peid', 'rtype')
    removejs = "removeInlinedEntity('%s', '%s', '%s')"

    def call(self, **kwargs):
        """redefine default call() method to avoid automatic
        insertions of <div class="section"> between each row of
        the resultset
        """
        rset = self.rset
        for i in xrange(len(rset)):
            self.wview(self.id, rset, row=i, **kwargs)

    def cell_call(self, row, col, peid, rtype, role='subject', **kwargs):
        """
        :param peid: the parent entity's eid hosting the inline form
        :param rtype: the relation bridging `etype` and `peid`
        :param role: the role played by the `peid` in the relation
        """
        entity = self.entity(row, col)
        divonclick = "restoreInlinedEntity('%s', '%s', '%s')" % (peid, rtype,
                                                                 entity.eid)
        self.render_form(entity, peid, rtype, role, divonclick=divonclick)

    def render_form(self, entity, peid, rtype, role, **kwargs):
        """fetch and render the form"""
        form = self.vreg.select('forms', 'edition', self.req, entity=entity,
                                form_renderer_id='inline', mainform=False,
                                copy_nav_params=False)
        self.add_hiddens(form, entity, peid, rtype, role)
        divid = '%s-%s-%s' % (peid, rtype, entity.eid)
        title = self.schema.rschema(rtype).display_name(self.req, role)
        removejs = self.removejs % (peid, rtype,entity.eid)
        countkey = '%s_count' % rtype
        try:
            self.req.data[countkey] += 1
        except:
            self.req.data[countkey] = 1
        self.w(form.form_render(divid=divid, title=title, removejs=removejs,
                                counter=self.req.data[countkey], **kwargs))

    def add_hiddens(self, form, entity, peid, rtype, role):
        # to ease overriding (see cubes.vcsfile.views.forms for instance)
        if self.keep_entity(form, entity, peid, rtype):
            if entity.has_eid():
                rval = entity.eid
            else:
                rval = INTERNAL_FIELD_VALUE
            form.form_add_hidden('edit%s-%s:%s' % (role[0], rtype, peid), rval)
        form.form_add_hidden(name='%s:%s' % (rtype, peid), value=entity.eid,
                             id='rel-%s-%s-%s'  % (peid, rtype, entity.eid))

    def keep_entity(self, form, entity, peid, rtype):
        if not entity.has_eid():
            return True
        # are we regenerating form because of a validation error ?
        if form.form_previous_values:
            cdvalues = self.req.list_form_param(eid_param(rtype, peid),
                                                form.form_previous_values)
            if unicode(entity.eid) not in cdvalues:
                return False
        return True


class InlineEntityCreationFormView(InlineEntityEditionFormView):
    id = 'inline-creation'
    __select__ = (match_kwargs('peid', 'rtype')
                  & specified_etype_implements('Any'))
    removejs = "removeInlineForm('%s', '%s', '%s')"

    def call(self, etype, peid, rtype, role='subject', **kwargs):
        """
        :param etype: the entity type being created in the inline form
        :param peid: the parent entity's eid hosting the inline form
        :param rtype: the relation bridging `etype` and `peid`
        :param role: the role played by the `peid` in the relation
        """
        try:
            entity = self.vreg.etype_class(etype)(self.req, None, None)
        except:
            self.w(self.req._('no such entity type %s') % etype)
            return
        self.initialize_varmaker()
        entity.eid = self.varmaker.next()
        self.render_form(entity, peid, rtype, role)
