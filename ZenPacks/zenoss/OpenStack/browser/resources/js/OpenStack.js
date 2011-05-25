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

}());

