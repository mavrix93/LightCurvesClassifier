%.js: %.src.js
	python minify.py "$<" "$@"
	
.PHONE: all

all: fancyroot.js gavo.js formal.js
