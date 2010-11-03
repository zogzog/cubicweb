Javascript docstrings
=====================

Whereas in Python source code we only need to include a module docstrings
using the directive `.. automodule:: mypythonmodule`, we will have to
explicitely define Javascript modules and functions in the doctrings since
there is no native directive to include Javascript files.

Rest generation
---------------

`pyjsrest` is a small utility parsing Javascript doctrings and generating the
corresponding Restructured file used by Sphinx to generate HTML documentation.
This script will have the following structure::

  ===========
  filename.js
  ===========
  .. module:: filename.js

We use the `.. module::` directive to register a javascript library
as a Python module for Sphinx. This provides an entry in the module index.

The contents of the docstring found in the javascript file will be added as is
following the module declaration. No treatment will be done on the doctring.
All the documentation structure will be in the docstrings and will comply
with the following rules.

Docstring structure
-------------------

Basically we document javascript with RestructuredText docstring
following the same convention as documenting Python code.

The doctring in Javascript files must be contained in standard
Javascript comment signs, starting with `/**` and ending with `*/`,
such as::

 /**
  * My comment starts here.
  * This is the second line prefixed with a `*`.
  * ...
  * ...
  * All the follwing line will be prefixed with a `*` followed by a space.
  * ...
  * ...
  */


Comments line prefixed by `//` will be ignored. They are reserved for source
code comments dedicated to developers.


Javscript functions docstring
-----------------------------

By default, the `function` directive describes a module-level function.

`function` directive
~~~~~~~~~~~~~~~~~~~~

Its purpose is to define the function prototype such as::

    .. function:: loadxhtml(url, data, reqtype, mode)

If any namespace is used, we should add it in the prototype for now,
until we define an appropriate directive::

    .. function:: jQuery.fn.loadxhtml(url, data, reqtype, mode)

Function parameters
~~~~~~~~~~~~~~~~~~~

We will define function parameters as a bulleted list, where the
parameter name will be backquoted and followed by its description.

Example of a javascript function docstring::

    .. function:: loadxhtml(url, data, reqtype, mode)

    cubicweb loadxhtml plugin to make jquery handle xhtml response

    fetches `url` and replaces this's content with the result

    Its arguments are:

    * `url`

    * `mode`, how the replacement should be done (default is 'replace')
       Possible values are :
           - 'replace' to replace the node's content with the generated HTML
           - 'swap' to replace the node itself with the generated HTML
           - 'append' to append the generated HTML to the node's content


Optional parameter specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Javascript functions handle arguments not listed in the function signature.
In the javascript code, they will be flagged using `/* ... */`. In the docstring,
we flag those optional arguments the same way we would define it in
Python::

    .. function:: asyncRemoteExec(fname, arg1=None, arg2=None)


