LDAP integration
================

Overview
--------

Using LDAP as a source for user credentials and information is quite
easy. The most difficult part lies in building an LDAP schema or
using an existing one.

At cube creation time, one is asked if more sources are wanted. LDAP
is one possible option at this time. Of course, it is always possible
to set it up later in the `source` configuration file, which we
discuss there.

It is possible to add as many LDAP sources as wanted, which translates
in as many [ldapxxx] sections in the `source` configuration file.

The general principle of the LDAP source is, given a proper
configuration, to create local users matching the users available in
the directory, deriving local user attributes from directory users
attributes. Then a periodic task ensures local user information
synchronization with the directory.

Credential checks are _always_ done against the LDAP server.

The base functionality for this is in
cubicweb/server/sources/ldapuser.py.

Configurations options
----------------------

Let us enumerate the options (but please keep in mind that the
authoritative source for these is in the aforementioned python
module), by categories (LDAP server connection, LDAP schema mapping
information, LDAP source internal configuration).

LDAP server connection options:

* host: may contain port information using <host>:<port> notation.
* protocol (choices are ldap, ldaps, ldapi)
* auth-mode (choices are simple, cram_md5, digest_md5, gssapi, support
  for the later being partial as of now)
* auth-realm, realm to use when using gssapi/kerberos authentication
* data-cnx-dn, user dn to use to open data connection to the ldap (eg
  used to respond to rql queries)
* data-cnx-password, password to use to open data connection to the
  ldap (eg used to respond to rql queries)

LDAP schema mapping:

* user-base-dn, base DN to lookup for users
* user-scope, user search scope
* user-classes, classes of user
* user-attrs-map, map from ldap user attributes to cubicweb attributes
* user-login-attr, attribute used as login on authentication

LDAP source internal configuration:

* user-default-group, name of a group in which ldap users will be by
  default. You can set multiple groups by separating them by a comma
* synchronization-interval, interval between synchronization with the
  ldap directory in seconds (default to once a day)
* life time of query cache in minutes (default to two hours).
