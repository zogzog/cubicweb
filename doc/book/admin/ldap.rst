.. _LDAP:

LDAP integration
================

Overview
--------

Using LDAP as a source for user credentials and information is quite
easy. The most difficult part lies in building an LDAP schema or
using an existing one.

At cube creation time, one is asked if more sources are wanted. LDAP
is one possible option at this time. Of course, it is always possible
to set it up later using the `CWSource` entity type, which we discuss
there.

It is possible to add as many LDAP sources as wanted, which translates
in as many `CWSource` entities as needed.

The general principle of the LDAP source is, given a proper
configuration, to create local users matching the users available in
the directory and deriving local user attributes from directory users
attributes. Then a periodic task ensures local user information
synchronization with the directory.

Users handled by such a source should not be edited directly from
within the application instance itself. Rather, updates should happen
at the LDAP server level.

Credential checks are _always_ done against the LDAP server.

.. Note::

  There are currently two ldap source types: the older `ldapuser` and
  the newer `ldapfeed`. The older will be deprecated anytime soon, as
  the newer has now gained all the features of the old and does not
  suffer from some of its illnesses.

  The ldapfeed creates real `CWUser` entities, and then
  activate/deactivate them depending on their presence/absence in the
  corresponding LDAP source. Their attribute and state
  (activated/deactivated) are hence managed by the source mechanism;
  they should not be altered by other means (as such alterations may
  be overridden in some subsequent source synchronisation).


Configuration of an LDAPfeed source
-----------------------------------

Additional sources are created at cube creation time or later through the
user interface.

Configure an `ldapfeed` source from the user interface under `Manage` then
`data sources`:

* At this point `type` has been set to `ldapfeed`.

* The `parser` attribute shall be set to `ldapfeed`.

* The `url` attribute shall be set to an URL such as ldap://ldapserver.domain/.

* The `configuration` attribute contains many options. They are described in
  detail in the next paragraph.


Options of an LDAPfeed source
-----------------------------

Let us enumerate the options by categories (LDAP server connection,
LDAP schema mapping information).

LDAP server connection options:

* `auth-mode`, (choices are simple, cram_md5, digest_md5, gssapi, support
  for the later being partial as of now)

* `auth-realm`, realm to use when using gssapi/kerberos authentication

* `data-cnx-dn`, user dn to use to open data connection to the ldap (eg
  used to respond to rql queries)

* `data-cnx-password`, password to use to open data connection to the
  ldap (eg used to respond to rql queries)

If the LDAP server accepts anonymous binds, then it is possible to
leave data-cnx-dn and data-cnx-password empty. This is, however, quite
unlikely in practice. Beware that the LDAP server might hide attributes
such as "userPassword" while the rest of the attributes remain visible
through an anonymous binding.

LDAP schema mapping options:

* `user-base-dn`, base DN to lookup for users

* `user-scope`, user search scope (valid values: "BASE", "ONELEVEL",
  "SUBTREE")

* `user-classes`, classes of user (with Active Directory, you want to
  say "user" here)

* `user-filter`, additional filters to be set in the ldap query to
  find valid users

* `user-login-attr`, attribute used as login on authentication (with
  Active Directory, you want to use "sAMAccountName" here)

* `user-default-group`, name of a group in which ldap users will be by
  default. You can set multiple groups by separating them by a comma

* `user-attrs-map`, map from ldap user attributes to cubicweb
  attributes (with Active Directory, you want to use
  sAMAccountName:login,mail:email,givenName:firstname,sn:surname)


Other notes
-----------

* Cubicweb is able to start if ldap cannot be reached, even on
  cubicweb-ctl start ... If some source ldap server cannot be used
  while an instance is running, the corresponding users won't be
  authenticated but their status will not change (e.g. they will not
  be deactivated)

* The user-base-dn is a key that helps cubicweb map CWUsers to LDAP
  users: beware updating it

* When a user is removed from an LDAP source, it is deactivated in the
  CubicWeb instance; when a deactivated user comes back in the LDAP
  source, it (automatically) is activated again

* You can use the :class:`CWSourceHostConfig` to have variants for a source
  configuration according to the host the instance is running on. To do so
  go on the source's view from the sources management view.
