import logging

import sys
import types

from time import sleep
import multiprocessing
from Queue import Empty
import traceback
import random

from re import compile, search, match

from . import NetConfig
from ConfigurationStorage import Storage

import traceback

class Tally( object ):
    """ a simply tally table of worker successes and failures """

    # an array of dict's, with 'hostname' key being the main entry
    input_queue = None
    
    # queues for success and errors
    okay_queue = None
    error_queue = None
    
    def __init__( self ):
        self.manager = multiprocessing.Manager()
        
        # an array of dict's, with 'hostname' key being the main entry
        self.input_queue = multiprocessing.JoinableQueue(-1)

        # queues for success and errors
        self.okay_queue = self.manager.Queue(-1)
        self.error_queue = self.manager.Queue(-1)
    
    def __str__( self ):
        return "Input Queue has " + str(self.input_queue.qsize()) + " items"
    
    def add( self, item ):
        """ add an item into the input queue """
        # todo: check for hostname?
        self.input_queue.put( item )

    def get( self ):
        this = self.input_queue.get()
        #logging.warn( " Getting " + str(this))
        return this

    def empty(self):
        return self.input_queue.empty()

    def done( self ):
        """ mark as done """
        self.input_queue.task_done()
        
    def __len__(self):
        """ return size of input_queue """
        return self.input_queue.qsize()

    def join( self ):
        """ block until the input queue has been  depleted """
        self.input_queue.join()

    def summary( self ):
        """ summary results """
        return self.okay_queue, self.error_queue

    def categorise( self, queue ):
        """ organise the queue entries into the associated message """
        stuff = {}
        while True:
            try:
                # make sure we do a nowait get, otherwise it will block indefinately
                d = queue.get(False)
                # logging.error( 'CAT got %s' % (d,))
                this = "%s" % ( d['msg'], )
                if not stuff.has_key( this ):
                    stuff[this] = []
                stuff[ this ].append( d['host'] )
                if type(queue).__name__ == 'JoinableQueue':
                    queue.task_done()
            except Empty:
                break
                
        return stuff

    def stream( self, queue ):
        while True:
            try:
                yield queue.get(False)
                if type(queue).__name__ == 'JoinableQueue':
                    queue.task_done()
            except Empty:
                break
        return

    def report( self ):
        error = self.categorise( self.error_queue )
        okay = self.categorise( self.okay_queue )
        return okay, error

    def error( self, host, message ):
        """ adds the error to the queue """
        this = {
            'host':   host,
            'msg':    message,
        }
        #logging.warn("error: " + str(this))
        self.error_queue.put( this )

    def okay( self, host, message ):
        """ adds a sucess to queue """  
        this = {
            'host': host,
            'msg': message,
        }
        self.okay_queue.put( this )



class Ticket( object ):
    """
    basic object to allow definition of a test to run 
    typically used with a netConfigThread and tally object
    ie tally.add( Ticket )
    """
    
    hostname = None
    def __init__( self ):
        self.hostname = None
        
    def __init__( self, hostname ):
        self.hostname = hostname

    def has_key(self, key):
        if key == 'hostname':
            return True
        return False

    def __str__( self ):
        return ' hostname=' + self.hostname


class StorageTicket( Ticket ):

    hostname = None
    user = None
    rt = None
    comment = None

    def __init__( self, hostname ):
        self.hostname = hostname
        self.user = None
        self.rt = None
        self.comment = None

    def has_key( self, key ):
        if key == 'hostname':
            return True
        return False


#######################################################################
# Managers deal with managing many Workers
#######################################################################


