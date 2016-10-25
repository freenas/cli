PREFIX ?= /usr/local
PYTHON ?= python
VENV_PYTHON = ${.CURDIR}/venv/bin/python3.5
VENV_PIP = ${.CURDIR}/venv/bin/pip
BE_ROOT ?= ${.CURDIR}/..

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

run:
	pyvenv-3.5 venv
	${VENV_PIP} install -U cython==0.24.1 six ply columnize natural termcolor texttable pyte future rollbar gnureadline
	${VENV_PIP} install -U ${BE_ROOT}/py-freenas.utils
	${VENV_PIP} install -U ${BE_ROOT}/dispatcher-client/python
	${VENV_PYTHON} -m freenas.cli.repl ${ARGS}
