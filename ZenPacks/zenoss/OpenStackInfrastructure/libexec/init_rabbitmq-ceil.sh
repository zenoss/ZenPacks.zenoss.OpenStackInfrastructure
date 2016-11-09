#!/bin/sh

set -e
SENTINEL=/tmp/rabbit_ceil_ok
if [ ! -e $SENTINEL ] ; then
    USER=$1
    PASSWORD=$2
    rabbitmqctl add_vhost /zenoss || true
    rabbitmqctl clear_permissions -p /zenoss $USER
    rabbitmqctl set_permissions -p /zenoss $USER '.*' '.*' '.*'
    rabbitmqadmin --port=45672 --vhost=/zenoss --username=$USER --password=$PASSWORD declare exchange name=zenoss.openstack.ceilometer type=topic
    rabbitmqadmin --port=45672 --vhost=/zenoss --username=$USER --password=$PASSWORD declare exchange name=zenoss.openstack.heartbeats type=topic
    rabbitmqctl delete_user guest || true
    touch $SENTINEL
fi
