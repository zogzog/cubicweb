.. _XmlAndRss:

XML and RSS views (:mod:`cubicweb.web.views.xmlrss`)
----------------------------------------------------

Overview
+++++++++

*rss*
    Creates a RSS/XML view and call the view `rssitem` for each entity of
    the result set.

*rssitem*
    Create a RSS/XML view for each entity based on the results of the dublin core
    methods of the entity (`dc_*`)


RSS Channel Example
++++++++++++++++++++

Assuming you have several blog entries, click on the title of the
search box in the left column. A larger search box should appear. Enter::

   Any X ORDERBY D WHERE X is BlogEntry, X creation_date D

and you get a list of blog entries.

Click on your login at the top right corner. Chose "user preferences",
then "boxes", then "possible views box" and check "visible = yes"
before validating your changes.

Enter the same query in the search box and you will see the same list,
plus a box titled "possible views" in the left column. Click on
"entityview", then "RSS".

You just applied the "RSS" view to the RQL selection you requested.

That's it, you have a RSS channel for your blog.

Try again with::

    Any X ORDERBY D WHERE X is BlogEntry, X creation_date D,
    X entry_of B, B title "MyLife"

Another RSS channel, but a bit more focused.

A last one for the road::

    Any C ORDERBY D WHERE C is Comment, C creation_date D LIMIT 15

displayed with the RSS view, that's a channel for the last fifteen
comments posted.

[WRITE ME]

* show that the RSS view can be used to display an ordered selection
  of blog entries, thus providing a RSS channel

* show that a different selection (by category) means a different channel



