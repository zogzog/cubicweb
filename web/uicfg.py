# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""This module (``cubicweb.web.uicfg``) regroups a set of structures that may be
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

    from cubicweb.web import uicfg
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
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.compat import any

from cubicweb import neg_role
from cubicweb.rtags import (RelationTags, RelationTagsBool, RelationTagsSet,
                            RelationTagsDict, NoTargetRelationTagsDict,
                            register_rtag, _ensure_str_key)
from cubicweb.schema import META_RTYPES, INTERNAL_TYPES, WORKFLOW_TYPES


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


class DisplayCtrlRelationTags(NoTargetRelationTagsDict):
    def __init__(self, *args, **kwargs):
        super(DisplayCtrlRelationTags, self).__init__(*args, **kwargs)
        self.counter = 0

def init_primaryview_display_ctrl(rtag, sschema, rschema, oschema, role):
    if role == 'subject':
        oschema = '*'
    else:
        sschema = '*'
    rtag.counter += 1
    rtag.setdefault((sschema, rschema, oschema, role), 'order', rtag.counter)

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
        elif role == 'subject' and rschema in sschema.meta_attributes():
            # meta attribute, usually embeded by the described attribute's field
            # (eg RichTextField, FileField...)
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
        rtags = cls('_'.join([section,value]) for section,value in rtags.iteritems())
        return rtags


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
autoform_field_kwargs = RelationTagsDict('autoform_field_kwargs')


# set of tags of the form <action>_on_new on relations. <action> is a
# schema action (add/update/delete/read), and when such a tag is found
# permissions checking is by-passed and supposed to be ok
autoform_permissions_overrides = RelationTagsSet('autoform_permissions_overrides')

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
    _keys = frozenset('novalue_label novalue_include_rtype reload rvid edit_target'.split())

    def tag_relation(self, key, tag):
        for tagkey in tag.iterkeys():
            assert tagkey in self._keys, 'tag %r not in accepted tags: %r' % (tag, self._keys)
        return super(ReleditTags, self).tag_relation(key, tag)

def init_reledit_ctrl(rtag, sschema, rschema, oschema, role):
    values = rtag.get(sschema, rschema, oschema, role)
    if not rschema.final:
        composite = rschema.rdef(sschema, oschema).composite == role
        if role == 'subject':
            oschema = '*'
        else:
            sschema = '*'
        edittarget = values.get('edit_target')
        if edittarget not in (None, 'rtype', 'related'):
            rtag.warning('reledit: wrong value for edit_target on relation %s: %s',
                         rschema, edittarget)
            edittarget = None
        if not edittarget:
            edittarget = 'related' if composite else 'rtype'
            rtag.tag_relation((sschema, rschema, oschema, role),
                              {'edit_target': edittarget})
    if not 'novalue_include_rtype' in values:
        showlabel = primaryview_display_ctrl.get(
            sschema, rschema, oschema, role).get('showlabel', True)
        rtag.tag_relation((sschema, rschema, oschema, role),
                          {'novalue_include_rtype': not showlabel})

reledit_ctrl = ReleditTags('reledit', init_reledit_ctrl)

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