class Manager( object ):
    """
    manage a pool of workers
    """
    working = None

    def __init__( self, worker_class, config_parser, options={}, num_threads=1, randomise=False, ticket_type=Ticket ):

        self.worker_class = worker_class
        self.config_parser = config_parser
        self.ticket_type = ticket_type

        self.all_hosts = []
        
        # queues for synchronisation of results
        self.working = False
        self.tally = Tally()
        
        self.options = options
        self.is_randomise = randomise

        # keep tabs on workers
        self.num_threads = int( num_threads )
        self.worker_pool = []
    
    def __del__( self ):
        for w in self.worker_pool:
            w.terminate()


    def _parse_file( self, item ):
        # if it's a string, see if there is a file by that name
        if isinstance( item, types.StringType ):
            if item == "None" or item == '':
                return 

            if not isinstance(item,list):
                try:
                    f = open( item, 'r' )
                    for l in f.readlines():
                        # logging.error("L: " + str(l))
                        h = l.rstrip()
                        if not h == "":
                            yield h
                    f.close()
                except IOError as e:
                    yield item
            else:
                for i in item:
                    yield i
        return
        
    def _append( self, item ):
        if isinstance( item, types.ListType ):
            for h in item:
                # see if it's a file, if not just add it to the array
                for i in self._parse_file( h ):
                    yield self.create_ticket( i )
        elif isinstance( item, dict ):
            yield self.create_ticket( item )
        else:            
            for i in self._parse_file( item ):
                yield self.create_ticket( i )
        return
    
    def append( self, items, randomise=False ):
        # randomise?
        if self.is_randomise or randomise:
            random.shuffle( items )
        # add hosts to queue
        for t in self._append( items ):
            # logging.error("APPEND: " + str(t))
            self.tally.add( t )
        return


    def create_ticket( self, h ):
        logging.debug("ticket: " + str(h))
        # create the relevant ticket type for this
        t = self.ticket_type( h )
        return t


    def start( self ):

        try:

            self.working = True
            
            # spawn pool of threads to get configs
            for i in range( self.num_threads ):
                # define the worker type
                # logging.info("staring worker of type " + str(self.worker_class))                
                t = self.worker_class( self.config_parser, self.options, self.tally )
                self.worker_pool.append( t )

            # start workers
            for w in self.worker_pool:
                w.start()

            # kill workers with poison pill
            for w in self.worker_pool:
                self.tally.add( None )

            # wait for all to finish
            self.tally.join()

            self.working = False
                        
        except KeyboardInterrupt:
            # empty the queue, then exit
            logging.error( "Caught ctrl-c: Terminating...")
            not_empty = True
            while not_empty:
                # logging.error("NOT EMPTY " + str(not_empty))
                try:
                    item = self.tally.get()
                    self.tally.done()
                except Empty:
                    not_empty = False
            for w in self.worker_pool:
                w.terminate()
                    
        except Exception, e:
            # TODO: cleanly destroy children
            logging.error('Experienced unknown error: ' + str(e))
            raise e

    def report( self, *args, **kwargs ):
        raise NotImplementedError, 'report() not implemented'


#######################################################################
# Workers deal with actually accomplishing a single (maybe complicated) task
#######################################################################


class Process( multiprocessing.Process ):
    """ threaded class to do and report stuff """

    quiet = False
    tally = None
    working = None

    def __init__( self, config_parser, options, tally ):
        
        self.options = options
        if options.has_key('quiet') and options['quiet']:
            self.quiet = True

        # control whether we continue to run
        self.working = False
        # queues
        self.tally = tally

        # init parents class
        multiprocessing.Process.__init__(self)

        self.netconfig = NetConfig( config_parser )

    def add_error( self, host, message ):
        """ add an error """
        if type(host) != str or not hasattr(host, '__str__'):
            host = 'unknown'
        self.tally.error( host, message )

    def add_okay( self, host, message ):
        """ identified that the host has changed """
        self.tally.okay( host, message )

    def do( self, item ):
        """ does the necessary work to get the config and store it """
        raise NotImplementedError, 'please inherit do()'

    def run( self ):
        """ does the necessary work to get the config and store it """

        # reload profile cache from disk
        self.netconfig.reload_profile_cache()

        self.working = True
        while self.working == True:

            item = None
            # get host
            try:
                item = self.tally.get()
                # exit on poison pill
                if item == None:
                    self.working = False

            # queue is empty, die
            except Empty:
                logging.error( "input queue is empty")
                self.working = False

            if self.working and not item == None:
                try:
                    # do something with the item; overload do() on inherited classes
                    logging.debug( "working on item: " + str(item.hostname) )
                    self.do( item )
                # catch any issues
                except Exception, e:
                    # throw error
                    host = 'unknown'
                    if item.has_key('hostname'): host = item.hostname
                    self.add_error( host, str(e) )
            
            # signal task is done; this must be done here, else parent will die too early if we join()
            logging.debug('marking task done; ending ' + str(self.working))
            self.tally.done()
            
            try:
                logging.debug( "queues - input=" + str( len( self.tally ) ) + ", okay=" + str(self.tally.okay_queue.qsize()) + ", error=" + str(self.tally.error_queue.qsize()) )
            except sys.excepthook, e:
                pass
                
            # save profile cache from disk
            self.netconfig.reload_profile_cache()

        # logging.error('EXITING')
        return


