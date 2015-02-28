#!/usr/bin/python

###
# quick test of netconf via ssh
###

from netconfig import NewNetConfig as NetConfig


if __name__ == '__main__':
    
    nc = NetConfig( '/afs/slac/g/scs/net/projects/net-config/conf/net-config.yaml' )
    device = nc.get( 'rtr-farm04' )

    if device.connect():
        
        xml = device.rpc( 'show environment fan')
        for i in xml.xpath( "//*[local-name()='ROW_faninfo']/*[local-name()='fanname']/text()" ):
        # for i in xml.xpath("//*:fanname/text()"): # not xpath2 compat!
            print "%s" % i
