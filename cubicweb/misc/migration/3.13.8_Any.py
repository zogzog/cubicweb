change_attribute_type('CWUser', 'last_login_time', 'TZDatetime')
change_attribute_type('CWSource', 'latest_retrieval', 'TZDatetime')
drop_attribute('CWSource', 'synchronizing')
add_attribute('CWSource', 'in_synchronization')
