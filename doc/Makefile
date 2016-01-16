SRC=.

# You can set these sphinx variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
PAPER         =
#BUILDDIR      = build
BUILDDIR      = _build
CWDIR         = ../cubicweb
JSDIR         = ${CWDIR}/web/data
JSTORST       = tools/pyjsrest.py
BUILDJS       = js_api

# Internal variables for sphinx
PAPEROPT_a4     = -D latex_paper_size=a4
PAPEROPT_letter = -D latex_paper_size=letter
ALLSPHINXOPTS   = -d ${BUILDDIR}/doctrees $(PAPEROPT_$(PAPER)) $(SPHINXOPTS) .



.PHONY: help clean html web pickle htmlhelp latex changes linkcheck

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  all       to make standalone HTML files, developer manual and API doc"
	@echo "  html      to make standalone HTML files"
	@echo "---  "
	@echo "  pickle    to make pickle files (usable by e.g. sphinx-web)"
	@echo "  htmlhelp  to make HTML files and a HTML help project"
	@echo "  latex     to make LaTeX files, you can set PAPER=a4 or PAPER=letter"
	@echo "  changes   to make an overview over all changed/added/deprecated items"
	@echo "  linkcheck to check all external links for integrity"

clean:
	rm -f *.html
	-rm -rf ${BUILDDIR}/html ${BUILDDIR}/doctrees
	-rm -rf ${BUILDJS}

all: html

# run sphinx ###
html: js
	mkdir -p ${BUILDDIR}/html ${BUILDDIR}/doctrees
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) ${BUILDDIR}/html
	@echo
	@echo "Build finished. The HTML pages are in ${BUILDDIR}/html."

js:
	mkdir -p ${BUILDJS}
	$(JSTORST) -p ${JSDIR} -o ${BUILDJS}

pickle:
	mkdir -p ${BUILDDIR}/pickle ${BUILDDIR}/doctrees
	$(SPHINXBUILD) -b pickle $(ALLSPHINXOPTS) ${BUILDDIR}/pickle
	@echo
	@echo "Build finished; now you can process the pickle files or run"
	@echo "  sphinx-web ${BUILDDIR}/pickle"
	@echo "to start the sphinx-web server."

web: pickle

htmlhelp:
	mkdir -p ${BUILDDIR}/htmlhelp ${BUILDDIR}/doctrees
	$(SPHINXBUILD) -b htmlhelp $(ALLSPHINXOPTS) ${BUILDDIR}/htmlhelp
	@echo
	@echo "Build finished; now you can run HTML Help Workshop with the" \
	      ".hhp project file in ${BUILDDIR}/htmlhelp."

latex:
	mkdir -p ${BUILDDIR}/latex ${BUILDDIR}/doctrees
	$(SPHINXBUILD) -b latex $(ALLSPHINXOPTS) ${BUILDDIR}/latex
	@echo
	@echo "Build finished; the LaTeX files are in ${BUILDDIR}/latex."
	@echo "Run \`make all-pdf' or \`make all-ps' in that directory to" \
	      "run these through (pdf)latex."

changes:
	mkdir -p ${BUILDDIR}/changes ${BUILDDIR}/doctrees
	$(SPHINXBUILD) -b changes $(ALLSPHINXOPTS) ${BUILDDIR}/changes
	@echo
	@echo "The overview file is in ${BUILDDIR}/changes."

linkcheck:
	mkdir -p ${BUILDDIR}/linkcheck ${BUILDDIR}/doctrees
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) ${BUILDDIR}/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the above output " \
	      "or in ${BUILDDIR}/linkcheck/output.txt."
