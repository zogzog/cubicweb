# :organization: Logilab
# :copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""This module regroups a set of structures that may be used to configure
various places of the generated web interface.

Primary view configuration
``````````````````````````
:primaryview_section:
   where to display a relation in primary view. Value may be one of:
   * 'attributes', display in the attributes section
   * 'relations', display in the relations section (below attributes)
   * 'sideboxes', display in the side boxes (beside attributes)
   * 'hidden', don't display

:primaryview_display_ctrl:

   how to display a relation in primary view. Values are dict with some of the
   following keys:

   :vid:
      identifier of a view to use to display the result set. Defaults depends on
      the section:
      * 'attributes' section: 'reledit' view
      * 'relations' section: 'autolimited' view
      * 'sideboxes' section: 'sidebox' view

   :label:
     label for the relations section or side box

   :limit:
      boolean telling if the results should be limited according to the
      configuration

   :filter:
      callback taking the related result set as argument and returning it
      filtered

   :order:
      int used to control order within a section. When not specified,
      automatically set according to order in which tags are added.

   Notice those values are only considered if the relation is in a displayed
   section (controlled by :attr:`primaryview_section`)


Index view configuration
````````````````````````
:indexview_etype_section:
   entity type category in the index/manage page. May be one of
   * 'application'
   * 'system'
   * 'schema'
   * 'subobject' (not displayed by default)


