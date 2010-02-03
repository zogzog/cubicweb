

API Python/RQL
~~~~~~~~~~~~~~

The Python API developped to interface with RQL is inspired from the standard db-api,
with a Connection object having the methods cursor, rollback and commit essentially.
The most important method is the `execute` method of a cursor :

`execute(rqlstring, args=None, cachekey=None, build_descr=True)`

:rqlstring: the RQL query to execute (unicode)
:args: if the query contains substitutions, a dictionary containing the values to use
:cachekey:
   an implementation detail of the RQL cache implies that if a substitution
   is used to introduce an eid *susceptible to raise the ambiguities in the query
   type resolution*, then we have to specify the corresponding key in the dictionary
   through this argument


The `Connection` object owns the methods `commit` and `rollback`. You *should
never need to use them* during the development of the web interface based on
the *CubicWeb* framework as it determines the end of the transaction depending
on the query execution success.

.. note::
  While executing update queries (SET, INSERT, DELETE), if a query generates
  an error related to security, a rollback is automatically done on the current
  transaction.

Executing RQL queries from a view or a hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you're within code of the web interface, the db-api like connexion is
handled by the request object. You should not have to access it directly, but
use the `execute` method directly available on the request, eg:

   rset = self._cw.execute(rqlstring, kwargs)

Similarly, on the server side (eg in hooks), there is no db-api connexion (since
you're directly inside the data-server), so you'll have to use the execute method
of the session object.


Important note about proper usage of .execute
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's say you want to get T which is in configuration C, this translates to:

.. sourcecode:: python

   self._cw.execute('Any T WHERE T in_conf C, C eid %s' % entity.eid)

But it can also be written in a syntax that will benefit from the use
of a cache on the RQL server side:

.. sourcecode:: python

   self._cw.execute('Any T WHERE T in_conf C, C eid %(x)s', {'x': entity.eid}, 'x')

Beside proper usage of the `args` argument, notice the latest argument: this is what's called
the cache key. The cache key should be either a string or a tuple containing the names of keys
in args which are referencing eids. *YOU MUST SET THIS PROPERLY* if you don't want weird result
on queries which have ambigous solutions deambiguified by specifing an eid. So the good habit is:
*always put in the cache key all eid keys*.

The syntax tree is build once for the "generic" RQL and can be re-used
with a number of different eid.

Alternativelly, some of the common data related to an entity can be obtained from
the top-level `entity.related()` method (which is used under the hood by the orm
when you use attribute access notation on an entity to get a relation. The above
would then be translated to:

.. sourcecode:: python

   entity.related('in_conf', 'object')

The `related()` method, as more generally others orm methods, makes extensive use
of the cache mechanisms so you don't have to worry about them. Additionnaly this
use will get you commonly used attributes that you will be able to use in your
view generation without having to ask the data backend.

