.. -*- coding: utf-8 -*-

.. _internationalization:

Internationalization
---------------------

Cubicweb fully supports the internalization of its content and interface.

Cubicweb's interface internationalization is based on the translation project `GNU gettext`_.

.. _`GNU gettext`: http://www.gnu.org/software/gettext/

Cubicweb' internalization involves two steps:

* in your Python code and cubicweb-tal templates : mark translatable strings

* in your instance : handle the translation catalog, edit translations

String internationalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~

User defined string
```````````````````

In the Python code and cubicweb-tal templates translatable strings can be
marked in one of the following ways :

 * by using the *built-in* function `_`:

   .. sourcecode:: python

     class PrimaryView(EntityView):
         """the full view of an non final entity"""
         __regid__ = 'primary'
         title = _('primary')

  OR

 * by using the equivalent request's method:

   .. sourcecode:: python

     class NoResultView(View):
         """default view when no result has been found"""
         __regid__ = 'noresult'

         def call(self, **kwargs):
             self.w(u'<div class="searchMessage"><strong>%s</strong></div>\n'
                 % self._cw._('No result matching query'))

The goal of the *built-in* function `_` is only **to mark the
translatable strings**, it will only return the string to translate
itself, but not its translation (it's actually another name for the
`unicode` builtin).

In the other hand the request's method `self._cw._` is also meant to
retrieve the proper translation of translation strings in the
requested language.

Finally you can also use the `__` attribute of request object to get a
translation for a string *which should not itself added to the catalog*,
usually in case where the actual msgid is created by string interpolation ::

  self._cw.__('This %s' % etype)

In this example ._cw.__` is used instead of ._cw._` so we don't have 'This %s' in
messages catalogs.

Translations in cubicweb-tal template can also be done with TAL tags
`i18n:content` and `i18n:replace`.

If you need to add messages on top of those that can be found in the source,
you can create a file named `i18n/static-messages.pot`.

You could put there messages not found in the python sources or
overrides for some messages of used cubes.

Generated string
````````````````

We do not need to mark the translation strings of entities/relations used by a
particular instance's schema as they are generated automatically. String for
various actions are also generated.

For exemple the following schema:

.. sourcecode:: python


  class EntityA(EntityType):
      relation_a2b = SubjectRelation('EntityB')

  class EntityB(EntityType):
      pass

May generate the following message ::

  add EntityA relation_a2b EntityB subject

This message will be used in views of ``EntityA`` for creation of a new
``EntityB`` with a preset relation ``relation_a2b`` between the current
``EntityA`` and the new ``EntityB``. The opposite message ::

  add EntityA relation_a2b EntityB object

Is used for similar creation of an ``EntityA`` from a view of ``EntityB``. The
title of they respective creation form will be ::

  creating EntityB (EntityA %(linkto)s relation_a2b EntityB)

  creating EntityA (EntityA relation_a2b %(linkto)s EntityA)

In the translated string you can use ``%(linkto)s`` for reference to the source
``entity``.

Handling the translation catalog
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the internationalization is done in your code, you need to populate and
update the translation catalog. Cubicweb provides the following commands for this
purpose:


* `i18ncubicweb` updates Cubicweb framework's translation
  catalogs. Unless you actually work on the framework itself, you
  don't need to use this command.

* `i18ncube` updates the translation catalogs of *one particular cube*
  (or of all cubes). After this command is executed you must update
  the translation files *.po* in the "i18n" directory of your
  cube. This command will of course not remove existing translations
  still in use. It will mark unused translation but not remove them.

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


Customizing the messages extraction process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The messages extraction performed by the ``i18ncommand`` collects messages
from a few different sources:

- the schema and application definition (entity names, docstrings,
  help messages, uicfg),

- the source files:

  - ``i18n:content`` or ``i18n:replace`` directives from TAL files (with ``.pt`` extension),
  - strings prefixed by an underscore (``_``) in python files,
  - strings with double quotes prefixed by an underscore in javascript files.

The source files are collected by walking through the cube directory,
but ignoring a few directories like ``.hg``, ``.tox``, ``test`` or
``node_modules``.

If you need to customize this behaviour in your cube, you have to
extend the ``cubicweb.devtools.devctl.I18nCubeMessageExtractor``. The
example below will collect strings from ``jinja2`` files and ignore
the ``static`` directory during the messages collection phase::

  # mymodule.py
  from cubicweb.devtools import devctl

  class MyMessageExtractor(devctl.I18nCubeMessageExtractor):

      blacklist = devctl.I18nCubeMessageExtractor | {'static'}
      formats = devctl.I18nCubeMessageExtractor.formats + ['jinja2']

      def collect_jinja2(self):
          return self.find('.jinja2')

      def extract_jinja2(self, files):
          return self._xgettext(files, output='jinja.pot',
                                extraopts='-L python --from-code=utf-8')

Then, you'll have to register it with a ``cubicweb.i18ncube`` entry point
in your cube's setup.py::

  setup(
      # ...
      entry_points={
          # ...
          'cubicweb.i18ncube': [
              'mycube=cubicweb_mycube.mymodule:MyMessageExtractor',
          ],
      },
      # ...
  )


Editing po files
~~~~~~~~~~~~~~~~

Using a PO aware editor
````````````````````````

Many tools exist to help maintain .po (PO) files. Common editors or
development environment provides modes for these. One can also find
dedicated PO files editor, such as `poedit`_.

.. _`poedit`:  http://www.poedit.net/

While usage of such a tool is commendable, PO files are perfectly
editable with a (unicode aware) plain text editor. It is also useful
to know their structure for troubleshooting purposes.

Structure of a PO file
``````````````````````

In this section, we selectively quote passages of the `GNU gettext`_
manual chapter on PO files, available there::

 http://www.gnu.org/software/hello/manual/gettext/PO-Files.html

One PO file entry has the following schematic structure::

     white-space
     #  translator-comments
     #. extracted-comments
     #: reference...
     #, flag...
     #| msgid previous-untranslated-string
     msgid untranslated-string
     msgstr translated-string


A simple entry can look like this::

     #: lib/error.c:116
     msgid "Unknown system error"
     msgstr "Error desconegut del sistema"

It is also possible to have entries with a context specifier. They
look like this::

     white-space
     #  translator-comments
     #. extracted-comments
     #: reference...
     #, flag...
     #| msgctxt previous-context
     #| msgid previous-untranslated-string
     msgctxt context
     msgid untranslated-string
     msgstr translated-string


The context serves to disambiguate messages with the same
untranslated-string. It is possible to have several entries with the
same untranslated-string in a PO file, provided that they each have a
different context. Note that an empty context string and an absent
msgctxt line do not mean the same thing.

Contexts and CubicWeb
`````````````````````

CubicWeb PO files have both non-contextual and contextual msgids.

Contextual entries are automatically used in some cases. For instance,
entity.dc_type(), eschema.display_name(req) or display_name(etype,
req, form, context) methods/function calls will use them.

It is also possible to explicitly use the with _cw.pgettext(context,
msgid).


Specialize translation for an application cube
``````````````````````````````````````````````

Every cube has its own translation files. For a specific application cube
it can be useful to specialize translations of other cubes. You can either mark
those strings for translation using `_` in the python code, or add a
`static-messages.pot` file into the `i18n` directory. This file
looks like: ::

    msgid ""
    msgstr ""
    "PO-Revision-Date: YEAR-MO-DA HO:MI +ZONE\n"
    "MIME-Version: 1.0\n"
    "Content-Type: text/plain; charset=UTF-8\n"
    "Content-Transfer-Encoding: 8bit\n"
    "Generated-By: pygettext.py 1.5\n"
    "Plural-Forms: nplurals=2; plural=(n > 1);\n"

    msgig "expression to be translated"
    msgstr ""

Doing this, ``expression to be translated`` will be taken into account by
the ``i18ncube`` command and additional messages will then appear in `.po` files
of the cube.
