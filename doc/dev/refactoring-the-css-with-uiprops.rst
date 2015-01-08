=========================================
Refactoring the CSSs with UI properties
=========================================

Overview
=========

Managing styles progressively became difficult in CubicWeb. The
introduction of uiprops is an attempt to fix this problem.

The goal is to make it possible to use variables in our CSSs.

These variables are defined or computed in the uiprops.py python file
and inserted in the CSS using the Python string interpolation syntax.

A quick example, put in ``uiprops.py``::

  defaultBgColor = '#eee'

and in your css::

  body { background-color: %(defaultBgColor)s; }


The good practices are:

- define a variable in uiprops to avoid repetitions in the CSS
  (colors, borders, fonts, etc.)

- define a variable in uiprops when you need to compute values
  (compute a color palette, etc.)

The algorithm implemented in CubicWeb is the following:

- read uiprops file while walk up the chain of cube dependencies: if
  cube myblog depends on cube comment, the variables defined in myblog
  will have precedence over the ones in comment

- replace the %(varname)s in all the CSSs of all the cubes

Keep in mind that the browser will then interpret the CSSs and apply
the standard cascading mechanism.
