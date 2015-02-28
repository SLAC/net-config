import argparse

from slac_utils.command import Command
from slac_utils.util import get_array, boolean

from netconfig import NewNetConfig as NetConfig

from re import search, match, compile, sub

from copy import copy
import sys
import logging
from slac_utils.logger import init_loggers
import traceback


def set_ports( device, ports ):
    for port in ports:

        try:
        
            logging.info("processing: %s" % (port))
            action, data = device.ports.set( port['port'], port )
            # raise Exception, 'something'

            yield device.hostname, port, action, data

        except Exception, e:
            logging.warn("Err: %s %s\n%s" % (type(e),e,traceback.format_exc()))

    return

delimiter_map = {
    'ssv':  r'\s+',
    'tsv':  r'\t',
    'csv':  r',',
}


def parse_file( **kwargs ):
    
    # parse the file!
    use_delimiter = delimiter_map['ssv']
    if delimiter_map.has_key( kwargs['delimiter'] ):
        use_delimiter = delimiter_map[kwargs['delimiter']]
        # logging.debug( "using delimiter " + kwargs['delimiter'] + " -> '" + use_delimiter + "'")
    else:
        use_delimiter = None
    
    logging.info("parsing file %s with %s (%s)" % (kwargs['input_file'], kwargs['delimiter'], use_delimiter ))

    fields = kwargs['field']        
    for l in get_array( kwargs['input_file'] ):

        logging.debug(" >: %s" % (l,))
        
        f = []
        if not use_delimiter:
            f = i.split( use_delimiter )
        else:
            m = sub( use_delimiter, "\x00", l)
            f = m.split( "\x00" )
            # logging.debug("splittting sub " + str(options['delimiter']) + ': ' + str(fields))

        if len(f) < len(fields):
            logging.warning( ' skipping line with wrong number of fields: %s', l[0:19] )
            continue
        
        this = {}
        
        # set defaults for this port
        logging.debug( " setting defaults:" )
        for i in ( 'device', 'state', 'vlan' ):
            if not i in kwargs: continue
            val = kwargs[i]
            if i in ( 'state', ): 
                val = boolean( val )
                # logging.error("VAL: %s" % (val))
        
            if i in kwargs:
                if i in ( 'state', 'vlan' ):
                    this[i] = val
                else:
                    this[i] = str(val)
                logging.debug( "  set %s as %s" % (i, val) )
    
        # set all optiosn from file
        logging.debug( " setting options: %s" % (fields) )
        for i in fields:
            val = f.pop(0)
            if not i == 'none':
                if i == 'alias' and val == '-': val = ''
                this[i] = val
                logging.debug( "  set %s as %s" % (i, val) )
        
        for k in this.keys():
            if this[k] == None:
                del this[k]
        
        yield this
    return




class Interface( Command ):
    """
    Batch configure interfaces
    """

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        parser.add_argument( '-f', '--profile', help='profile to use', default=None )
        parser.add_argument( '-d', '--delimiter', help='delimiter for text fields', choices=[ 'csv','tsv', 'ssv' ], default='ssv' )
        parser.add_argument( '-s', '--state', help='port(s) state' )
        parser.add_argument( '-V', '--vlan', help='port(s) vlan' )

        parser.add_argument( '--device', help='name of device to program' )
        parser.add_argument( 'input_file', help='file to parse' )
        parser.add_argument( 'field', help='file to parse', nargs="+" )

        
    def run( self, *args, **kwargs ):
        
        init_loggers( **kwargs )
        
        # organise by device
        by_device = {}
        for i in parse_file( **kwargs ):
            logging.debug(" >= %s" % i)
            if not i['device'] in by_device:
                by_device[i['device']] = []
            by_device[i['device']].append( i )

        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        netconfig = NetConfig( kwargs['config'] )        
        
        for d in by_device:

            dev = None
            try:
            
                dev = netconfig.get( d )
                netconfig.connect( dev )
    
                # disable buffering
                dev.prompt.terminal_buffer( 0 )
    
                for d,port,action,data in set_ports( dev, by_device[d] ):
                    if action == True:
                        logging.info(" updated")
                    elif action == None:
                        logging.info(" no changes required")
                    else:
                        raise Exception( "%s %s failed: %s" % (d,port['port'],data) )

                
        
            except Exception, e:
                t = traceback.format_exc()
                logging.error("%s: %s\n%s" %(type(e),e,t))
            finally:
                if dev:
                    dev.disconnect()