default: template

template:
	sed -f ../variables.sed network_setup.tpl > /tmp/network_setup.sh
	chmod 755 /tmp/network_setup.sh

clean:
	rm /tmp/network_setup.sh

