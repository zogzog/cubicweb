.. -*- coding: utf-8 -*-

.. _BlogTenMinutes:

Get a Blog running in less than ten minutes!
--------------------------------------------

You need to install the following packages (:ref:`DebianInstallation`)::

    cubicweb, cubicweb-dev, cubicweb-blog

Creation and initialization of your application by running::

    cubicweb-ctl create blog myblog

Your application is now ready to go::

    cubicweb-ctl start -D myblog

This is it. Your blog is running. Go to http://localhost:8080 and enjoy!

As a developer, you'll want to know more about how to develop new
cubes and cutomize the look of your application and this is what the next
section is about.


