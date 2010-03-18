#:organization: Logilab
#:copyright: 2009-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
#:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
#:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses

"""This module (``cubicweb.web.uicfg``) regroups a set of structures that may be used to configure
various options of the generated web interface.

To configure the interface generation, we use ``RelationTag`` objects.

Primary view configuration
``````````````````````````

If you want to customize the primary view of an entity, overriding the
primary view class may not be necessary. For simple adjustments
(attributes or relations display locations and styles), a much simpler
way is to use uicfg.

Attributes/relations display location
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the primary view, there are 3 sections where attributes and
relations can be displayed (represented in pink in the image below):
   * attributes
   * relations
   * sideboxes

.. image:: ../../images/primaryview_template.png


**Attributes** can only be displayed in the attributes section (default behavior). They can also be hidden.

For instance, to hide the ``title`` attribute of the ``Blog`` entity:

.. sourcecode:: python

   from cubicweb.web import uicfg
   uicfg.primaryview_section.tag_attribute(('Blog', 'title'), 'hidden')


**Relations** can be either displayed in one of the three sections or hidden.

For relations, there are two methods:
   * ``tag_object_of`` for modifying the primary view of the object
   * ``tag_subject_of`` for modifying the primary view of the subject

These two methods take two arguments:
   * a triplet ``(subject, relation_name, object)``, where subject or object can be replaced with ``'*'``
   * the section name or ``hidden``

.. sourcecode:: python

   # hide every relation ``entry_of`` in the ``Blog`` primary view
   uicfg.primaryview_section.tag_object_of(('*', 'entry_of', 'Blog'), 'hidden')

   # display ``entry_of`` relations in the ``relations`` section in the ``BlogEntry`` primary view
   uicfg.primaryview_section.tag_subject_of(('BlogEntry', 'entry_of', '*'),
                                             'relations')


Display content
^^^^^^^^^^^^^^^

You can use ``primaryview_display_ctrl`` to customize the display of attributes or relations. Values of ``primaryview_display_ctrl`` are dictionaries.


Common keys for attributes and relations are:
   * ``vid``: specifies the regid of the view for displaying the attribute or the relation.

     If ``vid`` is not specified, the default value depends on the section:
       * ``attributes`` section: 'reledit' view
       * ``relations`` section: 'autolimited' view
       * ``sideboxes`` section: 'sidebox' view

   * ``order``: int used to control order within a section. When not specified, automatically set according to order in which tags are added.


Keys for relations only:

   * ``label``: label for the relations section or side box

   * ``showlabel``: boolean telling whether the label is displayed

   * ``limit``: boolean telling if the results should be limited. If so, a link to all results is displayed

   * ``filter``: callback taking the related result set as argument and returning it filtered

.. sourcecode:: python

   # in ``CWUser`` primary view, display ``created_by`` relations in relations section
   uicfg.primaryview_section.tag_object_of(('*', 'created_by', 'CWUser'), 'relations')

   # displays this relation as a list, sets the label, limits the number of results and filters on comments
   uicfg.primaryview_display_ctrl.tag_object_of(
       ('*', 'created_by', 'CWUser'),
       {'vid': 'list', 'label': _('latest comment(s):'), 'limit': True,
        'filter': lambda rset: rset.filtered_rset(lambda x: x.e_schema == 'Comment')})

.. warning:: with the ``primaryview_display_ctrl`` rtag, the subject or the object of the relation is ignored for respectively ``tag_object_of`` or  ``tag_subject_of``. To avoid warnings during execution, they should be set to ``'*'``.


Index view configuration
````````````````````````
:indexview_etype_section:
   entity type category in the index/manage page. May be one of:
      * ``application``
      * ``system``
      * ``schema``
      * ``subobject`` (not displayed by default)


Actions box configuration
`````````````````````````
:actionbox_appearsin_addmenu:
  simple boolean relation tags used to control the "add entity" submenu.
  Relations whose rtag is True will appears, other won't.

.. sourcecode:: python

   # Adds all subjects of the entry_of relation in the add menu of the ``Blog`` primary view
   uicfg.actionbox_appearsin_addmenu.tag_object_of(('*', 'entry_of', 'Blog'), True)



Automatic form configuration
````````````````````````````

Attributes/relations display location
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``uicfg.autoform_section`` specifies where to display a relation in creation/edition entity form for a given form type.
``tag_attribute``, ``tag_subject_of`` and ``tag_object_of`` methods for this
relation tag expect two arguments additionally to the relation key: a
``formtype`` and a ``section``.

formtype may be one of:
   * ``main``, the main entity form (via the modify action)
   * ``inlined``, the form for an entity inlined into another form
   * ``muledit``, the table form to edit multiple entities

section may be one of:
   * ``hidden``, don't display
   * ``attributes``, display in the attributes section
   * ``relations``, display in the relations section, using the generic relation
     selector combobox (available in main form only, and not for attribute
     relation)
   * ``inlined``, display target entity of the relation in an inlined form
     (available in main form only, and not for attribute relation)
   * ``metadata``, display in a special metadata form (NOT YET IMPLEMENTED,
     subject to changes)

By default, mandatory relations are displayed in the ``attributes`` section, others in ``relations`` section.

Change default fields
^^^^^^^^^^^^^^^^^^^^^

Use ``autoform_field`` to replace the default field type of an attribute.

.. warning: ``autoform_field_kwargs`` should usually be used instead of ``autoform_field``. Do not use both methods for the same relation!


Customize field options
^^^^^^^^^^^^^^^^^^^^^^^

In order to customize field options (see :class:`cubicweb.web.formfields.Field` for a detailed list of options), use ``autoform_field_kwargs``. This rtag takes a relation triplet and a dictionary as arguments.

.. sourcecode:: python

   # Change the content of the combobox
   # here ``ticket_done_in_choices`` is a function which returns a list of elements to populate the combobox
   uicfg.autoform_field_kwargs.tag_subject_of(('Ticket', 'done_in', '*'), {'sort': False,
                                                  'choices': ticket_done_in_choices})



Overriding permissions
^^^^^^^^^^^^^^^^^^^^^^

``autoform_permissions_overrides`` provides a way to by-pass security checking for dark-corner case where it can't
be verified properly. XXX documents.

"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.compat import any

from cubicweb import neg_role
from cubicweb.rtags import (RelationTags, RelationTagsBool, RelationTagsSet,
                            RelationTagsDict, register_rtag, _ensure_str_key)
from cubicweb.schema import META_RTYPES


# primary view configuration ##################################################

def init_primaryview_section(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        rdef = rschema.rdef(sschema, oschema)
        if rschema.final:
            if rschema.meta or sschema.is_metadata(rschema) \
                    or oschema.type in ('Password', 'Bytes'):
                section = 'hidden'
            else:
                section = 'attributes'
        else:
            if rdef.role_cardinality(role) in '1+':
                section = 'attributes'
            elif rdef.composite == neg_role(role):
                section = 'relations'
            else:
                section = 'sideboxes'
        rtag.tag_relation((sschema, rschema, oschema, role), section)

primaryview_section = RelationTags('primaryview_section',
                                   init_primaryview_section,
                                   frozenset(('attributes', 'relations',
                                               'sideboxes', 'hidden')))


class DisplayCtrlRelationTags(RelationTagsDict):
    def __init__(self, *args, **kwargs):
        super(DisplayCtrlRelationTags, self).__init__(*args, **kwargs)
        self._counter = 0

    def tag_relation(self, key, tag):
        tag = super(DisplayCtrlRelationTags, self).tag_relation(key, tag)
        self._counter += 1
        tag.setdefault('order', self._counter)

    def tag_subject_of(self, key, tag):
        subj, rtype, obj = key
        if obj != '*':
            self.warning('using explict target type in display_ctrl.tag_subject_of() '
                         'has no effect, use (%s, %s, "*") instead of (%s, %s, %s)',
                         subj, rtype, subj, rtype, obj)
        super(DisplayCtrlRelationTags, self).tag_subject_of((subj, rtype, '*'), tag)

    def tag_object_of(self, key, tag):
        subj, rtype, obj = key
        if subj != '*':
            self.warning('using explict subject type in display_ctrl.tag_object_of() '
                         'has no effect, use ("*", %s, %s) instead of (%s, %s, %s)',
                         rtype, obj, subj, rtype, obj)
        super(DisplayCtrlRelationTags, self).tag_object_of(('*', rtype, obj), tag)

def init_primaryview_display_ctrl(rtag, sschema, rschema, oschema, role):
    if role == 'subject':
        oschema = '*'
        label = rschema.type
    else:
        sschema = '*'
        label = '%s_%s' % (rschema, role)
    rtag.setdefault((sschema, rschema, oschema, role), 'label', label)
    rtag.setdefault((sschema, rschema, oschema, role), 'order', rtag._counter)

primaryview_display_ctrl = DisplayCtrlRelationTags('primaryview_display_ctrl',
                                                   init_primaryview_display_ctrl)


# index view configuration ####################################################
# entity type section in the index/manage page. May be one of
# * 'application'
# * 'system'
# * 'schema'
# * 'hidden'
# * 'subobject' (not displayed by default)

class InitializableDict(dict):
    def __init__(self, *args, **kwargs):
        super(InitializableDict, self).__init__(*args, **kwargs)
        register_rtag(self)
        self.__defaults = dict(self)

    def init(self, schema, check=True):
        self.update(self.__defaults)
        for eschema in schema.entities():
            if eschema.final:
                continue
            if eschema.schema_entity():
                self.setdefault(eschema, 'schema')
            elif eschema.is_subobject(strict=True):
                self.setdefault(eschema, 'subobject')
            else:
                self.setdefault(eschema, 'application')

indexview_etype_section = InitializableDict(
    EmailAddress='subobject',
    # entity types in the 'system' table by default (managers only)
    CWUser='system', CWGroup='system',
    CWPermission='system',
    CWCache='system',
    Workflow='system',
    ExternalUri='system',
    Bookmark='system',
    )

# autoform.AutomaticEntityForm configuration ##################################

def _formsections_as_dict(formsections):
    result = {}
    for formsection in formsections:
        formtype, section = formsection.split('_', 1)
        result[formtype] = section
    return result

def _card_and_comp(sschema, rschema, oschema, role):
    rdef = rschema.rdef(sschema, oschema)
    if role == 'subject':
        card = rdef.cardinality[0]
        composed = not rschema.final and rdef.composite == 'object'
    else:
        card = rdef.cardinality[1]
        composed = not rschema.final and rdef.composite == 'subject'
    return card, composed

class AutoformSectionRelationTags(RelationTagsSet):
    """autoform relations'section"""

    bw_tag_map = {
        'primary':   {'main': 'attributes', 'muledit': 'attributes'},
        'secondary': {'main': 'attributes', 'muledit': 'hidden'},
        'metadata':  {'main': 'metadata'},
        'generic':   {'main': 'relations'},
        'generated': {'main': 'hidden'},
        }

    _allowed_form_types = ('main', 'inlined', 'muledit')
    _allowed_values = {'main': ('attributes', 'inlined', 'relations',
                                'metadata', 'hidden'),
                       'inlined': ('attributes', 'inlined', 'hidden'),
                       'muledit': ('attributes', 'hidden'),
                       }

    def init(self, schema, check=True):
        super(AutoformSectionRelationTags, self).init(schema, check)
        self.apply(schema, self._initfunc_step2)

    @staticmethod
    def _initfunc(self, sschema, rschema, oschema, role):
        formsections = self.init_get(sschema, rschema, oschema, role)
        if formsections is None:
            formsections = self.tag_container_cls()
        if not any(tag.startswith('inlined') for tag in formsections):
            if not rschema.final:
                negsects = self.init_get(sschema, rschema, oschema, neg_role(role))
                if 'main_inlined' in negsects:
                    formsections.add('inlined_hidden')
        key = _ensure_str_key( (sschema, rschema, oschema, role) )
        self._tagdefs[key] = formsections

    @staticmethod
    def _initfunc_step2(self, sschema, rschema, oschema, role):
        formsections = self.get(sschema, rschema, oschema, role)
        sectdict = _formsections_as_dict(formsections)
        if rschema in META_RTYPES:
            sectdict.setdefault('main', 'hidden')
            sectdict.setdefault('muledit', 'hidden')
            sectdict.setdefault('inlined', 'hidden')
        # ensure we have a tag for each form type
        if not 'main' in sectdict:
            if not rschema.final and (
                sectdict.get('inlined') == 'attributes' or
                'inlined_attributes' in self.init_get(sschema, rschema, oschema,
                                                      neg_role(role))):
                sectdict['main'] = 'hidden'
            elif sschema.is_metadata(rschema):
                sectdict['main'] = 'metadata'
            else:
                card, composed = _card_and_comp(sschema, rschema, oschema, role)
                if card in '1+':
                    sectdict['main'] = 'attributes'
                    if not 'muledit' in sectdict:
                        sectdict['muledit'] = 'attributes'
                elif rschema.final:
                    sectdict['main'] = 'attributes'
                else:
                    sectdict['main'] = 'relations'
        if not 'muledit' in sectdict:
            sectdict['muledit'] = 'hidden'
            if sectdict['main'] == 'attributes':
                card, composed = _card_and_comp(sschema, rschema, oschema, role)
                if card in '1+' and not composed:
                    sectdict['muledit'] = 'attributes'
        if not 'inlined' in sectdict:
            sectdict['inlined'] = sectdict['main']
        # recompute formsections and set it to avoid recomputing
        for formtype, section in sectdict.iteritems():
            formsections.add('%s_%s' % (formtype, section))

    def tag_relation(self, key, formtype, section=None):
        if isinstance(formtype, tuple):
            for ftype in formtype:
                self.tag_relation(key, ftype, section)
            return
        if section is None:
            tag = formtype
            for formtype, section in self.bw_tag_map[tag].iteritems():
                warn('[3.6] add tag to autoform section by specifying form '
                     'type and tag. Replace %s by formtype="%s", section="%s"'
                     % (tag, formtype, section), DeprecationWarning,
                     stacklevel=3)
                self.tag_relation(key, formtype, section)
        assert formtype in self._allowed_form_types, \
               'formtype should be in (%s), not %s' % (
            ','.join(self._allowed_form_types), formtype)
        assert section in self._allowed_values[formtype], \
               'section for %s should be in (%s), not %s' % (
            formtype, ','.join(self._allowed_values[formtype]), section)
        rtags = self._tagdefs.setdefault(_ensure_str_key(key),
                                         self.tag_container_cls())
        # remove previous section for this form type if any
        if rtags:
            for tag in rtags.copy():
                if tag.startswith(formtype):
                    rtags.remove(tag)
        rtags.add('%s_%s' % (formtype, section))
        return rtags

    def init_get(self, *key):
        return super(AutoformSectionRelationTags, self).get(*key)

    def get(self, *key):
        # overriden to avoid recomputing done in parent classes
        return self._tagdefs.get(key, ())

    def relations_by_section(self, entity, formtype, section, permission,
                             strict=False):
        """return a list of (relation schema, target schemas, role) for the
        given entity matching categories and permission.

        `strict`:
          bool telling if having local role is enough (strict = False) or not
        """
        tag = '%s_%s' % (formtype, section)
        eschema  = entity.e_schema
        permsoverrides = autoform_permissions_overrides
        if entity.has_eid():
            eid = entity.eid
        else:
            eid = None
            strict = False
        if permission == 'update':
            assert section in ('attributes', 'metadata', 'hidden')
            relpermission = 'add'
        else:
            assert section not in ('attributes', 'metadata', 'hidden')
            relpermission = permission
        cw = entity._cw
        for rschema, targetschemas, role in eschema.relation_definitions(True):
            _targetschemas = []
            for tschema in targetschemas:
                # check section's tag first, potentially lower cost than
                # checking permission which may imply rql queries
                if not tag in self.etype_get(eschema, rschema, role, tschema):
                    continue
                rdef = rschema.role_rdef(eschema, tschema, role)
                if rschema.final:
                    if not rdef.has_perm(cw, permission, eid=eid,
                                         creating=eid is None):
                        continue
                elif strict or not rdef.has_local_role(relpermission):
                    if role == 'subject':
                        if not rdef.has_perm(cw, relpermission, fromeid=eid):
                            continue
                    elif role == 'object':
                        if not rdef.has_perm(cw, relpermission, toeid=eid):
                            continue
                _targetschemas.append(tschema)
            if not _targetschemas:
                continue
            targetschemas = _targetschemas
            rdef = eschema.rdef(rschema, role=role, targettype=targetschemas[0])
            # XXX tag allowing to hijack the permission machinery when
            # permission is not verifiable until the entity is actually
            # created...
            if eid is None and '%s_on_new' % permission in permsoverrides.etype_get(eschema, rschema, role):
                yield (rschema, targetschemas, role)
                continue
            if not rschema.final and role == 'subject':
                # on relation with cardinality 1 or ?, we need delete perm as well
                # if the relation is already set
                if (relpermission == 'add'
                    and rdef.role_cardinality(role) in '1?'
                    and eid and entity.related(rschema.type, role)
                    and not rdef.has_perm(cw, 'delete', fromeid=eid,
                                          toeid=entity.related(rschema.type, role)[0][0])):
                    continue
            elif role == 'object':
                # on relation with cardinality 1 or ?, we need delete perm as well
                # if the relation is already set
                if (relpermission == 'add'
                    and rdef.role_cardinality(role) in '1?'
                    and eid and entity.related(rschema.type, role)
                    and not rdef.has_perm(cw, 'delete', toeid=eid,
                                          fromeid=entity.related(rschema.type, role)[0][0])):
                    continue
            yield (rschema, targetschemas, role)

