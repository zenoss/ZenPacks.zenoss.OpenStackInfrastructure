(function(){

var ZC = Ext.ns('Zenoss.component');

var addOpenStack = new Zenoss.Action({
    text: _t('Add OpenStack Endpoint (Infrastructure)') + '...',
    id: 'addopenstackinfrastructure-item',
    permission: 'Manage DMD',
    handler: function(btn, e){
        // store for the region dropdown
        regionStore = new Zenoss.NonPaginatedStore({
            fields: ['key', 'label'],
            root: 'data',
            directFn: Zenoss.remote.OpenStackInfrastructureRouter.getRegions,
            remoteFilter: false,
            autoload: false
        });

        var win = new Zenoss.dialog.CloseDialog({
            width: 640,
            title: _t('Add OpenStack Endpoint (Infrastructure)'),
            items: [{
                xtype: 'form',
                id: 'addopenstackinfrastructure-form',
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
                        name: 'device_name',
                        fieldLabel: _t('Device to Create'),
                        labelWidth: 120,
                        id: "openstack_device_name",
                        width: 350,
                        allowBlank: false,
                        vtype: 'hostnameorIP'
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',
                        text: '(Do not use an actual hostname)',
                        margin: '0 0 0 10'
                    }]
                }, {
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{
                        xtype: 'textfield',
                        name: 'auth_url',
                        fieldLabel: _t('Auth URL'),
                        labelWidth: 120,
                        id: "openstack_auth_url",
                        width: 350,
                        allowBlank: false,
                        listeners: {
                            blur: this.updateRegions,
                            scope: this
                        }
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
                        name: 'username',
                        fieldLabel: _t('Username'),
                        labelWidth: 120,
                        id: "openstack_username",
                        width: 350,
                        allowBlank: false,
                        listeners: {
                            blur: this.updateRegions,
                            scope: this
                        }
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
                        xtype: 'password',
                        name: 'api_key',
                        fieldLabel: _t('Password / API Key'),
                        labelWidth: 120,
                        id: "openstack_api_key",
                        width: 350,
                        allowBlank: false,
                        listeners: {
                            blur: this.updateRegions,
                            scope: this
                        }
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
                        fieldLabel: _t('Project/Tenant Name'),
                        labelWidth: 120,
                        id: "openstack_project_id",
                        width: 350,
                        allowBlank: false,
                        listeners: {
                            blur: this.updateRegions,
                            scope: this
                        }
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
                        name: 'domain_id',
                        fieldLabel: _t('Domain Id'),
                        labelWidth: 120,
                        id: "openstack_domain_id",
                        width: 350,
                        allowBlank: false,
                        listeners: {
                            blur: this.updateRegions,
                            scope: this
                        }
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',
                        text: '(OS_PROJECT/USER_DOMAIN_NAME)',
                        margin: '0 0 0 10'
                    }]
                },{
                    xtype: 'container',
                    layout: 'hbox',
                    items: [{
                        xtype: 'combo',
                        width: 350,
                        name: 'region_name',
                        fieldLabel: _t('Region Name'),
                        labelWidth: 120,
                        id: 'region_name',
                        triggerAction: 'all',
                        queryMode: 'local',
                        valueField: 'key',
                        displayField: 'label',
                        store: regionStore,
                        forceSelection: true,
                        editable: false,
                        allowBlank: false,
                        triggerAction: 'all',
                        selectOnFocus: false
                    },{
                        xtype: 'label',
                        style: 'font-style: italic',
                        text: '(OS_REGION_NAME)',
                        margin: '0 0 0 10'
                    }]
                }, {
                    xtype: 'combo',
                    width: 350,
                    name: 'collector',
                    fieldLabel: _t('Collector'),
                        labelWidth: 120,
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

                        Zenoss.remote.OpenStackInfrastructureRouter.addOpenStack(opts,
                        function(response) {
                            if (response.success) {
                                if (Zenoss.JobsWidget) {
                                    Zenoss.message.success(_t('Add OpenStack Infrastructure job submitted.'));
                                } else {
                                    Zenoss.message.success(
                                        _t('Add OpenStack Infrastructure job submitted. <a href="/zport/dmd/JobManager/jobs/{0}/viewlog">View Job Log</a>'),
                                        response.jobId);
                                }
                            }
                            else {
                                Zenoss.message.error(_t('Error adding OpenStack Infrastructure: {0}'),
                                    response.msg);
                            }
                        });
                    }
                }, Zenoss.dialog.CANCEL]
            }]
        });

        win.show();
    },

    updateRegions: function () {
        form = Ext.getCmp('addopenstackinfrastructure-form').getForm();
        formvalues = form.getFieldValues();
        combo = Ext.getCmp('region_name');
        store = combo.getStore();

        if (formvalues.username && formvalues.api_key && formvalues.project_id && formvalues.domain_id && formvalues.auth_url) {
            store.load({
               params: {
                   username: formvalues.username,
                   api_key: formvalues.api_key,
                   project_id: formvalues.project_id,
                   auth_url: formvalues.auth_url,
                   domain_id: formvalues.domain_id
               },
               callback: function(records, operation, success) {
                    combo.select(store.getAt(0));
                    combo.fireEvent('select');
               }
            });
        } else {
            store.removeAll()
        }
    }

});

// Push the addOpenStack action to the adddevice button
Ext.ns('Zenoss.extensions');
Zenoss.extensions.adddevice = Zenoss.extensions.adddevice instanceof Array ?
                              Zenoss.extensions.adddevice : [];
Zenoss.extensions.adddevice.push(addOpenStack);

})();
