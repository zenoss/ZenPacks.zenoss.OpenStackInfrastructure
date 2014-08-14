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
    });
});
