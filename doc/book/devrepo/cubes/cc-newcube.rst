Creating a new cube from scratch
--------------------------------

Let's start by creating the cube environment in which we will develop ::

  cd ~/myproject
  # use cubicweb-ctl to generate a template for the cube
  # will ask some questions, most with nice default
  cubicweb-ctl newcube mycube
  # makes the cube source code managed by mercurial
  cd cubicweb-mycube
  hg init
  hg add .
  hg ci

If all went well, you should see the cube you just created in the list
returned by ``cubicweb-ctl list`` in the  *Available cubes* section.
If not, please refer to :ref:`ConfigurationEnv`.

To reuse an existing cube, add it to the list named
``__depends_cubes__`` which is defined in :file:`__pkginfo__.py`.
This variable is used for the instance packaging (dependencies handled
by system utility tools such as APT) and to find used cubes when the
database for the instance is created.
