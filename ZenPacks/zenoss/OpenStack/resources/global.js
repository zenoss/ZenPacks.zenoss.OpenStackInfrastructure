(function(){

var addOpenStack = new Zenoss.Action({
    text: _t('Add OpenStack') + '...',
    id: 'addopenstack-item',
    permission: 'Manage DMD',
    handler: function(btn, e){
        var win = new Zenoss.dialog.CloseDialog({
            width: 450,
            title: _t('Add OpenStack'),
            items: [{
                xtype: 'form',
                buttonAlign: 'left',
                monitorValid: true,
                labelAlign: 'top',
                footerStyle: 'padding-left: 0',
                border: false,
                items: [{
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{
                        xtype: 'textfield',
                        name: 'username',
                        fieldLabel: _t('Username'),
                        id: "openstack_username",
                        width: 260,
                        allowBlank: false   
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',
                        text: '(OS_USERNAME)',
                        margin: '0 0 0 10'                        
                    }]
                }, {
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{
                        xtype: 'textfield',
                        name: 'api_key',
                        fieldLabel: _t('API Key'),
                        id: "openstack_api_key",
                        width: 260,
                        allowBlank: false
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',                        
                        text: '(OS_PASSWORD)',
                        margin: '0 0 0 10'                        
                    }]                        
                }, {
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{                
                        xtype: 'textfield',
                        name: 'project_id',
                        fieldLabel: _t('Project/Tenant ID'),
                        id: "openstack_project_id",
                        width: 260,
                        allowBlank: true
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',                        
                        text: '(NOVA_PROJECT_ID or OS_TENANT_NAME)',
                        margin: '0 0 0 10'
                    }]
                }, {
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{               
                        xtype: 'textfield',
                        name: 'auth_url',
                        fieldLabel: _t('Auth URL'),
                        id: "openstack_auth_url",
                        width: 260,
                        allowBlank: true,
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',                        
                        text: '(OS_AUTH_URL)',
                        margin: '0 0 0 10'
                    }]
                }, {
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{                    
                        xtype: 'textfield',
                        name: 'region_name',
                        fieldLabel: _t('Region Name'),
                        id: "openstack_region_name",
                        width: 260,
                        allowBlank: true
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',                        
                        text: '(OS_REGION_NAME)',
                        margin: '0 0 0 10'
                    }]
                }, {
                    xtype: 'combo',
                    width: 260,
                    name: 'collector',
                    fieldLabel: _t('Collector'),
                    id: 'openstack_collector',
                    mode: 'local',
                    store: new Ext.data.ArrayStore({
                        data: Zenoss.env.COLLECTORS,
                        fields: ['name']
                    }),
                    valueField: 'name',
                    displayField: 'name',
                    forceSelection: true,
                    editable: false,
                    allowBlank: false,
                    triggerAction: 'all',
                    selectOnFocus: false,
                    listeners: {
                        'afterrender': function(component) {
                            var index = component.store.find('name', 'localhost');
                            if (index >= 0) {
                                component.setValue('localhost');
                            }
                        }
                    }
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
                                if (Zenoss.JobsWidget) {
                                    Zenoss.message.success(_t('Add OpenStack job submitted.'));
                                } else {
                                    Zenoss.message.success(
                                        _t('Add OpenStack job submitted. <a href="/zport/dmd/JobManager/jobs/{0}/viewlog">View Job Log</a>'),
                                        response.jobId);
                                }
                            }
                            else {
                                Zenoss.message.error(_t('Error adding OpenStack: {0}'),
                                    response.msg);
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

})();

