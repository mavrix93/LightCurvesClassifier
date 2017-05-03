"""
Code to support DC-external code (preprocessing, testing...)
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

# Do not import anything here since it's important that testhelpers
# can be imported without base begin pulled in (since testhelpers
# manipulates the environment).
#
# Thus, only import complete modules from helpers.
