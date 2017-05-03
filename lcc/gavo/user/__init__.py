"""
"User-interface"-type code.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports


from gavo.user import useless
from gavo.user import plainui

interfaces = {
	"deluge": useless.DelugeUI,
	"null": useless.NullUI,
	"stingy": plainui.StingyPlainUI,
	"plain": plainui.PlainUI,
}
