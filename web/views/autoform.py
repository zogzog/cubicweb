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


class AutomaticEntityForm(forms.EntityFieldsForm):
    """base automatic form to edit any entity.

    Designed to be fully generated from schema but highly configurable through:
    * rtags (rcategories, rfields, rwidgets, inlined, rpermissions)
    * various standard form parameters

    XXX s/rtags/uicfg/ ?

    You can also easily customise it by adding/removing fields in
    AutomaticEntityForm instances.
    """
    id = 'edition'

    cwtarget = 'eformframe'
    cssclass = 'entityForm'
    copy_nav_params = True
    form_buttons = [fwdgs.SubmitButton(),
                    fwdgs.Button(stdmsgs.BUTTON_APPLY, cwaction='apply'),
                    fwdgs.Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]
    attrcategories = ('primary', 'secondary')
    # class attributes below are actually stored in the uicfg module since we
    # don't want them to be reloaded
    rcategories = uicfg.autoform_section
    rfields = uicfg.autoform_field
    rfields_kwargs = uicfg.autoform_field_kwargs
    rinlined = uicfg.autoform_is_inlined
    rpermissions_overrides = uicfg.autoform_permissions_overrides

    # class methods mapping schema relations to fields in the form ############

    @classmethod
    def erelations_by_category(cls, entity, categories=None, permission=None,
                               rtags=None, strict=False):
        """return a list of (relation schema, target schemas, role) matching
        categories and permission

        `strict`:
          bool telling if having local role is enough (strict = False) or not
        """
        if categories is not None:
            if not isinstance(categories, (list, tuple, set, frozenset)):
                categories = (categories,)
            if not isinstance(categories, (set, frozenset)):
                categories = frozenset(categories)
        eschema  = entity.e_schema
        if rtags is None:
            rtags = cls.rcategories
        permsoverrides = cls.rpermissions_overrides
        if entity.has_eid():
            eid = entity.eid
        else:
            eid = None
            strict = False
        for rschema, targetschemas, role in eschema.relation_definitions(True):
            # check category first, potentially lower cost than checking
            # permission which may imply rql queries
            if categories is not None:
                targetschemas = [tschema for tschema in targetschemas
                                 if rtags.etype_get(eschema, rschema, role, tschema) in categories]
                if not targetschemas:
                    continue
            if permission is not None:
                # tag allowing to hijack the permission machinery when
                # permission is not verifiable until the entity is actually
                # created...
                if eid is None and '%s_on_new' % permission in permsoverrides.etype_get(eschema, rschema, role):
                    yield (rschema, targetschemas, role)
                    continue
                if rschema.final:
                    if not rschema.has_perm(entity.req, permission, eid):
                        continue
                elif role == 'subject':
                    if not ((not strict and rschema.has_local_role(permission)) or
                            rschema.has_perm(entity.req, permission, fromeid=eid)):
                        continue
                    # on relation with cardinality 1 or ?, we need delete perm as well
                    # if the relation is already set
                    if (permission == 'add'
                        and rschema.cardinality(eschema, targetschemas[0], role) in '1?'
                        and eid and entity.related(rschema.type, role)
                        and not rschema.has_perm(entity.req, 'delete', fromeid=eid,
                                                 toeid=entity.related(rschema.type, role)[0][0])):
                        continue
                elif role == 'object':
                    if not ((not strict and rschema.has_local_role(permission)) or
                            rschema.has_perm(entity.req, permission, toeid=eid)):
                        continue
                    # on relation with cardinality 1 or ?, we need delete perm as well
                    # if the relation is already set
                    if (permission == 'add'
                        and rschema.cardinality(targetschemas[0], eschema, role) in '1?'
                        and eid and entity.related(rschema.type, role)
                        and not rschema.has_perm(entity.req, 'delete', toeid=eid,
                                                 fromeid=entity.related(rschema.type, role)[0][0])):
                        continue
            yield (rschema, targetschemas, role)

    @classmethod
    def esrelations_by_category(cls, entity, categories=None, permission=None,
                                strict=False):
        """filter out result of relations_by_category(categories, permission) by
        removing final relations

        return a sorted list of (relation's label, relation'schema, role)
        """
        result = []
        for rschema, ttypes, role in cls.erelations_by_category(
            entity, categories, permission, strict=strict):
            if rschema.final:
                continue
            result.append((rschema.display_name(entity.req, role), rschema, role))
        return sorted(result)

    @iclassmethod
    def field_by_name(cls_or_self, name, role='subject', eschema=None):
        """return field with the given name and role. If field is not explicitly
        defined for the form but `eclass` is specified, guess_field will be
        called.
        """
        try:
            return super(AutomaticEntityForm, cls_or_self).field_by_name(name, role)
        except form.FieldNotFound:
            if eschema is None or not name in cls_or_self.schema:
                raise
            rschema = cls_or_self.schema.rschema(name)
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
        for rschema, role in self.editable_attributes():
            try:
                self.field_by_name(rschema.type, role)
                continue # explicitly specified
            except form.FieldNotFound:
                # has to be guessed
                try:
                    field = self.field_by_name(rschema.type, role,
                                               eschema=entity.e_schema)
                    self.fields.append(field)
                except form.FieldNotFound:
                    # meta attribute such as <attr>_format
                    continue
        self.maxrelitems = self.req.property_value('navigation.related-limit')
        self.force_display = bool(self.req.form.get('__force_display'))

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
            return self.build_url('validateform')

    def set_action(self, value):
        """override default action"""
        self._action = value

    action = property(action, set_action)

    # methods mapping edited entity relations to fields in the form ############

    def relations_by_category(self, categories=None, permission=None):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        return self.erelations_by_category(self.edited_entity, categories,
                                           permission)

    def inlined_relations(self):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        # we'll need an initialized varmaker if there are some inlined relation
        self.initialize_varmaker()
        return self.erelations_by_category(self.edited_entity, True, 'add',
                                           self.rinlined)

    def srelations_by_category(self, categories=None, permission=None,
                               strict=False):
        """filter out result of relations_by_category(categories, permission) by
        removing final relations

        return a sorted list of (relation's label, relation'schema, role)
        """
        return self.esrelations_by_category(self.edited_entity, categories,
                                           permission, strict=strict)

    def editable_attributes(self):
        """return a list of (relation schema, role) to edit for the entity"""
        return [(rschema, role) for rschema, _, role in self.relations_by_category(
                self.attrcategories, 'add') if rschema != 'eid']

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
        pending_deletes = self.req.get_pending_deletes(entity.eid)
        for label, rschema, role in self.srelations_by_category('generic', 'add',
                                                                strict=True):
            relatedrset = entity.related(rschema, role, limit=self.related_limit)
            if rschema.has_perm(self.req, 'delete'):
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
                eview = self.view('oneline', relatedrset, row=row)
                related.append((nodeid, dellink, status, eview))
            yield (rschema, role, related)

    def restore_pending_inserts(self, cell=False):
        """used to restore edition page as it was before clicking on
        'search for <some entity type>'
        """
        eid = self.edited_entity.eid
        cell = cell and "div_insert_" or "tr"
        pending_inserts = set(self.req.get_pending_inserts(eid))
        for pendingid in pending_inserts:
            eidfrom, rtype, eidto = pendingid.split(':')
            if typed_eid(eidfrom) == eid: # subject
                label = display_name(self.req, rtype, 'subject')
                reid = eidto
            else:
                label = display_name(self.req, rtype, 'object')
                reid = eidfrom
            jscall = "javascript: cancelPendingInsert('%s', '%s', null, %s);" \
                     % (pendingid, cell, eid)
            rset = self.req.eid_rset(reid)
            eview = self.view('text', rset, row=0)
            # XXX find a clean way to handle baskets
            if rset.description[0][0] == 'Basket':
                eview = '%s (%s)' % (eview, display_name(self.req, 'Basket'))
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
                if role == 'subject':
                    card = rschema.rproperty(entity.e_schema, ttype, 'cardinality')[0]
                else:
                    card = rschema.rproperty(ttype, entity.e_schema, 'cardinality')[1]
                # there is no related entity and we need at least one: we need to
                # display one explicit inline-creation view
                if self.should_display_inline_creation_form(rschema, formviews, card):
                    formviews += self.inline_creation_form_view(rschema, ttype, role)
                # we can create more than one related entity, we thus display a link
                # to add new related entities
                if self.should_display_add_new_relation_link(rschema, formviews, card):
                    addnewlink = self.vreg['views'].select(
                        'inline-addnew-link', self.req,
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
        """
        return True

    def should_display_inline_creation_form(self, rschema, existant, card):
        """return true if a creation form should be inlined

        by default true if there is no related entity and we need at least one
        """
        return not existant and card in '1+' or self.req.form.has_key('force_%s_display' % rschema)

    def should_display_add_new_relation_link(self, rschema, existant, card):
        """return true if we should add a link to add a new creation form
        (through ajax call)

        by default true if there is no related entity or if the relation has
        multiple cardinality
        """
        return not existant or card in '+*'

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
            vvreg = self.vreg['views']
            # display inline-edition view for all existing related entities
            for i, relentity in enumerate(related.entities()):
                if relentity.has_perm('update'):
                    yield vvreg.select('inline-edition', self.req, rset=related,
                                       row=i, col=0, rtype=rschema, role=role,
                                       peid=entity.eid, pform=self)

    def inline_creation_form_view(self, rschema, ttype, role):
        """yield inline form views to a newly related (hence created) entity
        through the given relation
        """
        yield self.vreg['views'].select('inline-creation', self.req,
                                        etype=ttype, rtype=rschema, role=role,
                                        peid=self.edited_entity.eid, pform=self)


def etype_relation_field(etype, rtype, role='subject'):
    eschema = AutomaticEntityForm.schema.eschema(etype)
    return AutomaticEntityForm.field_by_name(rtype, role, eschema)


## default form ui configuration ##############################################

# use primary and not generated for eid since it has to be an hidden
uicfg.autoform_section.tag_attribute(('*', 'eid'), 'primary')
uicfg.autoform_section.tag_attribute(('*', 'description'), 'secondary')
uicfg.autoform_section.tag_attribute(('*', 'creation_date'), 'metadata')
uicfg.autoform_section.tag_attribute(('*', 'modification_date'), 'metadata')
uicfg.autoform_section.tag_attribute(('*', 'cwuri'), 'metadata')
uicfg.autoform_section.tag_attribute(('*', 'has_text'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'in_state', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'owned_by', '*'), 'metadata')
uicfg.autoform_section.tag_subject_of(('*', 'created_by', '*'), 'metadata')
uicfg.autoform_section.tag_subject_of(('*', 'is', '*'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'is', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'is_instance_of', '*'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'is_instance_of', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'identity', '*'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'identity', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'require_permission', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'by_transition', '*'), 'primary')
uicfg.autoform_section.tag_object_of(('*', 'by_transition', '*'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'from_state', '*'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'to_state', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'wf_info_for', '*'), 'primary')
uicfg.autoform_section.tag_object_of(('*', 'wf_info_for', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('*', 'for_user', '*'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'for_user', '*'), 'generated')
uicfg.autoform_section.tag_subject_of(('CWPermission', 'require_group', '*'), 'primary')
uicfg.autoform_section.tag_attribute(('CWEType', 'final'), 'generated')
uicfg.autoform_section.tag_attribute(('CWRType', 'final'), 'generated')
uicfg.autoform_section.tag_attribute(('CWUser', 'firstname'), 'secondary')
uicfg.autoform_section.tag_attribute(('CWUser', 'surname'), 'secondary')
uicfg.autoform_section.tag_attribute(('CWUser', 'last_login_time'), 'metadata')
uicfg.autoform_section.tag_subject_of(('CWUser', 'in_group', '*'), 'primary')
uicfg.autoform_section.tag_object_of(('*', 'owned_by', 'CWUser'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'created_by', 'CWUser'), 'generated')
uicfg.autoform_section.tag_object_of(('*', 'bookmarked_by', 'CWUser'), 'metadata')
uicfg.autoform_section.tag_attribute(('Bookmark', 'path'), 'primary')
uicfg.autoform_section.tag_subject_of(('*', 'primary_email', '*'), 'generic')

uicfg.autoform_field_kwargs.tag_attribute(('RQLExpression', 'expression'),
                                          {'widget': fwdgs.TextInput})
uicfg.autoform_field_kwargs.tag_attribute(('Bookmark', 'path'),
                                          {'widget': fwdgs.TextInput})
uicfg.autoform_field_kwargs.tag_subject_of(('TrInfo', 'wf_info_for', '*'),
                                           {'widget': fwdgs.HiddenInput})

uicfg.autoform_is_inlined.tag_subject_of(('*', 'use_email', '*'), True)
uicfg.autoform_is_inlined.tag_subject_of(('CWRelation', 'relation_type', '*'), True)
uicfg.autoform_is_inlined.tag_subject_of(('CWRelation', 'from_entity', '*'), True)
uicfg.autoform_is_inlined.tag_subject_of(('CWRelation', 'to_entity', '*'), True)
