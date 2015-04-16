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

        box.addField({name: 'region_title',
            fieldLabel: _t('Region Name'),
            xtype: 'displayfield'});
        box.addField({name: 'numberZones',
            fieldLabel: _t('Number of Availability Zones'),
            xtype: 'displayfield'});
        box.addField({name: 'numberHosts',
            fieldLabel: _t('Number of Hosts'),
            xtype: 'displayfield'});
        box.addField({name: 'numberNovaServices',
            fieldLabel: _t('Number of Nova Services'),
            xtype: 'displayfield'});
        box.addField({name: 'numberNeutronAgents',
            fieldLabel: _t('Number of Neutron Agents'),
            xtype: 'displayfield'});
        box.addField({name: 'numberFloatingips',
            fieldLabel: _t('Number of Floating IP Addresses'),
            xtype: 'displayfield'});
        box.addField({name: 'numberTenants',
            fieldLabel: _t('Number of Tenants'),
            xtype: 'displayfield'});
        box.addField({name: 'numberInstances',
            fieldLabel: _t('Number of Virtual Machines'),
            xtype: 'displayfield'});
        box.addField({name: 'numberNetworks',
            fieldLabel: _t('Number of Networks'),
            xtype: 'displayfield'});
        box.addField({name: 'numberRouters',
            fieldLabel: _t('Number of Routers'),
            xtype: 'displayfield'});
    });
});


Ext.apply(Zenoss.render, {
    openstack_ServiceOperStatus: function(value) {
        switch (value) {
            case 'UNKNOWN': return Zenoss.render.severity(1);
            case 'UP': return Zenoss.render.severity(0);
            case 'DOWN': return Zenoss.render.severity(5);
            default: return Zenoss.render.severity(1);
        }
    },

    openstack_ServiceEnabledStatus: function(value) {
        switch (value) {
            case true: return Zenoss.render.severity(0);
            case false: return Zenoss.render.severity(5);
            default: return Zenoss.render.severity(1);
        }
    },

    openstack_uppercase_renderer: function(value) {
        return value.toUpperCase();
    },

    openstack_uid_renderer: function(uid, name) {
        // Just straight up links to the object.
        var parts;
        if (!uid) {
            return uid;
        }
        if (Ext.isObject(uid)) {
            if (uid.uid && uid.uid.indexOf('/') > -1) {
                parts = uid.uid.split('/');
                name = parts[parts.length-1];
            }
            else {
                name = uid.name;
            }
            uid = uid.uid;
        }
        if (!name) {
            parts = uid.split('/');
            name = parts[parts.length-1];
        }
        return Zenoss.render.link(null, uid, name);
    },
});


/*
 * Add the OpenStack Component View for device page.
 */
Zenoss.nav.appendTo('Device', [{
    id: 'openstackcomponentview',
    text: _t('OpenStack Component View'),
    xtype: 'dynamicview',
    relationshipFilter: 'openstack_link',
    viewName: 'openstack_view'
}]);

/*
 * Enable OpenStack Component View for components as well.
 */

 Zenoss.nav.appendTo('Component', [{
    id: 'component_openstackcomponentview',
    text: _t('OpenStack Component View'),
    xtype: 'dynamicview',
    relationshipFilter: 'openstack_link',
    viewName: 'openstack_view'
}]);


