# server debugging flag
DEBUG = False

# sqlite'stored procedures have to be registered at connexion opening time
SQL_CONNECT_HOOKS = {}

# add to this set relations which should have their add security checking done
# *BEFORE* adding the actual relation (done after by default)
BEFORE_ADD_RELATIONS = set(('owned_by',))

# add to this set relations which should have their add security checking done
# *at COMMIT TIME* (done after by default)
ON_COMMIT_ADD_RELATIONS = set(())

# available sources registry
SOURCE_TYPES = {}
