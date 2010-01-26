"""The automatic entity form.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.decorators import iclassmethod

from cubicweb import typed_eid
from cubicweb.web import stdmsgs, uicfg, form, \
     formwidgets as fw, formfields as ff
from cubicweb.web.views import forms, editforms, editviews

_AFS = uicfg.autoform_section
_AFFK = uicfg.autoform_field_kwargs


class AutomaticEntityForm(forms.EntityFieldsForm):
    """base automatic form to edit any entity.

    Designed to be fully generated from schema but highly configurable through:

    * uicfg (autoform_* relation tags)
    * various standard form parameters
    * overriding

    You can also easily customise it by adding/removing fields in
    AutomaticEntityForm instances or by inheriting from it.
    """
    __regid__ = 'edition'

    cwtarget = 'eformframe'
    cssclass = 'entityForm'
    copy_nav_params = True
    form_buttons = [fw.SubmitButton(),
                    fw.Button(stdmsgs.BUTTON_APPLY, cwaction='apply'),
                    fw.Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]
    # for attributes selection when searching in uicfg.autoform_section
    formtype = 'main'
    # set this to a list of [(relation, role)] if you want to explictily tell
    # which relations should be edited
    display_fields = None

    @iclassmethod
    def field_by_name(cls_or_self, name, role=None, eschema=None):
        """return field with the given name and role. If field is not explicitly
        defined for the form but `eclass` is specified, guess_field will be
        called.
        """
        try:
            return super(AutomaticEntityForm, cls_or_self).field_by_name(name, role, eschema)
        except form.FieldNotFound:
            if name == '_cw_generic_field' and not isinstance(cls_or_self, type):
                return cls_or_self._generic_relations_field()
            raise

    # base automatic entity form methods #######################################

    def __init__(self, *args, **kwargs):
        super(AutomaticEntityForm, self).__init__(*args, **kwargs)
        entity = self.edited_entity
        if entity.has_eid():
            entity.complete()
        for rtype, role in self.editable_attributes():
            try:
                self.field_by_name(str(rtype), role)
                continue # explicitly specified
            except form.FieldNotFound:
                # has to be guessed
                try:
                    field = self.field_by_name(str(rtype), role,
                                               eschema=entity.e_schema)
                    self.fields.append(field)
                except form.FieldNotFound:
                    # meta attribute such as <attr>_format
                    continue
        if self.formtype == 'main':
            if self.fieldsets_in_order:
                fsio = list(self.fieldsets_in_order)
            else:
                fsio = [None]
            self.fieldsets_in_order = fsio
            # add fields for relation whose target should have an inline form
            for formview in self.inlined_form_views():
                field = self._inlined_form_view_field(formview)
                self.fields.append(field)
                if not field.fieldset in fsio:
                    fsio.append(field.fieldset)
            # add the generic relation field if necessary
            if entity.has_eid() and (
                self.display_fields is None or
                '_cw_generic_field' in self.display_fields):
                try:
                    field = self.field_by_name('_cw_generic_field')
                except form.FieldNotFound:
                    # no editable relation
                    pass
                else:
                    self.fields.append(field)
                    if not field.fieldset in fsio:
                        fsio.append(field.fieldset)
        self.maxrelitems = self._cw.property_value('navigation.related-limit')
        self.force_display = bool(self._cw.form.get('__force_display'))
        fnum = len(self.fields)
        self.fields.sort(key=lambda f: f.order is None and fnum or f.order)

    @property
    def related_limit(self):
        if self.force_display:
            return None
        return self.maxrelitems + 1

    def action(self):
        """return the form's action attribute. Default to validateform if not
        explicitly overriden.
        """
        try:
            return self._action
        except AttributeError:
            return self._cw.build_url('validateform')

    def set_action(self, value):
        """override default action"""
        self._action = value

    action = property(action, set_action)

    # autoform specific fields #################################################

    def _generic_relations_field(self):
        try:
            srels_by_cat = self.srelations_by_category('generic', 'add', strict=True)
            warn('[3.6] %s: srelations_by_category is deprecated, use uicfg or '
                 'override editable_relations instead' % classid(form),
                 DeprecationWarning)
        except AttributeError:
            srels_by_cat = self.editable_relations()
        if not srels_by_cat:
            raise form.FieldNotFound('_cw_generic_field')
        fieldset = u'%s :' % self._cw.__('This %s' % self.edited_entity.e_schema)
        fieldset = fieldset.capitalize()
        return editviews.GenericRelationsField(self.editable_relations(),
                                               fieldset=fieldset, label=None)

    def _inlined_form_view_field(self, view):
        # XXX allow more customization
        kwargs = _AFFK.etype_get(self.edited_entity.e_schema, view.rtype,
                                 view.role, view.etype)
        if kwargs is None:
            kwargs = {}
        return editforms.InlinedFormField(view=view, **kwargs)

    # methods mapping edited entity relations to fields in the form ############

    def _relations_by_section(self, section, permission='add', strict=False):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        return _AFS.relations_by_section(
            self.edited_entity, self.formtype, section, permission, strict)

    def editable_attributes(self, strict=False):
        """return a list of (relation schema, role) to edit for the entity"""
        if self.display_fields is not None:
            return self.display_fields
        # XXX we should simply put eid in the generated section, no?
        return [(rtype, role) for rtype, _, role in self._relations_by_section(
            'attributes', strict=strict) if rtype != 'eid']

    def editable_relations(self):
        """return a sorted list of (relation's label, relation'schema, role) for
        relations in the 'relations' section
        """
        result = []
        for rschema, _, role in self._relations_by_section('relations',
                                                           strict=True):
            result.append( (rschema.display_name(self.edited_entity._cw, role,
                                                 self.edited_entity.__regid__),
                            rschema, role) )
        return sorted(result)

    def inlined_relations(self):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        return self._relations_by_section('inlined')

    # inlined forms control ####################################################

    def inlined_form_views(self):
        """compute and return list of inlined form views (hosting the inlined
        form object)
        """
        allformviews = []
        entity = self.edited_entity
        for rschema, ttypes, role in self.inlined_relations():
            # show inline forms only if there's one possible target type
            # for rschema
            if len(ttypes) != 1:
                self.warning('entity related by the %s relation should have '
                             'inlined form but there is multiple target types, '
                             'dunno what to do', rschema)
                continue
            ttype = ttypes[0].type
            if self.should_inline_relation_form(rschema, ttype, role):
                formviews = list(self.inline_edition_form_view(rschema, ttype, role))
                card = rschema.rdef(entity.e_schema, ttype).role_cardinality(role)
                # there is no related entity and we need at least one: we need to
                # display one explicit inline-creation view
                if self.should_display_inline_creation_form(rschema, formviews, card):
                    formviews += self.inline_creation_form_view(rschema, ttype, role)
                # we can create more than one related entity, we thus display a link
                # to add new related entities
                if self.should_display_add_new_relation_link(rschema, formviews, card):
                    addnewlink = self._cw.vreg['views'].select(
                        'inline-addnew-link', self._cw,
                        etype=ttype, rtype=rschema, role=role,
                        peid=self.edited_entity.eid, pform=self, card=card)
                    formviews.append(addnewlink)
                allformviews += formviews
        return allformviews

    def should_inline_relation_form(self, rschema, targettype, role):
        """return true if the given relation with entity has role and a
        targettype target should be inlined

        At this point we now relation has inlined_attributes tag (eg is returned
        by `inlined_relations()`. Overrides this for more finer control.
        """
        return True

    def should_display_inline_creation_form(self, rschema, existant, card):
        """return true if a creation form should be inlined

        by default true if there is no related entity and we need at least one
        """
        return not existant and card in '1+' or self._cw.form.has_key('force_%s_display' % rschema)

    def should_display_add_new_relation_link(self, rschema, existant, card):
        """return true if we should add a link to add a new creation form
        (through ajax call)

        by default true if there is no related entity or if the relation has
        multiple cardinality
        """
        return not existant or card in '+*' # XXX add target type permisssions

    def should_hide_add_new_relation_link(self, rschema, card):
        """return true if once an inlined creation form is added, the 'add new'
        link should be hidden

        by default true if the relation has single cardinality
        """
        return card in '1?'

    def inline_edition_form_view(self, rschema, ttype, role):
        """yield inline form views for already related entities through the
        given relation
        """
        entity = self.edited_entity
        related = entity.has_eid() and entity.related(rschema, role)
        if related:
            vvreg = self._cw.vreg['views']
            # display inline-edition view for all existing related entities
            for i, relentity in enumerate(related.entities()):
                if relentity.has_perm('update'):
                    yield vvreg.select('inline-edition', self._cw,
                                       rset=related, row=i, col=0,
                                       etype=ttype, rtype=rschema, role=role,
                                       peid=entity.eid, pform=self)

    def inline_creation_form_view(self, rschema, ttype, role):
        """yield inline form views to a newly related (hence created) entity
        through the given relation
        """
        yield self._cw.vreg['views'].select('inline-creation', self._cw,
                                            etype=ttype, rtype=rschema, role=role,
                                            peid=self.edited_entity.eid, pform=self)


## default form ui configuration ##############################################

# use primary and not generated for eid since it has to be an hidden
_AFS.tag_attribute(('*', 'eid'), 'main', 'attributes')
_AFS.tag_attribute(('*', 'eid'), 'muledit', 'attributes')
_AFS.tag_attribute(('*', 'description'), 'main', 'attributes')
_AFS.tag_attribute(('*', 'creation_date'), 'main', 'metadata')
_AFS.tag_attribute(('*', 'modification_date'), 'main', 'metadata')
_AFS.tag_attribute(('*', 'cwuri'), 'main', 'metadata')
_AFS.tag_attribute(('*', 'has_text'), 'main', 'hidden')
_AFS.tag_subject_of(('*', 'in_state', '*'), 'main', 'hidden')
_AFS.tag_subject_of(('*', 'owned_by', '*'), 'main', 'metadata')
_AFS.tag_subject_of(('*', 'created_by', '*'), 'main', 'metadata')
_AFS.tag_subject_of(('*', 'require_permission', '*'), 'main', 'hidden')
_AFS.tag_subject_of(('*', 'by_transition', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('*', 'by_transition', '*'), 'muledit', 'attributes')
_AFS.tag_object_of(('*', 'by_transition', '*'), 'main', 'hidden')
_AFS.tag_object_of(('*', 'from_state', '*'), 'main', 'hidden')
_AFS.tag_object_of(('*', 'to_state', '*'), 'main', 'hidden')
_AFS.tag_subject_of(('*', 'wf_info_for', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('*', 'wf_info_for', '*'), 'muledit', 'attributes')
_AFS.tag_object_of(('*', 'wf_info_for', '*'), 'main', 'hidden')
_AFS.tag_subject_of(('CWPermission', 'require_group', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('CWPermission', 'require_group', '*'), 'muledit', 'attributes')
_AFS.tag_attribute(('CWEType', 'final'), 'main', 'hidden')
_AFS.tag_attribute(('CWRType', 'final'), 'main', 'hidden')
_AFS.tag_attribute(('CWUser', 'firstname'), 'main', 'attributes')
_AFS.tag_attribute(('CWUser', 'surname'), 'main', 'attributes')
_AFS.tag_attribute(('CWUser', 'last_login_time'), 'main', 'metadata')
_AFS.tag_subject_of(('CWUser', 'in_group', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('CWUser', 'in_group', '*'), 'muledit', 'attributes')
_AFS.tag_subject_of(('*', 'primary_email', '*'), 'main', 'relations')
_AFS.tag_subject_of(('*', 'use_email', '*'), 'main', 'inlined')
_AFS.tag_subject_of(('CWRelation', 'relation_type', '*'), 'main', 'inlined')
_AFS.tag_subject_of(('CWRelation', 'from_entity', '*'), 'main', 'inlined')
_AFS.tag_subject_of(('CWRelation', 'to_entity', '*'), 'main', 'inlined')

_AFFK.tag_attribute(('RQLExpression', 'expression'),
                    {'widget': fw.TextInput})
_AFFK.tag_subject_of(('TrInfo', 'wf_info_for', '*'),
                     {'widget': fw.HiddenInput})

def registration_callback(vreg):
    global etype_relation_field

    def etype_relation_field(etype, rtype, role='subject'):
        eschema = vreg.schema.eschema(etype)
        return AutomaticEntityForm.field_by_name(rtype, role, eschema)

    vreg.register_all(globals().values(), __name__)
