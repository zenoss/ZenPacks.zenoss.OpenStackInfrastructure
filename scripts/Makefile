default: template

template:
	sed -f replace.sed bootstrap.tpl > bootstrap.sh
	chmod 755 bootstrap.sh

clean:
	rm bootstrap.sh

