.. -*- coding: utf-8 -*-

.. _BlogFiveMinutes:

Get a blog running in five minutes!
-----------------------------------

First install the following packages (:ref:`DebianInstallation`)::

    cubicweb, cubicweb-dev, cubicweb-blog

Then create and initialize your instance::

    cubicweb-ctl create blog myblog

And start it::

    cubicweb-ctl start -D myblog

This is it. Your blog is running. Visit http://localhost:8080 and enjoy it!

As a developer, you'll want to know more about developing new cubes and
customizing the look of your instance. This is what the next section is about.


