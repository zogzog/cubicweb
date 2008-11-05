Les données concernant l'utilisateur sont paramétrables par la page
d'édition de l'utilisateur. Vous pouvez accéder à celle ci par le menu
déroulant apparaissant en cliquant sur le lien en haut à droite de la
fenêtre de l'application, dont l'intitulé est votre login. Dans ce
menu, cliquez sur "information personnelles" pour modifier vos données
personnelles (y compris le mot de passe d'accès à l'application).

Chaque utilisateur peut également personaliser l'apparence du site via le lien
"préférences utilisateur"_. Ce formulaire permet notamment de configurer les
boîtes qui seront affichées, leur ordre, etc...

L'administrateur possède quant à lui un menu "configuration du site" qui reprend l'ensemble des préférences utilisateurs mais les applique par défaut au site.


Les types de préférences
========================

- navigation: détermine des caractériques plus personnelles pour l'ergonomie liée à la taille de votre écran (taille des champs d'entrées, nombre d'éléments à afficher dans des listes, ...)
- propriétés génériques de l'interface: détermine essentiellement la localisation de l'application avec des formats d'affichages particulier (champ date et heure).
- boîtes: éléments dynamiques et optionnels installés par les composants disponibles au sein de l'application.
- composants: éléments permettant l'usage d'une navigation plus évoluée
- composants contextuels: possibilité d'agir sur les comportements par défaut de l'application.

Changement de la langue
-----------------------
Dans l'onglet **ui -> ui.language**, choisissez la langue voulue

Changement de l'outil d'édition en ligne
----------------------------------------
Il est possible de choisir le format de balisage par défaut pour les notes. Par défaut, le format html est proposé pour les débutants avec la possibilité d'utiliser un éditeur en ligne.

Si vous êtes dans ce cas, vérifiez les deux entrées suivantes:

- **ui -> ui.default-text-format** à HTML
- **ui -> ui.fckeditor** à 'yes'

Usage avancé de RQL
-------------------
Il est possible d'afficher les requêtes RQL_ en jeu pour l'affichage d'une page en activant une barre d'entrée spécifique:

- **components -> rql input box** à 'yes'

Il est alors possible d'éditer et de relancer toute requête

.. _"préférences utilisateur: myprefs
.. _RQL: doc/tut_rql
.. image:: doc/images/userprefs