class ConfigWorker( Process ):
    """ threaded class to get configs """

    netconfig = None
    storage = None
    write = True # boolean to write to storage or not
    tally = None
    
    def __init__( self, config, options, tally ):

        super( ConfigWorker, self ).__init__( config, options, tally )

        if 'nowrite' in options:
            self.write = False
        else:
            self.write = True

        # data = self.netconfig.getDeviceMap()
        # logging.debug("DATA: " + str(data))

        if self.write:
            # create object to store stuff
            self.storage = Storage( config )
            self.storage.connect()

    def add_error( self, host, message ):
        """ add an error """
        self.tally.error( host, message )
        if not self.quiet:
            logging.error( 'Error fetching configuration from ' + str(host) + ': ' + str(message) )
            
    def add_okay( self, host, message ):
        """ identified that the host has changed """
        self.tally.okay( host, message )
        if not self.quiet:
            logging.info( host + ': configuration updated' )

    def do( self, item ):
        """ atomic operation """

        if not self.quiet:
            logging.info( item.hostname + ": fetching" )

        # create the device object to interact with host
        device = None                
        try:
            device = self.netconfig.get( item.hostname, options=self.options )
        except Exception, e:
            # logging.debug('caught exception in _run after getNetworkDevice')
            # logging.debug(traceback.format_exc())
            hostname = 'unknown'
            if hasattr(item, 'hostname'):
                hostname = item.hostname
            self.add_error( hostname, str(e) )

        if not device == None:

            # 1) fetch the device configurations
            config = None
            try:
                # get the device and connect to it
                self.netconfig.connect( device, **self.options )
                # get all the configs from teh device; each type of config will be the key on returned dict
                config = device.system.config.get()
                # disconnect
                device.disconnect()
                if not self.quiet:
                    logging.info( item.hostname + ": done fetching" )

            except Exception, e:
                logging.debug('caught exception in _run after connect and getRunningConfiguration')
                logging.debug(traceback.format_exc())
                hostname = 'unknown'
                if hasattr(item, 'hostname'):
                    hostname = item.hostname
                self.add_error( hostname, str(e) )
            
            # ensure the profile cache is mapped to the storage configuration map
            device_map = self.netconfig.get_device_map()
            
            # 2) only store if valid
            if self.write \
                and not config == None \
                and len( config.getContexts() ) > 0:

                try:
                    #logging.error( item.hostname + ": storing configuration" )
                    
                    # write to datastores
                    self.storage.set_device_map( device_map )
                    res, person, diff = self.storage.put( item.hostname, config, user=item.user, rt=item.rt, comment=item.comment, commit=self.write )

                    # storage was good
                    if res: 
                        self.add_okay( item.hostname, { 'person': person, 'diffs': diff } )
                    # storage does not need to happen
                    elif not res:
                        if not self.quiet:
                            logging.info( item.hostname + ": configuration has no changes" )
                    # error!
                    else:
                        self.add_error( item.hostname, 'unrecognised return code' )

                # generic error with storage
                except Exception, e:
                    logging.error("ERROR: %s %s\t%s" % (type(e),e,traceback.format_exc()))
                    self.add_error( item.hostname, str(e) )

            # error with getting the config
            elif self.write \
                and not config == None:
                self.add_error( item.hostname, 'invalid configuration fetched' )
                # else not storing anyway
            elif not self.write \
                and not config == None:
                # print it to screen
                print( config )
            else:
                logging.debug( "invalid configuration fetched")


