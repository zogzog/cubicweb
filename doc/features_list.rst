=================
CubicWeb features
=================

This page  tries to resume features found in the bare cubicweb framework,
how mature and documented they are.

:code maturity (CM):

  - 0: experimental, not ready at all for production, may be killed

  - 1: draft / unsatisfying, api may change in a near future, much probably in long
       term

  - 2: good enough, api sounds good but will probably evolve a bit with more
    hindsight

  - 3: mature, backward incompatible changes unexpected (may still evolve though,
    of course)


:documentation level (DL):

  - 0: no documentation

  - 1: poor documentation

  - 2: some valuable documentation but some parts keep uncovered

  - 3: good / complete documentation


Instance configuration and maintainance
=======================================

+====================================================================+====+====+
|  FEATURE                                                           | CM | DL |
+====================================================================+====+====+
| setup - installation                                               | 2  | 3  |
| setup - environment variables                                      | 3  | 2  |
| setup - running modes                                              | 2  | 2  |
| setup - administration tasks                                       | 2  | 2  |
| setup - configuration file                                         | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| configuration - user / groups handling                             | 3  | 1  |
| configuration - site configuration                                 | 3  | 1  |
| configuration - distributed configuration                          | 2  | 1  |
| configuration - pyro                                               | 2  | 2  |
+--------------------------------------------------------------------+----+----+
| multi-sources - capabilities                                       | NA | 0  |
| multi-sources - configuration                                      | 2  | 0  |
| multi-sources - ldap integration                                   | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| usage - custom ReST markup                                         | 2  | 0  |
| usage - personal preferences                                       | 2  | 1  |
+--------------------------------------------------------------------+----+----+


Core development
================

+====================================================================+====+====+
|  FEATURE                                                           | CM | DL |
+====================================================================+====+====+
| base - concepts                                                    | NA | 3  |
| base - security model                                              | NA | 2  |
| base - database initialization                                     | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| rql - base                                                         | 2  | 2  |
| rql - write                                                        | 2  | 2  |
| rql - function                                                     | 2  | 0  |
| rql - outer joins                                                  | 2  | 1  |
| rql - aggregates                                                   | 2  | 1  |
| rql - subqueries                                                   | 2  | 0  |
+--------------------------------------------------------------------+----+----+
| schema - base                                                      | 2  | 3  |
| schema - constraints                                               | 3  | 2  |
| schema - security                                                  | 2  | 2  |
| schema - inheritance                                               | 1  | 1  |
| schema - customization                                             | 1  | 1  |
| schema - introspection                                             | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| vregistry - appobject                                              | 2  | 2  |
| vregistry - registration                                           | 2  | 2  |
| vregistry - selection                                              | 3  | 2  |
| vregistry - core selectors                                         | 3  | 3  |
| vregistry - custom selectors                                       | 2  | 1  |
| vregistry - debugging selection                                    | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| entities - interfaces                                              | 2  | ?  |
| entities - customization (dc_,...)                                 | 2  | ?  |
| entities - app logic                                               | 2  | 2  |
| entities - orm configuration                                       | 2  | 1  |
| entities - pluggable mixins                                        | 1  | 0  |
| entities - workflow                                                | 3  | 2  |
+--------------------------------------------------------------------+----+----+
| dbapi - connection                                                 | 3  | 1  |
| dbapi - data management                                            | 1  | 1  |
| dbapi - result set                                                 | 3  | 1  |
| dbapi - transaction, undo                                          | 2  | 0  |
+--------------------------------------------------------------------+----+----+
| cube - layout                                                      | 2  | 3  |
| cube - new cube                                                    | 2  | 2  |
+--------------------------------------------------------------------+----+----+
| migration - context                                                | 2  | 1  |
| migration - commands                                               | 2  | 2  |
+--------------------------------------------------------------------+----+----+
| testlib - CubicWebTC                                               | 2  | 1  |
| testlib - automatic tests                                          | 2  | 2  |
+--------------------------------------------------------------------+----+----+
| i18n - mark string                                                 | 3  | 2  |
| i18n - customize strings from other cubes / cubicweb               | 3  | 1  |
| i18n - update catalog                                              | 3  | 2  |
+--------------------------------------------------------------------+----+----+
| more - reloading tips                                              | NA | 0  |
| more - site_cubicweb                                               | 2  | ?  |
| more - adding options in configuration file                        | 3  | 0  |
| more - adding options in site configuration / preferences          | 3  | ?  |
| more - optimizing / profiling                                      | 2  | 1  |
| more - c-c plugins                                                 | 3  | 0  |
| more - crypto services                                             | 0  | 0  |
| more - massive import                                              | 2  | 0  |
| more - mime type based conversion                                  | 2  | 0  |
| more - CWCache                                                     | 1  | 0  |
+--------------------------------------------------------------------+----+----+


