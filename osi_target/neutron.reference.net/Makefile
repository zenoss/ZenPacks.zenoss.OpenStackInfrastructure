# export TEXINPUTS="::${HOME}/texas/inputs:"

default: all

# %:
# 	ansible-playbook -i inventory -K $@.yml 

all:
	ansible-playbook -vvvvv -i inventory all.yml -Kk

check:
	ansible-playbook -vvvvv -i inventory all.yml -Kk --check

packstack:
	ansible-playbook -vvvv -i inventory packstack.yml -Kk

neutron:
	ansible-playbook -vvvv -i inventory neutron.yml -Kk

vars:
	ansible-playbook -vvvv -i inventory vars.yml -Kk

xvars:
	ansible -u zenoss -k -m setup -i inventory packstack > /tmp/xvars.json

test:
	ansible-playbook -vvv -i inventory test.yml -Kk


