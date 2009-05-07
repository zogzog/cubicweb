
Available cubes
---------------

An application is based on several basic cubes. In the set of available
basic cubes we can find for example :

Base entity types
~~~~~~~~~~~~~~~~~
* addressbook_: PhoneNumber and PostalAddress
* card_: Card, generic documenting card
* event_: Event (define events, display them in calendars)
* file_: File (to allow users to upload and store binary or text files)
* link_: Link (to collect links to web resources)
* mailinglist_: MailingList (to reference a mailing-list and the URLs
  for its archives and its admin interface)
* person_: Person (easily mixed with addressbook)
* task_: Task (something to be done between start and stop date)
* zone_: Zone (to define places within larger places, for example a
  city in a state in a country)


Classification
~~~~~~~~~~~~~~
* folder_: Folder (to organize things but grouping them in folders)
* keyword_: Keyword (to define classification schemes)
* tag_: Tag (to tag anything)

Other features
~~~~~~~~~~~~~~
* basket_: Basket (like a shopping cart)
* blog_: a blogging system uxing Blog and BlogEntry entity types
* comment_: system to attach comment threads to entities)
* email_: archiving management for emails (`Email`, `Emailpart`,
  `Emailthread`), trigger action in cubicweb through email





.. _addressbook: http://www.cubicweb.org/project/cubicweb-addressbook
.. _basket: http://www.cubicweb.org/project/cubicweb-basket
.. _card: http://www.cubicweb.org/project/cubicweb-card
.. _blog: http://www.cubicweb.org/project/cubicweb-blog
.. _comment: http://www.cubicweb.org/project/cubicweb-comment
.. _email: http://www.cubicweb.org/project/cubicweb-email
.. _event: http://www.cubicweb.org/project/cubicweb-event
.. _file: http://www.cubicweb.org/project/cubicweb-file
.. _folder: http://www.cubicweb.org/project/cubicweb-folder
.. _keyword: http://www.cubicweb.org/project/cubicweb-keyword
.. _link: http://www.cubicweb.org/project/cubicweb-link
.. _mailinglist: http://www.cubicweb.org/project/cubicweb-mailinglist
.. _person: http://www.cubicweb.org/project/cubicweb-person
.. _tag: http://www.cubicweb.org/project/cubicweb-tag
.. _task: http://www.cubicweb.org/project/cubicweb-task
.. _zone: http://www.cubicweb.org/project/cubicweb-zone

To declare the use of a component, once installed, add the name of the component
to the variable `__use__` in the file `__pkginfo__.py` of your own component.

.. note::
  The listed cubes above are available as debian-packages on `CubicWeb's forge`_.

.. _`CubicWeb's forge`: http://www.cubicweb.org/project?vtitle=All%20cubicweb%20projects
