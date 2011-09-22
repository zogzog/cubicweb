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
"""
The *primary* view is supposed to render a maximum of informations about the
entity.

.. _primary_view_layout:

Layout
``````

The primary view has the following layout.

.. image:: ../../images/primaryview_template.png

.. _primary_view_configuration:

Primary view configuration
``````````````````````````

If you want to customize the primary view of an entity, overriding the primary
view class may not be necessary. For simple adjustments (attributes or relations
display locations and styles), a much simpler way is to use uicfg.

Attributes/relations display location
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the primary view, there are three sections where attributes and
relations can be displayed (represented in pink in the image above):

* 'attributes'
* 'relations'
* 'sideboxes'

**Attributes** can only be displayed in the attributes section (default
  behavior). They can also be hidden. By default, attributes of type `Password`
  and `Bytes` are hidden.

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

   pv_section = uicfg.primaryview_section
   # hide every relation `entry_of` in the `Blog` primary view
   pv_section.tag_object_of(('*', 'entry_of', 'Blog'), 'hidden')

   # display `entry_of` relations in the `relations`
   # section in the `BlogEntry` primary view
   pv_section.tag_subject_of(('BlogEntry', 'entry_of', '*'), 'relations')


Display content
^^^^^^^^^^^^^^^

You can use ``primaryview_display_ctrl`` to customize the display of attributes
or relations. Values of ``primaryview_display_ctrl`` are dictionaries.


Common keys for attributes and relations are:

* ``vid``: specifies the regid of the view for displaying the attribute or the relation.

  If ``vid`` is not specified, the default value depends on the section:
    * ``attributes`` section: 'reledit' view
    * ``relations`` section: 'autolimited' view
    * ``sideboxes`` section: 'sidebox' view

* ``order``: int used to control order within a section. When not specified,
  automatically set according to order in which tags are added.

* ``label``: label for the relations section or side box

* ``showlabel``: boolean telling whether the label is displayed

.. sourcecode:: python

   # let us remind the schema of a blog entry
   class BlogEntry(EntityType):
       title = String(required=True, fulltextindexed=True, maxsize=256)
       publish_date = Date(default='TODAY')
       content = String(required=True, fulltextindexed=True)
       entry_of = SubjectRelation('Blog', cardinality='?*')

   # now, we want to show attributes
   # with an order different from that in the schema definition
   view_ctrl = uicfg.primaryview_display_ctrl
   for index, attr in enumerate('title', 'content', 'publish_date'):
       view_ctrl.tag_attribute(('BlogEntry', attr), {'order': index})

By default, relations displayed in the 'relations' section are being displayed by
the 'autolimited' view. This view will use comma separated values, or list view
and/or limit your rset if there is too much items in it (and generate the "view
all" link in this case).

You can control this view by setting the following values in the
`primaryview_display_ctrl` relation tag:

* `limit`, maximum number of entities to display. The value of the
  'navigation.related-limit'  cwproperty is used by default (which is 8 by default).
  If None, no limit.

* `use_list_limit`, number of entities until which they should be display as a list
  (eg using the 'list' view). Below that limit, the 'csv' view is used. If None,
  display using 'csv' anyway.

* `subvid`, the subview identifier (eg view that should be used of each item in the
  list)

Notice you can also use the `filter` key to set up a callback taking the related
result set as argument and returning it filtered, to do some arbitrary filtering
that can't be done using rql for instance.




.. sourcecode:: python

   pv_section = uicfg.primaryview_section
   # in `CWUser` primary view, display `created_by`
   # relations in relations section
   pv_section.tag_object_of(('*', 'created_by', 'CWUser'), 'relations')

   # display this relation as a list, sets the label,
   # limit the number of results and filters on comments
   def filter_comment(rset):
       return rset.filtered_rset(lambda x: x.e_schema == 'Comment')
   pv_ctrl = uicfg.primaryview_display_ctrl
   pv_ctrl.tag_object_of(('*', 'created_by', 'CWUser'),
                         {'vid': 'list', 'label': _('latest comment(s):'),
                          'limit': True,
                          'filter': filter_comment})

.. warning:: with the ``primaryview_display_ctrl`` rtag, the subject or the
   object of the relation is ignored for respectively ``tag_object_of`` or
   ``tag_subject_of``. To avoid warnings during execution, they should be set to
   ``'*'``.

Rendering methods and attributes
````````````````````````````````

The basic layout of a primary view is as in the
:ref:`primary_view_layout` section. This layout is actually drawn by
the `render_entity` method.

The methods you may want to modify while customizing a ``PrimaryView``
are:

*render_entity_title(self, entity)*
    Renders the entity title, by default using entity's :meth:`dc_title()` method.

*render_entity_attributes(self, entity)*
    Renders all attributes and relations in the 'attributes' section . The
    :attr:`skip_none` attribute controls the display of `None` valued attributes.

*render_entity_relations(self, entity)*
    Renders all relations in the 'relations' section.

*render_side_boxes(self, entity, boxes)*
    Renders side boxes on the right side of the content. This will generate a box
    for each relation in the 'sidebox' section, as well as explicit box
    appobjects selectable in this context.

The placement of relations in the relations section or in side boxes
can be controlled through the :ref:`primary_view_configuration` mechanism.

*content_navigation_components(self, context)*
    This method is applicable only for entity type implementing the interface
    `IPrevNext`. This interface is for entities which can be linked to a previous
    and/or next entity. This method will render the navigation links between
    entities of this type, either at the top or at the bottom of the page
    given the context (navcontent{top|bottom}).

Also, please note that by setting the following attributes in your
subclass, you can already customize some of the rendering:

*show_attr_label*
    Renders the attribute label next to the attribute value if set to `True`.
    Otherwise, does only display the attribute value.

*show_rel_label*
    Renders the relation label next to the relation value if set to `True`.
    Otherwise, does only display the relation value.

*skip_none*
    Does not render an attribute value that is None if set to `True`.

*main_related_section*
    Renders the relations of the entity if set to `True`.

A good practice is for you to identify the content of your entity type for which
the default rendering does not answer your need so that you can focus on the specific
method (from the list above) that needs to be modified. We do not advise you to
overwrite ``render_entity`` unless you want a completely different layout.


Example of customization and creation
`````````````````````````````````````

We'll show you now an example of a ``primary`` view and how to customize it.

If you want to change the way a ``BlogEntry`` is displayed, just
override the method ``cell_call()`` of the view ``primary`` in
``BlogDemo/views.py``.

.. sourcecode:: python

   from cubicweb.selectors import is_instance
   from cubicweb.web.views.primary import Primaryview

   class BlogEntryPrimaryView(PrimaryView):
     __select__ = PrimaryView.__select__ & is_instance('BlogEntry')

       def render_entity_attributes(self, entity):
           self.w(u'<p>published on %s</p>' %
                  entity.publish_date.strftime('%Y-%m-%d'))
           super(BlogEntryPrimaryView, self).render_entity_attributes(entity)


The above source code defines a new primary view for
``BlogEntry``. The `__reid__` class attribute is not repeated there since it
is inherited through the `primary.PrimaryView` class.

The selector for this view chains the selector of the inherited class
with its own specific criterion.

The view method ``self.w()`` is used to output data. Here `lines
08-09` output HTML for the publication date of the entry.

.. image:: ../../images/lax-book_09-new-view-blogentry_en.png
   :alt: blog entries now look much nicer

Let us now improve the primary view of a blog

.. sourcecode:: python

 from logilab.mtconverter import xml_escape
 from cubicweb.selectors import is_instance, one_line_rset
 from cubicweb.web.views.primary import Primaryview

 class BlogPrimaryView(PrimaryView):
     __regid__ = 'primary'
     __select__ = PrimaryView.__select__ & is_instance('Blog')
     rql = 'Any BE ORDERBY D DESC WHERE BE entry_of B, BE publish_date D, B eid %(b)s'

     def render_entity_relations(self, entity):
         rset = self._cw.execute(self.rql, {'b' : entity.eid})
         for entry in rset.entities():
             self.w(u'<p>%s</p>' % entry.view('inblogcontext'))

 class BlogEntryInBlogView(EntityView):
     __regid__ = 'inblogcontext'
     __select__ = is_instance('BlogEntry')

     def cell_call(self, row, col):
         entity = self.cw_rset.get_entity(row, col)
         self.w(u'<a href="%s" title="%s">%s</a>' %
                entity.absolute_url(),
                xml_escape(entity.content[:50]),
                xml_escape(entity.description))

This happens in two places. First we override the
render_entity_relations method of a Blog's primary view. Here we want
to display our blog entries in a custom way.

At `line 10`, a simple request is made to build a result set with all
the entities linked to the current ``Blog`` entity by the relationship
``entry_of``. The part of the framework handling the request knows
about the schema and infers that such entities have to be of the
``BlogEntry`` kind and retrieves them (in the prescribed publish_date
order).

The request returns a selection of data called a result set. Result
set objects have an .entities() method returning a generator on
requested entities (going transparently through the `ORM` layer).

At `line 13` the view 'inblogcontext' is applied to each blog entry to
output HTML. (Note that the 'inblogcontext' view is not defined
whatsoever in *CubicWeb*. You are absolutely free to define whole view
families.) We juste arrange to wrap each blogentry output in a 'p'
html element.

Next, we define the 'inblogcontext' view. This is NOT a primary view,
with its well-defined sections (title, metadata, attribtues,
relations/boxes). All a basic view has to define is cell_call.

Since views are applied to result sets which can be tables of data, we
have to recover the entity from its (row,col)-coordinates (`line
20`). Then we can spit some HTML.

.. warning::

  Be careful: all strings manipulated in *CubicWeb* are actually
  unicode strings. While web browsers are usually tolerant to
  incoherent encodings they are being served, we should not abuse
  it. Hence we have to properly escape our data. The xml_escape()
  function has to be used to safely fill (X)HTML elements from Python
  unicode strings.

Assuming we added entries to the blog titled `MyLife`, displaying it
now allows to read its description and all its entries.

.. image:: ../../images/lax-book_10-blog-with-two-entries_en.png
   :alt: a blog and all its entries

Views that may be used to display an entity's attribute or relation
```````````````````````````````````````````````````````````````````

Yoy may easily the display of an attribute or relation by simply configuring the
view using one of `primaryview_display_ctrl` or `reledit_ctrl` to use one of the
views describled below. For instance:

.. sourcecode:: python

    primaryview_display_ctrl.tag_attribute(('Foo', 'bar'), {'vid': 'attribute'})


.. autoclass:: AttributeView
.. autoclass:: URLAttributeView

"""

