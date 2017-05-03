"""
IVOA, W3C, and custom protocol helpers (in cooperation with twisted-based
code in weg).

The guiding line should be: Stuff that depends on nevow (or even twisted)
should go to web or svcs, generic code should be here.  Of course, these
rules are constantly bent.

When writing support for a protocol, do as much as possible as far as
templates for RDs in an RD //<protoname>.

Use the code in protocols for the core and possible library-like functionality.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# Not checked by pyflakes: API file with gratuitous imports
