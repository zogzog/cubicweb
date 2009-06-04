The VRegistry
--------------

The recording process on startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details of the recording process
````````````````````````````````

* par défaut on enregistre automatiquement tout les objets

* si certains objets doivent remplacer d'autres objets ou être inclus
  conditionnellement,
  - enregistrement explicite en définissant la fonction `registration_callback(vreg)`
  - appel des méthodes d'enregistrement des objets sur le vreg
.. note::
    Once the function `registration_callback(vreg)` is implemented, all the objects
    need to be explicitely registered as it disables the automatic object registering.
    
* suppression de l'ancien système quand il ne restera plus de réference au
  module registerers dans le code des cubes existants.


Examples

.. code-block:: python

   # web/views/basecomponents.py
   def registration_callback(vreg):
      vreg.register_all(globals().values(), __name__, (SeeAlsoVComponent,))
      if 'see_also' in vreg.schema:
          vreg.register(SeeAlsoVComponent)

   # goa/appobjects/sessions.py
   def registration_callback(vreg):
      vreg.register(SessionsCleaner)
      vreg.register(GAEAuthenticationManager, clear=True)
      vreg.register(GAEPersistentSessionManager, clear=True)


API d'enregistrement des objets
```````````````````````````````
.. code-block:: python

   register(obj, registryname=None, oid=None, clear=False)

   register_all(objects, modname, butclasses=())

   unregister(obj, registryname=None)

   register_and_replace(obj, replaced, registryname=None)

   register_if_interface_found(obj, ifaces, **kwargs)


Runtime objects selection
~~~~~~~~~~~~~~~~~~~~~~~~~

Defining selectors
``````````````````
The object's selector is defined by itsd `__select__` class attribute.

When two selectors are combined using the `&` operator (former `chainall`), it
means that both should return a positive score. On success, the sum of scores is returned.

When two selectors are combined using the `|` operator (former `chainfirst`), it
means that one of them should return a positive score. On success, the first
positive score is returned.

Of course you can use paren to balance expressions.


For instance, if you're selecting the primary (eg `id = 'primary'`) view (eg
`__registry__ = 'view'`) for a result set containing a `Card` entity, 2 objects
will probably be selectable:

* the default primary view (`__select__ = implements('Any')`), meaning that the object is selectable for any kind of entity type

* the specific `Card` primary view (`__select__ = implements('Card')`, meaning that the object is selectable for Card entities

Other primary views specific to other entity types won't be selectable in this
case. Among selectable objects, the implements selector will return a higher score
to the second view since it's more specific, so it will be selected as expected.


Example
````````

Le but final : quand on est sur un Blog, on veut que le lien rss de celui-ci pointe
vers les entrées de ce blog, non vers l'entité blog elle-même.

L'idée générale pour résoudre ça : on définit une méthode sur les classes d'entité
qui renvoie l'url du flux rss pour l'entité en question. Avec une implémentation
par défaut sur AnyEntity et une implémentation particulière sur Blog qui fera ce
qu'on veut.

La limitation : on est embêté dans le cas ou par ex. on a un result set qui contient
plusieurs entités Blog (ou autre chose), car on ne sait pas sur quelle entité appeler
la méthode sus-citée. Dans ce cas, on va conserver le comportement actuel (eg appel
à limited_rql)

Donc : on veut deux cas ici, l'un pour un rset qui contient une et une seule entité,
l'autre pour un rset qui contient plusieurs entité.

Donc... On a déja dans web/views/boxes.py la classe RSSIconBox qui fonctionne. Son
sélecteur ::

  class RSSIconBox(ExtResourcesBoxTemplate):
    """just display the RSS icon on uniform result set"""
    __select__ = ExtResourcesBoxTemplate.__select__ & non_final_entity()


indique qu'il prend en compte :

* les conditions d'apparition de la boite (faut remonter dans les classes parentes
  pour voir le détail)
* non_final_entity, qui filtre sur des rset contenant une liste d'entité non finale

ça correspond donc à notre 2eme cas. Reste à fournir un composant plus spécifique
pour le 1er cas ::

  class EntityRSSIconBox(RSSIconBox):
    """just display the RSS icon on uniform result set for a single entity"""
    __select__ = RSSIconBox.__select__ & one_line_rset()


Ici, on ajoute le selector one_line_rset, qui filtre sur des result set de taille 1. Il faut
savoir que quand on chaine des selecteurs, le score final est la somme des scores
renvoyés par chaque sélecteur (sauf si l'un renvoie zéro, auquel cas l'objet est
non sélectionnable). Donc ici, sur un rset avec plusieurs entités, onelinerset_selector
rendra la classe EntityRSSIconBox non sélectionnable, et on obtiendra bien la
classe RSSIconBox. Pour un rset avec une entité, la classe EntityRSSIconBox aura un
score supérieur à RSSIconBox et c'est donc bien elle qui sera sélectionnée.

Voili voilou, il reste donc pour finir tout ça :

* à définir le contenu de la méthode call de EntityRSSIconBox
* fournir l'implémentation par défaut de la méthode renvoyant l'url du flux rss sur
  AnyEntity
* surcharger cette methode dans blog.Blog


When to use selectors?
```````````````````````

Il faut utiliser les sélecteurs pour faire des choses différentes en
fonction de ce qu'on a en entrée. Dès qu'on a un "if" qui teste la
nature de `self.rset` dans un objet, il faut très sérieusement se
poser la question s'il ne vaut pas mieux avoir deux objets différent
avec des sélecteurs approprié.

Debugging
`````````
XXX explain traced_selection context manager
