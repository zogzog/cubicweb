.. -*- coding: utf-8 -*-

Creation of your first instance
===============================

Instance creation
-----------------

Now that we created our cube, we can create an instance to view our
application in a web browser. To do so we will use a `all-in-one`
configuration to simplify things ::

  cubicweb-ctl create -c all-in-one mycube myinstance

.. note::
  Please note that we created a new cube for a demo purpose but
  you could have use an existing cube available in our standard library
  such as blog or person for example.

A serie of questions will be prompted to you, the default answer is usually
sufficient. You can anyway modify the configuration later on by editing
configuration files. When a user/psswd is requested to access the database
please use the login you create at the time you configured the database
(:ref:`ConfigurationPostgres`).

It is important to distinguish here the user used to access the database and the
user used to login to the cubicweb application. When an instance starts, it uses
the login/psswd for the database to get the schema and handle low level
transaction. But, when :command:`cubicweb-ctl create` asks for a manager
login/psswd of `CubicWeb`, it refers to the user you will use during the
development to administrate your web application. It will be possible, later on,
to use this user to create others users for your final web application.


Instance administration
-----------------------

start / stop
~~~~~~~~~~~~
When this command is completed, the definition of your instance is
located in :file:`~/etc/cubicweb.d/myinstance/*`. To launch it, you just type ::

  cubicweb-ctl start -D myinstance

The option `-D` specify the *debug mode* : the instance is not running in
server mode and does not disconnect from the termnial, which simplifies debugging
in case the instance is not properly launched. You can see how it looks by
visiting the URL `http://localhost:8080` (the port number depends of your
configuration). To login, please use the cubicweb administrator login/psswd you
defined when you created the instance.

To shutdown the instance, Crtl-C in the terminal window is enough.
If you did not use the option `-D`, then type ::

  cubicweb-ctl stop myinstance

This is it! All is settled down to start developping your data model...


upgrade
~~~~~~~

XXX write me

