@echo off
rem = """-*-Python-*- script
rem -------------------- DOS section --------------------
rem You could set PYTHONPATH or TK environment variables here
python -x "%~f0" %*
goto exit
 
"""
# -------------------- Python section --------------------
from cubicweb.cwctl import run
import sys
run(sys.argv[1:])

DosExitLabel = """
:exit
rem """


