VERSION=1.0
.export-env VERSION

#-------------------------
# Command line arguments:
#
# O=<dirname>               # Output directory for .html files; Default = ./cli.docs
#-------------------------

CONFIG = $(PWD)/config

VENV = $(PWD)/venv
VENV_PYTHON = $(VENV)/bin/python3.4
VENV_PIP = $(VENV)/bin/pip3.4
VENV_REQS = $(CONFIG)/requirements.txt
VENV_SPHINXBUILD = $(VENV)/bin/sphinx-build

FREENAS_PYBSD = $(VENV)/py-bsd
FREENAS_UTILS = $(VENV)/py-freenas-utils
FREENAS_CLIENT = $(VENV)/dispatcher-client
FREENAS_CLI = $(PWD)/..

BUILD_SETUP = $(CONFIG)/build_env
BUILD_ENV = $(VENV)/build_env
BUILD = $(BUILD_ENV)/build
BUILD_SRC = $(BUILD_ENV)/source
BUILD_META = /var/tmp/cli.docs

HTML = $(BUILD)/html

O ?= $(PWD)/cli.docs

.PHONY: all
all: env html clean

.PHONY: env 
env: $(VENV) install_pybsd install_utils install_dispatcher_client

.PHONY: html
html: meta
	@cd $(BUILD_ENV) && $(MAKE) html SPHINXBUILD=$(VENV_SPHINXBUILD)
	@rm -rf $(O) && mkdir $(O) 
	cp -r $(HTML)/* $(O)/

.PHONY: clean
clean:
	rm -rf $(VENV)

.PHONY: meta
meta:
	@cd $(FREENAS_CLI)/ && $(VENV_PYTHON) -m  freenas.cli.repl --makedocs
	@cp $(BUILD_META)/* $(BUILD_SRC)/

.PHONY: install_pybsd
install_pybsd: $(FREENAS_PYBSD)

.PHONY: install_utils
install_utils: $(FREENAS_UTILS)

.PHONY: install_dispatcher_client
install_dispatcher_client: $(FREENAS_CLIENT)

$(VENV):
	@virtualenv $(VENV) --python=python3
	@$(VENV_PIP) install -Ur $(VENV_REQS)
	@mkdir -p $(BUILD_ENV)
	@cp -r $(BUILD_SETUP)/ $(BUILD_ENV)/ 

$(FREENAS_PYBSD):
	@git clone https://github.com/freenas/py-bsd $(FREENAS_PYBSD)
	@cd $(FREENAS_PYBSD) && $(VENV_PYTHON) setup.py install

$(FREENAS_UTILS):
	@git clone https://github.com/freenas/py-freenas-utils $(FREENAS_UTILS)
	@cd $(FREENAS_UTILS) && $(VENV_PYTHON) setup.py install

$(FREENAS_CLIENT):
	@git clone https://github.com/freenas/dispatcher-client $(FREENAS_CLIENT)
	@cd $(FREENAS_CLIENT)/python && $(VENV_PYTHON) setup.py install
