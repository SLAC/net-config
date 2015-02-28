#!/usr/local/bin/python

import logging
import getopt
import sys

import slac.netconfig
from slac.netconfig import SmartNetConfig



if __name__ == "__main__":
    
    config_file = '/afs/slac.stanford.edu/g/scs/net/projects/net-config/config/netconfig';
    args = {
        '-h'        : 'help',
        '--help'    : 'help',
        '-u'        : 'username=',
        '--username': 'username=',
        '-p'        : 'password=',
        '--password': 'password=',
        '-P'        : 'enable_password=',
        '--enable_password' : 'enable_password=',
        '-t'        : 'device_type=',
        '--type'    : 'device_type=',
        '-e'        : 'enter_enable',
        '--enable'  : 'enter_enable',
        '--profile' : 'profile=',
        '-f'        : 'profile=',
        '-v'        : 'verbose',
        '--verbose' : 'verbose'
    }
    
    logging.basicConfig(level=logging.DEBUG)
    
    # parse arguments
    hosts, options = slac.netconfig.parseArgs( args )
    netconfig = SmartNetConfig( config_file )
    
    for host in hosts:
        device = netconfig.getNetworkDevice( host, options=options )
        device.smartConnect( )
        #device.enableMode()
        #device.interactiveMode()