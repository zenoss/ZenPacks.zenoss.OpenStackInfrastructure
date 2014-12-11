default: packstack network
all: packstack network
test: hi lo

packstack:
	chmod 700 setup.sh
	./setup.sh packstack

neutron:
	chmod 700 setup.sh
	./setup.sh neutron

vars:
	cd neutron.reference.net && $(MAKE) vars

lo:
	echo lo

