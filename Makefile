PREFIX ?= /usr/local
PYTHON ?= python

install:
	install tools/cli ${PREFIX}/bin/
	install tools/logincli ${PREFIX}/bin/
	install -d ${PREFIX}/lib/freenascli
	install -d ${PREFIX}/lib/freenascli/src
	install -d ${PREFIX}/lib/freenascli/plugins
	cp -R src/ ${PREFIX}/lib/freenascli/src/
	cp -R plugins/ ${PREFIX}/lib/freenascli/plugins/

bin:
	virtualenv venv
	./venv/bin/pip install -U https://github.com/pyinstaller/pyinstaller/archive/develop.zip
	./venv/bin/pip install -U freenas.cli
	./venv/bin/pyinstaller -y --clean --windowed freenas-cli.spec
