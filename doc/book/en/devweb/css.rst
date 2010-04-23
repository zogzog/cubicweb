.. -*- coding: utf-8 -*-

CSS Stylesheet
---------------
Conventions
~~~~~~~~~~~

XXX external_resources variable
    naming convention
    request.add_css


Extending / overriding existing styles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We cannot modify the order in which the application is reading the CSS. In
the case we want to create new CSS style, the best is to define it a in a new
CSS located under ``myapp/data/`` and use those new styles while writing
customized views and templates.

If you want to modify an existing CSS styling property, you will have to use
``!important`` declaration to override the existing property. The application
apply a higher priority on the default CSS and you can not change that.
Customized CSS will not be read first.


CubicWeb stylesheets
~~~~~~~~~~~~~~~~~~~~
XXX explain diffenrent files and main classes
