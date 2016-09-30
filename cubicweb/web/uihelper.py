# copyright 2011-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""This module provide highlevel helpers to avoid uicfg boilerplate
for most common tasks such as fields ordering, widget customization, etc.


Here are a few helpers to customize *action box* rendering:

.. autofunction:: cubicweb.web.uihelper.append_to_addmenu
.. autofunction:: cubicweb.web.uihelper.remove_from_addmenu


and a few other ones for *form configuration*:

.. autofunction:: cubicweb.web.uihelper.set_fields_order
.. autofunction:: cubicweb.web.uihelper.hide_field
.. autofunction:: cubicweb.web.uihelper.hide_fields
.. autofunction:: cubicweb.web.uihelper.set_field_kwargs
.. autofunction:: cubicweb.web.uihelper.set_field
.. autofunction:: cubicweb.web.uihelper.edit_inline
.. autofunction:: cubicweb.web.uihelper.edit_as_attr
.. autofunction:: cubicweb.web.uihelper.set_muledit_editable

The module also provides a :class:`FormConfig` base class that lets you gather
uicfg declaration in the scope of a single class, which can sometimes
be clearer to read than a bunch of sequential function calls.

.. autoclass:: cubicweb.web.uihelper.FormConfig

"""


from six import add_metaclass

from logilab.common.deprecation import deprecated
from cubicweb.web.views import uicfg


## generic uicfg helpers ######################################################

backward_compat_funcs = (('append_to_addmenu', uicfg.actionbox_appearsin_addmenu),
                         ('remove_from_addmenu', uicfg.actionbox_appearsin_addmenu),
                         ('set_fields_order', uicfg.autoform_field_kwargs),
                         ('hide_field', uicfg.autoform_section),
                         ('hide_fields', uicfg.autoform_section),
                         ('set_field_kwargs', uicfg.autoform_field_kwargs),
                         ('set_field', uicfg.autoform_field),
                         ('edit_inline', uicfg.autoform_section),
                         ('edit_as_attr', uicfg.autoform_section),
                         ('set_muledit_editable', uicfg.autoform_section),
                         )

for funcname, tag in backward_compat_funcs:
    msg = ('[3.16] uihelper.%(name)s is deprecated, please use '
           'web.views.uicfg.%(rtagid)s.%(name)s' % dict(
               name=funcname, rtagid=tag.__regid__))
    globals()[funcname] = deprecated(msg)(getattr(tag, funcname))


class meta_formconfig(type):
    """metaclass of FormConfig classes, only for easier declaration purpose"""
    def __init__(cls, name, bases, classdict):
        if cls.etype is None:
            return
        uicfg_afs = cls.uicfg_afs or uicfg.autoform_section
        uicfg_aff = cls.uicfg_aff or uicfg.autoform_field
        uicfg_affk = cls.uicfg_affk or uicfg.autoform_field_kwargs
        for attr_role in cls.hidden:
            uicfg_afs.hide_field(cls.etype, attr_role, formtype=cls.formtype)
        for attr_role in cls.rels_as_attrs:
            uicfg_afs.edit_as_attr(cls.etype, attr_role, formtype=cls.formtype)
        for attr_role in cls.inlined:
            uicfg_afs.edit_inline(cls.etype, attr_role, formtype=cls.formtype)
        for rtype, widget in cls.widgets.items():
            uicfg_affk.set_field_kwargs(cls.etype, rtype, widget=widget)
        for rtype, field in cls.fields.items():
            uicfg_aff.set_field(cls.etype, rtype, field)
        uicfg_affk.set_fields_order(cls.etype, cls.fields_order)
        super(meta_formconfig, cls).__init__(name, bases, classdict)


@add_metaclass(meta_formconfig)
class FormConfig:
    """helper base class to define uicfg rules on a given entity type.

    In all descriptions below, attributes list can either be a list of
    attribute names of a list of 2-tuples (relation name, role of
    the edited entity in the relation).

    **Attributes**

    :attr:`etype`
      which entity type the form config is for. This attribute is **mandatory**

    :attr:`formtype`
      the formtype the class tries toc customize (i.e. *main*, *inlined*, or *muledit*),
      default is *main*.

    :attr:`hidden`
      the list of attributes or relations to hide.

    :attr:`rels_as_attrs`
      the list of attributes to edit in the *attributes* section.

    :attr:`inlined`
      the list of attributes to edit in the *inlined* section.

    :attr:`fields_order`
      the list of attributes to edit, in the desired order. Unspecified
      fields will be displayed after specified ones, their order
      being consistent with the schema definition.

    :attr:`widgets`
      a dictionary mapping attribute names to widget instances.

    :attr:`fields`
      a dictionary mapping attribute names to field instances.

    :attr:`uicfg_afs`
      an instance of ``cubicweb.web.uicfg.AutoformSectionRelationTags``
      Default is None, meaning ``cubicweb.web.uicfg.autoform_section`` is used.

    :attr:`uicfg_aff`
      an instance of ``cubicweb.web.uicfg.AutoformFieldTags``
      Default is None, meaning ``cubicweb.web.uicfg.autoform_field`` is used.

    :attr:`uicfg_affk`
      an instance of ``cubicweb.web.uicfg.AutoformFieldKwargsTags``
      Default is None, meaning ``cubicweb.web.uicfg.autoform_field_kwargs`` is used.

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper, formwidgets as fwdgs

  class LinkFormConfig(uihelper.FormConfig):
      etype = 'Link'
      hidden = ('title', 'description', 'embed')
      widgets = dict(
          url=fwdgs.TextInput(attrs={'size':40}),
          )

  class UserFormConfig(uihelper.FormConfig):
      etype = 'CWUser'
      hidden = ('login',)
      rels_as_attrs = ('in_group',)
      fields_order = ('firstname', 'surname', 'in_group', 'use_email')
      inlined = ('use_email',)

    """
    formtype = 'main'
    etype = None # must be defined in concrete subclasses
    hidden = ()
    rels_as_attrs = ()
    inlined = ()
    fields_order = ()
    widgets = {}
    fields = {}
    uicfg_afs = None
    uicfg_aff = None
    uicfg_affk = None
