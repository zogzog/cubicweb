

Templates
---------

*Templates* are specific views that do not depend on a result set. The basic
class `Template` (`cubicweb.common.view`) is derived from the class `View`.

To build a HTML page, a *main template* is used. In general, the template of
identifier `main` is the one to use (it is not used in case an error is raised or for
the login form for example). This template uses other templates in addition
to the views which depends on the content to generate the HTML page to return.

A *template* is responsible for:

1. executing RQL query of data to render if necessary
2. identifying the view to use to render data if it is not specified
3. composing the HTML page to return

You will find out more about templates in :ref:`templates`.
