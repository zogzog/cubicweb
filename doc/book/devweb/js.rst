.. -*- coding: utf-8 -*-

Javascript
----------

*CubicWeb* uses quite a bit of javascript in its user interface and
ships with jquery (1.3.x) and parts of the jquery UI library, plus a
number of homegrown files and also other third party libraries.

All javascript files are stored in cubicweb/web/data/. There are
around thirty js files there. In a cube it goes to data/.

Obviously one does not want javascript pieces to be loaded all at
once, hence the framework provides a number of mechanisms and
conventions to deal with javascript resources.

Conventions
~~~~~~~~~~~

It is good practice to name cube specific js files after the name of
the cube, like this : 'cube.mycube.js', so as to avoid name clashes.

.. XXX external_resources variable (which needs love)

Server-side Javascript API
~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Javascript events
~~~~~~~~~~~~~~~~~

* ``server-response``: this event is triggered on HTTP responses (both
  standard and ajax). The two following extra parameters are passed
  to callbacks :

  - ``ajax``: a boolean that says if the reponse was issued by an
    ajax request

  - ``node``: the DOM node returned by the server in case of an
    ajax request, otherwise the document itself for standard HTTP
    requests.

Important javascript AJAX APIS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* `asyncRemoteExec` and `remoteExec` are the base building blocks for
  doing arbitrary async (resp. sync) communications with the server

* `reloadComponent` is a convenience function to replace a DOM node
  with server supplied content coming from a specific registry (this
  is quite handy to refresh the content of some boxes for instances)

* `jQuery.fn.loadxhtml` is an important extension to jQuery which
  allows proper loading and in-place DOM update of xhtml views. It is
  suitably augmented to trigger necessary events, and process CubicWeb
  specific elements such as the facet system, fckeditor, etc.


A simple example with asyncRemoteExec
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the python side, we have to define an
:class:`cubicweb.web.views.ajaxcontroller.AjaxFunction` object. The
simplest way to do that is to use the
:func:`cubicweb.web.views.ajaxcontroller.ajaxfunc` decorator (for more
details on this, refer to :ref:`ajax`).

.. sourcecode: python

    from cubicweb.web.views.ajaxcontroller import ajaxfunc

    # serialize output to json to get it back easily on the javascript side
    @ajaxfunc(output_type='json')
    def js_say_hello(self, name):
        return u'hello %s' % name

On the javascript side, we do the asynchronous call. Notice how it
creates a `deferred` object. Proper treatment of the return value or
error handling has to be done through the addCallback and addErrback
methods.

.. sourcecode: javascript

    function asyncHello(name) {
        var deferred = asyncRemoteExec('say_hello', name);
        deferred.addCallback(function (response) {
            alert(response);
        });
        deferred.addErrback(function (error) {
            alert('something fishy happened');
        });
     }

     function syncHello(name) {
         alert( remoteExec('say_hello', name) );
     }

Anatomy of a reloadComponent call
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`reloadComponent` allows to dynamically replace some DOM node with new
elements. It has the following signature:

* `compid` (mandatory) is the name of the component to be reloaded

* `rql` (optional) will be used to generate a result set given as
  argument to the selected component

* `registry` (optional) defaults to 'components' but can be any other
  valid registry name

* `nodeid` (optional) defaults to compid + 'Component' but can be any
  explicitly specified DOM node id

* `extraargs` (optional) should be a dictionary of values that will be
  given to the cell_call method of the component

A simple reloadComponent example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The server side implementation of `reloadComponent` is the
:func:`cubicweb.web.views.ajaxcontroller.component` *AjaxFunction* appobject.

The following function implements a two-steps method to delete a
standard bookmark and refresh the UI, while keeping the UI responsive.

.. sourcecode:: javascript

    function removeBookmark(beid) {
        d = asyncRemoteExec('delete_bookmark', beid);
        d.addCallback(function(boxcontent) {
            reloadComponent('bookmarks_box', '', 'boxes', 'bookmarks_box');
            document.location.hash = '#header';
            updateMessage(_("bookmark has been removed"));
         });
    }

