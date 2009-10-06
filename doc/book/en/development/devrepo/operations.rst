.. -*- coding: utf-8 -*-

Repository operations
======================

When one needs to perform operations (real world operations like mail
notifications, file operations, real-world side-effects) at
transaction commit time, Operations are the way to go.

Possible events are:

* precommit: the pool is preparing to commit. You shouldn't do
  anything things which has to be reverted if the commit fail at this
  point, but you can freely do any heavy computation or raise an
  exception if the commit can't go.  You can add some new operation
  during this phase but their precommit event won't be triggered

* commit: the pool is preparing to commit. You should avoid to do to
  expensive stuff or something that may cause an exception in this
  event

* revertcommit: if an operation failed while commited, this event is
  triggered for all operations which had their commit event already to
  let them revert things (including the operation which made fail the
  commit)

* rollback: the transaction has been either rollbacked either
  * intentionaly
  * a precommit event failed, all operations are rollbacked
  * a commit event failed, all operations which are not been triggered
    for commit are rollbacked

Exceptions signaled from within a rollback are logged and swallowed.

The order of operations may be important, and is controlled according
to operation's class (see : Operation, LateOperation, SingleOperation,
SingleLastOperation).
