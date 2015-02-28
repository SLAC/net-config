#!/bin/env/python

import sys
import netconfig
import logging

if __name__ == "__main__":
    logging.basicConfig( level=logging.DEBUG )
    d = sys.argv[1]
    c = sys.argv[2]
    logging.warn("Device: %s Component %s" % (d,c))

    device = None
    
    try:
        # get factory instance
        nc = netconfig.NetConfig( netconfig.config_file( '/afs/slac/g/scs/net/projects/net-config/etc/net-config/net-config.conf' ) )

        # create device object
        device = nc.get( d )
        device.connect()
    
        component = device.get_component( c )
        for d in component:
            logging.info("%s" % (d[-1],))


    finally:
        if device:
            device.disconnect()