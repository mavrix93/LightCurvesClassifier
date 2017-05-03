"""
A frontend to google's minifying service.  Ah well, we should
really have an all-local minifyer.
This is really intended to be called from the makefile.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import json
import sys
import urllib

SERVICE_URL = "http://closure-compiler.appspot.com/compile"

def main():
	if len(sys.argv)!=3:
		sys.exit("Usage minify <js source> <destination name>\n")

	postData = urllib.urlencode([
		("compilation_level", "SIMPLE_OPTIMIZATIONS"),
		("output_format", "json"),
		("output_info", "compiled_code"),
		("output_info", "warnings"),
		("output_info", "errors"),
		("js_code", open(sys.argv[1]).read())])
	result = json.load(urllib.urlopen(SERVICE_URL, postData))

	if "warnings" in result:
		print "Warnings: %s"%str(result["warnings"])

	if "errors" in result:
		print "*** Compilation failed: %s"%str(result["errors"])
		sys.exit("Bad js, aborting")
	
	with open(sys.argv[2], "w") as f:
		f.write(result["compiledCode"])


if __name__=="__main__":
	main()
