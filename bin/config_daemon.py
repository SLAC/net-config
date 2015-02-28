#!/usr/local/bin/python

import logging
import getopt
import sys
import os
import time
import sys
import resource

import slac.netconfig
from slac.netconfig import NetConfig, NetConfigStorage, ConfigWorker
from slac.netconfig.StorageQueue import StorageQueue
import Queue

THREADS=1

WORKING_DIR = '/tmp'
UMASK = 0
MAX_FD = 1023

def usage( message ):
    print "Daemon to collect and store device configurations"
    print "Usage: "
    print "  net-config config_daemon DIR [--threads=INT]"
    print
    print " options:"
    print "  --threads=INT   number of threads to get configs"
    print "  --quiet         only report summary report"
    print
    if not message == None:
        print "  Error: " + message




class ConfigQueue( threading.Thread ):
    """ simple thread that watches a directory for new tickets and inserts into queue for ConfigWorkers """
    
    store = None
    queue = None
    
    def __init__( self, config_parser, queue ):
        # init parents class
        threading.Thread.__init__(self)
        
        # don't bother connecting
        self.store = slac.netconfig.NetConfigStorage( config_parser )

        # queue for workers
        self.queue = queue
    
    def run( self ):
        """ just loops and watches the directory and inserts the result into a queue for workers """
        while True:
            
            tickets = self.store.listQueue()
            for t in tickets:
                # retrieve info from ticket and dequeue
                ticket = self.store.dequeue( t )
                # put it into the worker job queue for processing
                self.queue.put( ticket )
                
            time.sleep(1)
        

if __name__ == "__main__":

    config_file = slac.netconfig.getConfigFile()
    args = {
        '-h'        : 'help',
        '--help'    : 'help',

        '--threads' : 'threads=',

        '-v'        : 'verbose',
        '--verbose' : 'verbose'
    }
    
    # parse arguments
    lists, options = slac.netconfig.parseArgs( args )

    if (options.has_key( 'help' ) and options['help'] == 1) or len(lists) < 1:
        usage( None )
        sys.exit()

    # logging
    if options.has_key( 'verbose' ) and options['verbose'] == 1:
        logging.basicConfig( level=logging.DEBUG, format="%(relativeCreated)7d %(levelname)-7s %(thread)-12d %(module)-28s %(lineno)-5d %(message)s" )
    else:
        logging.basicConfig( level=logging.INFO, format="%(thread)-12d %(message)s" )

    # we want to be able to fork off
    if not options.has_key( 'threads'):
        options['threads'] = THREADS
    options['threads'] = int( options['threads'] )

    # quiet
    if options.has_key('quiet'):
        options['quiet'] = True
    else:
        options['quiet'] = False

    # preload the config so that threads dont' accidentially lock it
    config_parser = slac.netconfig.getConfig( config_file )

    ###
    # start doing stuff!
    ###

    # queues for synchronisation of results
    in_queue = Queue.Queue()
    changed_queue = Queue.Queue()
    error_queue = Queue.Queue()

    # add hosts to queue
    section = 'net-config'
    config_ticket_queue = None
    if config_parser.has_section( section ):
        config_ticket_queue = config_parser.get( section, 'config_ticket_queue' )
    if config_ticket_queue == None:
        raise Exception, 'config ticket directory is not defined'

    # create the instance to monitor the config ticket queue
    p = ConfigQueue( config_ticket_queue, in_queue )
    p.start

    # spawn pool of threads to get configs
    for i in range( options['threads'] ):
        t = ConfigWorker( config_parser, options, in_queue, changed_queue, error_queue )
        #t.setDaemon(True)
        t.start()
        time.sleep(1)

    ###
    # daemonise
    ###

    # close fd's
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if (maxfd == resource.RLIM_INFINITY):
        maxfd = MAX_FD
    # Iterate through and close all file descriptors.
    for fd in range(0, maxfd):
        try:
            os.close(fd)
        except OSError:	# ERROR, fd wasn't open to begin with (ignored)
            pass

    # This call to open is guaranteed to return the lowest file descriptor,
    # which will be 0 (stdin), since it was closed above.
    os.open(REDIRECT_TO, os.O_RDWR)	# standard input (0)

    # Duplicate standard input to standard output and standard error.
    os.dup2(0, 1)   # standard output (1)
    os.dup2(0, 2)   # standard error (2)


    # done
    sys.exit(0)

    
