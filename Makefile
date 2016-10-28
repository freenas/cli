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
	${VENV_PIP} install -U cython==0.24.1 setuptools six ply columnize natural termcolor texttable pyte future rollbar gnureadline
	${VENV_PIP} install -U --egg ${BE_ROOT}/py-freenas.utils
	${VENV_PIP} install -U --egg ${BE_ROOT}/py-filewrap
	${VENV_PIP} install -U --egg ${BE_ROOT}/dispatcher-client/python
	PYTHONPATH=. ${VENV_PYTHON} -m freenas.cli.repl ${ARGS}
