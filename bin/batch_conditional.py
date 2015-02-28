#!/usr/local/bin/python

import logging
import sys
import re
import json

from netconfig import NetConfig, config_file, util
from netconfig.Workers import Ticket, Manager, Process

THREADS=32

def usage():
    print "Logs on to a network device and provides the user a parallelized pipeable command line"
    print "Usage: "
    print "  net-config batch_pipe [--enable|-e] [--verbose|-v] FILE|DEVICE1 DEVICE2..."



class ConditionalCommandManager( Manager ):
    """
    manager to get config files from devices
    """

    def report( self, format='txt', width=80 ):
        return


class ConditionalWorker( Process ):
    
    def add_error( self, host, message ):
        """ add an error """
        self.tally.error( host, message )
        if not self.quiet:
            logging.error( 'Error on ' + host + ': ' + message )

    def add_okay( self, host, message ):
        """ identified that the host has changed """
        self.tally.okay( host, message )
        if not message == '':
            if not self.quiet:
                logging.info( host + ': ' + message )
    
    def do( self, item ):
        
        # create the device object to interact with host
        device = None                
        hostname = 'unknown'
        if hasattr(item, 'hostname'):
            hostname = item.hostname

        try:
            device = self.netconfig.get( hostname, options=self.options )
        except Exception, e:
            self.add_error( hostname, str(e) )

        if not device == None:
            
            if device.connect():
                device.prompt.mode_enable()
            
                cmd = 'show run | inc aaa authentication login default group ' 
                condition = device.prompt.request( cmd, timeout=10 )
                if 'tacacs' in condition:

                    # check we have auth
                    device.prompt.ask( 'no username configuration', cursor=device.prompt.cursor('mode', 'config') )
                    if device.system.config.commit():
                        self.add_okay( hostname, 'ok')

                else:
                    self.add_error( hostname, 'not configured')

                device.disconnect()
                return
        self.add_error( hostname, 'no connectivity')

if __name__ == "__main__":
    
    config_file = config_file()
    args = {
        '-h'        : 'help',
        '--help'    : 'help',

        '-v'        : 'verbose',
        '--verbose' : 'verbose',
        
        '--echo'    : 'echo',
        

        '-e'        : 'enter_enable',
        '--enable'  : 'enter_enable',

        '--threads' : 'threads=',

        '--format' : 'format=',
    }
    
    # parse arguments
    lists, options = util.parseArgs( args )
    
    if ( 'help' in options and options['help'] == 1 ) or len(lists) < 1:
        usage( None )
        sys.exit( 0 )

    if not 'threads' in options:
        options['threads'] = THREADS
    
    if 'verbose' in options and options['verbose'] == 1:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(module)-25s %(funcName)-20s %(lineno)-5d %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')

    # create the manager and add the list of hosts
    manager = ConditionalCommandManager( ConditionalWorker, config_file, options=options, num_threads=options['threads'] )

    # logging.error("LISTS: " + str(lists))
    manager.append( lists )

    # blocks until finished
    manager.start()
    
    # report back
    format = 'txt'
    if 'format' in options:
        format = options['format']
    # report = [ l for l in manager.report( format=format ) ]
    # for l in report:
    #     print l

    # done
    sys.exit(0)
