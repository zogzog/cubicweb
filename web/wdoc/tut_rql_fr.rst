.. -*- coding: utf-8 -*-

Apprenons RQL par la pratique...

.. contents::


Introduction
------------

RQL est assez proche par sa syntaxe et ses principes du langage de requête des
bases de données relationnelles SQL. Il est cependant plus intuitif et mieux
adapté pour faire des recherches avancées sur des bases de données structurées
par un schéma de données. On retiendra les points suivants :

* RQL est un langage mettant l'accent sur le parcours de relations.
* Les attributs sont considérés comme des cas particuliers de relations.
* RQL s'inspire de SQL mais se veut plus haut niveau.
* Une connaissance du schéma définissant l'application est nécessaire.

Pour s'en servir, il convient de connaître les règles de base du langage RQL,
mais surtout d'avoir une bonne vision du schéma de données de l'application. Ce
schéma est toujours disponible dans l'application par le lien `schéma`, dans la
boîte affichée en cliquant sur le lien de l'utilisateur connectée (en haut à droite).
Vous pouvez également le voir en cliquant ici_.

.. _ici: schema


Un peu de théorie
-----------------

Variables et typage
~~~~~~~~~~~~~~~~~~~
Les entités et valeurs à parcourir et / ou séléctionner sont représentées dans
la requête par des *variables* qui doivent être écrites en majuscule

Les types possibles pour chaque variable sont déduits à partir du schéma en
fonction des contraintes présentes dans la requête.

On peut contraindre les types possibles pour une variable à l'aide de la
relation spéciale `is`.

Types de bases
~~~~~~~~~~~~~~
* `String` (litéral: entre doubles ou simples quotes)
* `Int`, `Float` (le séparateur étant le '.')
* `Date`, `Datetime`, `Time` (litéral: chaîne YYYY/MM/DD[ hh:mm] ou mots-clés
  `TODAY` et `NOW`)
* `Boolean` (mots-clés `TRUE` et `FALSE`)
* mot-clé `NULL`

Opérateurs
~~~~~~~~~~
* Opérateurs logiques : `AND`, `OR`, `,`
* Opérateurs mathématiques: `+`, `-`, `*`, `/`
* Operateur de comparaisons: `=`, `<`, `<=`, `>=`, `>`, `~=`, `LIKE`, `IN`

  * L'opérateur `=` est l'opérateur par défaut

  * L'opérateur `LIKE` / `~=` permet d'utiliser le caractère `%` dans une chaine
    de caractère pour indiquer que la chaîne doit commencer ou terminer par un
    préfix/suffixe ::
    
      Any X WHERE X nom ~= 'Th%'
      Any X WHERE X nom LIKE '%lt'

  * L'opérateur `IN` permet de donner une liste de valeurs possibles ::

      Any X WHERE X nom IN ('chauvat', 'fayolle', 'di mascio', 'thenault')

Grammaire des requêtes de recherche
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

  [DISTINCT] <type d'entité> V1(, V2)*
  [GROUPBY V1(, V2)*]  [ORDERBY <orderterms>]
  [WHERE <restriction>] 
  [LIMIT <value>] [OFFSET <value>]

:type d'entité:
  Type de la ou des variables séléctionnées. 
  Le type spécial `Any`, revient à ne pas spécifier de type.
:restriction:
  liste des relations à parcourir sous la forme 
    `V1 relation V2|<valeur constante>`
:orderterms:
  Définition de l'ordre de sélection : variable ou n° de colonne suivie de la
  méthode de tri (`ASC`, `DESC`), ASC étant la valeur par défaut

note pour les requêtes groupées (i.e. avec une clause `GROUPBY`) :
toutes les variables sélectionnées doivent être soit groupée soit
aggrégée


Schéma
------

Nous supposerons dans la suite de ce document que le schéma de l'application est
le suivant. Les différentes entités disponibles sont :

:Personne:
  ::

	nom    (String, obligatoire) 
	datenaiss (Date)


:Societe:
  ::

	nom   (String)


:Note:
  ::

	diem (Date)
	type (String)