Web UI development
==================

+====================================================================+====+====+
|  FEATURE                                                           | CM | DL |
+====================================================================+====+====+
| base - web request                                                 | 2  | 2  |
| base - exceptions                                                  | 2  | 0  |
| base - session, authentication                                     | 1  | 0  |
| base - http caching                                                | 2  | 1  |
| base - external resources                                          | 2  | 2  |
| base - static files                                                | 2  | ?  |
| base - data sharing                                                | 2  | 2  |
| base - graphical chart customization                               | 1  | 1  |
+--------------------------------------------------------------------+----+----+
| publishing - cycle                                                 | 2  | 2  |
| publishing - error handling                                        | 2  | 1  |
| publishing - transactions                                          | NA | ?  |
+--------------------------------------------------------------------+----+----+
| controller - base                                                  | 2  | 2  |
| controller - view                                                  | 2  | 1  |
| controller - edit                                                  | 2  | 1  |
| controller - json                                                  | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| views - base                                                       | 2  | 2  |
| views - templates                                                  | 2  | 2  |
| views - boxes                                                      | 2  | 1  |
| views - components                                                 | 2  | 1  |
| views - primary                                                    | 2  | 1  |
| views - tabs                                                       | 2  | 1  |
| views - xml                                                        | 2  | 0  |
| views - text                                                       | 2  | 1  |
| views - table                                                      | 2  | 1  |
| views - plot                                                       | 2  | 0  |
| views - navigation                                                 | 2  | 0  |
| views - calendar, timeline                                         | 2  | 0  |
| views - index                                                      | 2  | 2  |
| views - breadcrumbs                                                | 2  | 1  |
| views - actions                                                    | 2  | 1  |
| views - debugging                                                  | 2  | 1  |
+--------------------------------------------------------------------+----+----+
| form - base                                                        | 2  | 1  |
| form - fields                                                      | 2  | 1  |
| form - widgets                                                     | 2  | 1  |
| form - captcha                                                     | 2  | 0  |
| form - renderers                                                   | 2  | 0  |
| form - validation error handling                                   | 2  | 0  |
| form - autoform                                                    | 2  | 2  |
| form - reledit                                                     | 2  | 0  |
+--------------------------------------------------------------------+----+----+
| facets - base                                                      | 2  | ?  |
| facets - configuration                                             | 2  | 1  |
| facets - custom facets                                             | 2  | 0  |
+--------------------------------------------------------------------+----+----+
| css - base                                                         | 1  | 1  |
| css - customization                                                | 1  | 1  |
+--------------------------------------------------------------------+----+----+
| js - base                                                          | 1  | 1  |
| js - jquery                                                        | 1  | 1  |
| js - base functions                                                | 1  | 0  |
| js - ajax                                                          | 1  | 0  |
| js - widgets                                                       | 1  | 1  |
+--------------------------------------------------------------------+----+----+
| other - page template                                              | 0  | 0  |
| other - inline doc (wdoc)                                          | 2  | 0  |
| other - magic search                                               | 2  | 0  |
| other - url mapping                                                | 1  | 1  |
| other - apache style url rewrite                                   | 1  | 1  |
| other - sparql                                                     | 1  | 0  |
| other - bookmarks                                                  | 2  | 1  |
+--------------------------------------------------------------------+----+----+


Repository development
======================

+====================================================================+====+====+
|  FEATURE                                                           | CM | DL |
+====================================================================+====+====+
| base - session                                                     | 2  | 2  |
| base - more security control                                       | 2  | 0  |
| base - debugging                                                   | 2  | 0  |
+--------------------------------------------------------------------+----+----+
| hooks - development                                                | 2  | 2  |
| hooks - abstract hooks                                             | 2  | 0  |
| hooks - core hooks                                                 | 2  | 0  |
| hooks - control                                                    | 2  | 0  |
| hooks - operation                                                  | 2  | 2  |
+--------------------------------------------------------------------+----+----+
| notification - sending email                                       | 2  | ?  |
| notification - base views                                          | 1  | ?  |
| notification - supervisions                                        | 1  | 0  |
+--------------------------------------------------------------------+----+----+
| source - storages                                                  | 2  | 0  |
| source - authentication plugins                                    | 2  | 0  |
| source - custom sources                                            | 2  | 0  |
+--------------------------------------------------------------------+----+----+
