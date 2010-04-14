

API Python/RQL
~~~~~~~~~~~~~~

The Python API developped to interface with RQL is inspired from the standard db-api,
with a Connection object having the methods cursor, rollback and commit essentially.
The most important method is the `execute` method of a cursor.

.. sourcecode:: python

  execute(rqlstring, args=None, cachekey=None, build_descr=True)

:rqlstring: the RQL query to execute (unicode)
:args: if the query contains substitutions, a dictionary containing the values to use
:cachekey:
   an implementation detail of the RQL cache implies that if a substitution
   is used to introduce an eid *susceptible to raise the ambiguities in the query
   type resolution*, then we have to specify the corresponding key in the dictionary
   through this argument


The `Connection` object owns the methods `commit` and `rollback`. You
*should never need to use them* during the development of the web
interface based on the *CubicWeb* framework as it determines the end
of the transaction depending on the query execution success. They are
however useful in other contexts such as tests.

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

But it must be written in a syntax that will benefit from the use
of a cache on the RQL server side:

.. sourcecode:: python

   self._cw.execute('Any T WHERE T in_conf C, C eid %(x)s', {'x': entity.eid})

The syntax tree is built once for the "generic" RQL and can be re-used
with a number of different eids. There rql IN operator is an exception
to this rule.

.. sourcecode:: python

   self._cw.execute('Any T WHERE T in_conf C, C name IN (%s)' % ','.join(['foo', 'bar']))

Alternativelly, some of the common data related to an entity can be
obtained from the `entity.related()` method (which is used under the
hood by the orm when you use attribute access notation on an entity to
get a relation. The initial request would then be translated to:

.. sourcecode:: python

   entity.related('in_conf', 'object')

Additionnaly this benefits from the fetch_attrs policy eventually
defined on the class element, which says which attributes must be also
loaded when the entity is loaded through the orm.
