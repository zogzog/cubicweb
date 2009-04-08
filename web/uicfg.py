"""schema driven ui configuration.

set of properties configuring edition, actions box, ... rendering using tags
on schema relations. Those properties are defined here so we don't get module
reloading problems.

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"
from cubicweb.rtags import RelationTags

# editforms.AutomaticEntityForm configuration #################################

# relations'category (eg primary/secondary/generic/metadata/generated)
rcategories = RelationTags()
# use primary and not generated for eid since it has to be an hidden
rcategories.set_rtag('primary', 'eid', 'subject')
rcategories.set_rtag('primary', 'in_state', 'subject')
rcategories.set_rtag('secondary', 'description', 'subject')
rcategories.set_rtag('metadata', 'creation_date', 'subject')
rcategories.set_rtag('metadata', 'modification_date', 'subject')
rcategories.set_rtag('metadata', 'owned_by', 'subject')
rcategories.set_rtag('metadata', 'created_by', 'subject')
rcategories.set_rtag('generated', 'has_text', 'subject')
rcategories.set_rtag('generated', 'is', 'subject')
rcategories.set_rtag('generated', 'is', 'object')
rcategories.set_rtag('generated', 'is_instance_of', 'subject')
rcategories.set_rtag('generated', 'is_instance_of', 'object')
rcategories.set_rtag('generated', 'identity', 'subject')
rcategories.set_rtag('generated', 'identity', 'object')
rcategories.set_rtag('generated', 'require_permission', 'subject')
rcategories.set_rtag('generated', 'wf_info_for', 'subject')
rcategories.set_rtag('generated', 'wf_info_for', 'object')
rcategories.set_rtag('generated', 'for_user', 'subject')
rcategories.set_rtag('generated', 'for_user', 'object')

# relations'widget (eg one of available class name in cubicweb.web.formwidgets)
rwidgets = RelationTags()

# inlined view flag for non final relations: when True for an entry, the
# entity(ies) at the other end of the relation will be editable from the
# form of the edited entity
rinlined = RelationTags()

# set of tags of the form <action>_on_new on relations. <action> is a
# schema action (add/update/delete/read), and when such a tag is found
# permissions checking is by-passed and supposed to be ok
rpermissions_overrides = RelationTags(use_set=True)


# boxes.EditBox configuration #################################################

# 'link' / 'create' relation tags, used to control the "add entity" submenu
rmode = RelationTags() 
rmode.set_rtag('link', 'is', 'subject')
rmode.set_rtag('link', 'is', 'object')
rmode.set_rtag('link', 'is_instance_of', 'subject')
rmode.set_rtag('link', 'is_instance_of', 'object')
rmode.set_rtag('link', 'identity', 'subject')
rmode.set_rtag('link', 'identity', 'object')
rmode.set_rtag('link', 'owned_by', 'subject')
rmode.set_rtag('link', 'created_by', 'subject')
rmode.set_rtag('link', 'require_permission', 'subject')
rmode.set_rtag('link', 'wf_info_for', 'subject')
rmode.set_rtag('link', 'wf_info_for', 'subject')
