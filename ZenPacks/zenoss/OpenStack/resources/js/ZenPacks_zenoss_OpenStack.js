(function(){

var ZC = Ext.ns('Zenoss.component');

ZC.registerName('OpenStackLogicalComponent', _t('LogicalComponent'), _t('LogicalComponents'));
ZC.registerName('OpenStackCell', _t('Cell'), _t('Cells'));
ZC.registerName('OpenStackControllerNode', _t('ControllerNode'), _t('ControllerNodes'));
ZC.registerName('OpenStackNovaScheduler', _t('NovaScheduler'), _t('NovaSchedulers'));
ZC.registerName('OpenStackOrgComponent', _t('OrgComponent'), _t('OrgComponents'));
ZC.registerName('OpenStackNovaDatabase', _t('NovaDatabase'), _t('NovaDatabases'));
ZC.registerName('OpenStackHypervisor', _t('Hypervisor'), _t('Hypervisors'));
ZC.registerName('OpenStackSoftwareComponent', _t('SoftwareComponent'), _t('SoftwareComponents'));
ZC.registerName('OpenStackNovaConductor', _t('NovaConductor'), _t('NovaConductors'));
ZC.registerName('OpenStackComputeNode', _t('ComputeNode'), _t('ComputeNodes'));
ZC.registerName('OpenStackKeystoneEndpoint', _t('KeystoneEndpoint'), _t('KeystoneEndpoints'));
ZC.registerName('OpenStackRegion', _t('Region'), _t('Regions'));
ZC.registerName('OpenStackImage', _t('Image'), _t('Images'));
ZC.registerName('OpenStackFlavor', _t('Flavor'), _t('Flavors'));
ZC.registerName('OpenStackNovaCompute', _t('NovaCompute'), _t('NovaComputes'));
ZC.registerName('OpenstackComponent', _t('OpenstackComponent'), _t('OpenstackComponents'));
ZC.registerName('OpenStackNodeComponent', _t('NodeComponent'), _t('NodeComponents'));
ZC.registerName('OpenStackEndpoint', _t('Endpoint'), _t('Endpoints'));
ZC.registerName('OpenStackNovaApi', _t('NovaApi'), _t('NovaApis'));
ZC.registerName('OpenStackServer', _t('Server'), _t('Servers'));
ZC.registerName('OpenStackAvailabilityZone', _t('AvailabilityZone'), _t('AvailabilityZones'));
ZC.registerName('OpenStackNovaEndpoint', _t('NovaEndpoint'), _t('NovaEndpoints'));
ZC.registerName('OpenStackDeviceProxyComponent', _t('DeviceProxyComponent'), _t('DeviceProxyComponents'));

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
                        xtype: 'combo',
                        width: 260,
                        name: 'api_version',
                        fieldLabel: _t('Compute API Version'),
                        id: "openstack_api_version",
                        mode: 'local',
                        store: [['1.1', '1.1'], ['2', '2'], ['3', '3']],
                        value: '2',
                        forceSelection: true,
                        editable: false,
                        allowBlank: false,
                        triggerAction: 'all',
                        selectOnFocus: false,
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',                        
                        text: '(NOVA_VERSION)',
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

