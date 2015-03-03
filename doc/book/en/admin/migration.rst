.. -*- coding: utf-8 -*-

Migrating cubicweb instances - benefits from a distributed architecture
=======================================================================

Migrate apache & cubicweb
-------------------------

**Aim** : do the migration for N cubicweb instances hosted on a server to another with no downtime.

**Prerequisites** : have an explicit definition of the database host (not default or localhost). In our case, the database is hosted on another host.

**Steps** :

1. *on new machine* : install your environment (*pseudocode*) ::

     apt-get install cubicweb cubicweb-applications apache2

2. *on old machine* : copy your cubicweb and apache configuration to the new machine ::

    scp /etc/cubicweb.d/ newmachine:/etc/cubicweb.d/
    scp /etc/apache2/sites-available/ newmachine:/etc/apache2/sites-available/

3. *on new machine* : start your instances ::

     cubicweb start

4. *on new machine* : enable sites and modules for apache and start it, test it using by modifying your /etc/host file.

5. change dns entry from your oldmachine to newmachine

6. shutdown your *old machine* (if it doesn't host other services or your database)

7. That's it.

**Possible enhancements** : use right from the start a pound server behind your apache, that way you can add backends and smoothily migrate by shuting down backends that pound will take into account.


