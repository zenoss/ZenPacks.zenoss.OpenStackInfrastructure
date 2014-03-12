/*
 * Customizations to Endpoint Overview Page
 */
Ext.onReady(function() {
    var DEVICE_OVERVIEW_ID = 'deviceoverviewpanel_summary';
    Ext.ComponentMgr.onAvailable(DEVICE_OVERVIEW_ID, function(){
        var box = Ext.getCmp(DEVICE_OVERVIEW_ID);
        box.removeField('uptime');
        box.removeField('memory');
    });

    var DEVICE_OVERVIEW_IDSUMMARY = 'deviceoverviewpanel_idsummary';
    Ext.ComponentMgr.onAvailable(DEVICE_OVERVIEW_IDSUMMARY, function(){
        var box = Ext.getCmp(DEVICE_OVERVIEW_IDSUMMARY);
        box.removeField('tagNumber');
        box.removeField('serialNumber');
    });

    var DEVICE_OVERVIEW_DESCRIPTION = 'deviceoverviewpanel_descriptionsummary';
    Ext.ComponentMgr.onAvailable(DEVICE_OVERVIEW_DESCRIPTION, function(){
        var box = Ext.getCmp(DEVICE_OVERVIEW_DESCRIPTION);
        box.removeField('rackSlot');
        box.removeField('hwManufacturer');
        box.removeField('hwModel');
        box.removeField('osManufacturer');
        box.removeField('osModel');
    });

    var DEVICE_OVERVIEW_SNMP = 'deviceoverviewpanel_snmpsummary';
    Ext.ComponentMgr.onAvailable(DEVICE_OVERVIEW_SNMP, function(){
        var box = Ext.getCmp(DEVICE_OVERVIEW_SNMP);
        box.removeField('snmpSysName');
        box.removeField('snmpLocation');
        box.removeField('snmpContact');
        box.removeField('snmpDescr');
        box.removeField('snmpCommunity');
        box.removeField('snmpVersion');
    });
});

(function(){

var ZC = Ext.ns('Zenoss.component');

Ext.apply(Zenoss.render, {
    ZenPacks_zenoss_OpenStack_Endpoint_entityLinkFromGrid: function(obj, col, record) {
        if (!obj)
            return;

        if (typeof(obj) == 'string')
            obj = record.data;

        if (!obj.title && obj.name)
            obj.title = obj.name;

        var isLink = false;

        if (this.refName == 'componentgrid') {
            // Zenoss >= 4.2 / ExtJS4
            if (this.subComponentGridPanel || this.componentType != obj.meta_type)
                isLink = true;
        } else {
            // Zenoss < 4.2 / ExtJS3
            if (!this.panel || this.panel.subComponentGridPanel)
                isLink = true;
        }

        if (isLink) {
            return '<a href="javascript:Ext.getCmp(\'component_card\').componentgrid.jumpToEntity(\''+obj.uid+'\', \''+obj.meta_type+'\');">'+obj.title+'</a>';
        } else {
            return obj.title;
        }
    },
});

ZC.OpenStackAvailabilityZonePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackAvailabilityZone',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackAvailabilityZonePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackAvailabilityZonePanel', ZC.OpenStackAvailabilityZonePanel);

ZC.OpenStackCellPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackCell',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackCellPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackCellPanel', ZC.OpenStackCellPanel);

ZC.OpenStackComputeNodePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackComputeNode',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackComputeNodePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackComputeNodePanel', ZC.OpenStackComputeNodePanel);

ZC.OpenStackControllerNodePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackControllerNode',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackControllerNodePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackControllerNodePanel', ZC.OpenStackControllerNodePanel);

ZC.OpenStackFlavorPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackFlavor',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'flavorRAM',
                direction: 'ASC'
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'flavorId'},
                {name: 'flavorRAM'},
                {name: 'flavorDisk'},
                {name: 'servers_count'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                dataIndex: 'flavorRAM',
                header: _t('RAM'),
                renderer: Zenoss.render.bytesString,                
                sortable: true,
                width: 70,
                id: 'flavorRAM'
            },{
                dataIndex: 'flavorDisk',
                header: _t('Disk'),
                renderer: Zenoss.render.bytesString,                
                sortable: true,
                width: 70,
                id: 'flavorDisk'
            },{
                id: 'servers_count',
                dataIndex: 'servers_count',
                header: _t('# Servers'),
                sortable: true,
                width: 70
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackFlavorPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackFlavorPanel', ZC.OpenStackFlavorPanel);

ZC.OpenStackHypervisorPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackHypervisor',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackHypervisorPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackHypervisorPanel', ZC.OpenStackHypervisorPanel);

Zenoss.nav.appendTo('Component', [{
    id: 'component_Hypervisors',
    text: _t('Hypervisors'),
    xtype: 'OpenStackHypervisorPanel',
    subComponentGridPanel: true,
    filterNav: function(navpanel) {
        switch (navpanel.refOwner.componentType) {
            case 'OpenStackServer': return true;
            default: return false;
        }
    },
    setContext: function(uid) {
        ZC.OpenStackHypervisorPanel.superclass.setContext.apply(this, [uid]);
    }
}]);