`reloadComponent` is called with the id of the bookmark box as
argument, no rql expression (because the bookmarks display is actually
independant of any dataset context), a reference to the 'boxes'
registry (which hosts all left, right and contextual boxes) and
finally an explicit 'bookmarks_box' nodeid argument that stipulates
the target DOM node.

Anatomy of a loadxhtml call
~~~~~~~~~~~~~~~~~~~~~~~~~~~

`jQuery.fn.loadxhtml` is an important extension to jQuery which allows
proper loading and in-place DOM update of xhtml views. The existing
`jQuery.load`_ function does not handle xhtml, hence the addition. The
API of loadxhtml is roughly similar to that of `jQuery.load`_.

.. _`jQuery.load`: http://api.jquery.com/load/


* `url` (mandatory) should be a complete url (typically referencing
  the :class:`cubicweb.web.views.ajaxcontroller.AjaxController`,
  but this is not strictly mandatory)

* `data` (optional) is a dictionary of values given to the
  controller specified through an `url` argument; some keys may have a
  special meaning depending on the choosen controller (such as `fname`
  for the JSonController); the `callback` key, if present, must refer
  to a function to be called at the end of loadxhtml (more on this
  below)

* `reqtype` (optional) specifies the request method to be used (get or
  post); if the argument is 'post', then the post method is used,
  otherwise the get method is used

* `mode` (optional) is one of `replace` (the default) which means the
  loaded node will replace the current node content, `swap` to replace
  the current node with the loaded node, and `append` which will
  append the loaded node to the current node content

About the `callback` option:

* it is called with two parameters: the current node, and a list
  containing the loaded (and post-processed node)

* whenever it returns another function, this function is called in
  turn with the same parameters as above

This mechanism allows callback chaining.


A simple example with loadxhtml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here we are concerned with the retrieval of a specific view to be
injected in the live DOM. The view will be of course selected
server-side using an entity eid provided by the client side.

.. sourcecode:: python

    from cubicweb.web.views.ajaxcontroller import ajaxfunc

    @ajaxfunc(output_type='xhtml')
    def frob_status(self, eid, frobname):
        entity = self._cw.entity_from_eid(eid)
        return entity.view('frob', name=frobname)

.. sourcecode:: javascript

    function updateSomeDiv(divid, eid, frobname) {
        var params = {fname:'frob_status', eid: eid, frobname:frobname};
        jQuery('#'+divid).loadxhtml(JSON_BASE_URL, params, 'post');
     }

In this example, the url argument is the base json url of a cube
instance (it should contain something like
`http://myinstance/ajax?`). The actual AjaxController method name is
encoded in the `params` dictionary using the `fname` key.

A more real-life example
~~~~~~~~~~~~~~~~~~~~~~~~

A frequent need of Web 2 applications is the delayed (or demand
driven) loading of pieces of the DOM. This is typically achieved using
some preparation of the initial DOM nodes, jQuery event handling and
proper use of loadxhtml.

We present here a skeletal version of the mecanism used in CubicWeb
and available in web/views/tabs.py, in the `LazyViewMixin` class.

.. sourcecode:: python

    def lazyview(self, vid, rql=None):
        """ a lazy version of wview """
        w = self.w
        self._cw.add_js('cubicweb.lazy.js')
        urlparams = {'vid' : vid, 'fname' : 'view'}
        if rql is not None:
            urlparams['rql'] = rql
        w(u'<div id="lazy-%s" cubicweb:loadurl="%s">' % (
            vid, xml_escape(self._cw.build_url('json', **urlparams))))
        w(u'</div>')
        self._cw.add_onload(u"""
            jQuery('#lazy-%(vid)s').bind('%(event)s', function() {
                   loadNow('#lazy-%(vid)s');});"""
            % {'event': 'load_%s' % vid, 'vid': vid})

This creates a `div` with a specific event associated to it.

The full version deals with:

* optional parameters such as an entity eid, an rset

* the ability to further reload the fragment

* the ability to display a spinning wheel while the fragment is still
  not loaded

* handling of browsers that do not support ajax (search engines,
  text-based browsers such as lynx, etc.)

The javascript side is quite simple, due to loadxhtml awesomeness.

