# export TEXINPUTS="::${HOME}/texas/inputs:"

default: site

# %:
# 	ansible-playbook -i inventory -K $@.yml 

vars:
	ansible -u zenoss -k -m setup -i inventory packstack > vars.json

test:
	ansible-playbook -vvv -i inventory test.yml -Kk

packstack:
	ansible-playbook -vvvv -i inventory packstack.yml -Kk

neutron:
	ansible-playbook -vvvv -i inventory neutron.yml -Kk

