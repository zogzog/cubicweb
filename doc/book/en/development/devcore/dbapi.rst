

API Python/RQL
~~~~~~~~~~~~~~

The Python API developped to interface with RQL is inspired from the standard db-api,
with a Connection object having the methods cursor, rollback and commit essentially.
The most important method is the `execute` method of a cursor :

`execute(rqlstring, args=None, eid_key=None, build_descr=True)`

:rqlstring: the RQL query to execute (unicode)
:args: if the query contains substitutions, a dictionary containing the values to use
:eid_key:
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
