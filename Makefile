PREFIX ?= /usr/local
PYTHON ?= python

ifneq ($(OS), Windows_NT)
ifeq ($(shell uname -s), Darwin)
OPTARG= --distpath=dist/usr/local/lib
endif
endif

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
	./venv/bin/pip install -U ../utils
	./venv/bin/pip install -U ../dispatcher/client/python
	./venv/bin/pip install -U .
	./venv/bin/pyinstaller -y --clean --windowed $(OPTARG) freenas-cli.spec

macosx:	bin
ifeq ($(shell uname -s), Darwin)
	@mkdir -p dist/usr/local/bin
	@rm -f dist/usr/local/bin/freenas-cli
	ln -s ../lib/freenas-cli.framework/Contents/MacOS/freenas-cli dist/usr/local/bin/freenas-cli
	pkgbuild --root dist --identifier org.freenas.cli freenas-cli.pkg
else
	@true
endif
