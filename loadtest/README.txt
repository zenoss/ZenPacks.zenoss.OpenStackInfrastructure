To use:

1) Generate a fake device in zenoss, with a large number of components

 Run load_model.py
    This will create a model in the database with a specified number of controller, compute nodes, tenants, and instances.  The default size parameters can be overridden with command line arguments:
        -d DEVICE                  Device Name            (default: test_ostack)
        --controllers=CONTROLLERS  Number of Controller Nodes to create (3)
        --computes=COMPUTES        Number of Compute Nodes to create    (30)
        --tenants=TENANTS          Number of tenants to create          (50)
        --instances=INSTANCES      Number of Instances to create        (2250)

2) Start zenpython (for data collection)
    Run zenpython run -c -d <device name specified above> -v10

3) Generate simulated perf messages (over amqp)
    Run sim_perf.py -d <same device name> --nottl

    The nottl option causes the AMQP messages being generated to not have 
    time to live values, so they will not auto-expire from the rabbit queue.
    This will give a more reaslistic indication of whether the system is 
    consuming messages fast enough, as it will allow the queue to get backed up.

4)  Generate simulated model change events (over amqp)
    Run sim_events.py -d <same device name> -v10

    By default, this will perform 4 operations every 60 seconds (staggered):
        delete and re-create a random instance
        power cycle a random instance
        suspend and resume a random instance
        reboot a random instance

    The interval for each may be controlled with command-line arguments.

