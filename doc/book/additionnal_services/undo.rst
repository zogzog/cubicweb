Undoing changes in CubicWeb
---------------------------

Many desktop applications offer the possibility for the user to
undo its last changes : this *undo feature* has now been
integrated into the CubicWeb framework. This document will
introduce you to the *undo feature* both from the end-user and the
application developer point of view.

But because a semantic web application and a common desktop
application are not the same thing at all, especially as far as
undoing is concerned, we will first introduce *what* is the *undo
feature* for now.

What's *undoing* in a CubicWeb application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What is an *undo feature* is quite intuitive in the context of a
desktop application. But it is a bit subtler in the context of a
Semantic Web application. This section introduces some of the main
differences between a classical desktop and a Semantic Web
applications to keep in mind in order to state precisely *what we
want*.

The notion transactions
```````````````````````

A CubicWeb application acts upon an *Entity-Relationship* model,
described by a schema. This allows to ensure some data integrity
properties. It also implies that changes are made by all-or-none
groups called *transactions*, such that the data integrity is
preserved whether the transaction is completely applied *or* none
of it is applied.

A transaction can thus include more actions than just those
directly required by the main purpose of the user.  For example,
when a user *just* writes a new blog entry, the underlying
*transaction* holds several *actions* as illustrated below :

* By admin on 2012/02/17 15:18 - Created Blog entry : Torototo

  #. Created Blog entry : Torototo
  #. Added relation : Torototo owned by admin
  #. Added relation : Torototo blog entry of Undo Blog
  #. Added relation : Torototo in state draft (draft)
  #. Added relation : Torototo created by admin

Because of the very nature (all-or-none) of the transactions, the
"undoable stuff" are the transactions and not the actions !

Public and private actions within a transaction
```````````````````````````````````````````````

Actually, within the *transaction* "Created Blog entry :
Torototo", two of those *actions* are said to be *public* and
the others are said to be *private*. *Public* here means that the
public actions (1 and 3) were directly requested by the end user ;
whereas *private* means that the other actions (2, 4, 5) were
triggered "under the hood" to fulfill various requirements for the
user operation (ensuring integrity, security, ... ).

And because quite a lot of actions can be triggered by a "simple"
end-user request, most of which the end-user is not (and does not
need or wish to be) aware, only the so-called public actions will
appear [1]_ in the description of the an undoable transaction.

* By admin on 2012/02/17 15:18 - Created Blog entry : Torototo

  #. Created Blog entry : Torototo
  #. Added relation : Torototo blog entry of Undo Blog

But note that both public and private actions will be undone
together when the transaction is undone.

(In)dependent transactions : the simple case
````````````````````````````````````````````

A CubicWeb application can be used *simultaneously* by different users
(whereas a single user works on an given office document at a
given time), so that there is not always a single history
time-line in the CubicWeb case. Moreover CubicWeb provides
security through the mechanism of *permissions* granted to each
user. This can lead to some transactions *not* being undoable in
some contexts.

In the simple case two (unprivileged) users Alice and Bob make
relatively independent changes : then both Alice and Bob can undo
their changes. But in some case there is a clean dependency
between Alice's and Bob's actions or between actions of one of
them. For example let's suppose that :

- Alice has created a blog,
- then has published a first post inside,
- then Bob has published a second post in the same blog,
- and finally Alice has updated its post contents.

Then it is clear that Alice can undo her contents changes and Bob
can undo his post creation independently. But Alice can not undo
her post creation while she has not first undone her changes.
It is also clear that Bob should *not* have the
permissions to undo any of Alice's transactions.


More complex dependencies between transactions
``````````````````````````````````````````````

But more surprising things can quickly happen. Going back to the
previous example, Alice *can* undo the creation of the blog after
Bob has published its post in it ! But this is possible only
because the schema does not *require* for a post to be in a
blog. Would the *blog entry of* relation have been mandatory, then
Alice could not have undone the blog creation because it would
have broken integrity constraint for Bob's post.

When a user attempts to undo a transaction the system will check
whether a later transaction has explicit dependency on the
would-be-undone transaction. In this case the system will not even
attempt the undo operation and inform the user.

If no such dependency is detected the system will attempt the undo
operation but it can fail, typically because of integrity
constraint violations. In such a case the undo operation is
completely [3]_ rollbacked.


The *undo feature* for CubicWeb end-users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The exposition of the undo feature to the end-user through a Web
interface is still quite basic and will be improved toward a
greater usability. But it is already fully functional.  For now
there are two ways to access the *undo feature* as long as the it
has been activated in the instance configuration file with the
option *undo-support=yes*.

Immediately after having done the change to be canceled through
the **undo** link in the message. This allows to undo an
hastily action immediately. For example, just after having
validated the creation of the blog entry *A second blog entry* we
get the following message, allowing to undo the creation.

.. image:: /images/undo_mesage_w600.png
   :width: 600px
   :alt: Screenshot of the undo link in the message
   :align: center

At any time we can access the **undo-history view** accessible from the
start-up page.

.. image:: /images/undo_startup-link_w600.png
   :width: 600px
   :alt: Screenshot of the startup menu with access to the history view
   :align: center

This view will provide inspection of the transaction and their (public)
actions. Each transaction provides its own **undo** link. Only the
transactions the user has permissions to see and undo will be shown.

.. image:: /images/undo_history-view_w600.png
   :width: 600px
   :alt: Screenshot of the undo history main view
   :align: center

