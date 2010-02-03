
.. _Getting Data:

Getting Data
------------

You might have spotted this in the explanations about the views, to
get data, when not using a toplevel method, you will execute an RQL
query over the._cwuest. For more details about RQL, head out to the
`RQL chapter`

Basic cases
```````````
In a similiar way that you might be used to in SQL, to obtain data
from the RQL backend, you will execute an RQL command and obtain a
resultset ::

   rset = self._cw.execute(rql_command)

Then, you can use the data from the rset.

XXX complete section with examples

Use of the cache for RQL execution
``````````````````````````````````
Let's say you want to get T which is in configuration C, this translates to ::

         self._cw.execute('Any T WHERE T in_conf C, C eid "%s"' % entity.eid)

But it can also be written in a syntax that will benefit from the use
of a cache on the RQL server side. ::

          self._cw.execute('Any T WHERE T in_conf C, C eid %(x)s', {'x': entity.eid}, 'x')

The syntax tree is build once for the "generic" RQL and can be re-used
with a number of different eid. Alternativelly, some of the common
data related to an entity can be obtained from the top-level
`entity.related()` method. The above would then be translated to ::

    entity.related('in_conf', 'object')

The `related()` method makes extensive use of the cache mechanisms so
you don't have to worry about them. Additionnaly this use will get you
commonly used attributes that you will be able to use in your view
generation without having to ask the data backend.

