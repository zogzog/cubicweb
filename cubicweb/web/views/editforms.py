# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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



from copy import copy

from logilab.common.registry import yes

from cubicweb import _
from cubicweb import tags
from cubicweb.predicates import (one_line_rset, non_final_entity,
                                 specified_etype_implements, is_instance)
from cubicweb.view import EntityView
from cubicweb.web import stdmsgs, eid_param, formwidgets as fw
from cubicweb.web.form import FormViewMixIn
from cubicweb.web.views import uicfg, forms, reledit

_pvdc = uicfg.primaryview_display_ctrl


class DeleteConfForm(forms.CompositeForm):
    __regid__ = 'deleteconf'
    # XXX non_final_entity does not implement eclass_selector
    __select__ = is_instance('Any')

    domid = 'deleteconf'
    copy_nav_params = True
    form_buttons = [fw.Button(stdmsgs.BUTTON_DELETE, cwaction='delete'),
                    fw.Button(stdmsgs.BUTTON_CANCEL,
                              {'class': fw.Button.css_class + ' cwjs-edition-cancel'})]

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
    # show first level of composite relations in a treeview
    show_composite = False
    show_composite_skip_rtypes = set('wf_info_for',)

    def _iter_composite_entities(self, entity, limit=None):
        eids = set()
        for rdef, role in sorted(entity.e_schema.composite_rdef_roles,
                                 key=lambda x: x[0].rtype):
            if rdef.rtype in self.show_composite_skip_rtypes:
                continue
            for centity in entity.related(
                rdef.rtype, role, limit=limit
            ).entities():
                if centity.eid not in eids:
                    eids.add(centity.eid)
                    yield centity

    def call(self, onsubmit=None):
        """ask for confirmation before real deletion"""
        req, w = self._cw, self.w
        _ = req._
        if self.show_composite:
            req.add_css(('jquery-treeview/jquery.treeview.css', 'cubicweb.treeview.css'))
        w(u'<script type="text/javascript">updateMessage(\'%s\');</script>\n'
          % _('this action is not reversible!'))
        # XXX above message should have style of a warning
        w(u'<h4>%s</h4>\n' % _('Do you want to delete the following element(s)?'))
        form = self._cw.vreg['forms'].select(self.__regid__, req,
                                             rset=self.cw_rset,
                                             onsubmit=onsubmit)
        w(u'<ul>\n')
        page_size = req.property_value('navigation.page-size')
        for entity in self.cw_rset.entities():
            # don't use outofcontext view or any other that may contain inline
            # edition form
            w(u'<li>%s' % tags.a(entity.view('textoutofcontext'),
                                 href=entity.absolute_url()))
            if self.show_composite:
                content = None
                for count, centity in enumerate(self._iter_composite_entities(
                    entity, limit=page_size,
                )):
                    if count == 0:
                        w(u'<ul class="treeview">')
                    if content is not None:
                        w(u'<li>%s</li>' % content)
                    if count == page_size - 1:
                        w(u'<li class="last">%s</li></ul>' % _(
                            'And more composite entities'))
                        break
                    content = tags.a(centity.view('textoutofcontext'),
                                     href=centity.absolute_url())
                else:
                    if content is not None:
                        w(u'<li class="last">%s</li></ul>' % content)
            w(u'</li>\n')
        w(u'</ul>\n')
        form.render(w=self.w)


class EditionFormView(FormViewMixIn, EntityView):
    """display primary entity edition form"""
    __regid__ = 'edition'
    # add yes() so it takes precedence over deprecated views in baseforms,
    # though not baseforms based customized view
    __select__ = one_line_rset() & non_final_entity() & yes()
    form_id = 'edition'

    title = _('modification')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.complete_entity(row, col)
        self.render_form(entity)

    def render_form(self, entity):
        """fetch and render the form"""
        self.form_title(entity)
        form = self._cw.vreg['forms'].select(self.form_id, self._cw,
                                             entity=entity,
                                             submitmsg=self.submited_message())
        self.init_form(form, entity)
        form.render(w=self.w)

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
        entity.eid = next(self._cw.varmaker)
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
        req = self._cw
        return req.vreg["etypes"].etype_class(req.form['etype']).cw_create_url(
            req)

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
        self.newentity.eid = next(self._cw.varmaker)
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
                self.newentity.cw_set_relation_cache(rschema, role, rset)

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
        for row in range(len(self.cw_rset)):
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
        form.render(w=self.w)
