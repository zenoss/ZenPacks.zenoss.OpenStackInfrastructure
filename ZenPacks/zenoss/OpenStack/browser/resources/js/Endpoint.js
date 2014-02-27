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

/*
 * Endpoint-local custom renderers.
 */
Ext.apply(Zenoss.render, {
    OpenStack_entityLinkFromGrid: function(obj, col, record) {
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
    }
});

/*
 * Generic ComponentGridPanel
 */
ZC.OpenStackComponentGridPanel = Ext.extend(ZC.ComponentGridPanel, {
    subComponentGridPanel: false,

    jumpToEntity: function(uid, meta_type) {
        var tree = Ext.getCmp('deviceDetailNav').treepanel;
        var tree_selection_model = tree.getSelectionModel();
        var components_node = tree.getRootNode().findChildBy(
            function(n) {
                if (n.data) {
                    // Zenoss >= 4.2 / ExtJS4
                    return n.data.text == 'Components';
                }

                // Zenoss < 4.2 / ExtJS3
                return n.text == 'Components';
            });

        // Reset context of component card.
        var component_card = Ext.getCmp('component_card');

        if (components_node.data) {
            // Zenoss >= 4.2 / ExtJS4
            component_card.setContext(components_node.data.id, meta_type);
        } else {
            // Zenoss < 4.2 / ExtJS3
            component_card.setContext(components_node.id, meta_type);
        }

        // Select chosen row in component grid.
        component_card.selectByToken(uid);

        // Select chosen component type from tree.
        var component_type_node = components_node.findChildBy(
            function(n) {
                if (n.data) {
                    // Zenoss >= 4.2 / ExtJS4
                    return n.data.id == meta_type;
                }

                // Zenoss < 4.2 / ExtJS3
                return n.id == meta_type;
            });

        if (component_type_node.select) {
            tree_selection_model.suspendEvents();
            component_type_node.select();
            tree_selection_model.resumeEvents();
        } else {
            tree_selection_model.select([component_type_node], false, true);
        }
    }
});

/*
 * Flavor ComponentGridPanel
 */
ZC.OpenStackFlavorPanel = Ext.extend(ZC.OpenStackComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            autoExpandColumn: 'name',
            componentType: 'OpenStackFlavor',
            sortInfo: {
                field: 'flavorRAM',
                direction: 'ASC'
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'severity'},
                {name: 'flavorRAM'},
                {name: 'flavorDisk'},
                {name: 'serverCount'},
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
                renderer: Zenoss.render.OpenStack_entityLinkFromGrid,
                panel: this
            },{
                id: 'flavorRAM',
                dataIndex: 'flavorRAM',
                header: _t('RAM'),
                renderer: Zenoss.render.bytesString,
                sortable: true,
                width: 70
            },{
                id: 'flavorDisk',
                dataIndex: 'flavorDisk',
                header: _t('Disk'),
                renderer: Zenoss.render.bytesString,
                sortable: true,
                width: 70
            },{
                id: 'serverCount',
                dataIndex: 'serverCount',
                header: _t('# Servers'),
                sortable: true,
                width: 70
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 65
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });
        ZC.OpenStackFlavorPanel.superclass.constructor.call(this, config);
    }
});

Ext.reg('OpenStackFlavorPanel', ZC.OpenStackFlavorPanel);

/*
 * Image ComponentGridPanel
 */
ZC.OpenStackImagePanel = Ext.extend(ZC.OpenStackComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            autoExpandColumn: 'name',
            componentType: 'OpenStackImage',
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'severity'},
                {name: 'imageStatus'},
                {name: 'imageCreated'},
                {name: 'imageUpdated'},
                {name: 'serverCount'},
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
                renderer: Zenoss.render.OpenStack_entityLinkFromGrid,
                panel: this
            },{
                id: 'imageStatus',
                dataIndex: 'imageStatus',
                header: _t('Status'),
                sortable: true,
                width: 80
            },{
                id: 'imageCreated',
                dataIndex: 'imageCreated',
                header: _t('Created'),
                sortable: true,
                width: 155
            },{
                id: 'imageUpdated',
                dataIndex: 'imageUpdated',
                header: _t('Updated'),
                sortable: true,
                width: 155
            },{
                id: 'serverCount',
                dataIndex: 'serverCount',
                header: _t('# Servers'),
                sortable: true,
                width: 70
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 65
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });
        ZC.OpenStackImagePanel.superclass.constructor.call(this, config);
    }
});

Ext.reg('OpenStackImagePanel', ZC.OpenStackImagePanel);

/*
 * Server ComponentGridPanel
 */
ZC.OpenStackServerPanel = Ext.extend(ZC.OpenStackComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            autoExpandColumn: 'name',
            componentType: 'OpenStackServer',
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'meta_type'},
                {name: 'severity'},
                {name: 'guestDevice'},
                {name: 'serverStatus'},
                {name: 'flavor'},
                {name: 'image'},
                {name: 'publicIps'},
                {name: 'privateIps'},
                {name: 'serverBackupEnabled'},
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
                renderer: Zenoss.render.OpenStack_entityLinkFromGrid,
                panel: this
            },{
                id: 'guestDevice',
                dataIndex: 'guestDevice',
                header: _t('Guest Device'),
                renderer: function(obj) {
                    if (obj && obj.uid && obj.name) {
                        return Zenoss.render.link(obj.uid, undefined, obj.name);
                    }
                },
                width: 160
            },{
                id: 'serverStatus',
                dataIndex: 'serverStatus',
                header: _t('Status'),
                sortable: true,
                width: 80
            },{
                id: 'flavor',
                dataIndex: 'flavor',
                header: _t('Flavor'),
                renderer: Zenoss.render.OpenStack_entityLinkFromGrid,
                width: 85
            },{
                id: 'image',
                dataIndex: 'image',
                header: _t('Image'),
                renderer: Zenoss.render.OpenStack_entityLinkFromGrid,
                width: 140
            },{
                id: 'publicIps',
                dataIndex: 'publicIps',
                header: _t('Public IPs'),
                width: 85
            },{
                id: 'privateIps',
                dataIndex: 'privateIps',
                header: _t('Private IPs'),
                width: 85
            },{
                id: 'serverBackupEnabled',
                dataIndex: 'serverBackupEnabled',
                header: _t('Backup'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 55
            },{
                id: 'monitored',
                dataIndex: 'monitored',
                header: _t('Monitored'),
                renderer: Zenoss.render.checkbox,
                sortable: true,
                width: 65
            },{
                id: 'locking',
                dataIndex: 'locking',
                header: _t('Locking'),
                renderer: Zenoss.render.locking_icons,
                width: 65
            }]
        });
        ZC.OpenStackServerPanel.superclass.constructor.call(this, config);
    }
});

Ext.reg('OpenStackServerPanel', ZC.OpenStackServerPanel);

})();

