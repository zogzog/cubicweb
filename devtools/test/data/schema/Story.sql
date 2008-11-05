title		ivarchar(64) not null
state		CHOICE('open', 'rejected', 'validation pending', 'resolved') default 'open'
priority	CHOICE('minor', 'normal', 'important') default 'normal'
cost	        integer
description	ivarchar(4096)
