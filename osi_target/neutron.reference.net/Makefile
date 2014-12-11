# export TEXINPUTS="::${HOME}/texas/inputs:"

default: site

# %:
# 	ansible-playbook -i inventory -K $@.yml 

packstack:
	ansible-playbook -vvvv -i inventory packstack.yml -Kk

neutron:
	ansible-playbook -vvvv -i inventory neutron.yml -Kk

vars:
	ansible-playbook -vvvv -i inventory vars.yml -Kk

xvars:
	ansible -u zenoss -k -m setup -i inventory packstack > xvars.json

test:
	ansible-playbook -vvv -i inventory test.yml -Kk