ZC.OpenStackImagePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackImage',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'imageId'},
                {name: 'imageStatus'},
                {name: 'imageCreated'},
                {name: 'imageUpdated'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                dataIndex: 'imageId',
                header: _t('imageId'),
                sortable: true,
                width: 10,
                id: 'imageId'
            },{
                dataIndex: 'imageStatus',
                header: _t('imageStatus'),
                sortable: true,
                width: 10,
                id: 'imageStatus'
            },{
                dataIndex: 'imageCreated',
                header: _t('imageCreated'),
                sortable: true,
                width: 10,
                id: 'imageCreated'
            },{
                dataIndex: 'imageUpdated',
                header: _t('imageUpdated'),
                sortable: true,
                width: 10,
                id: 'imageUpdated'
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackImagePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackImagePanel', ZC.OpenStackImagePanel);

ZC.OpenStackNovaApiPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackNovaApi',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackNovaApiPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackNovaApiPanel', ZC.OpenStackNovaApiPanel);

ZC.OpenStackNovaComputePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackNovaCompute',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackNovaComputePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackNovaComputePanel', ZC.OpenStackNovaComputePanel);

ZC.OpenStackNovaConductorPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackNovaConductor',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackNovaConductorPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackNovaConductorPanel', ZC.OpenStackNovaConductorPanel);

ZC.OpenStackNovaDatabasePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackNovaDatabase',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackNovaDatabasePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackNovaDatabasePanel', ZC.OpenStackNovaDatabasePanel);

ZC.OpenStackNovaDatabasePanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackNovaDatabase',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackNovaDatabasePanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackNovaDatabasePanel', ZC.OpenStackNovaDatabasePanel);

ZC.OpenStackNovaSchedulerPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackNovaScheduler',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackNovaSchedulerPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackNovaSchedulerPanel', ZC.OpenStackNovaSchedulerPanel);

ZC.OpenStackRegionPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackRegion',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackRegionPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackRegionPanel', ZC.OpenStackRegionPanel);

ZC.OpenStackServerPanel = Ext.extend(ZC.ComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            componentType: 'OpenStackServer',
            autoExpandColumn: 'name',
            sortInfo: {
                field: 'name',
                direction: 'asc',
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'status'},
                {name: 'severity'},
                {name: 'usesMonitorAttribute'},
                {name: 'monitor'},
                {name: 'monitored'},
                {name: 'serverId'},
                {name: 'serverStatus'},
                {name: 'serverBackupEnabled'},
                {name: 'serverBackupDaily'},
                {name: 'serverBackupWeekly'},
                {name: 'publicIps'},
                {name: 'privateIps'},
                {name: 'hostId'},
                {name: 'locking'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'name',
                dataIndex: 'name',
                header: _t('Name'),
                sortable: true
            },{
                dataIndex: 'serverId',
                header: _t('serverId'),
                sortable: true,
                width: 10,
                id: 'serverId'
            },{
                dataIndex: 'serverStatus',
                header: _t('serverStatus'),
                sortable: true,
                width: 10,
                id: 'serverStatus'
            },{
                dataIndex: 'serverBackupEnabled',
                header: _t('serverBackupEnabled'),
                sortable: true,
                width: 10,
                id: 'serverBackupEnabled'
            },{
                dataIndex: 'serverBackupDaily',
                header: _t('serverBackupDaily'),
                sortable: true,
                width: 10,
                id: 'serverBackupDaily'
            },{
                dataIndex: 'serverBackupWeekly',
                header: _t('serverBackupWeekly'),
                sortable: true,
                width: 10,
                id: 'serverBackupWeekly'
            },{
                dataIndex: 'publicIps',
                header: _t('publicIps'),
                sortable: true,
                width: 10,
                id: 'publicIps'
            },{
                dataIndex: 'privateIps',
                header: _t('privateIps'),
                sortable: true,
                width: 10,
                id: 'privateIps'
            },{
                dataIndex: 'hostId',
                header: _t('hostId'),
                sortable: true,
                width: 10,
                id: 'hostId'
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 70
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });

        ZC.OpenStackServerPanel.superclass.constructor.call(
            this, config);
    }
});

Ext.reg('OpenStackServerPanel', ZC.OpenStackServerPanel);

Zenoss.nav.appendTo('Component', [{
    id: 'component_Servers',
    text: _t('Servers'),
    xtype: 'OpenStackServerPanel',
    subComponentGridPanel: true,
    filterNav: function(navpanel) {
        switch (navpanel.refOwner.componentType) {
            case 'OpenStackFlavor': return true;
            case 'OpenStackImage': return true;
            default: return false;
        }
    },
    setContext: function(uid) {
        ZC.OpenStackServerPanel.superclass.setContext.apply(this, [uid]);
    }
}]);


})();
