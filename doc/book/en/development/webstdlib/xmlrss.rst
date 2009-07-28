.. _XmlAndRss:

XML and RSS views (:mod:`cubicweb.web.views.xmlrss`)
----------------------------------------------------

*rss*
    Creates a RSS/XML view and call the view `rssitem` for each entity of
    the result set.

*rssitem*
    Create a RSS/XML view for each entity based on the results of the dublin core
    methods of the entity (`dc_*`)
