title		ivarchar(64) not null
state		CHOICE('open', 'rejected', 'validation pending', 'resolved') default 'open'
severity	CHOICE('important', 'normal', 'minor') default 'normal'
cost 		integer
description	ivarchar(4096)
