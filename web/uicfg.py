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

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import neg_role
from cubicweb.rtags import (RelationTags, RelationTagsBool,
                            RelationTagsSet, RelationTagsDict)
from cubicweb.web import formwidgets


def card_from_role(card, role):
    if role == 'subject':
        return card[0]
    assert role in ('object', 'sobject'), repr(role)
    return card[1]

# primary view configuration ##################################################

def init_primaryview_section(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        card = card_from_role(rschema.rproperty(sschema, oschema, 'cardinality'), role)
        composed = rschema.rproperty(sschema, oschema, 'composite') == neg_role(role)
        if rschema.is_final():
            if rschema.meta or sschema.is_metadata(rschema) \
                    or oschema.type in ('Password', 'Bytes'):
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

indexview_etype_section = {'EmailAddress': 'subobject',
                           'CWUser': 'system',
                           'CWGroup': 'system',
                           'CWPermission': 'system',
                           'CWCache': 'system',
                           'BaseTransition': 'hidden',
                           }


# autoform.AutomaticEntityForm configuration ##################################

# relations'section (eg primary/secondary/generic/metadata/generated)

def init_autoform_section(rtag, sschema, rschema, oschema, role):
    if rtag.get(sschema, rschema, oschema, role) is None:
        if autoform_is_inlined.get(sschema, rschema, oschema, role) or \
               autoform_is_inlined.get(sschema, rschema, oschema, neg_role(role)):
            section = 'generated'
        elif sschema.is_metadata(rschema):
            section = 'metadata'
        else:
            if role == 'subject':
                card = rschema.rproperty(sschema, oschema, 'cardinality')[0]
                composed = rschema.rproperty(sschema, oschema, 'composite') == 'object'
            else:
                card = rschema.rproperty(sschema, oschema, 'cardinality')[1]
                composed = rschema.rproperty(sschema, oschema, 'composite') == 'subject'
            if card in '1+':
                if not rschema.is_final() and composed:
                    # XXX why? probably because we want it unlined, though this
                    # is not the case by default
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

# relations'field class
autoform_field = RelationTags('autoform_field')

# relations'field explicit kwargs (given to field's __init__)
autoform_field_kwargs = RelationTagsDict()

# inlined view flag for non final relations: when True for an entry, the
# entity(ies) at the other end of the relation will be editable from the
# form of the edited entity
autoform_is_inlined = RelationTagsBool('autoform_is_inlined')


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