Actions box configuration
`````````````````````````
:actionbox_appearsin_addmenu:
  simple boolean relation tags used to control the "add entity" submenu.
  Relations whose rtag is True will appears, other won't.

Automatic form configuration
````````````````````````````

"""
__docformat__ = "restructuredtext en"

from cubicweb.rtags import RelationTags, RelationTagsBool, RelationTagsSet
from cubicweb.web import formwidgets

# primary view configuration ##################################################

def dual_role(role):
    return role == 'subject' and 'object' or 'subject'

def card_from_role(card, role):
    if role == 'subject':
        return card[0]
    assert role in ('object', 'sobject'), repr(role)
    return card[1]

def init_primaryview_section(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        card = card_from_role(rschema.rproperty(sschema, oschema, 'cardinality'), role)
        composed = rschema.rproperty(sschema, oschema, 'composite') == dual_role(role)
        if rschema.is_final():
            if rschema.meta or oschema.type in ('Password', 'Bytes'):
                section = 'hidden'
            else:
                section = 'attributes'
        elif card in '1+':
            section = 'attributes'
        elif composed:
            section = 'relations'
        else:
            section = 'sideboxes'
        rtag.tag_relation((sschema, rschema, oschema, role), section)

primaryview_section = RelationTags('primaryview_section',
                                   init_primaryview_section,
                                   frozenset(('attributes', 'relations',
                                               'sideboxes', 'hidden')))
for rtype in ('eid', 'creation_date', 'modification_date',
              'is', 'is_instance_of', 'identity',
              'owned_by', 'created_by',
              'in_state', 'wf_info_for', 'require_permission',
              'from_entity', 'to_entity',
              'see_also'):
    primaryview_section.tag_subject_of(('*', rtype, '*'), 'hidden')
    primaryview_section.tag_object_of(('*', rtype, '*'), 'hidden')
primaryview_section.tag_subject_of(('*', 'use_email', '*'), 'attributes')
primaryview_section.tag_subject_of(('*', 'primary_email', '*'), 'hidden')

for attr in ('name', 'meta', 'final'):
    primaryview_section.tag_attribute(('CWEType', attr), 'hidden')
for attr in ('name', 'meta', 'final', 'symetric', 'inlined'):
    primaryview_section.tag_attribute(('CWRType', attr), 'hidden')


class DisplayCtrlRelationTags(RelationTags):
    def __init__(self, *args, **kwargs):
        super(DisplayCtrlRelationTags, self).__init__(*args, **kwargs)
        self._counter = 0

    def tag_relation(self, key, tag):
        assert isinstance(tag, dict)
        super(DisplayCtrlRelationTags, self).tag_relation(key, tag)
        self._counter += 1
        tag.setdefault('order', self._counter)


def init_primaryview_display_ctrl(rtag, sschema, rschema, oschema, role):
    if role == 'subject':
        oschema = '*'
        label = rschema.type
    else:
        sschema = '*'
        label = '%s_%s' % (rschema, role)
    displayinfo = rtag.get(sschema, rschema, oschema, role)
    if displayinfo is None:
        displayinfo = {}
        rtag.tag_relation((sschema, rschema, oschema, role), displayinfo)
    displayinfo.setdefault('label', label)

primaryview_display_ctrl = DisplayCtrlRelationTags('primaryview_display_ctrl',
                                                   init_primaryview_display_ctrl)


# index view configuration ####################################################
# entity type section in the index/manage page. May be one of
# * 'application'
# * 'system'
# * 'schema'
# * 'subobject' (not displayed by default)

indexview_etype_section = {'EmailAddress': 'subobject'}


# autoform.AutomaticEntityForm configuration ##################################

# relations'section (eg primary/secondary/generic/metadata/generated)

def init_autoform_section(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        if role == 'subject':
            card = rschema.rproperty(sschema, oschema, 'cardinality')[0]
            composed = rschema.rproperty(sschema, oschema, 'composite') == 'object'
        else:
            card = rschema.rproperty(sschema, oschema, 'cardinality')[1]
            composed = rschema.rproperty(sschema, oschema, 'composite') == 'subject'
        if sschema.is_metadata(rschema):
            section = 'generated'
        elif card in '1+':
            if not rschema.is_final() and composed:
                section = 'generated'
            else:
                section = 'primary'
        elif rschema.is_final():
            section = 'secondary'
        else:
            section = 'generic'
        rtag.tag_relation((sschema, rschema, oschema, role), section)

autoform_section = RelationTags('autoform_section', init_autoform_section,
                                set(('primary', 'secondary', 'generic',
                                     'metadata', 'generated')))
# use primary and not generated for eid since it has to be an hidden
autoform_section.tag_attribute(('*', 'eid'), 'primary')
autoform_section.tag_attribute(('*', 'description'), 'secondary')
autoform_section.tag_attribute(('*', 'creation_date'), 'metadata')
autoform_section.tag_attribute(('*', 'modification_date'), 'metadata')
autoform_section.tag_attribute(('*', 'has_text'), 'generated')
autoform_section.tag_subject_of(('*', 'in_state', '*'), 'primary')
autoform_section.tag_subject_of(('*', 'owned_by', '*'), 'metadata')
autoform_section.tag_subject_of(('*', 'created_by', '*'), 'metadata')
autoform_section.tag_subject_of(('*', 'is', '*'), 'generated')
autoform_section.tag_object_of(('*', 'is', '*'), 'generated')
autoform_section.tag_subject_of(('*', 'is_instance_of', '*'), 'generated')
autoform_section.tag_object_of(('*', 'is_instance_of', '*'), 'generated')
autoform_section.tag_subject_of(('*', 'identity', '*'), 'generated')
autoform_section.tag_object_of(('*', 'identity', '*'), 'generated')
autoform_section.tag_subject_of(('*', 'require_permission', '*'), 'generated')
autoform_section.tag_subject_of(('*', 'wf_info_for', '*'), 'generated')
autoform_section.tag_object_of(('*', 'wf_info_for', '*'), 'generated')
autoform_section.tag_subject_of(('*', 'for_user', '*'), 'generated')
autoform_section.tag_object_of(('*', 'for_user', '*'), 'generated')
autoform_section.tag_subject_of(('CWPermission', 'require_group', '*'), 'primary')
autoform_section.tag_attribute(('CWEType', 'final'), 'generated')
autoform_section.tag_attribute(('CWRType', 'final'), 'generated')
autoform_section.tag_attribute(('CWUser', 'firstname'), 'secondary')
autoform_section.tag_attribute(('CWUser', 'surname'), 'secondary')
autoform_section.tag_attribute(('CWUser', 'last_login_time'), 'metadata')
autoform_section.tag_subject_of(('CWUser', 'in_group', '*'), 'primary')
autoform_section.tag_object_of(('*', 'owned_by', 'CWUser'), 'generated')
autoform_section.tag_object_of(('*', 'created_by', 'CWUser'), 'generated')
autoform_section.tag_object_of(('*', 'bookmarked_by', 'CWUser'), 'metadata')
autoform_section.tag_attribute(('Bookmark', 'path'), 'primary')
autoform_section.tag_subject_of(('*', 'use_email', '*'), 'generated') # inlined actually
autoform_section.tag_subject_of(('*', 'primary_email', '*'), 'generic')


# relations'field class
autoform_field = RelationTags('autoform_field')

# relations'field explicit kwargs (given to field's __init__)
autoform_field_kwargs = RelationTags()
autoform_field_kwargs.tag_attribute(('RQLExpression', 'expression'),
                                    {'widget': formwidgets.TextInput})
autoform_field_kwargs.tag_attribute(('Bookmark', 'path'),
                                    {'widget': formwidgets.TextInput})



# inlined view flag for non final relations: when True for an entry, the
# entity(ies) at the other end of the relation will be editable from the
# form of the edited entity
autoform_is_inlined = RelationTagsBool('autoform_is_inlined')
autoform_is_inlined.tag_subject_of(('*', 'use_email', '*'), True)
autoform_is_inlined.tag_subject_of(('CWRelation', 'relation_type', '*'), True)
autoform_is_inlined.tag_subject_of(('CWRelation', 'from_entity', '*'), True)
autoform_is_inlined.tag_subject_of(('CWRelation', 'to_entity', '*'), True)


# set of tags of the form <action>_on_new on relations. <action> is a
# schema action (add/update/delete/read), and when such a tag is found
# permissions checking is by-passed and supposed to be ok
autoform_permissions_overrides = RelationTagsSet('autoform_permissions_overrides')


# boxes.EditBox configuration #################################################

# 'link' / 'create' relation tags, used to control the "add entity" submenu
def init_actionbox_appearsin_addmenu(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        card = rschema.rproperty(sschema, oschema, 'cardinality')[role == 'object']
        if not card in '?1' and \
               rschema.rproperty(sschema, oschema, 'composite') == role:
            rtag.tag_relation((sschema, rschema, oschema, role), True)

actionbox_appearsin_addmenu = RelationTagsBool('actionbox_appearsin_addmenu',
                                               init_actionbox_appearsin_addmenu)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'is', '*'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'is', '*'), False)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'is_instance_of', '*'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'is_instance_of', '*'), False)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'identity', '*'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'identity', '*'), False)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'owned_by', '*'), False)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'created_by', '*'), False)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'require_permission', '*'), False)
actionbox_appearsin_addmenu.tag_subject_of(('*', 'wf_info_for', '*'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'wf_info_for', '*'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'state_of', 'CWEType'), True)
actionbox_appearsin_addmenu.tag_object_of(('*', 'transition_of', 'CWEType'), True)
actionbox_appearsin_addmenu.tag_object_of(('*', 'relation_type', 'CWRType'), True)
actionbox_appearsin_addmenu.tag_object_of(('*', 'from_entity', 'CWEType'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'to_entity', 'CWEType'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'in_group', 'CWGroup'), True)
actionbox_appearsin_addmenu.tag_object_of(('*', 'owned_by', 'CWUser'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'created_by', 'CWUser'), False)
actionbox_appearsin_addmenu.tag_object_of(('*', 'bookmarked_by', 'CWUser'), True)
actionbox_appearsin_addmenu.tag_subject_of(('Transition', 'destination_state', '*'), True)
actionbox_appearsin_addmenu.tag_object_of(('*', 'allowed_transition', 'Transition'), True)
actionbox_appearsin_addmenu.tag_object_of(('*', 'destination_state', 'State'), True)
actionbox_appearsin_addmenu.tag_subject_of(('State', 'allowed_transition', '*'), True)

