#!/usr/local/bin/python
import sys

import logging
from re import search

from netconfig import NetConfig, config_file, util
from netconfig.Workers import Manager, Process

THREADS=8

def usage( message ):
    print "Fetches the bssids from list(s) of acess points"
    print "Usage: "
    print "  net-config batch_get_wireless_bssid FILE1 FILE2 ... [--randomize] [--threads=INT] [--quiet]"
    print
    print " options:"
    print "  --threads=INT   number of threads to get configs"
    print "  --randomize     randomize polling sequence of hosts"
    print "  --quiet         only report summary report"
    print "  --password      password to use"
    
    print
    if not message == None:
        print "Error: " + message



class BssidWorker( Process ):
    """
    threaded worker to get the bssid from the provided access point
    """
    
    def do( self, item ):
        """ item defines the item to poll """
        m = []
        found = {}

        # get and connect device
        device = self.netconfig.get( item.hostname, options=self.options )
        device.connect()

        # runt he command and parse it's output
        cmd = 'show int | inc Radio,'
        for i in device.prompt.tell( cmd ):
            if m.append( search( r'address is (?P<addr>.*) \(bia (?P<bia>.*)\)$', i ) ) or m[-1]:
                addr, bia = m[-1].group( 'addr', 'bia' )
                string = str(bia)
                logging.debug( "  found: " + str(string) )
                found[string] = 1
                
        # add as success
        tot = ""
        for k in found:
            tot += "\t" + k

        self.add_okay( item.hostname.lower(), tot )
                
        return True
        

class BssidManager( Manager ):
    """ 
    manager for threads
    """    
    def report( self ):
        """ prints out summary results """
        okay, errors = self.tally.summary()

        #logging.error( "get summary results")
        output = []
        # spit out errors
        errs = self.tally.categorise( errors )
        if len(errs) > 0:
            output.append( "The following hosts experienced errors whilst fetching their bssids:" )
            output.append('')
        for msg in errs:
            output.append( "  error: " + msg )
            for h in sorted(errs[msg]):
                output.append( '    ' + h )

        output.append('')

        changed = self.tally.categorise( okay )
        if len(changed) > 0:
            output.append('')
            output.append( "The following access points reported their bssid's as:" )
            output.append('')
        # spit out changed
        for msg in changed:
            for h in sorted(changed[msg]):
                output.append( h + "\t"  + msg )

        #logging.error( " res " + str(output))
        return output




def parseArguments( options ):

    # logging
    if options.has_key( 'verbose' ) and options['verbose'] == 1:
        logging.basicConfig( level=logging.DEBUG, format="%(relativeCreated)7d %(levelname)-7s %(thread)-12d %(module)-28s %(lineno)-5d %(message)s" )
    else:
        logging.basicConfig( level=logging.INFO, format="%(thread)-12d %(message)s" )

    # we want to be able to fork off
    if not options.has_key( 'threads'): options['threads'] = THREADS
    options['threads'] = int( options['threads'] )

    # quiet
    if options.has_key('quiet'): options['quiet'] = True
    else: options['quiet'] = False

    return options

if __name__ == "__main__":

    config_file = config_file()
    args = {
        '-h'        : 'help',
        '--help'    : 'help',

        '--threads' : 'threads=',
        '--quiet'   : 'quiet',
        '--randomize': 'randomize',
        '-p'        : 'password=',
        '--password': 'password=',

        '-v'        : 'verbose',
        '--verbose' : 'verbose'
    }
    
    # grab arguments
    lists, options = util.parseArgs( args )
    
    # parse options
    if (options.has_key( 'help' ) and options['help'] == 1) or len(lists) < 1:
        usage( None )
        sys.exit()
        
    # force writes
    options['write'] = True
    
    # parse rest of arguments
    options = parseArguments( options )

    # preload the config so that threads dont' accidentially lock it

    # create the manager and add the list of hosts
    manager = BssidManager( BssidWorker, config_file, options=options, num_threads=options['threads'] )
    manager.append( lists )
    
    # blocks until finished
    manager.start()
    
    # report back
    for l in manager.report():
        print( l )


