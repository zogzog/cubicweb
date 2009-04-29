"""schema driven ui configuration.

set of properties configuring edition, actions box, ... rendering using tags
on schema relations. Those properties are defined here so we don't get module
reloading problems.

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.rtags import RelationTags, RelationTagsSet

# primary view configuration ##################################################

# how to display a relation in primary view.
# values a dict with the following keys:
#
# 'where', whose value may be one of:
#  * 'attributes', display in the attributes section
#  * 'relations', display in the relations section (below attributes)
#  * 'sideboxes', display in the side boxes (beside attributes)
# if this key is missing, the relation won't be displayed at all.
#
# 'vid' is an optional view identifier
#
# 'label' is an optional label
#
# 'limit' is a boolean telling if the results should be limited according to
#  the configuration
class RDisplayRelationTags(RelationTags):
    def __init__(self):
        super(RDisplayRelationTags, self).__init__()
        self._counter = 0

    def tag_relation(self, values, *args, **kwargs):
        super(RDisplayRelationTags, self).tag_relation(values, *args, **kwargs)
        if values:
            values['order'] = self.get_timestamp()

    def get_timestamp(self):
        self._counter += 1
        return self._counter

rdisplay = RDisplayRelationTags()
for rtype in ('eid', 'creation_date', 'modification_date',
              'is', 'is_instance_of', 'identity',
              'owned_by', 'created_by',
              'in_state', 'wf_info_for', 'require_permission',
              'from_entity', 'to_entity',
              'see_also'):
    rdisplay.tag_relation({}, ('*', rtype, '*'), 'subject')
    rdisplay.tag_relation({}, ('*', rtype, '*'), 'object')


# autoform.AutomaticEntityForm configuration ##################################

# relations'category (eg primary/secondary/generic/metadata/generated)
rcategories = RelationTags()
# use primary and not generated for eid since it has to be an hidden
rcategories.tag_relation('primary', ('*', 'eid', '*'), 'subject')
rcategories.tag_relation('primary', ('*', 'in_state', '*'), 'subject')
rcategories.tag_relation('secondary', ('*', 'description', '*'), 'subject')
rcategories.tag_relation('metadata', ('*', 'creation_date', '*'), 'subject')
rcategories.tag_relation('metadata', ('*', 'modification_date', '*'), 'subject')
rcategories.tag_relation('metadata', ('*', 'owned_by', '*'), 'subject')
rcategories.tag_relation('metadata', ('*', 'created_by', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'has_text', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'is', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'is', '*'), 'object')
rcategories.tag_relation('generated', ('*', 'is_instance_of', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'is_instance_of', '*'), 'object')
rcategories.tag_relation('generated', ('*', 'identity', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'identity', '*'), 'object')
rcategories.tag_relation('generated', ('*', 'require_permission', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'wf_info_for', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'wf_info_for', '*'), 'object')
rcategories.tag_relation('generated', ('*', 'for_user', '*'), 'subject')
rcategories.tag_relation('generated', ('*', 'for_user', '*'), 'object')

# relations'field class
rfields = RelationTags()

# relations'widget class
rwidgets = RelationTags()

# inlined view flag for non final relations: when True for an entry, the
# entity(ies) at the other end of the relation will be editable from the
# form of the edited entity
rinlined = RelationTags()

# set of tags of the form <action>_on_new on relations. <action> is a
# schema action (add/update/delete/read), and when such a tag is found
# permissions checking is by-passed and supposed to be ok
rpermissions_overrides = RelationTagsSet()


# boxes.EditBox configuration #################################################

# 'link' / 'create' relation tags, used to control the "add entity" submenu
rmode = RelationTags()
rmode.tag_relation('link', ('*', 'is', '*'), 'subject')
rmode.tag_relation('link', ('*', 'is', '*'), 'object')
rmode.tag_relation('link', ('*', 'is_instance_of', '*'), 'subject')
rmode.tag_relation('link', ('*', 'is_instance_of', '*'), 'object')
rmode.tag_relation('link', ('*', 'identity', '*'), 'subject')
rmode.tag_relation('link', ('*', 'identity', '*'), 'object')
rmode.tag_relation('link', ('*', 'owned_by', '*'), 'subject')
rmode.tag_relation('link', ('*', 'created_by', '*'), 'subject')
rmode.tag_relation('link', ('*', 'require_permission', '*'), 'subject')
rmode.tag_relation('link', ('*', 'wf_info_for', '*'), 'subject')
rmode.tag_relation('link', ('*', 'wf_info_for', '*'), 'object')