Et les relations entre elles : ::

	Person  travaille_pour Societe
	Person  evaluee_par    Note
	Societe evaluee_par    Note


Méta-données
~~~~~~~~~~~~
Tous les types d'entités ont les métadonnées suivantes :

* `eid (Int)`, permettant d'identifier chaque instance de manière unique
* `creation_date (Datetime)`, date de création de l'entité
* `modification_date (Datetime)`, date de dernière modification de l'entité

* `created_by (EUser)`, relation vers l'utilisateur ayant créé l'entité

* `owned_by (EUser)`, relation vers le où les utilisateurs considérés comme 
  propriétaire de l'entité, par défaut le créateur de l'entité

* `is (Eetype)`, relation spéciale permettant de spécifier le
  type d'une variable. 

Enfin, le schéma standard d'un utilisateur est le suivant :

:EUser:
  ::

	login  	  (String, obligatoire)
	password  (Password)
	firstname (String)
	surname   (String)


L'essentiel
-----------
0. *Toutes les personnes* ::
   
      Personne X

   ou ::

      Any X WHERE X is Personne


1. *La societé nommé Logilab* ::

     Societe S WHERE S nom 'Logilab'


2. *Toutes les entités ayant un attribut nom commençant par 'Log'* ::

     Any S WHERE S nom LIKE 'Log%'

   ou ::

      Any S WHERE S nom ~= 'Log%'

   Cette requête peut renvoyer des entités de type personne et de type
   société.


3. *Toutes les personnes travaillant pour la société nommé Logilab* ::

      Personne P WHERE P travaille_pour S, S nom "Logilab"

   ou ::

      Personne P WHERE P travaille_pour S AND S nom "Logilab"


4. *Les societés nommées Caesium ou Logilab* ::

      Societe S WHERE S nom IN ('Logilab','Caesium')

   ou ::

      Societe S WHERE S nom 'Logilab' OR S nom 'Caesium'


5. *Toutes les societés sauf celles nommées Caesium ou Logilab* ::

      Societe S WHERE NOT S nom IN ('Logilab','Caesium')

   ou ::

      Societe S WHERE NOT S nom 'Logilab' AND NOT S nom 'Caesium'


6. *Les entités évalués par la note d'identifiant 43* ::

      Any X WHERE X evaluee_par N, N eid 43


7. *Toutes les personnes triés par date de naissance dans l'ordre antechronologique* ::
   
      Personne X ORDERBY D DESC WHERE X datenaiss D

   On note qu'il faut définir une variable et la séléctionner pour s'en
   servir pour le tri. 


8. *Nombre de personne travaillant pour chaque société* ::
   
      Any S, COUNT(X) GROUPBY S WHERE X travaille_pour S

   On note qu'il faut définir une variable pour s'en servir pour le
   groupage. De plus les variables séléctionnée doivent être groupée
   (mais les variables groupées ne doivent pas forcément être sélectionnées).


   
Exemples avancés
----------------
0. *Toutes les personnes dont le champ nom n'est pas spécifié (i.e NULL)* ::

      Personne P WHERE P nom NULL


1. *Toutes les personnes ne travaillant pour aucune société* ::

      Personne P WHERE NOT p travaille_pour S


2. *Toutes les sociétés où la personne nommée toto ne travaille pas* ::

      Societe S WHERE NOT P travaille_pour S , P nom 'toto'


3. *Toutes les entités ayant été modifiées entre aujourd'hui et hier* ::

      Any X WHERE X modification_date <= TODAY, X modification_date >= TODAY - 1


4. *Toutes les notes n'ayant pas de type et à effectuer dans les 7 jours, triées par date* ::

      Any N, D where N is Note, N type NULL, N diem D, N diem >= TODAY,
      N diem < today + 7 ORDERBY D


5. *Les personnes ayant un homonyme (sans doublons)* ::

      DISTINCT Personne X,Y where X nom NX, Y nom NX

   ou mieux (sans avoir (Xeid, Yeid) et (Yeid, Xeid) dans les résultats) ::

      Personne X,Y where X nom NX, Y nom NX, X eid XE, Y eid > XE
