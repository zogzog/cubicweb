.. -*- coding: utf-8 -*-

.. _Part4:

----------
Appendixes
----------

The following chapters are reference material.

.. toctree::
   :maxdepth: 1
   :numbered:

   faq
   cookbook
   cubicweb-ctl
   rql/index
   mercurial
   depends

(X)HTML tricks to apply
-----------------------

Some web browser (Firefox for example) are not happy with empty `<div>`
(by empty we mean that there is no content in the tag, but there
could be attributes), so we should always use `<div></div>` even if
it is empty and not use `<div/>`.
