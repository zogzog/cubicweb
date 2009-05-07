.. -*- coding: utf-8 -*-

.. _hooks:

Hooks
=====

XXX FILLME

*Hooks* are executed before or after updating an entity or a relation in the
repository.

Their prototypes are as follows: 
    
    * after_add_entity     (session, entity)
    * after_update_entity  (session, entity)
    * after_delete_entity  (session, eid)
    * before_add_entity    (session, entity)
    * before_update_entity (session, entity)
    * before_delete_entity (session, eid)

    * after_add_relation     (session, fromeid, rtype, toeid)
    * after_delete_relation  (session, fromeid, rtype, toeid)
    * before_add_relation    (session, fromeid, rtype, toeid)
    * before_delete_relation (session, fromeid, rtype, toeid)
    
    * server_startup
    * server_shutdown
    
    * session_open
    * session_close

