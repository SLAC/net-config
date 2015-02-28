#!/usr/local/bin/python
import logging
import getopt
import sys
import re

from netconfig import NetConfig, config_file, util


if __name__ == "__main__":
    
    config_file = config_file()

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
    
    args, options = util.parseArgs( args )
    host = args.pop(0)

    if options.has_key( 'verbose' ) and options['verbose'] == 1:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(module)-25s %(funcName)-20s %(lineno)-5d %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
    else:
        logging.basicConfig(level=logging.INFO)

        

    if options.has_key( 'help' ) and options['help'] == 1:
        usage()
        sys.exit()
        
    # create object
    netconfig = NetConfig( config_file )
    device = netconfig.get( host, options=options )
    
    netconfig.connect( device, options )
    
    for d in device.ports.filter():
        print( "%s" % d )
        
    device.disconnect()