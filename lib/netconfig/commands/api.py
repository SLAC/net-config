import argparse

from slac_utils.command import Command, MultiprocessMixin
from slac_utils.logger import init_loggers
from slac_utils.util import get_array
from multiprocessing import Manager

from netconfig import NewNetConfig as NetConfig
import sys
import logging


def api( hostname, netconfig_conf, mutex, kwargs, options, quiet ):
    device = None
    error = None
    res = []
    if not quiet:
        logging.info("%s"%hostname)
    try:
        netconfig = NetConfig( netconfig_conf, mutex=mutex )
        device = netconfig.get( hostname, options=options )
        netconfig.connect( device, **options )
    
        component = device.get_component( kwargs['component'] )
        # logging.info("C: %s" % component)
        # component lists allow __iter__
        # if kwargs['arg']:
        #     logging.info( "%s" %  component( kwargs['arg'] ) )
        # else:
        done = component()
        if isinstance( done, bool ):
            done = [ True ]
        for d in done:
            # logging.info("%s" % (d,))
            # for i in d:
            res.append( d )
    except Exception, e:
        logging.error("Err: %s: %s %s" %(hostname,type(e),e))
        error = str(e)
    finally:
        if device:
            device.disconnect()
    out = { 'res': res, 'error': error }
    if not quiet:
        log = getattr( logging, 'info' )
        if error:
            log = getattr( logging, 'warn' )
        log("%s\t%s" % (hostname,out))
    return out



class Api( Command, MultiprocessMixin ):
    """
    calls a component api
    """
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( '-f', '--profile', help='profile to use', default=None )
        parser.add_argument( '--port', help='port number for connection', required=False )
        parser.add_argument( '--quiet', help='minimise output', required=False )
        parser.add_argument( '-w', '--workers', help='number of concurrent workers', default=1, type=int )
        parser.add_argument( '--cache_group', help='cache group', required=False )

        parser.add_argument( 'device', help='device to log onto' )
        parser.add_argument( 'component', help='component to call' )
        parser.add_argument( 'arg', help='argument', default=None, nargs='?' )

        parser.add_argument( '--randomise', help='randomise order of tests', default=False, action="store_true" )
        
    def run( self, *args, **kwargs ):
        
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', 'port', 'prime', 'password', 'username', 'cache_group' ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
                
        devices = get_array( kwargs['device'] )
        if kwargs['randomise']:
            shuffle(devices)

        # get lock
        manager = Manager()
        mutex = manager.Lock()
                
        # map/reduce
        target_args = [ kwargs['config'], mutex, kwargs, options, kwargs['quiet'] ]
        res = self.map( api, devices, num_workers=kwargs['workers'], target_args=target_args )
        for hostname, status in self.fold( devices, res ):
            # don't bother if not changed
            logging.info("%s: %s" % (hostname,status))
            
