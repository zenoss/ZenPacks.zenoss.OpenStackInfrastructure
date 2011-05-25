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
                    name: 'hostname',
                    fieldLabel: _t('Hostname or IP'),
                    id: "openstackTitleField",
                    width: 260,
                    allowBlank: false
                }, {
                    xtype: 'textfield',
                    name: 'authUrl',
                    fieldLabel: _t('Auth URL'),
                    id: "openstackAuthUrlField",
                    width: 260,
                    allowBlank: false
                }, {
                    xtype: 'textfield',
                    name: 'username',
                    fieldLabel: _t('Username'),
                    id: "openstackUsernameField",
                    width: 260,
                    allowBlank: false
                }, {
                    xtype: 'textfield',
                    name: 'apiKey',
                    inputType: 'password',
                    fieldLabel: _t('API Key'),
                    id: "openstackApiKeyField",
                    width: 260,
                    allowBlank: false
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

NS.OpenStackEndpointInspector = Ext.extend(Zenoss.inspector.DeviceInspector, {
    constructor: function(config) {
        NS.OpenStackEndpointInspector.superclass.constructor.call(this, config);
        this.addPropertyTpl(_t('Authentication URL'), '{values.authUrl}');
        this.addPropertyTpl(_t('Username'), '{values.username}');
        this.addPropertyTpl(_t('Total Servers'), '{values.serverCount}');
        this.addPropertyTpl(_t('Total Flavors'), '{values.flavorCount}');
        this.addPropertyTpl(_t('Total Images'), '{values.imageCount}');
    }
});

Ext.reg('OpenStackEndpointInspector', NS.OpenStackEndpointInspector);
Zenoss.inspector.registerInspector(
    'OpenStackEndpoint', 'OpenStackEndpointInspector');

NS.OpenStackServerInspector = Ext.extend(Zenoss.inspector.ComponentInspector, {
    constructor: function(config) {
        NS.OpenStackServerInspector.superclass.constructor.call(this, config);
        this.addPropertyTpl(_t('Guest Device'),
            '{[Zenoss.render.link(values.guestDevice)]}');

        this.addPropertyTpl(_t('Server Status'), '{values.serverStatus}');
        this.addPropertyTpl(_t('Public IP'), '{values.publicIp}');
        this.addPropertyTpl(_t('Private IP'), '{values.privateIp}');
        this.addPropertyTpl(_t('Flavor'),
            '{[Zenoss.render.link(values.flavor)]}');

        this.addPropertyTpl(_t('Image'),
            '{[Zenoss.render.link(values.image)]}');

        this.addPropertyTpl(_t('Host ID'), '{values.hostId}');
    }
});

Ext.reg('OpenStackServerInspector', NS.OpenStackServerInspector);
Zenoss.inspector.registerInspector(
    'OpenStackServer', 'OpenStackServerInspector');

}());