.. sourcecode:: javascript

    function loadNow(eltsel) {
        var lazydiv = jQuery(eltsel);
        lazydiv.loadxhtml(lazydiv.attr('cubicweb:loadurl'));
    }

This is all significantly different of the previous `simple example`
(albeit this example actually comes from real-life code).

Notice how the `cubicweb:loadurl` is used to convey the url
information. The base of this url is similar to the global javascript
JSON_BASE_URL. According to the pattern described earlier,
the `fname` parameter refers to the standard `js_view` method of the
JSonController. This method renders an arbitrary view provided a view
id (or `vid`) is provided, and most likely an rql expression yielding
a result set against which a proper view instance will be selected.

The `cubicweb:loadurl` is one of the 29 attributes extensions to XHTML
in a specific cubicweb namespace. It is a means to pass information
without breaking HTML nor XHTML compliance and without resorting to
ungodly hacks.

Given all this, it is easy to add a small nevertheless useful feature
to force the loading of a lazy view (for instance, a very
computation-intensive web page could be scinded into one fast-loading
part and a delayed part).

On the server side, a simple call to a javascript function is
sufficient.

.. sourcecode:: python

    def forceview(self, vid):
        """trigger an event that will force immediate loading of the view
        on dom readyness
        """
        self._cw.add_onload("triggerLoad('%s');" % vid)

The browser-side definition follows.

.. sourcecode:: javascript

    function triggerLoad(divid) {
        jQuery('#lazy-' + divd).trigger('load_' + divid);
    }


Javascript library: overview
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* jquery.* : jquery and jquery UI library

* cubicweb.ajax.js : concentrates all ajax related facilities (it
  extends jQuery with the loahxhtml function, provides a handfull of
  high-level ajaxy operations like asyncRemoteExec, reloadComponent,
  replacePageChunk, getDomFromResponse)

* cubicweb.python.js : adds a number of practical extension to stdanrd
  javascript objects (on Date, Array, String, some list and dictionary
  operations), and a pythonesque way to build classes. Defines a
  CubicWeb namespace.

* cubicweb.htmlhelpers.js : a small bag of convenience functions used
  in various other cubicweb javascript resources (baseuri, progress
  cursor handling, popup login box, html2dom function, etc.)

* cubicweb.widgets.js : provides a widget namespace and constructors
  and helpers for various widgets (mainly facets and timeline)

* cubicweb.edition.js : used by edition forms

* cubicweb.preferences.js : used by the preference form

* cubicweb.facets.js : used by the facets mechanism

There is also javascript support for massmailing, gmap (google maps),
fckcwconfig (fck editor), timeline, calendar, goa (CubicWeb over
AppEngine), flot (charts drawing), tabs and bookmarks.

API
~~~

.. toctree::
    :maxdepth: 1

    /js_api/index


Testing javascript
~~~~~~~~~~~~~~~~~~

You with the ``cubicweb.qunit.QUnitTestCase`` can include standard Qunit tests
inside the python unittest run . You simply have to define a new class that
inherit from ``QUnitTestCase`` and register your javascript test file in the
``all_js_tests`` lclass attribut. This  ``all_js_tests`` is a sequence a
3-tuple (<test_file, [<dependencies> ,] [<data_files>]):

The <test_file> should contains the qunit test. <dependencies> defines the list
of javascript file that must be imported before the test script.  Dependencies
are included their definition order. <data_files> are additional files copied in the
test directory. both <dependencies> and <data_files> are optionnal.
``jquery.js`` is preincluded in for all test.

.. sourcecode:: python

    from cubicweb.qunit import QUnitTestCase

    class MyQUnitTest(QUnitTestCase):

        all_js_tests = (
            ("relative/path/to/my_simple_testcase.js",)
            ("relative/path/to/my_qunit_testcase.js",(
                "rel/path/to/dependency_1.js",
                "rel/path/to/dependency_2.js",)),
            ("relative/path/to/my_complexe_qunit_testcase.js",(
                 "rel/path/to/dependency_1.js",
                 "rel/path/to/dependency_2.js",
               ),(
                 "rel/path/file_dependency.html",
                 "path/file_dependency.json")
                ),
            )
