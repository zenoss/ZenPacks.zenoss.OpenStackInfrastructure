Ceilometer Configuration Example for Pike and Later
-------------------------------------------------------

This file should be part of your custom-network-configuration.yaml:

    ManagePipeline: true
    PipelinePublishers:
      - https://<first_zenoss_ip>:8342/ceilometer/v1/samples/<zenoss_devicename>?verify_ssl=False
      - https://<second_zenoss_ip>:8342/ceilometer/v1/samples/<zenoss_devicename>?verify_ssl=False
      - <other_pipeline_publishers>
    ManageEventPipeline: true
    EventPipelinePublishers:
      - https://<first_zenoss_ip>:8342/ceilometer/v1/events/<zenoss_devicename>?verify_ssl=False
      - https://<second_zenoss_ip>:8342/ceilometer/v1/events/<zenoss_devicename>?verify_ssl=False
      - <other_event_pipeline_publishers>


From bash you can populate your ip address and device name,
then execute the following:

    ipaddress=10.0.0.20
    device=TripleO411

    echo "
    ManagePipeline: true
    PipelinePublishers:
      - https://$ipaddress:8342/ceilometer/v1/samples/$device?verify_ssl=False
    ManageEventPipeline: true
    EventPipelinePublishers:
      - https://$ipaddress:8342/ceilometer/v1/events/$device?verify_ssl=False
    "

Make sure your resulting YAML is valid.
