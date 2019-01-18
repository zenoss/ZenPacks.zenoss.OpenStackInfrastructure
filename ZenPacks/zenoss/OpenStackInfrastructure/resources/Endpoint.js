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
      this.hide();
    });

    /* Hide Software component, as it always empty */
    var DEVICE_ELEMENTS = "subselecttreepaneldeviceDetailNav"
    Ext.ComponentMgr.onAvailable(DEVICE_ELEMENTS, function(){
        var DEVICE_PANEL = Ext.getCmp(DEVICE_ELEMENTS);
        Ext.apply(DEVICE_PANEL, {
            listeners: {
                afterrender: function() {
                    var tree = Ext.getCmp(DEVICE_PANEL.items.items[0].id);
                    var items = tree.store.data.items;
                    for (i in items){
                        if (items[i].data.id.match(/software*/)){
                            try {
                                tree.store.remove(items[i]);
                                tree.store.sync();
                            } catch(err){}
                        }
                    }
                }
            }
        })
    })
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
        if (value == null) {
            return "";
        } else {
            return value.toUpperCase();
        }
    },

});


Ext.onReady(function(){
    if (Ext.ClassManager.isCreated("Zenoss.dynamicview.DynamicViewComponent")) {
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
    }
});

