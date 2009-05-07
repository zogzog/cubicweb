Creating a new cube from scratch using :command:`cubicweb-ctl newcube`
----------------------------------------------------------------------

Let's start by creating the cube environment in which we will develop ::

  cd ~/hg

  cubicweb-ctl newcube mycube

  # answer questions 
  hg init moncube
  cd mycube
  hg add .
  hg ci

If all went well, you should see the cube you just create in the list
returned by `cubicweb-ctl list` in the section *Available components*,
and if it is not the case please refer to :ref:`ConfigurationEnv`.

To use a cube, you have to list it in the variable ``__use__``
of the file ``__pkginfo__.py`` of the instance.
This variable is used for the instance packaging (dependencies
handled by system utility tools such as APT) and the usable cubes
at the time the base is created (import_erschema('MyCube') will
not properly work otherwise).

.. note::
    Please note that if you do not wish to use default directory
    for your cubes library, then you want to use the option
    --directory to specify where you would like to place
    the source code of your cube:
    ``cubicweb-ctl newcube --directory=/path/to/cubes/library cube_name``

    
Usage of :command:`cubicweb-ctl liveserver`
-------------------------------------------

To quickly test a new cube, you can also use the `liveserver` command for cubicweb-ctl
which allows to create an instance in memory (using an SQLite database by 
default) and make it accessible through a web server ::

  cubicweb-ctl live-server mycube

or by using an existing database (SQLite or Postgres)::

  cubicweb-ctl live-server -s myfile_sources mycube
