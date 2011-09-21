###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

PYTHON=python
SRC_DIR=$(PWD)/src
NOVACLIENT_DIR=$(SRC_DIR)/python-novaclient
ZP_DIR=$(PWD)/ZenPacks/zenoss/OpenStack
BIN_DIR=$(ZP_DIR)/bin
LIB_DIR=$(ZP_DIR)/lib

default: egg

egg:
	# setup.py will call 'make build' before creating the egg
	python setup.py bdist_egg

build:
	git submodule init ; \
	GIT_SSL_NO_VERIFY=true git submodule update ; \
	cd $(NOVACLIENT_DIR) ; \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" \
		$(PYTHON) setup.py install \
		--install-lib="$(LIB_DIR)" \
		--install-scripts="$(BIN_DIR)"

clean:
	rm -rf build dist *.egg-info
	find . -name '*.pyc' | xargs rm
	cd $(NOVACLIENT_DIR) ; rm -rf build dist *.egg-info

