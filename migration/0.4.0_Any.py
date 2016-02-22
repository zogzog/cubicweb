
# just notify the user to put the secret keys in pyramid.ini

print("The pyramid-auth-secret and pyramid-session-secret options has been\n"
      "removed from the all-in-one.conf file in favor of the pyramid.ini config\n"
      "file. Make sure to set \n"
      "  cubicweb.session.secret, \n"
      "  cubicweb.auth.authtkt.persistent.secret and \n"
      "  cubicweb.auth.authtkt.session.secret \n"
      "keys in your $APP/pyramid.ini file.")
