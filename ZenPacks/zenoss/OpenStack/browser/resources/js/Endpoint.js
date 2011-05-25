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

    var DEVICE_OVERVIEW_DESCRIPTION = 'deviceoverviewpanel_descriptionsummary';
    Ext.ComponentMgr.onAvailable(DEVICE_OVERVIEW_DESCRIPTION, function(){
        var box = Ext.getCmp(DEVICE_OVERVIEW_DESCRIPTION);
        box.removeField('rackSlot');
        box.removeField('collector');
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
 * Friendly names for the components.
 */
ZC.registerName('OpenStackFlavor', _t('Flavor'), _t('Flavors'));
ZC.registerName('OpenStackImage', _t('Image'), _t('Images'));
ZC.registerName('OpenStackServer', _t('Server'), _t('Servers'));

/*
 * Register types so jumpToEntity will work.
 */

// The DeviceClass matcher got too greedy in 3.1.x branch. Throttling it.
Zenoss.types.TYPES.DeviceClass[0] = new RegExp(
    "^/zport/dmd/Devices(/(?!devices)[^/*])*/?$");

Zenoss.types.register({
    'OpenStackFlavor':
        "^/zport/dmd/Devices/OpenStack/devices/.*/flavors/[^/]*/?$",
    'OpenStackImage':
        "^/zport/dmd/Devices/OpenStack/devices/.*/images/[^/]*/?$",
    'OpenStackServer':
        "^/zport/dmd/Devices/OpenStack/devices/.*/servers/[^/]*/?$"
});


/*
 * Endpoint-local custom renderers.
 */
Ext.apply(Zenoss.render, {    
    entityLinkFromGrid: function(obj) {
        if (obj && obj.uid && obj.name) {
            if ( !this.panel || this.panel.subComponentGridPanel) {
                return String.format(
                    '<a href="javascript:Ext.getCmp(\'component_card\').componentgrid.jumpToEntity(\'{0}\', \'{1}\');">{1}</a>',
                    obj.uid, obj.name);
            } else {
                return obj.name;
            }
        }
    }
});

/*
 * Generic ComponentGridPanel
 */
ZC.OpenStackComponentGridPanel = Ext.extend(ZC.ComponentGridPanel, {
    subComponentGridPanel: false,
    
    jumpToEntity: function(uid, name) {
        var tree = Ext.getCmp('deviceDetailNav').treepanel,
            sm = tree.getSelectionModel(),
            compsNode = tree.getRootNode().findChildBy(function(n){
                return n.text=='Components';
            });
    
        var compType = Zenoss.types.type(uid);
        var componentCard = Ext.getCmp('component_card');
        componentCard.setContext(compsNode.id, compType);
        componentCard.selectByToken(uid);
        sm.suspendEvents();
        compsNode.findChildBy(function(n){return n.id==compType;}).select();
        sm.resumeEvents();
    }
});

/*
 * Flavor ComponentGridPanel
 */
ZC.OpenStackFlavorPanel = Ext.extend(ZC.OpenStackComponentGridPanel, {
    constructor: function(config) {
        config = Ext.applyIf(config||{}, {
            autoExpandColumn: 'entity',
            componentType: 'OpenStackFlavor',
            sortInfo: {
                field: 'flavorRAM',
                direction: 'ASC'
            },
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'severity'},
                {name: 'entity'},
                {name: 'flavorRAM'},
                {name: 'flavorDisk'},
                {name: 'serverCount'},
                {name: 'monitor'},
                {name: 'monitored'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'entity',
                dataIndex: 'entity',
                header: _t('Name'),
                renderer: Zenoss.render.entityLinkFromGrid,
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
            autoExpandColumn: 'entity',
            componentType: 'OpenStackImage',
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'severity'},
                {name: 'entity'},
                {name: 'imageStatus'},
                {name: 'imageCreated'},
                {name: 'imageUpdated'},
                {name: 'serverCount'},
                {name: 'monitor'},
                {name: 'monitored'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'entity',
                dataIndex: 'entity',
                header: _t('Name'),
                renderer: Zenoss.render.entityLinkFromGrid,
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
            autoExpandColumn: 'entity',
            componentType: 'OpenStackServer',
            fields: [
                {name: 'uid'},
                {name: 'name'},
                {name: 'severity'},
                {name: 'entity'},
                {name: 'serverStatus'},
                {name: 'flavor'},
                {name: 'image'},
                {name: 'publicIp'},
                {name: 'privateIp'},
                {name: 'serverBackupEnabled'},
                {name: 'monitor'},
                {name: 'monitored'}
            ],
            columns: [{
                id: 'severity',
                dataIndex: 'severity',
                header: _t('Events'),
                renderer: Zenoss.render.severity,
                sortable: true,
                width: 50
            },{
                id: 'entity',
                dataIndex: 'entity',
                header: _t('Name'),
                renderer: Zenoss.render.entityLinkFromGrid,
                panel: this
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
                renderer: Zenoss.render.entityLinkFromGrid,
                width: 85
            },{
                id: 'image',
                dataIndex: 'image',
                header: _t('Image'),
                renderer: Zenoss.render.entityLinkFromGrid,
                width: 140
            },{
                id: 'publicIp',
                dataIndex: 'publicIp',
                header: _t('Public IP'),
                sortable: true,
                width: 85
            },{
                id: 'privateIp',
                dataIndex: 'privateIp',
                header: _t('Private IP'),
                sortable: true,
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
            }]
        });
        ZC.OpenStackServerPanel.superclass.constructor.call(this, config);
    }
});

Ext.reg('OpenStackServerPanel', ZC.OpenStackServerPanel);

})();

