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
NOVACLIENT_DIR=$(SRC_DIR)/python-novaclient-2.15.0
KEYSTONECLIENT_DIR=$(SRC_DIR)/python-keystoneclient-0.4.0
CEILOMETERCLIENT_DIR=$(SRC_DIR)/python-ceilometerclient-1.0.6
ZP_DIR=$(PWD)/ZenPacks/zenoss/OpenStack
BIN_DIR=$(ZP_DIR)/bin
LIB_DIR=$(ZP_DIR)/lib

default: egg

egg:
	# setup.py will call 'make build' before creating the egg
	python setup.py bdist_egg

build:	
	cd $(SRC_DIR)/pip-1.5.5 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"
	cd $(SRC_DIR)/pbr-0.8.0 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"
	cd $(SRC_DIR)/prettytable-0.7.2 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"
	cd $(SRC_DIR)/Babel-1.3 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"
	cd $(SRC_DIR)/requests-2.0.0 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"
	cd $(SRC_DIR)/iso8601-0.1.9 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"
	cd $(SRC_DIR)/simplejson-3.3.1 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"	
	cd $(SRC_DIR)/netaddr-0.7.11 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"	
	cd $(SRC_DIR)/oslo.config-1.2.0 && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"	
	# convince openstack clients not to try to download any dependencies.
	# We have already taken care of them above.
	cp /dev/null $(NOVACLIENT_DIR)/requirements.txt
	cd $(NOVACLIENT_DIR) && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"

	cp /dev/null $(KEYSTONECLIENT_DIR)/requirements.txt
	cd $(KEYSTONECLIENT_DIR) && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"

	cp /dev/null $(CEILOMETERCLIENT_DIR)/requirements.txt
	cd $(CEILOMETERCLIENT_DIR) && \
		PYTHONPATH="$(PYTHONPATH):$(LIB_DIR)" $(PYTHON) setup.py install \
			--install-lib="$(LIB_DIR)" --install-scripts="$(BIN_DIR)"

clean:
	rm -rf build dist *.egg-info
	cd $(NOVACLIENT_DIR) ; rm -rf build dist *.egg-info ; cd $(SRC_DIR)
	cd $(KEYSTONECLIENT_DIR) ; rm -rf build dist *.egg-info ; cd $(SRC_DIR)
	cd $(CEILOMETERCLIENT_DIR) ; rm -rf build dist *.egg-info ; cd $(SRC_DIR)
	rm -f $(BIN_DIR)/nova
	rm -f $(BIN_DIR)/keystone
	rm -f $(BIN_DIR)/ceilometer
	cd $(LIB_DIR) ; rm -Rf keystoneclient ; cd $(SRC_DIR)
	cd $(LIB_DIR) ; rm -Rf novaclient ; cd $(SRC_DIR)
	cd $(LIB_DIR) ; rm -Rf ceilometerclient ; cd $(SRC_DIR)
	cd $(LIB_DIR) ; rm -Rf *.egg site.py easy-install.pth ; cd $(SRC_DIR)
	find . -name '*.pyc' | xargs rm

