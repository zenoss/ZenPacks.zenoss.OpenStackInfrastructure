default: template

template:
	sed -f ../variables.sed bootstrap.tpl > /tmp/bootstrap.sh
	chmod 755 /tmp/bootstrap.sh

clean:
	rm /tmp/bootstrap.sh

