(function(){

var addOpenStack = new Zenoss.Action({
    text: _t('Add OpenStack') + '...',
    id: 'addopenstack-item',
    permission: 'Manage DMD',
    handler: function(btn, e){
        var win = new Zenoss.dialog.CloseDialog({
            width: 300,
            title: _t('Add OpenStack'),
            items: [{
                xtype: 'form',
                buttonAlign: 'left',
                monitorValid: true,
                labelAlign: 'top',
                footerStyle: 'padding-left: 0',
                border: false,
                items: [{
                    xtype: 'textfield',
                    name: 'username',
                    fieldLabel: _t('Username'),
                    id: "openstack_username",
                    width: 260,
                    allowBlank: false
                }, {
                    xtype: 'textfield',
                    name: 'api_key',
                    fieldLabel: _t('API Key'),
                    id: "openstack_api_key",
                    width: 260,
                    allowBlank: false
                }, {
                    xtype: 'textfield',
                    name: 'project_id',
                    fieldLabel: _t('Project ID'),
                    id: "openstack_project_id",
                    width: 260,
                    allowBlank: true
                }, {
                    xtype: 'textfield',
                    name: 'auth_url',
                    fieldLabel: _t('Auth URL'),
                    id: "openstack_auth_url",
                    width: 260,
                    allowBlank: true,
                    value: 'https://auth.api.rackspacecloud.com/v1.0'
                }, {
                    xtype: 'textfield',
                    name: 'region_name',
                    fieldLabel: _t('Region Name'),
                    id: "openstack_region_name",
                    width: 260,
                    allowBlank: true
                }],
                buttons: [{
                    xtype: 'DialogButton',
                    id: 'addOpenStackdevice-submit',
                    text: _t('Add'),
                    formBind: true,
                    handler: function(b) {
                        var form = b.ownerCt.ownerCt.getForm();
                        var opts = form.getFieldValues();

                        Zenoss.remote.OpenStackRouter.addOpenStack(opts,
                        function(response) {
                            if (response.success) {
                                new Zenoss.dialog.SimpleMessageDialog({
                                    message: _t('Add OpenStack job submitted.'),
                                    buttons: [{
                                        xtype: 'DialogButton',
                                        text: _t('OK')
                                    }, {
                                        xtype: 'button',
                                        text: _t('View Job Log'),
                                        handler: function() {
                                            window.location =
                                                '/zport/dmd/JobManager/jobs/' +
                                                response.jobId + '/viewlog';
                                        }
                                    }]
                                }).show();
                            }
                            else {
                                new Zenoss.dialog.SimpleMessageDialog({
                                    message: response.msg,
                                    buttons: [{
                                        xtype: 'DialogButton',
                                        text: _t('OK')
                                    }]
                                }).show();
                            }
                        });
                    }
                }, Zenoss.dialog.CANCEL]
            }]
        });
        win.show();
    }
});

// Push the addOpenStack action to the adddevice button
Ext.ns('Zenoss.extensions');
Zenoss.extensions.adddevice = Zenoss.extensions.adddevice instanceof Array ?
                              Zenoss.extensions.adddevice : [];
Zenoss.extensions.adddevice.push(addOpenStack);


/*
 * Inspectors.
 */
var NS = Ext.namespace('Zenoss.zenpacks.OpenStack');


// OpenStackEndPoint Inspector
function addOpenStackEndPointInspectorFields(inspector) {
    inspector.addPropertyTpl(_t('Username'), '{values.username}');
    inspector.addPropertyTpl(_t('Project ID'), '{values.project_id}');
    inspector.addPropertyTpl(_t('Auth URL'), '{values.auth_url}');
    inspector.addPropertyTpl(_t('Region Name'), '{values.region_name}');
    inspector.addPropertyTpl(_t('Total Servers'), '{values.serverCount}');
    inspector.addPropertyTpl(_t('Total Flavors'), '{values.flavorCount}');
    inspector.addPropertyTpl(_t('Total Images'), '{values.imageCount}');
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
