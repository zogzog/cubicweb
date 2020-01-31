.. -*- coding: utf-8 -*-

.. _MercurialPresentation:

Introducing Mercurial
=====================

Introduction
````````````
Mercurial_ manages a distributed repository containing revisions
trees (each revision indicates the changes required to obtain the
next, and so on). Locally, we have a repository containing revisions
tree, and a working directory. It is possible
to put in its working directory, one of the versions of its local repository,
modify and then push it in its repository.
It is also possible to get revisions from another repository or to export
its own revisions from the local repository to another repository.

.. _Mercurial: http://www.selenic.com/mercurial/

In contrast to CVS/Subversion, we usually create a repository per
project to manage.

In a collaborative development, we usually create a central repository
accessible to all developers of the project. These central repository is used
as a reference. According to their needs, everyone can have a local repository,
that they will have to synchronize with the central repository from time to time.


Major commands
``````````````
* Create a local repository::

     hg clone ssh://myhost//home/src/repo

* See the contents of the local repository (graphical tool in Qt)::

     hgview

* Add a sub-directory or file in the current directory::

     hg add subdir

* Move to the working directory a specific revision (or last
  revision) from the local repository::

     hg update [identifier-revision]
     hg up [identifier-revision]

* Get in its local repository, the tree of revisions contained in a
  remote repository (this does not change the local directory)::

     hg pull ssh://myhost//home/src/repo
     hg pull -u ssh://myhost//home/src/repo # equivalent to pull + update

* See what are the heads of branches of the local repository if a `pull`
  returned a new branch::

     hg heads

* Submit the working directory in the local repository (and create a new
  revision)::

     hg commit
     hg ci

* Merge with the mother revision of local directory, another revision from
  the local respository (the new revision will be then two mothers
  revisions)::

     hg merge identifier-revision

* Export to a remote repository, the tree of revisions in its content
  local respository (this does not change the local directory)::

     hg push ssh://myhost//home/src/repo

* See what local revisions are not in another repository::

     hg outgoing ssh://myhost//home/src/repo

* See what are the revisions of a repository not found locally::

     hg incoming ssh://myhost//home/src/repo

* See what is the revision of the local repository which has been taken out
  from the working directory and amended::

     hg parent

* See the differences between the working directory and the mother revision
  of the local repository, possibly to submit them in the local repository::

     hg diff
     hg commit-tool
     hg ct


Best Practices
``````````````
* Remember to `hg pull -u` regularly, and particularly before
   a `hg commit`.

* Remember to `hg push` when your repository contains a version
  relatively stable of your changes.

* If a `hg pull -u` created a new branch head:

   1. find its identifier with `hg head`
   2. merge with `hg merge`
   3. `hg ci`
   4. `hg push`


More information
````````````````

For more information about Mercurial, please refer to the Mercurial project online documentation_.

.. _documentation: http://www.selenic.com/mercurial/wiki/

