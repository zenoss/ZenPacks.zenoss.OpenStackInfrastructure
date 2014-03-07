(function(){

/*
 * Inspectors.
 */
var NS = Ext.namespace('Zenoss.zenpacks.OpenStack');


// OpenStackEndPoint Inspector
function addOpenStackEndPointInspectorFields(inspector) {
    inspector.addPropertyTpl(_t('Username'), '{values.username}');
    inspector.addPropertyTpl(_t('Project ID'), '{values.project_id}');
    inspector.addPropertyTpl(_t('Auth URL'), '{values.auth_url}');
    inspector.addPropertyTpl(_t('Compute API Version'), '{values.api_version}');
    inspector.addPropertyTpl(_t('Region Name'), '{values.region_name}');
    inspector.addPropertyTpl(_t('Total Servers'), '{values.server_count}');
    inspector.addPropertyTpl(_t('Total Flavors'), '{values.flavor_count}');
    inspector.addPropertyTpl(_t('Total Images'), '{values.image_count}');
}

if (Ext.define === undefined) {
    // Compatibility with Zenoss versions earlier than 4.2.
    NS.OpenStackEndpointInspector = Ext.extend(Zenoss.inspector.DeviceInspector, {
        constructor: function(config) {
            NS.OpenStackEndpointInspector.superclass.constructor.call(this, config);
            addOpenStackEndPointInspectorFields(this);
        }
    });

    Ext.reg('OpenStackEndpointInspector', NS.OpenStackEndpointInspector);
} else {
    // Zenoss 4.2+ compatibility.
    Ext.define("Zenoss.zenpacks.OpenStack.OpenStackEndpointInspector", {
        extend: "Zenoss.inspector.DeviceInspector",
        alias: ["widget.OpenStackEndpointInspector"],
        constructor: function(config) {
            this.callParent(arguments);
            addOpenStackEndPointInspectorFields(this);
        }
    });
}

Zenoss.inspector.registerInspector('OpenStackEndpoint', 'OpenStackEndpointInspector');


// OpenStackServer Inspector
function addOpenStackServerInspectorFields(inspector) {
    inspector.addPropertyTpl(_t('Guest Device'),
        '{[Zenoss.render.link(values.guestDevice)]}');

    inspector.addPropertyTpl(_t('Server Status'), '{values.serverStatus}');
    inspector.addPropertyTpl(_t('Public IPs'), '{values.publicIps}');
    inspector.addPropertyTpl(_t('Private IPs'), '{values.privateIps}');
    inspector.addPropertyTpl(_t('Flavor'),
        '{[Zenoss.render.link(values.flavor)]}');

    inspector.addPropertyTpl(_t('Image'),
        '{[Zenoss.render.link(values.image)]}');

    inspector.addPropertyTpl(_t('Host ID'), '{values.hostId}');
}

if (Ext.define === undefined) {
    // Compatibility with Zenoss versions earlier than 4.2.
    NS.OpenStackServerInspector = Ext.extend(Zenoss.inspector.ComponentInspector, {
        constructor: function(config) {
            NS.OpenStackServerInspector.superclass.constructor.call(this, config);
            addOpenStackServerInspectorFields(this);
        }
    });

    Ext.reg('OpenStackServerInspector', NS.OpenStackServerInspector);
} else {
    // Zenoss 4.2+ compatibility.
    Ext.define("Zenoss.zenpacks.OpenStack.OpenStackServerInspector", {
        extend: "Zenoss.inspector.DeviceInspector",
        alias: ["widget.OpenStackServerInspector"],
        constructor: function(config) {
            this.callParent(arguments);
            addOpenStackServerInspectorFields(this);
        }
    });
}

Zenoss.inspector.registerInspector('OpenStackServer', 'OpenStackServerInspector');

}());
