Creating a new cube from scratch using :command:`cubicweb-ctl newcube`
----------------------------------------------------------------------

Let's start by creating the cube environment in which we will develop ::

  cd ~/hg
  # use cubicweb-ctl to generate a template for the cube
  cubicweb-ctl newcube mycube  # will ask some questions, most with nice default
  # makes the cube source code managed by mercurial
  cd mycube
  hg init
  hg add .
  hg ci

If all went well, you should see the cube you just created in the list
returned by ``cubicweb-ctl list`` in the section *Available cubes*,
and if it is not the case please refer to :ref:`ConfigurationEnv`.

To reuse an existing cube, add it to the list named ``__use__`` and defined in
:file:`__pkginfo__.py`.  This variable is used for the instance packaging
(dependencies handled by system utility tools such as APT) and the usable cubes
at the time the base is created (import_erschema('MyCube') will not properly
work otherwise).

.. note::

    Please note that if you do not wish to use default directory for your cubes
    library, you should set the :envvar:`CW_CUBES_PATH` environment variable to
    add extra directories where cubes will be search, and you'll then have to use
    the option `--directory` to specify where you would like to place the source
    code of your cube:

    ``cubicweb-ctl newcube --directory=/path/to/cubes/library mycube``


.. XXX resurrect once live-server is back
.. Usage of :command:`cubicweb-ctl liveserver`
.. -------------------------------------------

.. To quickly test a new cube, you can also use the `liveserver` command for cubicweb-ctl
.. which allows to create an instance in memory (using an SQLite database by
.. default) and make it accessible through a web server ::

..   cubicweb-ctl live-server mycube

.. or by using an existing database (SQLite or Postgres)::

..   cubicweb-ctl live-server -s myfile_sources mycube
