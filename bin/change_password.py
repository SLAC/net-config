#!/usr/local/bin/python

import logging
import getopt
import sys
import os.path

from netconfig.netconfig import NetConfig, ConfigFile
from netconfig import util


def usage( desc=None ):
    print "Logs on to a network device DEVICE changes the passwords for the device, a file containing a list of devices may also be provided"
    print "Usage: "
    print "  net-config change_password [--verbose|-v] [--profile NAME|-f NAME] DEVICE|FILE \\"
    print "      -q <new_login_password> -Q <new_enable_password>"
    if not desc == None:
        print ""
        print "Error: " + desc
        

def printCommands( device ):
    """ outputs the commands that (are) ran """
    if device.dry_run == True:
        for c in device.commands:
            print c
        device.commands = []


def getCheckDevice( check_device, host, options ):
    """ returns a device for testing """
    if check_device == None:
        check_options = options
        # overwrite the passwords
        check_options['password'] = options['new_login_password']
        check_options['enable_password'] = options['new_enable_password']
        device = netconfig.getNetworkDevice( host, options=check_options )
        device.connect()
        return device
    else:
        # already connected
        return check_device
    

if __name__ == "__main__":
    
    config_file = ConfigFile()
    args = {
        '-h'        : 'help',
        '--help'    : 'help',
        
        '-u'        : 'username=',
        '--username': 'username=',
        '-p'        : 'password=',
        '--password': 'password=',
        '-P'        : 'enable_password=',
        '--enable_password' : 'enable_password=',
        
        '-q'        : 'new_login_password=',
        '--new_password' : 'new_login_password=',
        '-Q'        : 'new_enable_password=',
        '--new_enable_password' : 'new_enable_password=',

        '-C'        : 'configuration_password=',
        '--configuration_password'        : 'configuration_password=',

        '-W'        : 'wireless_password=',
        '--wireless_password'        : 'wireless_password=',

        '-s'        : 'new_snmp_readonly_password=',
        '--new_snmp_password'   : 'new_snmp_readonly_password=',
        '-S'        : 'new_snmp_readwrite_password=',
        '--new_snmp_write_password'   : 'new_snmp_readwrite_password=',

        '-t'        : 'device_type=',
        '--type'    : 'device_type=',
        
        '--profile' : 'profile=',
        '-f'        : 'profile=',
        
        '-v'        : 'verbose',
        '--verbose' : 'verbose',
        
        '-w'        : 'commit',
        '--write'   : 'commit',
        
        '--dry_run' : 'dry_run',
        
    }
    
    #logging.basicConfig(level=logging.DEBUG)
    
    # parse arguments
    args, options = util.parseArgs( args )

    # exit on help request
    if (options.has_key( 'help' ) and options['help'] == 1):
        usage( )
        sys.exit( )
    
    # check to see if hosts is a file and determine appropriate argument array
    hosts = []
    for h in args:
        if os.path.isfile( h ):
            for i in util.getArray( h ):
                hosts.append( i )
        else:
            hosts.append( h )    

    # exit on lack of input parameters
    if len(hosts) < 1:
        usage( 'device name or file name required')
        sys.exit( )

    # get settings
    if options.has_key( 'verbose' ) and options['verbose'] == 1:
        logging.basicConfig(level=logging.DEBUG)

    # get netconfig object
    netconfig = NetConfig( config_file )

    # loop through all hosts        
    for host in hosts:

        logging.info( "-----------------------------------------------------------------------------")

        device = netconfig.getNetworkDevice( host, options=options )
        if device == None:
            logging.error( 'no profile match for device ' + host )
        else:
            # dry run?
            if options.has_key('dry_run'):
                device.dry_run = True
 
            # change passwords
            try:

                options = util.parsePasswords( options )

                # get the device and connect to it
                if not device.dry_run:
                    netconfig.connect( device, options )

                # have another device ready to test settings
                check_device = None

                if options.has_key( 'new_login_password' ):
                    logging.info( "Changing login passwords for " + host )
                    # change the passwords on the device
                    device.changeLoginPassword( options['new_login_password'] )
                    printCommands( device );
            
                    # try to log back in again
                    if not device.dry_run:

                        # output
                        printCommands( device );
                        try:
                            logging.info( "  testing new login password on " + host + "...")
                            check_device = getCheckDevice( check_device, host, options )
                            printCommands( device );
                            logging.info( "    success!")
                        except Exception, e:
                            logging.warn( "    failed!")
                            # failed to change the passwords, revert back!
                            device.configMode()
                            device.changeLoginPassword( options['password'] )
                            printCommands( device );
                            logging.error( 'could not change passwords for ' + host )

                # set hte enable password
                if options.has_key( 'new_enable_password' ):
                    logging.info( "Changing enable passwords for " + host )
                    # now change enable password
                    device.changeEnablePassword( options['new_enable_password'] )
                    printCommands( device );

                    # check we can enable
                    if not device.dry_run:
                        try:
                            logging.info( "  testing new enable password on " + host + "...")
                            check_device = getCheckDevice( check_device, host, options )
                            check_device.enableMode()
                            printCommands( device );
                            logging.info( "    success!")
                        except Exception, e:
                            logging.warn( "    failed!")
                            # revert back the enable password
                            device.configMode()
                            device.changeEnablePassword( options['enable_password'] )
                            printCommands( device );
                            logging.error( 'could not change enable password for ' + host )

                # close testing connection
                if not device.dry_run and not check_device == None:
                    check_device.disconnect()

                # change configuration accounts
                if options.has_key( 'configuration_password' ):
                    logging.info( "Changing configuration account for " + host )
                    device.changeAccountPassword( 'configuration', 15, options['configuration_password'] )
                    printCommands( device );

                if options.has_key( 'wireless_password' ):
                    logging.info( "Changing wireless account for " + host )
                    device.changeAccountPassword( 'netdev', 15, options['wireless_password'] )
                    printCommands( device );

                # change snmp strings
                if options.has_key( 'new_snmp_readonly_password' ) and options.has_key('new_snmp_readwrite_password'):
                    logging.info( "Changing snmp passwords for " + host )
                    device.changeSNMPReadPassword( options['new_snmp_readonly_password'] )
                    device.changeSNMPWritePassword( options['new_snmp_readwrite_password'] )
                    printCommands( device );

                logging.info( "-----------------------------------------------------------------------------")

                if options.has_key( 'commit' ):
                    device.commit()

                # disconnect
                if not device.dry_run:
                    device.disconnect()

            except Exception, e:
                logging.error( str(e) )