If the user attempts to undo a transaction which can't be undone or
whose undoing fails, then a message will explain the situation and
no partial undoing will be left behind.

This is all for the end-user side of the undo mechanism : this is
quite simple indeed ! Now, in the following section, we are going
to introduce the developer side of the undo mechanism.

The *undo feature* for CubicWeb application developers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A word of warning : this section is intended for developers,
already having some knowledge of what's under CubicWeb's hood. If
it is not *yet* the case, please refer to CubicWeb documentation
http://docs.cubicweb.org/ .

Overview
````````

The core of the undo mechanisms is at work in the *native source*,
beyond the RQL. This does mean that *transactions* and *actions*
are *no entities*. Instead they are represented at the SQL level
and exposed through the *DB-API* supported by the repository
*Connection* objects.

Once the *undo feature* has been activated in the instance
configuration file with the option *undo-support=yes*, each
mutating operation (cf. [2]_) will be recorded in some special SQL
table along with its associated transaction. Transaction are
identified by a *txuuid* through which the functions of the
*DB-API* handle them.

On the web side the last commited transaction *txuuid* is
remembered in the request's data to allow for imediate undoing
whereas the *undo-history view* relies upon the *DB-API* to list
the accessible transactions. The actual undoing is performed by
the *UndoController* accessible at URL of the form
`www.my.host/my/instance/undo?txuuid=...`

The repository side
```````````````````

Please refer to the file `cubicweb/server/sources/native.py` and
`cubicweb/transaction.py` for the details.

The undoing information is mainly stored in three SQL tables:

`transactions`
    Stores the txuuid, the user eid and the date-and-time of
    the transaction. This table is referenced by the two others.

`tx_entity_actions`
    Stores the undo information for actions on entities.

`tx_relation_actions`
    Stores the undo information for the actions on relations.

When the undo support is activated, entries are added to those
tables for each mutating operation on the data repository, and are
deleted on each transaction undoing.

Those table are accessible through the following methods of the
repository `Connection` object :

`undoable_transactions`
    Returns a list of `Transaction` objects accessible to the user
    and according to the specified filter(s) if any.

`tx_info`
    Returns a `Transaction` object from a `txuuid`

`undo_transaction`
    Returns the list of `Action` object for the given `txuuid`.

    NB:  By default it only return *public* actions.

The web side
````````````

The exposure of the *undo feature* to the end-user through the Web
interface relies on the *DB-API* introduced above. This implies
that the *transactions* and *actions* are not *entities* linked by
*relations* on which the usual views can be applied directly.

That's why the file `cubicweb/web/views/undohistory.py` defines
some dedicated views to access the undo information :

`UndoHistoryView`
    This is a *StartupView*, the one accessible from the home
    page of the instance which list all transactions.

`UndoableTransactionView`
    This view handles the display of a single `Transaction` object.

`UndoableActionBaseView`
    This (abstract) base class provides private methods to build
    the display of actions whatever their nature.

`Undoable[Add|Remove|Create|Delete|Update]ActionView`
    Those views all inherit from `UndoableActionBaseView` and
    each handles a specific kind of action.

`UndoableActionPredicate`
    This predicate is used as a *selector* to pick the appropriate
    view for actions.

Apart from this main *undo-history view* a `txuuid` is stored in
the request's data `last_undoable_transaction` in order to allow
immediate undoing of a hastily validated operation. This is
handled in `cubicweb/web/application.py` in the `main_publish` and
`add_undo_link_to_msg` methods for the storing and displaying
respectively.

Once the undo information is accessible, typically through a
`txuuid` in an *undo* URL, the actual undo operation can be
performed by the `UndoController` defined in
`cubicweb/web/views/basecontrollers.py`. This controller basically
extracts the `txuuid` and performs a call to `undo_transaction` and
in case of an undo-specific error, lets the top level publisher
handle it as a validation error.


Conclusion
~~~~~~~~~~

The undo mechanism relies upon a low level recording of the
mutating operation on the repository. Those records are accessible
through some method added to the *DB-API* and exposed to the
end-user either through a whole history view of through an
immediate undoing link in the message box.

The undo feature is functional but the interface and configuration
options are still quite reduced. One major improvement would be to
be able to filter with a finer grain which transactions or actions
one wants to see in the *undo-history view*. Another critical
improvement would be to enable the undo feature on a part only of
the entity-relationship schema to avoid storing too much useless
data and reduce the underlying overhead.

But both functionality are related to the strong design choice not
to represent transactions and actions as entities and
relations. This has huge benefits in terms of safety and conceptual
simplicity but prevents from using lots of convenient CubicWeb
features such as *facets* to access undo information.

Before developing further the undo feature or eventually revising
this design choice, it appears that some return of experience is
strongly needed. So don't hesitate to try the undo feature in your
application and send us some feedback.


Notes
~~~~~

.. [1] The end-user Web interface could be improved to enable
       user to choose whether he wishes to see private actions.

.. [2] There is only five kind of elementary actions (beyond
       merely accessing data for reading):

       * **C** : creating an entity
       * **D** : deleting an entity
       * **U** : updating an entity attributes
       * **A** : adding a relation
       * **R** : removing a relation

.. [3] Meaning none of the actions in the transaction is
       undone. Depending upon the application, it might make sense
       to enable *partial* undo. That is to say undo in which some
       actions could not be undo without preventing to undo the
       others actions in the transaction (as long as it does not
       break schema integrity). This is not forbidden by the
       back-end but is deliberately not supported by the front-end
       (for now at least).
