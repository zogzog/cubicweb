from cubicweb.web import formwidgets as wdgs
from cubicweb.web.views import uicfg

# fields required in the schema but automatically set by hooks. Tell about that
# to the ui
_pvdc = uicfg.autoform_field_kwargs
_pvdc.tag_attribute(('File', 'data_name'), {
    'required': False, 'widget': wdgs.TextInput({'size': 45})})
_pvdc.tag_attribute(('File', 'data_format'), {'required': False})