autoform_section = AutoformSectionRelationTags('autoform_section')

# relations'field class
autoform_field = RelationTags('autoform_field')

# relations'field explicit kwargs (given to field's __init__)
autoform_field_kwargs = RelationTagsDict()


# set of tags of the form <action>_on_new on relations. <action> is a
# schema action (add/update/delete/read), and when such a tag is found
# permissions checking is by-passed and supposed to be ok
autoform_permissions_overrides = RelationTagsSet('autoform_permissions_overrides')

# boxes.EditBox configuration #################################################

# 'link' / 'create' relation tags, used to control the "add entity" submenu
def init_actionbox_appearsin_addmenu(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        if rschema in META_RTYPES:
            rtag.tag_relation((sschema, rschema, oschema, role), False)
            return
        rdef = rschema.rdef(sschema, oschema)
        if not rdef.role_cardinality(role) in '?1' and rdef.composite == role:
            rtag.tag_relation((sschema, rschema, oschema, role), True)

actionbox_appearsin_addmenu = RelationTagsBool('actionbox_appearsin_addmenu',
                                               init_actionbox_appearsin_addmenu)


# deprecated ###################################################################

class AutoformIsInlined(RelationTags):
    """XXX for < 3.6 bw compat"""
    def tag_relation(self, key, tag):
        warn('autoform_is_inlined is deprecated, use autoform_section '
             'with formtype="main", section="inlined"',
             DeprecationWarning, stacklevel=3)
        section = tag and 'inlined' or 'hidden'
        autoform_section.tag_relation(key, 'main', section)

# inlined view flag for non final relations: when True for an entry, the
# entity(ies) at the other end of the relation will be editable from the
# form of the edited entity
autoform_is_inlined = AutoformIsInlined('autoform_is_inlined')
