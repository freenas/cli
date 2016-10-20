PREFIX ?= /usr/local
PYTHON ?= python
VENV_PYTHON = $(PWD)/venv/bin/python3.5
VENV_PIP = $(PWD)/venv/bin/pip
BE_ROOT ?= $(PWD)/..

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
	install -d ${PREFIX}/lib/freenascli/examples
	cp -R src/ ${PREFIX}/lib/freenascli/src/
	cp -R plugins/ ${PREFIX}/lib/freenascli/plugins/
	cp -R examples/ ${PREFIX}/lib/freenascli/examples/

bin:
	pyvenv-3.5 venv
	cd ../utils && $(VENV_PYTHON) setup.py egg_info
	cd ../dispatcher/client/python && $(VENV_PYTHON) setup.py egg_info
	$(VENV_PIP) install -U six ply ../utils
	$(VENV_PYTHON) ./setup.py egg_info
	$(VENV_PIP) install -U https://github.com/pyinstaller/pyinstaller/archive/develop.zip
	$(VENV_PIP) install -U .
	$(VENV_PIP) install -U ../utils
	$(VENV_PIP) install -U ../dispatcher/client/python
	./venv/bin/pyinstaller -y --clean --windowed $(OPTARG) freenas-cli.spec

run:
	pyvenv-3.5 venv
	$(VENV_PIP) install -U cython six ply columnize natural termcolor texttable pyte future rollbar gnureadline
	$(VENV_PIP) install -U $(BE_ROOT)/py-freenas.utils
	$(VENV_PIP) install -U $(BE_ROOT)/dispatcher-client/python
	$(VENV_PYTHON) -m freenas.cli.repl $(ARGS)


macosx:	bin
ifeq ($(shell uname -s), Darwin)
	@mkdir -p dist/usr/local/bin
	@rm -f dist/usr/local/bin/freenas-cli
	ln -s ../lib/freenas-cli.framework/Contents/MacOS/freenas-cli dist/usr/local/bin/freenas-cli
	pkgbuild --root dist --identifier org.freenas.cli freenas-cli.pkg
else
	@true
endif

clean:
	rm -rf venv build dist
