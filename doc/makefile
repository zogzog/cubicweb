MKHTML=mkdoc
MKHTMLOPTS=--doctype article --target html --stylesheet standard 
SRC=.

TXTFILES:= $(wildcard *.txt)
TARGET := $(TXTFILES:.txt=.html)

all: ${TARGET} devmanual apidoc

%.html: %.txt
	${MKHTML} ${MKHTMLOPTS} $<

devmanual:
	cd devmanual_fr && make	
#apydoc: 
#	epydoc --html -o epydoc/ -n ../server/*.py ../core/*.py ../common/*.py ../server/*/*.py ../modpython/*/*.py ../common/*/*.py
apidoc:
	epydoc --html -o apidoc -n "cubicweb" --exclude=setup --exclude=__pkginfo__ ../
clean:
	rm -rf apidoc/
	rm -f *.html
	cd devmanual_fr && make	clean
