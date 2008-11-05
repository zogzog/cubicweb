nom    ivarchar(64) NOT NULL
prenom ivarchar(64)
sexe   char(1) DEFAULT 'M' 
promo  choice('bon','pasbon')
titre  ivarchar(128)
adel   varchar(128)
ass    varchar(128)
web    varchar(128)
tel    integer
fax    integer
datenaiss datetime
test   boolean 
description text
salary float
