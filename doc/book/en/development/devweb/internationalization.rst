.. -*- coding: utf-8 -*-

.. _internationalization:

Internationalization
---------------------

Cubicweb fully supports the internalization of its content and interface.

Cubicweb's interface internationalization is based on the translation project `GNU gettext`_.

.. _`GNU gettext`: http://www.gnu.org/software/gettext/

Cubicweb' internalization involves two steps:

* in your Python code and cubicweb-tal templates : mark translatable strings

* in your instance : handle the translation catalog

String internationalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~

User defined string
```````````````````

In the Python code and cubicweb-tal templates translatable strings can be
marked in one of the following ways :

 * by using the *built-in* function `_` ::

     class PrimaryView(EntityView):
         """the full view of an non final entity"""
         id = 'primary'
         title = _('primary')

  OR

 * by using the equivalent request's method ::

     class NoResultView(EmptyRsetView):
         """default view when no result has been found"""
         id = 'noresult'

         def call(self, **kwargs):
             self.w(u'<div class="searchMessage"><strong>%s</strong></div>\n'
                 % self.req._('No result matching query'))

The goal of the *built-in* function `_` is only **to mark the
translatable strings**, it will only return the string to translate
itself, but not its translation (it's actually another name for the
`unicode` builtin).

In the other hand the request's method `self.req._` is meant to retrieve the
proper translation of translation strings in the requested language.

Finally you can also use the `__` attribute of request object to get a
translation for a string *which should not itself added to the catalog*,
usually in case where the actual msgid is created by string interpolation ::

  self.req.__('This %s' % etype)

In this example `req.__` is used instead of `req._` so we don't have 'This %s' in
messages catalogs.


Translations in cubicweb-tal template can also be done with TAL tags
`i18n:content` and `i18n:replace`.


If you need to add messages on top of those that can be found in the source,
you can create a file named `i18n/static-messages.pot`.

Generated string
````````````````

We do not need to mark the translation strings of entities/relations used by a
particular instance's schema as they are generated automatically. String for
various actions are also generated.

For exemple the following schema ::

  Class EntityA(EntityType):
      relationa2b = SubjectRelation('EntityB')

  class EntityB(EntityType):
      pass

May generate the following message ::

  add Execution has_export File subject

This message will be used in views of ``EntityA`` for creation of a new
``EntityB`` with a preset relation ``relation_a2b`` between the current
``EntityA`` and the new ``EntityB``. The opposite message ::

  add Execution has_export File object

Is used for similar creation of an ``EntityA`` from a view of ``EntityB``. The
title of they respective creation form will be ::

  creating EntityB (EntityA %(linkto)s relation_a2b EntityB)

  creating EntityA (EntityA relation_a2b %(linkto)s EntityA)

In the translated string you can use ``%(linkto)s`` for reference to the source
``entity``.

Handle the translation catalog
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the internationalization is done in your code, you need to populate and
update the translation catalog. Cubicweb provides the following commands for this
purpose:


* `i18ncubicweb` updates Cubicweb framework's translation
  catalogs. Unless you actually work on the framework itself, you
  don't need to use this command.

* `i18ncube` updates the translation catalogs of *one particular
  cube* (or of all cubes). After this command is
  executed you must update the translation files *.po* in the "i18n"
  directory of your template. This command will of course not remove
  existing translations still in use.

* `i18ninstance` recompiles the translation catalogs of *one particular
  instance* (or of all instances) after the translation catalogs of
  its cubes have been updated. This command is automatically
  called every time you create or update your instance. The compiled
  catalogs (*.mo*) are stored in the i18n/<lang>/LC_MESSAGES of
  instance where `lang` is the language identifier ('en' or 'fr'
  for exemple).


Example
```````
You have added and/or modified some translation strings in your cube
(after creating a new view or modifying the cube's schema for exemple).
To update the translation catalogs you need to do:

1. `cubicweb-ctl i18ncube <cube>`
2. Edit the <cube>/i18n/xxx.po  files and add missing translations (empty `msgstr`)
3. `hg ci -m "updated i18n catalogs"`
4. `cubicweb-ctl i18ninstance <myinstance>`