class PipeCommandWorker( Process ):
    """ threaded class to run a command on numerous devices """

    echo_command = False

    def __init__( self, config_parser, options, tally ):
        super( PipeCommandWorker, self ).__init__( config_parser, options, tally )
        if 'echo' in options and not options['echo'] == None:
            self.echo_command = True
        else:
            self.echo_command = False
        self.netconfig = NetConfig( config_parser )

    def add_error( self, host, message ):
        """ add an error """
        self.tally.error( host, message )
        if not self.quiet:
            logging.error( 'Error piping command to ' + host + ': ' + message )

    def add_okay( self, host, message ):
        """ identified that the host has changed """
        self.tally.okay( host, message )
        if not message == '':
            if not self.quiet:
                logging.info( host + ': ' + str(message) )

    def do( self, item ):
        """ does the necessary work to upgrade the firmware """
        this_host = item.hostname
        # create the device object to interact with host
        device = None                
        try:
            device = self.netconfig.get( this_host, options=self.options )
        except Exception, e:
            self.add_error( this_host, str(e) )

        if not device == None:

            comment_line = compile( '^\!')

            try:
                # connect
                device.connect()

                # disable buffering
                device.prompt.terminal_buffer( 0 )

                # logging.error("ENABLE: " + str(self.options))
                # enter enable if applicable
                if 'enter_enable' in self.options:
                    device.prompt.mode_enable()

                for l in item.command:
                    j = l.split( '\\n' )
                    logging.debug("="*10 + ' ' + str(j) + ' '+'='*10 )
                    for k in j:

                        args = { 'timeout': None, 'cmd': None, 'echo': None }
                        
                        # k is the command to run
                        k = k.strip()

                        # skip comments
                        if comment_line.match( k ):
                            logging.debug("found a comment line")
                            continue

                        # now we want to send commands for arguments, we look for these with ^[.*]
                        m = []
                        if m.append( search( r'^\[(?P<meta>.*)\]\s*(.*)$', k ) ) or m[-1]:
                            # get the command to send
                            k = m[-1].group(2)
                            # work out the args
                            a = m[-1].group('meta').split(',')
                            for i in a:
                                x = i.split('=')
                                logging.debug("x="+str(x))
                                if x[0] == 'run':
                                    x[0] = 'cmd'
                                args[x[0]] = x[1]

                        logging.debug('got instruction: ' + str(args) + ", k="+ str(k))
                        
                        # store the output
                        output = []
                        err = False
                        
                        # echo stuff from the pipe ([echo=.*])
                        if args['echo'] or ( 'echo' in self.options and self.options['echo'] ): 
                            # if not self.quiet:
                            #     logging.info( "# net-config command: " + str(k) )
                            output.append( "%s" %(k,) )

                        # just pipe the commands directly
                        if args['cmd'] == None:
                            logging.debug( "run: " + str(args) )
                            this = device.prompt.request( k, timeout=args['timeout'] )
                            # logging.error("THIS: %s" % (this,))
                            output.append( this )
                        
                        # we try to instantiate an api call
                        else:
                            a = args['cmd'].split(" ")
                            method = a.pop(0)
                            parameters = ""
                            if len(a):
                                parameters = a.pop(0)

                            kwargs = {}
                            for i in ( 'timeout' ):
                                if i in args:
                                    kwargs[i] = args[i]
                            
                            logging.debug( "  calling method " + str(method) + ", " + str(parameters))
                            # output = None
                            try:
                                hierachy = method.split('.')
                                method = hierachy.pop(-1)
                                if search( r'()', method ):
                                    method = method.replace(r'()', '')
                                this = device
                                for h in hierachy:
                                    this = this.__getattribute__( h )
                                    logging.debug("  component " + str(this))
                                logging.debug("  calling method " + str(method) + ' for component ' + str(this))
                                output.append( this.__getattribute__( method )( *parameters, **kwargs ) )

                            except Exception, e:
                                self.add_error( this_host, str(e) )
                                err = True

                        if err == False:
                            # logging.error("%s" % (output,) )
                            self.add_okay( this_host, output )
                            # self.add_okay( this_host, output )

                
            except Exception, e:
                # logging.error("ERROR: %s %s\t%s" % (type(e),e,traceback.format_exc()))
                self.add_error( this_host, str(e) )

        if not device == None:
            device.disconnect()


