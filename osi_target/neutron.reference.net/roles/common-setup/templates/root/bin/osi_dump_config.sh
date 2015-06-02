#! /bin/bash

if [[ "`id -un`" != "root" ]]; then
   echo This tool must be run as root.
   echo Exiting.....
   exit 1
fi

LOG=/tmp/osi.log

echo OpenStack/Neutron Conigurations > $LOG
echo ---------------------------------------------------------------------------------- >> $LOG
echo /etc/neutron/neutron.conf                                                          >> $LOG
echo ---------------------------------------------------------------------------------- >> $LOG
grep -v "^#" /etc/neutron/neutron.conf | sed '/^$/d'                                    >> $LOG

echo ---------------------------------------------------------------------------------- >> $LOG
echo /etc/neutron/plugin.ini                                                            >> $LOG
echo ---------------------------------------------------------------------------------- >> $LOG
grep -v "^#" /etc/neutron/plugin.ini | sed '/^$/d'                                      >> $LOG

echo ---------------------------------------------------------------------------------- >> $LOG
echo /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini                            >> $LOG
echo ---------------------------------------------------------------------------------- >> $LOG
grep -v "^#" /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini | sed '/^$/d'      >> $LOG

echo ---------------------------------------------------------------------------------- >> $LOG
echo ovs-vsctl show                                                                     >> $LOG
echo ---------------------------------------------------------------------------------- >> $LOG
ovs-vsctl show                                                                          >> $LOG

echo ---------------------------------------------------------------------------------- >> $LOG
echo tree /etc/neutron                                                                  >> $LOG
echo ---------------------------------------------------------------------------------- >> $LOG
tree /etc/neutron                                                                       >> $LOG


# Filter/Sanitize output.

sed -i 's/{{ network_prefix }}/192.168.1./g' $LOG
sed -i 's/zenoss/joeuser/g' $LOG
