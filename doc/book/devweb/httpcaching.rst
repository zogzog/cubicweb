HTTP cache management
=====================

.. automodule:: cubicweb.web.httpcache

Cache policies
--------------
.. autoclass:: cubicweb.web.httpcache.NoHTTPCacheManager
.. autoclass:: cubicweb.web.httpcache.MaxAgeHTTPCacheManager
.. autoclass:: cubicweb.web.httpcache.EtagHTTPCacheManager
.. autoclass:: cubicweb.web.httpcache.EntityHTTPCacheManager

Exception
---------
.. autoexception:: cubicweb.web.httpcache.NoEtag

Helper functions
----------------
.. autofunction:: cubicweb.web.httpcache.set_http_cache_headers

.. NOT YET AVAILABLE IN STABLE autofunction:: cubicweb.web.httpcache.lastmodified
