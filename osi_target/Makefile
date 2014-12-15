default: all

all:
	chmod 700 setup.sh
	./setup.sh
	cd neutron.reference.net && $(MAKE) all

packstack:
	cd neutron.reference.net && $(MAKE) packstack

neutron:
	cd neutron.reference.net && $(MAKE) neutron

vars:
	cd neutron.reference.net && $(MAKE) vars

