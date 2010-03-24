.. -*- coding: utf-8 -*-

Javascript
----------

*CubicWeb* uses quite a bit of javascript in its user interface and
ships with jquery (1.3.x) and parts of the jquery UI
library, plus a number of homegrown files and also other thirparty
libraries.

All javascript files are stored in cubicweb/web/data/. There are
around thirty js files there. In a cube it goes to data/.

Obviously one does not want javascript pieces to be loaded all at
once, hence the framework provides a number of mechanisms and
conventions to deal with javascript resources.

Conventions
~~~~~~~~~~~

It is good practice to name cube specific js files after the name of
the cube, like this : 'cube.mycube.js', so as to avoid name clashes.

XXX external_resources variable (which needs love)

CubicWeb javascript api
~~~~~~~~~~~~~~~~~~~~~~~

Javascript resources are typically loaded on demand, from views. The
request object (available as self._cw from most application objects,
for instance views and entities objects) has a few methods to do that:

* `add_js(self, jsfiles, localfile=True)` which takes a sequence of
  javascript files and writes proper entries into the HTML header
  section. The localfile parameter allows to declare resources which
  are not from web/data (for instance, residing on a content delivery
  network).

* `add_onload(self, jscode)` which adds one raw javascript code
  snippet inline in the html headers. This is quite useful for setting
  up early jQuery(document).ready(...) initialisations.

CubicWeb javascript events
~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``server-response``: this event is triggered on HTTP responses (both
  standard and ajax). The two following extra parameters are passed
  to callbacks :

  - ``ajax``: a boolean that says if the reponse was issued by an
    ajax request

  - ``node``: the DOM node returned by the server in case of an
    ajax request, otherwise the document itself for standard HTTP
    requests.


Overview of what's available
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* jquery.* : jquery and jquery UI library

* cubicweb.python.js : adds a number of practical extension to stdanrd
  javascript objects (on Date, Array, String, some list and dictionary
  operations), and a pythonesque way to build classes. Defines a
  CubicWeb namespace.

* cubicweb.htmlhelpers.js : a small bag of convenience functions used
  in various other cubicweb javascript resources (baseuri, progress
  cursor handling, popup login box, html2dom function, etc.)

* cubicweb.ajax.js : concentrates all ajax related facilities (it
  extends jQuery with the loahxhtml function, provides a handfull of
  high-level ajaxy operations like asyncRemoteExec, reloadComponent,
  replacePageChunk, getDomFromResponse)

* cubicweb.widgets.js : provides a widget namespace and constructors
  and helpers for various widgets (mainly facets and timeline)

* cubicweb.edition.js : used by edition forms

* cubicweb.preferences.js : used by the preference form

* cubicweb.facets.js : used by the facets mechanism

xxx massmailing, gmap, fckcwconfig, timeline-bundle, timeline-ext,
calendar, goa, flotn tazy, tabs, bookmarks
