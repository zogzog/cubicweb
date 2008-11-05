Qu'est-ce que ``LAX`` ?
=======================

``LAX`` (Logilab Application engine eXtension) est un framework 
d'application web qui facilite les développements faits pour
``Google AppEngine``.

``LAX`` est un portage de la partie web de la plate-forme
applicative développée par Logilab depuis 2001. Cette plate-forme 
publie des données que la partie stockage tire de bases SQL, 
d'annuaires LDAP et de systèmes de gestion de version. Depuis mai 
2008, elle fonctionne sur le "datastore" de ``Google AppEngine``.

``LAX`` est pour le moment en version alpha.

Django/GAE vs. LAX/GAE
=======================

NotImplementedError()


Téléchargement des sources
==========================

- Les sources de ``Google AppEngine`` peuvent être obtenues à l'adresse
  suivante : http://code.google.com/appengine/downloads.html

- Les sources de ``LAX`` se trouvent à l'adresse suivante :
  http://lax.logilab.org/


Installation
============

Les sources de ``Google AppEngine`` doivent être décompressées et le
répertoire `google` qui s'y trouve doit être accessible par la variable
d'environnement ``PYTHONPATH``. Correctement définir le ``PYTHONPATH`` 
n'est pas nécessaire pour le lancement de l'application elle-même mais 
pour l'utilisation des scripts fournis par ``LAX`` ou pour l'exécution 
des tests unitaires.

Une fois décompactée, l'archive ``lax-0.1.0-alpha.tar.gz``, on obtient
l'arborescence suivante::
  
  .
  |-- app.yaml
  |-- custom.py
  |-- data
  |-- cubicweb/
  |-- i18n/
  |-- logilab/
  |-- main.py
  |-- mx/
  |-- rql/
  |-- schema.py
  |-- simplejson/
  |-- tools/
  |   |-- generate_schema_img.py
  |   `-- i18ncompile.py
  |-- views.py
  |-- yams/
  `-- yapps/

  
On retrouve le squelette d'une application web de ``Google AppEngine``
(fichiers ``app.yaml``, ``main.py``en particulier) avec les dépendances
supplémentaires nécessaires à l'utilisation du framework ``LAX``


Lancement de l'application de base
==================================

python /path/to/google_appengine/dev_appserver.py /path/to/lax


