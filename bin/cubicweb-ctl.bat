@echo off
rem = """-*-Python-*- script
rem -------------------- DOS section --------------------
rem You could set PYTHONPATH or TK environment variables here
python -x "%~f0" %*
goto exit
 
"""
# -------------------- Python section --------------------
import sys
from os.path import join, dirname
sys.path.insert(0, join(dirname(__file__), '..', '..'))
from cubicweb.cwctl import run
run(sys.argv[1:])

DosExitLabel = """
:exit
rem """


