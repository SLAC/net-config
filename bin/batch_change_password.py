#!/usr/local/bin/python

import logging
import getopt
import sys
import os
import time
import sys
import random

from netconfig.netconfig import NetConfig, Manager, Process, ConfigFile, PasswordWorker
from netconfig import util
# from netconfig.StorageQueue import StorageQueue

THREADS = 8

def usage( message ):
    print "Changes passwords on network devices given a list in a file"
    print "Usage: "
    print "  net-config batch_get_config FILE1 FILE2 ... [--randomize] [--threads=INT] [--quiet]"
    print
    print ' passwords:'
    print '  -q              new login password'
    print '  -Q              new enable password'
    print '  -C              new configuration password'
    print '  -W              wireless_password'
    print '  -s              new snmp readonly community'
    print '  -S              new snmp readwrite community'
    print 
    print " options:"
    print "  --threads=INT   number of threads to get configs"
    print "  --randomize     randomize password change sequence of hosts"
    print "  --quiet         only report summary report"
    print
    if not message == None:
        print "Error: " + message


class PasswordManager( Manager ):
    """
    manager to get config files from devices
    """

    def report( self ):
        """ prints out summary results """
    
        okay, errors = self.tally.summary()
    
        #logging.error( "get summary results")
        output = []
        # spit out errors
        errs = self.tally.categorise( errors )
        if len(errs) > 0:
            output.append( "The following hosts experienced errors whilst changing their passwords:" )
            output.append('')
        for msg in errs:
            output.append( "  error: " + msg )
            for h in sorted(errs[msg]):
                output.append( '    ' + h )

        output.append('')
    
        changed = self.tally.categorise( okay )
        if len(changed) > 0:
            output.append('')
            output.append( "The following hosts had the following password changes:" )
            output.append('')
        # spit out changed
        for msg in changed:
            output.append( str(msg) + ":")
            for h in sorted(changed[msg]):
                output.append( '    ' + h )

        #logging.error( " res " + str(output))
        return output



def parseArguments( options ):

    # logging
    if options.has_key( 'verbose' ) and options['verbose'] == 1:
        logging.basicConfig( level=logging.DEBUG, format="%(relativeCreated)7d %(levelname)-7s %(thread)-12d %(module)-28s %(lineno)-5d %(message)s" )
    else:
        logging.basicConfig( level=logging.INFO, format="%(message)s" )

    # we want to be able to fork off
    if not options.has_key( 'threads'): options['threads'] = THREADS
    options['threads'] = int( options['threads'] )

    # quiet
    if options.has_key('quiet'): options['quiet'] = True
    else: options['quiet'] = False

    return options


if __name__ == "__main__":

    config_file = ConfigFile()
    args = {
    
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

        '--configuration_password'        : 'configuration_password=',
        '-C'        : 'configuration_password=',

        '-W'        : 'wireless_password=',
        '--wireless_password'        : 'wireless_password=',

        '-s'        : 'new_snmp_readonly_password=',
        '--new_snmp_password'   : 'new_snmp_readonly_password=',
        '-S'        : 'new_snmp_readwrite_password=',
        '--new_snmp_write_password'   : 'new_snmp_readwrite_password=',

        '-c'        : 'commit',
        '--commit'  : 'commit',
    
        '-h'        : 'help',
        '--help'    : 'help',

        '--threads' : 'threads=',
        '--quiet'   : 'quiet',
        '--randomize': 'randomize',
        
        '-v'        : 'verbose',
        '--verbose' : 'verbose'
    }
    
    # grab arguments
    lists, options = util.parseArgs( args )
    
    # parse options
    if (options.has_key( 'help' ) and options['help'] == 1) or len(lists) < 1:
        usage( None )
        sys.exit()
            
    # parse rest of arguments
    options = parseArguments( options )

    # get the passwords to set
    options = util.parsePasswords( options )

    # create the manager and add the list of hosts
    manager = PasswordManager( PasswordWorker, config_file, options=options, num_threads=options['threads'] )
    manager.append( lists )
    
    # blocks until finished
    manager.start()
    
    # report back
    for l in manager.report():
        print( l )

    # done
    sys.exit(0)

