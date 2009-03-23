"""Set of HTML automatic forms to create, delete, copy or edit a single entity
or a list of entities of the same type

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps

from cubicweb.selectors import match_kwargs, one_line_rset, non_final_entity
from cubicweb.utils import make_uid
from cubicweb.view import EntityView
from cubicweb.common import tags
from cubicweb.web import stdmsgs
from cubicweb.web.form import MultipleFieldsForm, EntityFieldsForm, FormMixIn, FormRenderer
from cubicweb.web.formfields import guess_field

_ = unicode


class DeleteConfForm(EntityView):
    id = 'deleteconf'
    title = _('delete')
    domid = 'deleteconf'
    onsubmit = None
    # don't use navigation, all entities asked to be deleted should be displayed
    # else we will only delete the displayed page
    need_navigation = False
    
    def call(self):
        """ask for confirmation before real deletion"""
        req, w = self.req, self.w
        _ = req._
        w(u'<script type="text/javascript">updateMessage(\'%s\');</script>\n'
          % _('this action is not reversible!'))
        # XXX above message should have style of a warning
        w(u'<h4>%s</h4>\n' % _('Do you want to delete the following element(s) ?'))
        form = MultipleFieldsForm(req, domid='deleteconf', action=self.build_url('edit'),
                                  onsubmit=self.onsubmit, copy_nav_params=True)
        form.buttons.append(form.button_delete(label=stdmsgs.YES))
        form.buttons.append(form.button_cancel(label=stdmsgs.NO))
        done = set()
        w(u'<ul>\n')
        for i in xrange(self.rset.rowcount):
            if self.rset[i][0] in done:
                continue
            done.add(self.rset[i][0])
            entity = self.rset.get_entity(i, 0)
            subform = EntityFieldsForm(req, set_error_url=False,
                                       entity=entity)
            form.form_add_subform(subform)
            # don't use outofcontext view or any other that may contain inline edition form
            w(u'<li>%s</li>' % tags.a(entity.view('textoutofcontext'),
                                      href=entity.absolute_url()))
        w(u'</ul>\n')
        w(form.form_render())


class ClickAndEditForm(FormMixIn, EntityView):
    id = 'reledit'
    __select__ = non_final_entity() & match_kwargs('rtype')

    # FIXME editableField class could be toggleable from userprefs
      
    def cell_call(self, row, col, rtype=None, role='subject', reload=False):
        entity = self.entity(row, col)
        if getattr(entity, rtype) is None:
            value = self.req._('not specified')
        else:
            value = entity.printable_value(rtype)
        if not entity.has_perm('update'):
            self.w(value)
            return
        self.req.add_js( ('cubicweb.ajax.js',) )
        eid = entity.eid
        edit_key = make_uid('%s-%s' % (rtype, eid))
        divid = 'd%s' % edit_key
        reload = dumps(reload)
        buttons = [tags.input(klass="validateButton", type="submit", name="__action_apply",
                              value=self.req._(stdmsgs.BUTTON_OK), tabindex=self.req.next_tabindex()),
                   tags.input(klass="validateButton", type="button",
                              value=self.req._(stdmsgs.BUTTON_CANCEL),
                              onclick="cancelInlineEdit(%s,\'%s\',\'%s\')" % (eid, rtype, divid),
                              tabindex=self.req.next_tabindex())]
        form = self.vreg.select_object('forms', 'edition', self.req, self.rset, row=row, col=col,
                                       entity=entity, domid='%s-form' % divid, action='#',
                                       cssstyle='display: none', buttons=buttons,
                                       onsubmit="return inlineValidateForm('%(divid)s-form', '%(rtype)s', '%(eid)s', '%(divid)s', %(reload)s);" % locals())
        renderer = FormRenderer(display_label=False, display_help=False,
                                display_fields=(rtype,), button_bar_class='buttonbar')
        self.w(tags.div(value, klass='editableField', id=divid,
                        ondblclick="showInlineEditionForm(%(eid)s, '%(rtype)s', '%(divid)s')" % locals()))
        self.w(form.render(renderer=renderer))


class AutomaticEntityForm(EntityFieldsForm):
    id = 'edition'
    needs_js = EntityFieldsForm.needs_js + ('cubicweb.ajax.js',)
    
    def __init__(self, *args, **kwargs):
        super(AutomaticEntityForm, self).__init__(*args, **kwargs)
        self.entity.complete()
        for rschema, target in self.editable_attributes(self.entity):
            field = guess_field(entity.__class__, self.entity.e_schema, rschema, target)
            self.fields.append(field)
            
    def form_buttons(self):
        return [self.button_ok(tabindex=self.req.next_tabindex()),
                self.button_apply(tabindex=self.req.next_tabindex()),
                self.button_cancel(tabindex=self.req.next_tabindex())]

    def editable_attributes(self, entity):
        # XXX both (add, delete) required for non final relations
        return [(rschema, x) for rschema, _, x in entity.relations_by_category(('primary', 'secondary'), 'add')
                if rschema != 'eid']
    
class _EditionForm(EntityView):
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

    def cell_call(self, row, col, **kwargs):
        self.req.add_js( ('cubicweb.ajax.js',) )
        self.initialize_varmaker()
        entity = self.complete_entity(row, col)

    def initialize_varmaker(self):
        varmaker = self.req.get_page_data('rql_varmaker')
        if varmaker is None:
            varmaker = self.req.varmaker
            self.req.set_page_data('rql_varmaker', varmaker)
        self.varmaker = varmaker
        
    def edit_form(self, entity, kwargs):
        form = EntityFieldsForm(self.req, entity=entity)
        for rschema, target in self.editable_attributes(entity):
            field = guess_field(entity.__class__, entity.e_schema, rschema, target)
            form.fields.append(field)
        form.buttons.append(form.button_ok())
        form.buttons.append(form.button_apply())
        form.buttons.append(form.button_cancel())
        self.w(form.form_render())

    def editable_attributes(self, entity):
        # XXX both (add, delete)
        return [(rschema, x) for rschema, _, x in entity.relations_by_category(('primary', 'secondary'), 'add')
                if rschema != 'eid']