class InterfaceTicket( Ticket ):
    """ extension of Ticket class for interface updates """
    __attributes = ['hostname', 'port', 'alias', 'vlan', 'autoneg', 'speed', 'duplex', 'state']
    
    @classmethod
    def listValidAttributes(cls):
        return cls.__attributes
    
    def __init__( self, hostname ):
        super( InterfaceTicket, self ).__init__( hostname )
        for i in self.__attributes:
            setattr( self, i, None )

    def __iter__(self):
        for i in self.__attributes:
            yield i
        return
        
    def __getitem__(self, k):
        if k in self.__attributes:
            return getattr(self, k)
        return None
        
    def __setitem__(self, k, v):
        if k in self.__attributes:
            setattr(self, k, v)
        return None
    
    def __str__( self ):
        s = [ '%s=%s' % ( i, str( getattr(self, i) ) ) for i in self.__attributes ]
        return '\n'.join(s)

    def getDict( self ):
        # map options from the ticket
        new = {}
        for i in self.__attributes:
            if hasattr(self, i) and getattr(self, i) != None:
                new[i] = getattr(self, i)

        return new


class InterfaceWorker( Process ):
    """ threaded class to update the interface information """

    netconfig = None
    last_hostname = None # cache the device if it's the same as previous
    last_device = None
    
    def __init__( self, config_parser, options, tally ):
        super( InterfaceWorker, self ).__init__( config_parser, options, tally )

        # create object to do stuff
        self.netconfig = NetConfig( config_parser )

    def __del__( self ):
        if not self.last_device == None:
            self.last_device.disconnect()

    def add_error( self, host, message ):
        """ add an error """
        if type(host) != str or not hasattr(host, '__str__'):
            host = 'unknown'
        self.tally.error( host, message )
        if not self.quiet:
            logging.error( 'Error upgrading interface on %s: %s' % (host, message) )

    def add_okay( self, host, message ):
        """ identified that the host has changed """
        self.tally.okay( host, message )
        if not self.quiet:
            logging.info( host + ': ' + message )

    def dumpPort( self, port, info ):
        print(" port " + str(port) + ": " + str(info['alias']) )
        for i in ( 'state', 'trunk', 'vlan', 'autoneg', 'duplex', 'speed' ):
            out = i
            if i == 'vlan':
                out = 'vlan#'
            if not i == 'alias':
                print( "   " + str(out) + "\t" + str(info[i]) )

    def _setPort( self, device, port, new={}, old={}, dry_run=False ):
        """
        given the options, use the options['port'] in order to set the info about the port
        """
        do = {}
        did = {}
        
        if dry_run == True:
            device.dry_run = True

        # makes sure it's an access port
        if old['trunk'] == False:

            # set the alias on the port
            if new.has_key( 'alias' ):
                # for some reason a null input comes out as '1'
                if new['alias'] == 1: new['alias'] = None
                # check against current
                if old['alias'] == '': old['alias'] = None
                if not old['alias'] == new['alias']:
                    logging.info( " setting alias to " + str(new['alias']) )
                    do['alias'] = new['alias']
                    # device.setInterfacePortAlias( port, new['alias'] )
                    # did_something = True

            # autoneg
            if new.has_key( 'autoneg'  ):
                state = util.boolean( new['autoneg'] )
                if ( state == True and old['autoneg'] == False ) or ( state == False and old['autoneg'] == True ):
                    logging.info( " setting autoneg to " + str(state) )
                    if state == True:
                        do['autoneg'] = state
                        # device.setInterfaceAutoneg( port, state )
                        # did_something = True
                    else:
                        # check to make sure we have specified the other settings
                        if ( not new.has_key( 'duplex') ) or ( not new.has_key('speed')):
                            logging.error( "need to specify speed or duplex settings for non-autonegotiated hosts")

            # duplex settings
            if new.has_key( 'duplex' ):
                if not old['duplex'] == new['duplex']:
                    logging.info( " setting duplex to " + new['duplex'] )
                    do['duplex'] = new['duplex']
                    # device.setInterfacePortDuplex( port, new['duplex'] )
                    # did_something = True

            # speed settings
            if new.has_key( 'speed' ):
                autoneg = None
                if new.has_key('autoneg'):
                    autoneg = util.boolean(new['autoneg'])
                # if autoneg is different
                # strip speed

                if new['speed'] == 'None':
                    new['speed'] = None
                else:
                    new['speed'] = new['speed'].replace(',', ' ')
                if ( not autoneg == old['autoneg'] ) or \
                    ( not new['speed'] == old['speed'] ):
                    logging.info( " setting speed to " + str(new['speed']) )
                    do['speed'] = new['speed']
                    # device.setInterfacePortSpeed( port, new['speed'], autoneg=autoneg )
                    # did_something = True

            # vlans, check to see vlans are valid for switch
            if new.has_key( 'vlan' ):
                # check to see if we're asking for it from the vlan number or the vlan name
                search_by_number = False
                vlan_number = None
                try:
                    vlan_number = int( new['vlan'] )
                    search_by_number = True
                except ValueError:
                    pass

                # search for the vlan number based on input string
                if not search_by_number:
                    # find out what the vlan number should be
                    vlans_on_switch = device.getVlans()
                    for v in vlans_on_switch:
                        #logging.error( "v=" + str(v) + ", " + vlans_on_switch[v] + " match " + new['vlan'])
                        if vlans_on_switch[v] == new['vlan']:
                            vlan_number = v
                    logging.info( "Found vlan number " + str(vlan_number) + " for " + str(new['vlan']))

                # logging.error("VLAN: " + str(vlan_number) + ", " + str(old))

                # set the vlan if not set to correct value
                if not vlan_number == None and not vlan_number == old['vlan']:
                    vlans_on_switch = device.getVlans()
                    logging.info( " setting access vlan to " + str(vlan_number) )
                    #for i in vlans_on_switch:
                    #    logging.info( "vlan '" + str(i) + "'")
                    if vlans_on_switch.has_key( str(vlan_number) ):
                        do['vlan'] = vlan_number
                        # device.setInterfacePortAccessVlan( port, vlan_number )
                        # did_something = True
                    else:
                        logging.error( "  vlan " + new['vlan'] + ' does not exist on device')

            # port shut/no shut
            if new.has_key( 'state' ):
                #logging.warn( "STATUS: " + str(new['status']))
                state = util.boolean( new['state'] )
                if not state == old['state']:
                    logging.info( " setting state to " + str(state) )
                    # device.setInterfacePortState( port, state )
                    # did_something = True
                    do['state'] = state

            # do it
            did = device.setInterface( port, do )

        else:
            self.add_error( 'host', "Port " + port + " is not an access port")

        return did            


    def setPort(self, device, interface, current={}, new={} ):
        # spit out the port
        logging.info( "\nFound matching port...")
        self.dumpPort( interface, current )

        this = new.getDict()
        logging.debug( "CURRENT " + str( current ))
        logging.debug( "NEW     " + str( this ))
        
        status = self._setPort( device, interface, new=this, old=current )
        if len(status.keys()) > 1:
            # print( "+" + item.hostname, p + ": changing port settings...")
            # validate to user, add space at end to filter out stuff we don't care about
            ports = device.findInterface( interface )
            self.dumpPort( interface, ports[interface] )

        return status


    def do( self, item ):
        """ does the necessary work to update interface information """

        # create the device object to interact with host
        if self.last_hostname == item.hostname:
            logging.debug( 'reusing last device')
            device = self.last_device
        else:
            try:
                device = None
                logging.debug( 'creating new device')
                device = self.netconfig.get( item.hostname, options=self.options )
                # even if it's a dry run, we need to determine the port sometimes
                device.connect( )
            except Exception, e:
                logging.debug('caught exception in _run after getNetworkDevice and connect')
                logging.debug(traceback.format_exc())
                if hasattr(item, 'hostname'):
                    self.add_error( item.hostname, str(e) )
                else:
                    self.add_error( '', str(e) )

        # device = None will disconnect
        if not device == None:
            # run the interface update
            try:
                # find all matching ports
                ports = device.findInterface( item.port )
                number_found = len(ports)
                if number_found == 0:
                    self.add_error( '+' + item.hostname, p + ': no interface matched ' + str(p))
                    logging.error( "\n" + item.hostname + ": no interfaces matched interface '" + item.port + "'" )
                else:
                    for p in ports:
                        if p == item.port:
                            did = self.setPort( device, p, current=ports[p], new=item )
                            if did == {}:
                                self.add_okay( '+' + item.hostname, p + ': no changes required')
                            elif did == None:
                                self.add_error( '+' + item.hostname, p + ': failed for some reason')
                            else:
                                self.add_okay( '+' + item.hostname, p + ': changes made ' + str(sorted(did.keys())) )

                if device.dry_run == True:
                    for c in device.commands:
                        print c
                        device.commands = []

                # replicate
                self.last_hostname = item.hostname
                self.last_device = device

            except Exception, e:
                logging.debug('in interface worker loop')
                logging.debug(traceback.format_exc())
                self.add_error( item.hostname, str(e) )

        return None