__docformat__ = "restructuredtext en"
_ = unicode

from warnings import warn

from logilab.common.deprecation import deprecated
from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized, NoSelectableObject
from cubicweb.utils import support_args
from cubicweb.selectors import match_kwargs, match_context
from cubicweb.view import EntityView
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, display_name
from cubicweb.web import uicfg, component


class PrimaryView(EntityView):
    """the full view of an non final entity"""
    __regid__ = 'primary'
    title = _('primary')
    show_attr_label = True
    show_rel_label = True
    skip_none = True
    rsection = uicfg.primaryview_section
    display_ctrl = uicfg.primaryview_display_ctrl
    main_related_section = True

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default primary views are indexed
        """
        return []

    def entity_call(self, entity):
        entity.complete()
        self.render_entity(entity)

    def render_entity(self, entity):
        self.render_entity_toolbox(entity)
        self.render_entity_title(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        if self.is_primary():
            boxes = self._prepare_side_boxes(entity)
        else:
            boxes = None
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'<table width="100%"><tr><td style="width: 75%">')
        if hasattr(self, 'render_entity_summary'):
            warn('[3.10] render_entity_summary method is deprecated (%s)' % self,
                 DeprecationWarning)
            self.render_entity_summary(entity)
        summary = self.summary(entity)
        if summary:
            warn('[3.10] summary method is deprecated (%s)' % self,
                 DeprecationWarning)
            self.w(u'<div class="summary">%s</div>' % summary)
        self.w(u'<div class="mainInfo">')
        self.content_navigation_components('navcontenttop')
        self.render_entity_attributes(entity)
        if self.main_related_section:
            self.render_entity_relations(entity)
        self.content_navigation_components('navcontentbottom')
        self.w(u'</div>')
        # side boxes
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'</td><td>')
            self.w(u'<div class="primaryRight">')
            if hasattr(self, 'render_side_related'):
                warn('[3.2] render_side_related is deprecated')
                self.render_side_related(entity, [])
            self.render_side_boxes(boxes)
            self.w(u'</div>')
            self.w(u'</td></tr></table>')

    def content_navigation_components(self, context):
        self.w(u'<div class="%s">' % context)
        for comp in self._cw.vreg['ctxcomponents'].poss_visible_objects(
            self._cw, rset=self.cw_rset, view=self, context=context):
            # XXX bw compat code
            try:
                comp.render(w=self.w, row=self.cw_row, view=self)
            except TypeError:
                comp.render(w=self.w)
        self.w(u'</div>')

    def render_entity_title(self, entity):
        """default implementation return dc_title"""
        title = xml_escape(entity.dc_title())
        if title:
            if self.is_primary():
                self.w(u'<h1>%s</h1>' % title)
            else:
                atitle = self._cw._('follow this link for more information on this %s') % entity.dc_type()
                self.w(u'<h4><a href="%s" title="%s">%s</a></h4>'
                       % (entity.absolute_url(), atitle, title))

    def render_entity_toolbox(self, entity):
        self.content_navigation_components('ctxtoolbar')

    @deprecated('[3.8] render_entity_metadata method is deprecated')
    def render_entity_metadata(self, entity):
        entity.view('metadata', w=self.w)

    def summary(self, entity):
        """default implementation return an empty string"""
        return u''

    def render_entity_attributes(self, entity):
        display_attributes = []
        for rschema, _, role, dispctrl in self._section_def(entity, 'attributes'):
            vid = dispctrl.get('vid', 'reledit')
            if rschema.final or vid == 'reledit' or dispctrl.get('rtypevid'):
                value = entity.view(vid, rtype=rschema.type, role=role,
                                    initargs={'dispctrl': dispctrl})
            else:
                rset = self._relation_rset(entity, rschema, role, dispctrl)
                if rset:
                    value = self._cw.view(vid, rset)
                else:
                    value = None
            if not self.skip_none or (value is not None and value != ''):
                display_attributes.append( (rschema, role, dispctrl, value) )
        if display_attributes:
            self.w(u'<table>')
            for rschema, role, dispctrl, value in display_attributes:
                if not hasattr(self, '_render_attribute'):
                    label = self._rel_label(entity, rschema, role, dispctrl)
                    self.render_attribute(label, value, table=True)
                elif support_args(self._render_attribute, 'dispctrl'):
                    warn('[3.9] _render_attribute prototype has changed and '
                         'renamed to render_attribute, please update %s'
                         % self.__class___, DeprecationWarning)
                    self._render_attribute(dispctrl, rschema, value, role=role,
                                           table=True)
                else:
                    self._render_attribute(rschema, value, role=role, table=True)
                    warn('[3.6] _render_attribute prototype has changed and '
                         'renamed to render_attribute, please update %s'
                         % self.__class___, DeprecationWarning)
            self.w(u'</table>')

    def render_attribute(self, label, value, table=False):
        self.field(label, value, tr=False, table=table)

    def render_entity_relations(self, entity):
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'relations'):
            if rschema.final or dispctrl.get('rtypevid'):
                vid = dispctrl.get('vid', 'reledit')
                try:
                    rview = self._cw.vreg['views'].select(
                        vid, self._cw, rset=entity.cw_rset, row=entity.cw_row,
                        col=entity.cw_col, dispctrl=dispctrl,
                        rtype=rschema, role=role)
                except NoSelectableObject:
                    continue
                value = rview.render(row=entity.cw_row, col=entity.cw_col,
                                     rtype=rschema.type, role=role)
            else:
                rset = self._relation_rset(entity, rschema, role, dispctrl)
                if not rset:
                    continue
                if hasattr(self, '_render_relation'):
                    if not support_args(self._render_relation, 'showlabel'):
                        self._render_relation(dispctrl, rset, 'autolimited')
                        warn('[3.9] _render_relation prototype has changed and has '
                             'been renamed to render_relation, please update %s'
                             % self.__class__, DeprecationWarning)
                    else:
                        self._render_relation(rset, dispctrl, 'autolimited',
                                              self.show_rel_label)
                        warn('[3.6] _render_relation prototype has changed and has '
                             'been renamed to render_relation, please update %s'
                             % self.__class__, DeprecationWarning)
                    continue
                vid = dispctrl.get('vid', 'autolimited')
                try:
                    rview = self._cw.vreg['views'].select(
                        vid, self._cw, rset=rset, dispctrl=dispctrl)
                except NoSelectableObject:
                    continue
                value = rview.render()
            label = self._rel_label(entity, rschema, role, dispctrl)
            self.render_relation(label, value)

    def render_relation(self, label, value):
        self.w(u'<div class="section">')
        if label:
            self.w(u'<h4>%s</h4>' % label)
        self.w(value)
        self.w(u'</div>')

    def render_side_boxes(self, boxes):
        """display side related relations:
        non-meta in a first step, meta in a second step
        """
        for box in boxes:
            if isinstance(box, tuple):
                try:
                    label, rset, vid, dispctrl  = box
                except ValueError:
                    label, rset, vid = box
                    dispctrl = {}
                warn('[3.10] box views should now be a RsetBox instance, '
                     'please update %s' % self.__class__.__name__,
                     DeprecationWarning)
                self.w(u'<div class="sideBox">')
                self.wview(vid, rset, title=label, initargs={'dispctrl': dispctrl})
                self.w(u'</div>')
            else:
                 try:
                     box.render(w=self.w, row=self.cw_row)
                 except TypeError:
                     box.render(w=self.w)

    def _prepare_side_boxes(self, entity):
        sideboxes = []
        boxesreg = self._cw.vreg['ctxcomponents']
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'sideboxes'):
            rset = self._relation_rset(entity, rschema, role, dispctrl)
            if not rset:
                continue
            label = self._rel_label(entity, rschema, role, dispctrl)
            vid = dispctrl.get('vid', 'autolimited')
            box = boxesreg.select('rsetbox', self._cw, rset=rset,
                                  vid=vid, title=label, dispctrl=dispctrl,
                                  context='incontext')
            sideboxes.append(box)
        sideboxes += boxesreg.poss_visible_objects(
             self._cw, rset=self.cw_rset, view=self,
             context='incontext')
        # XXX since we've two sorted list, it may be worth using bisect
        def get_order(x):
            if 'order' in x.cw_property_defs:
                return x.cw_propval('order')
            # default to 9999 so view boxes occurs after component boxes
            return x.cw_extra_kwargs.get('dispctrl', {}).get('order', 9999)
        return sorted(sideboxes, key=get_order)

    def _section_def(self, entity, where):
        rdefs = []
        eschema = entity.e_schema
        for rschema, tschemas, role in eschema.relation_definitions(True):
            if rschema in VIRTUAL_RTYPES:
                continue
            matchtschemas = []
            for tschema in tschemas:
                section = self.rsection.etype_get(eschema, rschema, role,
                                                  tschema)
                if section == where:
                    matchtschemas.append(tschema)
            if matchtschemas:
                dispctrl = self.display_ctrl.etype_get(eschema, rschema, role, '*')
                rdefs.append( (rschema, matchtschemas, role, dispctrl) )
        return sorted(rdefs, key=lambda x: x[-1]['order'])

    def _relation_rset(self, entity, rschema, role, dispctrl):
        try:
            rset = entity.related(rschema.type, role)
        except Unauthorized:
            return
        if 'filter' in dispctrl:
            rset = dispctrl['filter'](rset)
        return rset

    def _rel_label(self, entity, rschema, role, dispctrl):
        if rschema.final:
            showlabel = dispctrl.get('showlabel', self.show_attr_label)
        else:
            showlabel = dispctrl.get('showlabel', self.show_rel_label)
        if showlabel:
            if dispctrl.get('label'):
                label = self._cw._(dispctrl['label'])
            else:
                label = display_name(self._cw, rschema.type, role,
                                     context=entity.__regid__)
            return label
        return u''


class RelatedView(EntityView):
    """Display a rset, usually containing entities linked to another entity
    being displayed.

    It will try to display nicely according to the number of items in the result
    set.

    XXX include me in the doc
    """
    __regid__ = 'autolimited'

    def call(self, **kwargs):
        if 'dispctrl' in self.cw_extra_kwargs:
            if 'limit' in self.cw_extra_kwargs['dispctrl']:
                limit = self.cw_extra_kwargs['dispctrl']['limit']
            else:
                limit = self._cw.property_value('navigation.related-limit')
            list_limit = self.cw_extra_kwargs['dispctrl'].get('use_list_limit', 5)
            subvid = self.cw_extra_kwargs['dispctrl'].get('subvid', 'incontext')
        else:
            limit = list_limit = None
            subvid = 'incontext'
        if limit is None or self.cw_rset.rowcount <= limit:
            if self.cw_rset.rowcount == 1:
                self.wview(subvid, self.cw_rset, row=0)
            elif list_limit is None or 1 < self.cw_rset.rowcount <= list_limit:
                self.wview('csv', self.cw_rset, subvid=subvid)
            else:
                self.w(u'<div>')
                self.wview('simplelist', self.cw_rset, subvid=subvid)
                self.w(u'</div>')
        # else show links to display related entities
        else:
            rql = self.cw_rset.printable_rql()
            rset = self.cw_rset.limit(limit) # remove extra entity
            if list_limit is None:
                self.wview('csv', rset, subvid=subvid)
                self.w(u'[<a href="%s">%s</a>]' % (
                    xml_escape(self._cw.build_url(rql=rql, vid=subvid)),
                    self._cw._('see them all')))
            else:
                self.w(u'<div>')
                self.wview('simplelist', rset, subvid=subvid)
                self.w(u'[<a href="%s">%s</a>]' % (
                    xml_escape(self._cw.build_url(rql=rql, vid=subvid)),
                    self._cw._('see them all')))
                self.w(u'</div>')


class URLAttributeView(EntityView):
    """:__regid__: *urlattr*

    This view will wrap an attribute value (hence expect a string) into an '<a>'
    HTML tag to display a clickable link.
    """
    __regid__ = 'urlattr'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def entity_call(self, entity, rtype, **kwargs):
        url = entity.printable_value(rtype)
        if url:
            self.w(u'<a href="%s">%s</a>' % (url, url))

class AttributeView(EntityView):
    """:__regid__: *attribute*

    This view is generally used to disable the *reledit* feature. It works on
    both relations and attributes.
    """
    __regid__ = 'attribute'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def entity_call(self, entity, rtype, **kwargs):
        if self._cw.vreg.schema.rschema(rtype).final:
            self.w(entity.printable_value(rtype))
        else:
            dispctrl = uicfg.primaryview_display_ctrl.etype_get(
                entity.e_schema, rtype, role, '*')
            rset = entity.related(rtype, role)
            if rset:
                self.wview('autolimited', rset, initargs={'dispctrl': dispctrl})



class ToolbarLayout(component.Layout):
    # XXX include me in the doc
    __select__ = match_context('ctxtoolbar')

    def render(self, w):
        if self.init_rendering():
            self.cw_extra_kwargs['view'].render_body(w)


## default primary ui configuration ###########################################

_pvs = uicfg.primaryview_section
for rtype in META_RTYPES:
    _pvs.tag_subject_of(('*', rtype, '*'), 'hidden')
    _pvs.tag_object_of(('*', rtype, '*'), 'hidden')
_pvs.tag_subject_of(('*', 'require_permission', '*'), 'hidden')
_pvs.tag_object_of(('*', 'require_permission', '*'), 'hidden')
