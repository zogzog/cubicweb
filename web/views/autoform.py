"""The automatic entity form.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.decorators import iclassmethod, cached

from cubicweb import typed_eid
from cubicweb.web import stdmsgs, uicfg
from cubicweb.web import form, formwidgets as fwdgs
from cubicweb.web.formfields import guess_field
from cubicweb.web.views import forms, editforms

_afs = uicfg.autoform_section

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
    form_buttons = [fwdgs.SubmitButton(),
                    fwdgs.Button(stdmsgs.BUTTON_APPLY, cwaction='apply'),
                    fwdgs.Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]
    # for attributes selection when searching in uicfg.autoform_section
    formtype = 'main'
    # set this to a list of [(relation, role)] if you want to explictily tell
    # which relations should be edited
    display_fields = None
    # class attributes below are actually stored in the uicfg module since we
    # don't want them to be reloaded
    rfields = uicfg.autoform_field
    rfields_kwargs = uicfg.autoform_field_kwargs

    # class methods mapping schema relations to fields in the form ############

    @iclassmethod
    def field_by_name(cls_or_self, name, role='subject', eschema=None):
        """return field with the given name and role. If field is not explicitly
        defined for the form but `eclass` is specified, guess_field will be
        called.
        """
        try:
            return super(AutomaticEntityForm, cls_or_self).field_by_name(name, role)
        except form.FieldNotFound:
            if eschema is None or not name in eschema.schema:
                raise
            rschema = eschema.schema.rschema(name)
            # XXX use a sample target type. Document this.
            tschemas = rschema.targets(eschema, role)
            fieldcls = cls_or_self.rfields.etype_get(eschema, rschema, role,
                                                     tschemas[0])
            kwargs = cls_or_self.rfields_kwargs.etype_get(eschema, rschema,
                                                          role, tschemas[0])
            if kwargs is None:
                kwargs = {}
            if fieldcls:
                if not isinstance(fieldcls, type):
                    return fieldcls # already and instance
                return fieldcls(name=name, role=role, eidparam=True, **kwargs)
            field = guess_field(eschema, rschema, role, eidparam=True, **kwargs)
            if field is None:
                raise
            return field

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
        self.maxrelitems = self._cw.property_value('navigation.related-limit')
        self.force_display = bool(self._cw.form.get('__force_display'))
        fnum = len(self.fields)
        self.fields.sort(key=lambda f: f.order is None and fnum or f.order)

    @property
    def related_limit(self):
        if self.force_display:
            return None
        return self.maxrelitems + 1

    @property
    def form_needs_multipart(self):
        """true if the form needs enctype=multipart/form-data"""
        return self._subform_needs_multipart()

    def build_context(self, rendervalues=None):
        super(AutomaticEntityForm, self).build_context(rendervalues)
        for form in self.inlined_forms():
            form.build_context(rendervalues)

    def _subform_needs_multipart(self, _tested=None):
        if _tested is None:
            _tested = set()
        if super(AutomaticEntityForm, self).form_needs_multipart:
            return True
        # take a look at inlined forms to check (recursively) if they
        # need multipart handling.
        # XXX: this is very suboptimal because inlined forms will be
        #      selected / instantiated twice : here and during form rendering.
        #      Potential solutions:
        #       -> use subforms for inlined forms to get easiser access
        #       -> use a simple onload js function to check if there is
        #          a input type=file in the form
        #       -> generate the <form> node when the content is rendered
        #          and we know the correct enctype (formrenderer's w attribute
        #          is not a StringIO)
        for formview in self.inlined_form_views():
            if formview.form:
                if hasattr(formview.form, '_subform_needs_multipart'):
                    needs_multipart = formview.form._subform_needs_multipart(_tested)
                else:
                    needs_multipart = formview.form.form_needs_multipart
                if needs_multipart:
                    return True
        return False

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

    # methods mapping edited entity relations to fields in the form ############

    def _relations_by_section(self, section, permission='add', strict=False):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        return _afs.relations_by_section(
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

    # generic relations modifier ###############################################

    def relations_table(self):
        """yiels 3-tuples (rtype, target, related_list)
        where <related_list> itself a list of :
          - node_id (will be the entity element's DOM id)
          - appropriate javascript's togglePendingDelete() function call
          - status 'pendingdelete' or ''
          - oneline view of related entity
        """
        entity = self.edited_entity
        pending_deletes = self._cw.get_pending_deletes(entity.eid)
        for label, rschema, role in self.editable_relations():
            relatedrset = entity.related(rschema, role, limit=self.related_limit)
            if rschema.has_perm(self._cw, 'delete'):
                toggleable_rel_link_func = editforms.toggleable_relation_link
            else:
                toggleable_rel_link_func = lambda x, y, z: u''
            related = []
            for row in xrange(relatedrset.rowcount):
                nodeid = editforms.relation_id(entity.eid, rschema, role,
                                               relatedrset[row][0])
                if nodeid in pending_deletes:
                    status = u'pendingDelete'
                    label = '+'
                else:
                    status = u''
                    label = 'x'
                dellink = toggleable_rel_link_func(entity.eid, nodeid, label)
                eview = self._cw.view('oneline', relatedrset, row=row)
                related.append((nodeid, dellink, status, eview))
            yield (rschema, role, related)

    def restore_pending_inserts(self, cell=False):
        """used to restore edition page as it was before clicking on
        'search for <some entity type>'
        """
        eid = self.edited_entity.eid
        cell = cell and "div_insert_" or "tr"
        pending_inserts = set(self._cw.get_pending_inserts(eid))
        for pendingid in pending_inserts:
            eidfrom, rtype, eidto = pendingid.split(':')
            if typed_eid(eidfrom) == eid: # subject
                label = display_name(self._cw, rtype, 'subject',
                                     self.edited_entity.__regid__)
                reid = eidto
            else:
                label = display_name(self._cw, rtype, 'object',
                                     self.edited_entity.__regid__)
                reid = eidfrom
            jscall = "javascript: cancelPendingInsert('%s', '%s', null, %s);" \
                     % (pendingid, cell, eid)
            rset = self._cw.eid_rset(reid)
            eview = self._cw.view('text', rset, row=0)
            # XXX find a clean way to handle baskets
            if rset.description[0][0] == 'Basket':
                eview = '%s (%s)' % (eview, display_name(self._cw, 'Basket'))
            yield rtype, pendingid, jscall, label, reid, eview

    # inlined forms support ####################################################

    @cached
    def inlined_form_views(self):
        """compute and return list of inlined form views (hosting the inlined form object)
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

    def inlined_forms(self):
        for formview in self.inlined_form_views():
            if formview.form: # may be None for the addnew_link artefact form
                yield formview.form

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
                    yield vvreg.select('inline-edition', self._cw, rset=related,
                                       row=i, col=0, rtype=rschema, role=role,
                                       peid=entity.eid, pform=self)

    def inline_creation_form_view(self, rschema, ttype, role):
        """yield inline form views to a newly related (hence created) entity
        through the given relation
        """
        yield self._cw.vreg['views'].select('inline-creation', self._cw,
                                            etype=ttype, rtype=rschema, role=role,
                                            peid=self.edited_entity.eid, pform=self)


## default form ui configuration ##############################################

_afs = uicfg.autoform_section
# use primary and not generated for eid since it has to be an hidden
_afs.tag_attribute(('*', 'eid'), 'main', 'attributes')
_afs.tag_attribute(('*', 'eid'), 'muledit', 'attributes')
_afs.tag_attribute(('*', 'description'), 'main', 'attributes')
_afs.tag_attribute(('*', 'creation_date'), 'main', 'metadata')
_afs.tag_attribute(('*', 'modification_date'), 'main', 'metadata')
_afs.tag_attribute(('*', 'cwuri'), 'main', 'metadata')
_afs.tag_attribute(('*', 'has_text'), 'main', 'hidden')
_afs.tag_subject_of(('*', 'in_state', '*'), 'main', 'hidden')
_afs.tag_subject_of(('*', 'owned_by', '*'), 'main', 'metadata')
_afs.tag_subject_of(('*', 'created_by', '*'), 'main', 'metadata')
_afs.tag_subject_of(('*', 'require_permission', '*'), 'main', 'hidden')
_afs.tag_subject_of(('*', 'by_transition', '*'), 'main', 'attributes')
_afs.tag_subject_of(('*', 'by_transition', '*'), 'muledit', 'attributes')
_afs.tag_object_of(('*', 'by_transition', '*'), 'main', 'hidden')
_afs.tag_object_of(('*', 'from_state', '*'), 'main', 'hidden')
_afs.tag_object_of(('*', 'to_state', '*'), 'main', 'hidden')
_afs.tag_subject_of(('*', 'wf_info_for', '*'), 'main', 'attributes')
_afs.tag_subject_of(('*', 'wf_info_for', '*'), 'muledit', 'attributes')
_afs.tag_object_of(('*', 'wf_info_for', '*'), 'main', 'hidden')
_afs.tag_subject_of(('*', 'for_user', '*'), 'main', 'hidden')
_afs.tag_object_of(('*', 'for_user', '*'), 'main', 'hidden')
_afs.tag_subject_of(('CWPermission', 'require_group', '*'), 'main', 'attributes')
_afs.tag_subject_of(('CWPermission', 'require_group', '*'), 'muledit', 'attributes')
_afs.tag_attribute(('CWEType', 'final'), 'main', 'hidden')
_afs.tag_attribute(('CWRType', 'final'), 'main', 'hidden')
_afs.tag_attribute(('CWUser', 'firstname'), 'main', 'attributes')
_afs.tag_attribute(('CWUser', 'surname'), 'main', 'attributes')
_afs.tag_attribute(('CWUser', 'last_login_time'), 'main', 'metadata')
_afs.tag_subject_of(('CWUser', 'in_group', '*'), 'main', 'attributes')
_afs.tag_subject_of(('CWUser', 'in_group', '*'), 'muledit', 'attributes')
_afs.tag_object_of(('*', 'bookmarked_by', 'CWUser'), 'main', 'metadata')
_afs.tag_attribute(('Bookmark', 'path'), 'main', 'attributes')
_afs.tag_attribute(('Bookmark', 'path'), 'muledit', 'attributes')
_afs.tag_subject_of(('*', 'primary_email', '*'), 'main', 'relations')
_afs.tag_subject_of(('*', 'use_email', '*'), 'main', 'inlined')
_afs.tag_subject_of(('CWRelation', 'relation_type', '*'), 'main', 'inlined')
_afs.tag_subject_of(('CWRelation', 'from_entity', '*'), 'main', 'inlined')
_afs.tag_subject_of(('CWRelation', 'to_entity', '*'), 'main', 'inlined')

uicfg.autoform_field_kwargs.tag_attribute(('RQLExpression', 'expression'),
                                          {'widget': fwdgs.TextInput})
uicfg.autoform_field_kwargs.tag_attribute(('Bookmark', 'path'),
                                          {'widget': fwdgs.TextInput})
uicfg.autoform_field_kwargs.tag_subject_of(('TrInfo', 'wf_info_for', '*'),
                                           {'widget': fwdgs.HiddenInput})

def registration_callback(vreg):
    global etype_relation_field

    def etype_relation_field(etype, rtype, role='subject'):
        eschema = vreg.schema.eschema(etype)
        return AutomaticEntityForm.field_by_name(rtype, role, eschema)

    vreg.register_all(globals().values(), __name__)