class PasswordWorker( Process ):
    """ threaded class to update the interface information """

    netconfig = None
    last_hostname = None # cache the device if it's the same as previous
    last_device = None

    def __init__( self, config_parser, options, tally ):
        super( PasswordWorker, self ).__init__( config_parser, options, tally )

        # create object to do stuff
        self.netconfig = NetConfig( config_parser )

    def __del__( self ):
        if self.last_device:
            self.last_device.disconnect()

    def add_error( self, host, message ):
        """ add an error """
        if type(host) != str or not hasattr(host, '__str__'):
            host = 'unknown'
        self.tally.error( host, message )
        if not self.quiet:
            if not message:
                message = 'undefined'
            logging.error( 'Error changing passwords on %s: %s' % (str(host), str(message)) )

    def add_okay( self, host, message ):
        """ identified that the host has changed """
        self.tally.okay( host, message )
        if not self.quiet:
            logging.info( 'done - ' + host + ': ' + message )

    def printCommands( self, device ):
        """ outputs the commands that (are) ran """
        if device.dry_run == True:
            for c in device.commands:
                print c
            device.commands = []

    def getCheckDevice( self, check_device, host, options ):
        """ returns a device for testing """
        if check_device == None:
            check_options = options
            # overwrite the passwords
            if options.has_key( 'new_login_password' ):
                check_options['password'] = options['new_login_password']
            if options.has_key('new_enable_password'):
                check_options['enable_password'] = options['new_enable_password']
                        
            if options.has_key( 'user' ):
                check_options['user'] = options['user']
                
            check_device = self.netconfig.get( host, options=check_options )
            check_device.connect()
            return check_device
        else:
            # already connected
            check_device.execMode()
            return check_device

    def do( self, item ):
        """ does the necessary work to update the passwords """

        # clear the device
        device = None
        # have another device ready to test settings
        check_device = None

        # create the device object to interact with host
        try:
            logging.debug( 'creating new device')
            device = self.netconfig.get( item.hostname, options=self.options )
            # even if it's a dry run, we need to determine the port sometimes
            device.connect()
        except Exception, e:
            logging.debug('caught exception in _run after getNetworkDevice and connect')
            # logging.debug(traceback.format_exc())
            if hasattr(item, 'hostname'):
                self.add_error( item.hostname, str(e) )
            else:
                self.add_error( '', str(e) )
            device = None

        # device = None will disconnect
        if not device == None:

            if self.options.has_key('dry_run'):
                device.dry_run = True

            # change passwords
            try:

                #logging.info( "THREAD OPTIONS: " + str(self.options) )

                # keep an array for what succeed here and what we changed
                check_changed = []

                # new options for checking device
                this_options = {}
                if self.options.has_key( 'new_login_password'):
                    this_options['password'] = self.options['new_login_password']
                if self.options.has_key( 'new_enable_password'):
                    this_options['enable_password'] = self.options['new_enable_password']

                if self.options.has_key( 'new_login_password' ):
                    logging.info( "Changing login passwords for " + item.hostname )
                    # change the passwords on the device
                    device.changeLoginPassword( self.options['new_login_password'] )
                    self.printCommands( device );

                    # try to log back in again
                    if not device.dry_run:
                        # output
                        try:
                            logging.debug( "Testing new login password on " + item.hostname + "...")
                            check_device = self.getCheckDevice( check_device, item.hostname, this_options )
                            # self.printCommands( device );
                            check_changed.append( 'login_password' )
                        except Exception, e:
                            # failed to change the passwords, revert back!
                            # logging.error("PASSWORD 5: " + str(self.options))
                            logging.error( 'could not change login password for ' + item.hostname + ": " + str(e) + ', reverting back to ' + device.connector.password )
                            device.configMode()
                            device.changeLoginPassword( device.connector.password )
                            # self.printCommands( device );
                            self.add_error( item.hostname, str(e) )

                # set the enable password
                if self.options.has_key( 'new_enable_password' ):
                    logging.info( "Changing enable passwords for " + item.hostname )
                    # now change enable password
                    device.changeEnablePassword( self.options['new_enable_password'] )
                    self.printCommands( device );
                            
                    # check we can enable
                    if not device.dry_run:
                        try:
                            logging.debug( "Testing new enable password on " + item.hostname + "...")
                            check_device = self.getCheckDevice( check_device, item.hostname, this_options )
                            check_device.enableMode()
                            # self.printCommands( device );
                            check_changed.append( 'enable_password' )
                        except Exception, e:
                            # revert back the enable password
                            logging.error( 'could not change enable password for ' + item.hostname + ": " + str(e) + ', reverting back to ' + device.connector.enable_password )
                            device.configMode()
                            device.changeEnablePassword( device.connector.enable_password )
                            # self.printCommands( device );
                            self.add_error( item.hostname, str(e) )
                            
                
                # close testing connection
                if not device.dry_run and not check_device == None:
                    logging.debug( "terminating password checking connection")
                    check_device.disconnect()
                    
                # change configuration accounts
                if self.options.has_key( 'configuration_password' ):
                    logging.info( "Changing configuration account for " + item.hostname )
                    if not device.dry_run:
                        device.changeAccountPassword( 'configuration', 15, self.options['configuration_password'] )
                        check_changed.append( 'configuration_password' )
                    self.printCommands( device );

                # change the wireless password
                if self.options.has_key( 'wireless_password' ):
                    logging.info( "Changing wireless account for " + item.hostname )
                    if not device.dry_run:
                        try:
                            device.changeAccountPassword( 'netdev', 15, self.options['wireless_password'] )
                            # check
                            this_options['password'] = self.options['wireless_password']
                            this_options['user'] = device.connector.user
                            check_device = self.getCheckDevice( check_device, item.hostname, this_options )
                            check_changed.append( 'wireless_password' )
                        except Exception, e:
                            # revert back the enable password
                            logging.error( 'could not change wireless password for ' + item.hostname + ": " + str(e) + ', reverting back to ' + device.connector.password )
                            device.changeAccountPassword( 'netdev', 15, device.connector.password )
                            self.add_error( item.hostname, str(e) )

                # change snmp strings
                if self.options.has_key( 'new_snmp_readonly_password' ) and self.options.has_key('new_snmp_readwrite_password'):
                    logging.info( "Changing snmp passwords for " + item.hostname )
                    if not device.dry_run:
                        device.changeSNMPReadPassword( self.options['new_snmp_readonly_password'] )
                        device.changeSNMPWritePassword( self.options['new_snmp_readwrite_password'] )
                        check_changed.append( 'snmp_community' )
                    self.printCommands( device );
                                
                # finished!
                self.add_okay( item.hostname, str(check_changed) )

            except Exception, e:
                
                logging.error( str(e) )
                self.add_error( item.hostname, str(e) )

            check_device = None
            
            if self.options.has_key( 'commit' ):
                device.commit()
                
            # free up sessions
            if not device.dry_run:
                device.disconnect()

            device = None



