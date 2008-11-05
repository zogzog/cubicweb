MKHTMLOPTS=--doctype book --param toc.section.depth=1  --target html --stylesheet single-file
SRC=.

MKPDFOPTS=--doctype book --param toc.section.depth=2  --target pdf --stylesheet standard

TXTFILES:= $(wildcard *.txt)
TARGET := $(TXTFILES:.txt=.html)

all: index.html

index.html: *.txt
	mkdoc ${MKHTMLOPTS} index.txt

index.pdf: *.txt
	mkdoc ${MKPDFOPTS} index.txt

%.html: %.txt
	mkdoc ${MKHTMLOPTS} $<

clean:
	rm -f *.html
