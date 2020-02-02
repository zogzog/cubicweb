======================
Continuous Integration
======================

Jenkins
=======

A public instance of jenkins is used to test CubicWeb and its cubes :

* https://jenkins.logilab.org/
* https://jenkins.logilab.org/view/Cubes/
* https://jenkins.logilab.org/view/CubicWeb/

Badges
------

Badges are exported to be displayed on various pages. Here is an example :

.. raw:: html

  <table><tr><td>
  <a href='https://jenkins.logilab.org/job/cubicweb-default/'><img src='https://jenkins.logilab.org/buildStatus/icon?job=cubicweb-default'></a></td>

  <td>&nbsp;is the status for the draft head on branch default of the <a href="https://hg.logilab.org/review/cubicweb">review repository</a></td></tr></table>

Adding a project to Jenkins
---------------------------

Adding a project to jenkins needs to be done through the
`jenkins-jobs project <https://hg.logilab.org/master/jenkins-jobs/file/tip/README.rst>`_.

Changes to the configuration are implemented by the
`jenkins-jobs job <https://jenkins.logilab.org/job/jenkins-jobs/>`_.
