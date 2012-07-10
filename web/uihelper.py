# copyright 2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
__docformat__ = "restructuredtext en"

from cubicweb.web import uicfg
from functools import partial

def _tag_rel(rtag, etype, attr, desttype='*', *args, **kwargs):
    if isinstance(attr, basestring):
        attr, role = attr, 'subject'
    else:
        attr, role = attr
    if role == 'subject':
        rtag.tag_subject_of((etype, attr, desttype), *args, **kwargs)
    else:
        rtag.tag_object_of((desttype, attr, etype), *args, **kwargs)


## generic uicfg helpers ######################################################
def append_to_addmenu(etype, attr, createdtype='*'):
    """adds `attr` in the actions box *addrelated* submenu of `etype`.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation to hide

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

    """
    _tag_rel(uicfg.actionbox_appearsin_addmenu, etype, attr, createdtype, True)

def remove_from_addmenu(etype, attr, createdtype='*'):
    """removes `attr` from the actions box *addrelated* submenu of `etype`.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation to hide

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)
    """
    _tag_rel(uicfg.actionbox_appearsin_addmenu, etype, attr, createdtype, False)


## form uicfg helpers ##########################################################
def set_fields_order(etype, attrs):
    """specify the field order in `etype` main edition form.

    :param etype: the entity type as a string
    :param attrs: the ordered list of attribute names (or relations)

    `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_relation)

    Unspecified fields will be displayed after specified ones, their
    order being consistent with the schema definition.

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper
  uihelper.set_fields_order('CWUser', ('firstname', 'surname', 'login'))
  uihelper.set_fields_order('CWUser', ('firstname', ('in_group', 'subject'), 'surname', 'login'))

    """
    afk = uicfg.autoform_field_kwargs
    for index, attr in enumerate(attrs):
        _tag_rel(afk, etype, attr, '*', {'order': index})


def hide_field(etype, attr, desttype='*', formtype='main'):
    """hide `attr` in `etype` forms.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation to hide
    :param formtype: which form will be affected ('main', 'inlined', etc.), *main* by default.

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper
  uihelper.hide_field('CWUser', 'login')
  uihelper.hide_field('*', 'name')
  uihelper.hide_field('CWUser', 'use_email', formtype='inlined')

    """
    _tag_rel(uicfg.autoform_section, etype, attr, desttype,
             formtype=formtype, section='hidden')


def hide_fields(etype, attrs, formtype='main'):
    """simple for-loop wrapper around :func:`hide_field`.

    :param etype: the entity type as a string
    :param attrs: the ordered list of attribute names (or relations)
    :param formtype: which form will be affected ('main', 'inlined', etc.), *main* by default.

    `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_relation)

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper
  uihelper.hide_fields('CWUser', ('login', ('use_email', 'subject')), formtype='inlined')
    """
    for attr in attrs:
        hide_field(etype, attr, formtype=formtype)


def set_field_kwargs(etype, attr, **kwargs):
    """tag `attr` field of `etype` with additional named paremeters.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper, formwidgets as fwdgs

  uihelper.set_field_kwargs('Person', 'works_for', widget=fwdgs.AutoCompletionWidget())
  uihelper.set_field_kwargs('CWUser', 'login', label=_('login or email address'),
                            widget=fwdgs.TextInput(attrs={'size': 30}))
    """
    _tag_rel(uicfg.autoform_field_kwargs, etype, attr, '*', kwargs)


def set_field(etype, attr, field):
    """sets the `attr` field of `etype`.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

    """
    _tag_rel(uicfg.autoform_field, etype, attr, '*', field)


def edit_inline(etype, attr, desttype='*', formtype=('main', 'inlined')):
    """edit `attr` with and inlined form.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation
    :param desttype: the destination type(s) concerned, default is everything
    :param formtype: which form will be affected ('main', 'inlined', etc.), *main* and *inlined* by default.

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper

  uihelper.edit_inline('*', 'use_email')
  """
    _tag_rel(uicfg.autoform_section, etype, attr, desttype,
             formtype=formtype, section='inlined')


def edit_as_attr(etype, attr, desttype='*', formtype=('main', 'muledit')):
    """make `attr` appear in the *attributes* section of `etype` form.

    :param etype: the entity type as a string
    :param attr: the name of the attribute or relation
    :param desttype: the destination type(s) concerned, default is everything
    :param formtype: which form will be affected ('main', 'inlined', etc.), *main* and *muledit* by default.

    `attr` can be a string or 2-tuple (relname, role_of_etype_in_the_relation)

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper

  uihelper.edit_as_attr('CWUser', 'in_group')
    """
    _tag_rel(uicfg.autoform_section, etype, attr, desttype,
             formtype=formtype, section='attributes')


def set_muledit_editable(etype, attrs):
    """make `attrs` appear in muledit form of `etype`.

    :param etype: the entity type as a string
    :param attrs: the ordered list of attribute names (or relations)

    `attrs` can be strings or 2-tuples (relname, role_of_etype_in_the_relation)

    Examples:

.. sourcecode:: python

  from cubicweb.web import uihelper

  uihelper.set_muledit_editable('CWUser', ('firstname', 'surname', 'in_group'))
    """
    for attr in attrs:
        edit_as_attr(etype, attr, formtype='muledit')


class meta_formconfig(type):
    """metaclass of FormConfig classes, only for easier declaration purpose"""
    def __init__(cls, name, bases, classdict):
        if cls.etype is None:
            return
        for attr_role in cls.hidden:
            hide_field(cls.etype, attr_role, formtype=cls.formtype)
        for attr_role in cls.rels_as_attrs:
            edit_as_attr(cls.etype, attr_role, formtype=cls.formtype)
        for attr_role in cls.inlined:
            edit_inline(cls.etype, attr_role, formtype=cls.formtype)
        for rtype, widget in cls.widgets.items():
            set_field_kwargs(cls.etype, rtype, widget=widget)
        for rtype, field in cls.fields.items():
            set_field(cls.etype, rtype, field)
        set_fields_order(cls.etype, cls.fields_order)
        super(meta_formconfig, cls).__init__(name, bases, classdict)


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
    __metaclass__ = meta_formconfig
    formtype = 'main'
    etype = None # must be defined in concrete subclasses
    hidden = ()
    rels_as_attrs = ()
    inlined = ()
    fields_order = ()
    widgets = {}
    fields = {}
