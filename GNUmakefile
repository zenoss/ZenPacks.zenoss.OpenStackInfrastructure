###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
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
TXSSHCLIENT_DIR=$(SRC_DIR)/txsshclient-0.1.0dev1
ZP_DIR=$(PWD)/ZenPacks/zenoss/OpenStackInfrastructure
BIN_DIR=$(ZP_DIR)/bin
LIB_DIR=$(ZP_DIR)/lib

default: egg

egg:
	# setup.py will call 'make build' before creating the egg
	python setup.py bdist_egg

.PHONY: build

build:

	# Now build all the build dependencies for this zenpack.
	cd $(TXSSHCLIENT_DIR) && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"

clean:
	rm -rf build dist *.egg-info
	cd $(TXSSHCLIENT_DIR) ; rm -rf build dist *.egg-info ; cd $(SRC_DIR)
	cd $(LIB_DIR) ; rm -Rf *.egg site.py easy-install.pth ; cd $(SRC_DIR)
	find . -name '*.pyc' | xargs rm -f

