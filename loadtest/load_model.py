#!/usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import Globals

import logging
log = logging.getLogger('zen.load_model')

from collections import defaultdict
from itertools import count, chain
import yaml
import transaction

from Products.ZenUtils.Utils import unused
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from Products.DataCollector.plugins.DataMaps import RelationshipMap, ObjectMap
from Products.ZenUtils.ZenTales import talesEvalStr
from Products.DataCollector.ApplyDataMap import ApplyDataMap

unused(Globals)


class LoadModel(ZenScriptBase):

    def buildOptions(self):
        super(LoadModel, self).buildOptions()

        self.parser.add_option(
            '-d', dest='device',
            help='Device Name',
            default='test_ostack')

        self.parser.add_option(
            '--controllers', dest='controllers',
            help='Number of Controller Nodes to create',
            type=int,
            default=3
        )

        self.parser.add_option(
            '--computes', dest='computes',
            help='Number of Compute Nodes to create',
            type=int,
            default=30
        )

        self.parser.add_option(
            '--tenants', dest='tenants',
            help='Number of tenants to create',
            type=int,
            default=50
        )

        self.parser.add_option(
            '--instances', dest='instances',
            help='Number of Instances to create',
            type=int,
            default=2250
        )

    def get_model_template(self, template_name):
        result = []
        subconfig = self.model_config.get(template_name, [])

        for otype_dict in subconfig:
            modname = otype_dict.keys()[0]
            for obj_id, obj_attrs in otype_dict.values()[0].iteritems():
                obj_attrs['id'] = obj_id
                result.append((modname, dict(obj_attrs)))

        return result

    def talesEvalAttrs(self, obj_attrs, **kwargs):
        for attr in obj_attrs:
            if isinstance(obj_attrs[attr], list):
                obj_attrs[attr] = [talesEvalStr(x, self, extra=kwargs) for x in obj_attrs[attr]]
            else:
                obj_attrs[attr] = talesEvalStr(obj_attrs[attr], self, extra=kwargs)

    def run(self):
        with open('model.yaml', 'r') as f:
            self.model_config = yaml.load(f)

        self.connect()

        objmaps = []
        for modname, obj_attrs in self.get_model_template("Global"):
            objmaps.append(ObjectMap(modname=modname, data=obj_attrs))

        for controller_num in range(1, self.options.controllers + 1):
            for modname, obj_attrs in self.get_model_template("Controller"):
                self.talesEvalAttrs(
                    obj_attrs,
                    num=controller_num,
                    device_name=self.options.device
                )
                objmaps.append(ObjectMap(modname=modname, data=obj_attrs))

        for compute_num in range(1, self.options.computes + 1):
            for modname, obj_attrs in self.get_model_template("Compute"):
                self.talesEvalAttrs(
                    obj_attrs,
                    num=compute_num,
                    device_name=self.options.device
                )
                objmaps.append(ObjectMap(modname=modname, data=obj_attrs))

        for tenant_num in range(3, self.options.tenants + 3):
            for modname, obj_attrs in self.get_model_template("Tenant"):
                self.talesEvalAttrs(
                    obj_attrs,
                    num=tenant_num,
                    device_name=self.options.device
                )
                objmaps.append(ObjectMap(modname=modname, data=obj_attrs))

        compute_nums = range(1, self.options.computes + 1)
        tenant_nums = range(3, self.options.tenants + 3)

        for instance_num in range(1, self.options.instances + 1):
            for modname, obj_attrs in self.get_model_template("Instance"):
                tenant_num = tenant_nums[instance_num % self.options.tenants]
                compute_num = compute_nums[instance_num % self.options.computes]

                self.talesEvalAttrs(
                    obj_attrs,
                    num=instance_num,
                    device_name=self.options.device,
                    tenant_num=tenant_num,
                    compute_num=compute_num
                )
                objmaps.append(ObjectMap(modname=modname, data=obj_attrs))

        device = self.dmd.Devices.OpenStack.Infrastructure.findDevice(self.options.device)
        if not device:
            print "Creating OpenStackInfrastructure device %s" % self.options.device
            device = self.dmd.Devices.OpenStack.Infrastructure.createInstance(self.options.device)
        device.setPerformanceMonitor('localhost')

        for controller_num in range(1, self.options.controllers + 1):
            device_name = "%s_controller%d" % (self.options.device, controller_num)
            d = self.dmd.Devices.Server.SSH.Linux.NovaHost.findDevice(device_name)
            if not d:
                print "Creating controller device %s" % device_name
                d = self.dmd.Devices.Server.SSH.Linux.NovaHost.createInstance(device_name)
                d.setZenProperty('zIpServiceMapMaxPort', 32767)

        for compute_num in range(1, self.options.computes + 1):
            device_name = "%s_compute%d" % (self.options.device, compute_num)
            d = self.dmd.Devices.Server.SSH.Linux.NovaHost.findDevice(device_name)
            if not d:
                print "Creating compute device %s" % device_name
                d = self.dmd.Devices.Server.SSH.Linux.NovaHost.createInstance(device_name)
                d.setZenProperty('zIpServiceMapMaxPort', 32767)

        relmap = RelationshipMap(relname='components')
        for objmap in objmaps:
            relmap.append(objmap)

        endpoint_om = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_maintain_proxydevices=True
            )
        )

        print "Applying datamaps (1/2) (%d objects)" % len(objmaps)
        adm = ApplyDataMap()
        adm._applyDataMap(device, relmap)
        adm._applyDataMap(device, endpoint_om)

        print "Gathering network information"
        l3_agent_ids = [x.id for x in device.getDeviceComponents(type="OpenStackInfrastructureNeutronAgent") if x.type == 'L3 agent']
        dhcp_agent_ids = [x.id for x in device.getDeviceComponents(type="OpenStackInfrastructureNeutronAgent") if x.type == 'DHCP agent']
        all_network_ids = [x.id for x in device.getDeviceComponents(type="OpenStackInfrastructureNetwork")]
        all_router_ids = [x.id for x in device.getDeviceComponents(type="OpenStackInfrastructureRouter")]
        all_subnet_ids = [x.id for x in device.getDeviceComponents(type="OpenStackInfrastructureSubnet")]
        instance_network_ids = [x.id for x in device.getDeviceComponents(type="OpenStackInfrastructureNetwork") if x.ports() and len([y for y in x.ports() if y.instance()])]
        instance_subnet_ids = [y.id for y in set(chain.from_iterable([x.subnets() for x in device.getDeviceComponents(type="OpenStackInfrastructureNetwork") if x.ports() and len([y for y in x.ports() if y.instance()])]))]

        objmaps = []
        print "Adding L3 Agent Relationships"
        for agent_id in l3_agent_ids:
            objmaps.append(ObjectMap(
                modname="ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent",
                compname="components/%s" % agent_id,
                data=dict(
                    id=agent_id,
                    set_networks=all_network_ids,
                    set_routers=all_router_ids,
                    set_subnets=all_subnet_ids
                )))

        print "Adding DHCP agent Relationships"
        for agent_id in dhcp_agent_ids:
            objmaps.append(ObjectMap(
                modname="ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent",
                compname="components/%s" % agent_id,
                data=dict(
                    id=agent_id,
                    set_networks=instance_network_ids,
                    set_subnets=instance_subnet_ids
                )))

        print "Adding instance <-> hypervisor relationship"
        hypervisor_instances = defaultdict(list)
        for instance_num in range(1, self.options.instances + 1):
            instance_id = "server-%d" % instance_num
            compute_num = compute_nums[instance_num % self.options.computes]
            hypervisor_id = "hypervisor-compute%d.1" % compute_num
            hypervisor_instances[hypervisor_id].append(instance_id)

        for hypervisor_id, instance_ids in hypervisor_instances.iteritems():
            objmaps.append(ObjectMap(
                modname="ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor",
                compname="components/%s" % hypervisor_id,
                data=dict(
                    id=hypervisor_id,
                    set_instances=instance_ids
                )))

        print "Applying datamaps (2/2) (%d objects)" % len(objmaps)
        adm = ApplyDataMap()
        for objmap in objmaps:
            adm._applyDataMap(device, objmap)

        print "Committing model changes."
        transaction.commit()


def main():
    script = LoadModel()
    script.run()


if __name__ == '__main__':
    main()
