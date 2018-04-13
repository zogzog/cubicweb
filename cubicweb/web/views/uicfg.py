# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""This module (``cubicweb.web.views.uicfg``) regroups a set of structures that may be
used to configure various options of the generated web interface.

To configure the interface generation, we use ``RelationTag`` objects.

Index view configuration
````````````````````````
:indexview_etype_section:
   entity type category in the index/manage page. May be one of:

      * ``application``
      * ``system``
      * ``schema``
      * ``subobject`` (not displayed by default)

   By default only entities on the ``application`` category are shown.

.. sourcecode:: python

    from cubicweb.web.views import uicfg
    # force hiding
    uicfg.indexview_etype_section['HideMe'] = 'subobject'
    # force display
    uicfg.indexview_etype_section['ShowMe'] = 'application'


Actions box configuration
`````````````````````````
:actionbox_appearsin_addmenu:
  simple boolean relation tags used to control the "add entity" submenu.
  Relations whose rtag is True will appears, other won't.

.. sourcecode:: python

   # Adds all subjects of the entry_of relation in the add menu of the ``Blog``
   # primary view
   uicfg.actionbox_appearsin_addmenu.tag_object_of(('*', 'entry_of', 'Blog'), True)
"""

from itertools import repeat

from cubicweb import neg_role
from cubicweb.rtags import (RelationTags, RelationTagsBool, RelationTagsSet,
                            RelationTagsDict, NoTargetRelationTagsDict,
                            rtags_chain, _ensure_str_key)
from cubicweb.schema import META_RTYPES, INTERNAL_TYPES, WORKFLOW_TYPES


# primary view configuration ##################################################

class PrimaryViewSectionRelationTags(RelationTags):
    """primary view section configuration"""
    __regid__ = 'primaryview_section'

    _allowed_values = frozenset(('attributes', 'relations',
                                 'sideboxes', 'hidden'))

    def _init(self, sschema, rschema, oschema, role):
        if self.get(sschema, rschema, oschema, role) is None:
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
            self.tag_relation((sschema, rschema, oschema, role), section)


primaryview_section = PrimaryViewSectionRelationTags(__module__=__name__)


class DisplayCtrlRelationTags(NoTargetRelationTagsDict):
    """primary view display controller configuration"""
    __regid__ = 'primaryview_display_ctrl'

    def __init__(self, *args, **kwargs):
        super(DisplayCtrlRelationTags, self).__init__(*args, **kwargs)
        self.counter = 0

    def _init(self, sschema, rschema, oschema, role):
        if role == 'subject':
            oschema = '*'
        else:
            sschema = '*'
        self.counter += 1
        self.setdefault((sschema, rschema, oschema, role),
                        'order',
                        self.counter)

    def set_fields_order(self, etype, relations):
        """specify the field order in `etype` primary view.

        :param etype: the entity type as a string
        :param attrs: the ordered list of attribute names (or relations)

        `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_rel)

        Unspecified fields will be displayed after specified ones, their
        order being consistent with the schema definition.

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import primaryview_display_ctrl as pvdc
          pvdc.set_fields_order('CWUser', ('firstname', ('in_group', 'subject'),
                                           'surname', 'login'))

        """
        for index, relation in enumerate(relations):
            if not isinstance(relation, tuple):
                relation = (relation, 'subject')
            rtype, role = relation
            if role == 'subject':
                self.tag_subject_of((etype, rtype, '*'), {'order': index})
            else:
                self.tag_object_of(('*', rtype, etype), {'order': index})


primaryview_display_ctrl = DisplayCtrlRelationTags(__module__=__name__)


# index view configuration ####################################################
# entity type section in the index/manage page. May be one of
# * 'application'
# * 'system'
# * 'schema'
# * 'hidden'
# * 'subobject' (not displayed by default)

class InitializableDict(dict):  # XXX not a rtag. Turn into an appobject?
    def __init__(self, *args, **kwargs):
        super(InitializableDict, self).__init__(*args, **kwargs)
        self.__defaults = dict(self)

    def init(self, schema, check=True):
        self.update(self.__defaults)
        for eschema in schema.entities():
            if eschema.final:
                continue
            if eschema.schema_entity():
                self.setdefault(eschema, 'schema')
            elif eschema in INTERNAL_TYPES or eschema in WORKFLOW_TYPES:
                self.setdefault(eschema, 'system')
            elif eschema.is_subobject(strict=True):
                self.setdefault(eschema, 'subobject')
            else:
                self.setdefault(eschema, 'application')


indexview_etype_section = InitializableDict(
    EmailAddress='subobject',
    Bookmark='system',
    # entity types in the 'system' table by default (managers only)
    CWUser='system', CWGroup='system',
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
    """autoform relations'section

    Notice that unlike other rtags where wildcard handling is done when
    retrieving some value, all values are expanded here during initialization
    step.

    For derived rtags, values specified for the 'main' form type are propagated
    to the 'inlined' form type if unspecified. Others are fetched back from the
    parent.
    """
    __regid__ = 'autoform_section'

    _allowed_form_types = ('main', 'inlined', 'muledit')
    _allowed_values = {'main': ('attributes', 'inlined', 'relations',
                                'metadata', 'hidden'),
                       'inlined': ('attributes', 'inlined', 'hidden'),
                       'muledit': ('attributes', 'hidden'),
                       }

    def init(self, schema, check=True):
        super(AutoformSectionRelationTags, self).init(schema, check)
        if self._parent is None:
            self.apply(schema, self._initfunc_step2)
        else:
            # we still need to expand wildcard in defined keys
            for key in list(self._tagdefs):
                stype, rtype, otype, role = key
                rschema = schema.rschema(rtype)
                if stype == '*' and otype == '*':
                    concrete_rdefs = rschema.rdefs.keys()
                elif stype == '*':
                    concrete_rdefs = zip(rschema.subjects(otype), repeat(otype))
                elif otype == '*':
                    concrete_rdefs = zip(repeat(stype), rschema.objects(stype))
                else:
                    concrete_rdefs = [(stype, otype)]
                for sschema, oschema in concrete_rdefs:
                    self._init(sschema, rschema, oschema, role)
                    # also, we have to copy values from 'main' to 'inlined' and
                    # for other undefined sections from the parent's rtag
                    formsections = self.get(sschema, rschema, oschema, role)
                    sectdict = _formsections_as_dict(formsections)
                    parent_formsections = self._parent.get(sschema, rschema, oschema, role)
                    parent_sectdict = _formsections_as_dict(parent_formsections)
                    for formtype, section in parent_sectdict.items():
                        if formtype not in sectdict:
                            if formtype == 'inlined':
                                section = sectdict.get('main', section)
                            formsections.add('%s_%s' % (formtype, section))

    def _init(self, sschema, rschema, oschema, role):
        formsections = self.init_get(sschema, rschema, oschema, role)
        if formsections is None:
            formsections = self.tag_container_cls()
        key = _ensure_str_key((sschema, rschema, oschema, role))
        self._tagdefs[key] = formsections

    def _initfunc_step2(self, sschema, rschema, oschema, role):
        formsections = self.get(sschema, rschema, oschema, role)
        sectdict = _formsections_as_dict(formsections)
        if rschema in META_RTYPES:
            sectdict.setdefault('main', 'hidden')
            sectdict.setdefault('muledit', 'hidden')
            sectdict.setdefault('inlined', 'hidden')
        elif role == 'subject' and rschema in sschema.meta_attributes():
            # meta attribute, usually embeded by the described attribute's field
            # (eg RichTextField, FileField...)
            sectdict.setdefault('main', 'hidden')
            sectdict.setdefault('muledit', 'hidden')
            sectdict.setdefault('inlined', 'hidden')
        # ensure we have a tag for each form type
        if 'main' not in sectdict:
            if sschema.is_metadata(rschema):
                sectdict['main'] = 'metadata'
            else:
                card, composed = _card_and_comp(sschema, rschema, oschema, role)
                if card in '1+':
                    sectdict['main'] = 'attributes'
                    if 'muledit' not in sectdict:
                        sectdict['muledit'] = 'attributes'
                elif rschema.final:
                    sectdict['main'] = 'attributes'
                else:
                    sectdict['main'] = 'relations'
        if 'muledit' not in sectdict:
            sectdict['muledit'] = 'hidden'
            if sectdict['main'] == 'attributes':
                card, composed = _card_and_comp(sschema, rschema, oschema, role)
                if card in '1+' and not composed:
                    sectdict['muledit'] = 'attributes'
        if 'inlined' not in sectdict:
            sectdict['inlined'] = sectdict['main']
        # recompute formsections and set it to avoid recomputing
        for formtype, section in sectdict.items():
            formsections.add('%s_%s' % (formtype, section))

    def tag_relation(self, key, formtype, section):
        if isinstance(formtype, tuple):
            for ftype in formtype:
                self.tag_relation(key, ftype, section)
            return
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

    def init_get(self, stype, rtype, otype, tagged):
        key = (stype, rtype, otype, tagged)
        rtags = {}
        for key in self._get_keys(stype, rtype, otype, tagged):
            tags = self._tagdefs.get(key, ())
            for tag in tags:
                assert '_' in tag, (tag, tags)
                section, value = tag.split('_', 1)
                rtags[section] = value
        cls = self.tag_container_cls
        rtags = cls('_'.join([section, value])
                    for section, value in rtags.items())
        return rtags

    def get(self, *key):
        # overriden to avoid recomputing done in parent classes
        for rtag in rtags_chain(self):
            try:
                return rtag._tagdefs[key]
            except KeyError:
                continue
        return ()

    def relations_by_section(self, entity, formtype, section, permission,
                             strict=False):
        """return a list of (relation schema, target schemas, role) for the
        given entity matching categories and permission.

        `strict`:
          bool telling if having local role is enough (strict = False) or not
        """
        tag = '%s_%s' % (formtype, section)
        eschema = entity.e_schema
        cw = entity._cw
        permsoverrides = cw.vreg['uicfg'].select('autoform_permissions_overrides', cw,
                                                 entity=entity)
        if entity.has_eid():
            eid = entity.eid
        else:
            eid = None
            strict = False
        if permission == 'update':
            assert section in ('attributes', 'metadata', 'hidden')
            relpermission = 'add'
        else:
            assert section not in ('metadata', 'hidden')
            relpermission = permission
        for rschema, targetschemas, role in eschema.relation_definitions(True):
            _targetschemas = []
            for tschema in targetschemas:
                # check section's tag first, potentially lower cost than
                # checking permission which may imply rql queries
                if tag not in self.etype_get(eschema, rschema, role, tschema):
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
            if eid is None and '%s_on_new' % permission in permsoverrides.etype_get(
                    eschema, rschema, role):
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

    def hide_field(self, etype, attr, desttype='*', formtype='main'):
        """hide `attr` in `etype` forms.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation to hide
        :param formtype: which form will be affected ('main', 'inlined', etc.),
         *main* by default.

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_rel)

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_section as afs
          afs.hide_field('CWUser', 'login')
          afs.hide_field('*', 'name')
          afs.hide_field('CWUser', 'use_email', formtype='inlined')

        """
        self._tag_etype_attr(etype, attr, desttype,
                             formtype=formtype, section='hidden')

    def hide_fields(self, etype, attrs, formtype='main'):
        """simple for-loop wrapper around :func:`hide_field`.

        :param etype: the entity type as a string
        :param attrs: the ordered list of attribute names (or relations)
        :param formtype: which form will be affected ('main', 'inlined', etc.),
         *main* by default.

        `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_rel)

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_section as afs
          afs.hide_fields('CWUser', ('login', ('use_email', 'subject')),
                          formtype='inlined')
        """
        for attr in attrs:
            self.hide_field(etype, attr, formtype=formtype)

    def edit_inline(self, etype, attr, desttype='*', formtype=('main', 'inlined')):
        """edit `attr` with and inlined form.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation
        :param desttype: the destination type(s) concerned, default is everything
        :param formtype: which form will be affected ('main', 'inlined', etc.),
          *main* and *inlined* by default.

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_section as afs

          afs.edit_inline('*', 'use_email')
      """
        self._tag_etype_attr(etype, attr, desttype, formtype=formtype,
                             section='inlined')

    def edit_as_attr(self, etype, attr, desttype='*', formtype=('main', 'muledit')):
        """make `attr` appear in the *attributes* section of `etype` form.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation
        :param desttype: the destination type(s) concerned, default is everything
        :param formtype: which form will be affected ('main', 'inlined', etc.),
          *main* and *muledit* by default.

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_section as afs

          afs.edit_as_attr('CWUser', 'in_group')
        """
        self._tag_etype_attr(etype, attr, desttype,
                             formtype=formtype, section='attributes')

    def set_muledit_editable(self, etype, attrs):
        """make `attrs` appear in muledit form of `etype`.

        :param etype: the entity type as a string
        :param attrs: the ordered list of attribute names (or relations)

        `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_relation)

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_section as afs

          afs.set_muledit_editable('CWUser', ('firstname', 'surname', 'in_group'))
        """
        for attr in attrs:
            self.edit_as_attr(etype, attr, formtype='muledit')


autoform_section = AutoformSectionRelationTags(__module__=__name__)


# relations'field class

class AutoformFieldTags(RelationTags):
    __regid__ = 'autoform_field'

    def set_field(self, etype, attr, field):
        """sets the `attr` field of `etype`.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

        """
        self._tag_etype_attr(etype, attr, '*', field)


autoform_field = AutoformFieldTags(__module__=__name__)


# relations'field explicit kwargs (given to field's __init__)

class AutoformFieldKwargsTags(RelationTagsDict):
    __regid__ = 'autoform_field_kwargs'

    def set_fields_order(self, etype, attrs):
        """specify the field order in `etype` main edition form.

        :param etype: the entity type as a string
        :param attrs: the ordered list of attribute names (or relations)

        `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_rel)

        Unspecified fields will be displayed after specified ones, their
        order being consistent with the schema definition.

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_field_kwargs as affk
          affk.set_fields_order('CWUser', ('firstname', 'surname', 'login'))
          affk.set_fields_order('CWUser', ('firstname', ('in_group', 'subject'),
                                'surname', 'login'))

        """
        for index, attr in enumerate(attrs):
            self._tag_etype_attr(etype, attr, '*', {'order': index})

    def set_field_kwargs(self, etype, attr, **kwargs):
        """tag `attr` field of `etype` with additional named paremeters.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

        Examples:

        .. sourcecode:: python

          from cubicweb.web.views.uicfg import autoform_field_kwargs as affk
          affk.set_field_kwargs('Person', 'works_for', widget=fwdgs.AutoCompletionWidget())
          affk.set_field_kwargs('CWUser', 'login', label=_('login or email address'),
                                widget=fwdgs.TextInput(attrs={'size': 30}))
        """
        self._tag_etype_attr(etype, attr, '*', kwargs)


autoform_field_kwargs = AutoformFieldKwargsTags(__module__=__name__)


# set of tags of the form <action>_on_new on relations. <action> is a
# schema action (add/update/delete/read), and when such a tag is found
# permissions checking is by-passed and supposed to be ok
class AutoFormPermissionsOverrides(RelationTagsSet):
    __regid__ = 'autoform_permissions_overrides'


autoform_permissions_overrides = AutoFormPermissionsOverrides(__module__=__name__)


class ReleditTags(NoTargetRelationTagsDict):
    """Associate to relation a dictionary to control `reledit` (e.g. edition of
    attributes / relations from within views).

    Possible keys and associated values are:

    * `novalue_label`, alternative default value (shown when there is no value).

    * `novalue_include_rtype`, when `novalue_label` is not specified, this boolean
      flag control wether the generated default value should contains the
      relation label or not. Will be the opposite of the `showlabel` value found
      in the `primaryview_display_ctrl` rtag by default.

    * `reload`, boolean, eid (to reload to) or function taking subject and
      returning bool/eid. This is useful when editing a relation (or attribute)
      that impacts the url or another parts of the current displayed
      page. Defaults to False.

    * `rvid`, alternative view id (as str) for relation or composite edition.
      Default is 'autolimited'.

    * `edit_target`, may be either 'rtype' (to edit the relation) or 'related'
      (to edit the related entity).  This controls whether to edit the relation
      or the target entity of the relation.  Currently only one-to-one relations
      support target entity edition. By default, the 'related' option is taken
      whenever the relation is composite.
    """
    __regid__ = 'reledit'
    _keys = frozenset('novalue_label novalue_include_rtype reload rvid edit_target'.split())

    def tag_relation(self, key, tag):
        for tagkey in tag:
            assert tagkey in self._keys, 'tag %r not in accepted tags: %r' % (tag, self._keys)
        return super(ReleditTags, self).tag_relation(key, tag)

    def _init(self, sschema, rschema, oschema, role):
        values = self.get(sschema, rschema, oschema, role)
        if not rschema.final:
            composite = rschema.rdef(sschema, oschema).composite == role
            if role == 'subject':
                oschema = '*'
            else:
                sschema = '*'
            edittarget = values.get('edit_target')
            if edittarget not in (None, 'rtype', 'related'):
                self.warning('reledit: wrong value for edit_target on relation %s: %s',
                             rschema, edittarget)
                edittarget = None
            if not edittarget:
                edittarget = 'related' if composite else 'rtype'
                self.tag_relation((sschema, rschema, oschema, role),
                                  {'edit_target': edittarget})
        if 'novalue_include_rtype' not in values:
            showlabel = primaryview_display_ctrl.get(
                sschema, rschema, oschema, role).get('showlabel', True)
            self.tag_relation((sschema, rschema, oschema, role),
                              {'novalue_include_rtype': not showlabel})


reledit_ctrl = ReleditTags(__module__=__name__)


# boxes.EditBox configuration #################################################

# 'link' / 'create' relation tags, used to control the "add entity" submenu

class ActionBoxUicfg(RelationTagsBool):
    __regid__ = 'actionbox_appearsin_addmenu'

    def _init(self, sschema, rschema, oschema, role):
        if self.get(sschema, rschema, oschema, role) is None:
            if rschema in META_RTYPES:
                self.tag_relation((sschema, rschema, oschema, role), False)
                return
            rdef = rschema.rdef(sschema, oschema)
            if not rdef.role_cardinality(role) in '?1' and rdef.composite == role:
                self.tag_relation((sschema, rschema, oschema, role), True)

    def _tag_etype_attr(self, etype, attr, desttype='*', *args, **kwargs):
        if isinstance(attr, str):
            attr, role = attr, 'subject'
        else:
            attr, role = attr
        if role == 'subject':
            self.tag_subject_of((etype, attr, desttype), *args, **kwargs)
        else:
            self.tag_object_of((desttype, attr, etype), *args, **kwargs)

    def append_to_addmenu(self, etype, attr, createdtype='*'):
        """adds `attr` in the actions box *addrelated* submenu of `etype`.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation to hide
        :param createdtype: the target type of the relation
                            (optional, defaults to '*' (all possible types))

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

        """
        self._tag_etype_attr(etype, attr, createdtype, True)

    def remove_from_addmenu(self, etype, attr, createdtype='*'):
        """removes `attr` from the actions box *addrelated* submenu of `etype`.

        :param etype: the entity type as a string
        :param attr: the name of the attribute or relation to hide
        :param createdtype: the target type of the relation
                            (optional, defaults to '*' (all possible types))

        `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)
        """
        self._tag_etype_attr(etype, attr, createdtype, False)


actionbox_appearsin_addmenu = ActionBoxUicfg(__module__=__name__)


def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__)
    indexview_etype_section.init(vreg.schema)
