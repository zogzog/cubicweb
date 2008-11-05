try:
    # missing on some old databases
    sql('CREATE INDEX entities_extid_idx ON entities(extid)')
except:
    pass # already exists
checkpoint() 
sql('CREATE INDEX entities_type_idx ON entities(type)')
checkpoint()

