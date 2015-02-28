import argparse

from slac_utils.command import Command, CommandDispatcher, MultiprocessMixin
from slac_utils.util import get_array

from netconfig import NewNetConfig as NetConfig

from re import search, match, compile

import sys
import logging
from slac_utils.logger import init_loggers
import traceback


def execute_commands( device, *commands ):

    for l in commands:
    
        j = l.split( '\\n' )
        logging.debug("="*10 + ' ' + str(j) + ' '+'='*10 )

        for k in j:

            args = { 'timeout': None, 'cmd': None, 'echo': None }
        
            # k is the command to run
            k = k.strip()

            # skip comments
            if True in [ match( c, k ) for c in ( '^\!', ) ]:
                logging.debug("found a comment line")
                continue

            # now we want to send commands for arguments, we look for these with ^[.*]
            m = search( r'^\[(?P<meta>.*)\]\s*(?P<cmd>.*)$', k ) 
            if m:
                d = m.groupdict()
                # get the command to send
                k = d['cmd']
                # work out the args
                for i in d['meta'].split(','):
                    x = i.split('=')
                    logging.debug("x="+str(x))
                    if x[0] == 'run':
                        x[0] = 'cmd'
                    args[x[0]] = x[1]
            logging.debug('got instruction: %s, k=%s' %(args,k))
        
            # store the output
            output = []
            error = False
        
            
        
            # just pipe the commands directly
            if args['cmd'] == None:
                logging.debug( "run: " + str(args) )
                output = device.prompt.request( k, timeout=args['timeout'], interact={ 'question': '\n' } )
        
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
            
                logging.debug( "  calling method %s %s" % (method,parameters))
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
                    logging.debug("  calling method %s for component %s" % (method,this))
                    output = this.__getattribute__( method )( *parameters, **kwargs )

                except Exception, e:
                    logging.error("%s" % (output,) )
                    yield k, False, e

            # return results
            yield k, { 'output': output, 'error': error }

    

def pipe( hostname, netconfig_conf, mode, commands, options ):

    data = []
    device = None
    try:
        netconfig = NetConfig( netconfig_conf )
        device = netconfig.get( hostname, options=options )
        netconfig.connect( device, **options )
        # disable buffering
        device.prompt.terminal_buffer( 0 )
        
        if mode == 'enable':
            device.prompt.mode_enable()
        elif mode == 'config':
            device.prompt.mode_config()
        
        for cmd,d in execute_commands( device, *commands ):
            data.append( {
                'command':  cmd,
                'output':   d['output'],
                'error':    d['error']
            } )
                
    except Exception,e:
        logging.debug("Err: %s: %s\n%s" % (type(e),e,traceback.format_exc()) )
        error = str(e)
    finally:
        if device:
            device.disconnect()            
        
    return data


class Pipe( Command, MultiprocessMixin ):
    """
    Enable piping of commands to device(s)
    """

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        parser.add_argument( '-f', '--profile', help='profile to use', default=None )
        parser.add_argument( '-e', '--enable', help='enter privileged mode', action='store_true', default=True )
        parser.add_argument( '-t', '--confterm', help='enter configuration terminal mode', action='store_true', default=False )

        parser.add_argument( '-w', '--workers', help='number of concurrent workers', default=1, type=int )

        parser.add_argument( '--echo', help='echo commands', default=False, action='store_true' )
        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )
        parser.add_argument( 'device', help='device(s)', nargs="+" )
        parser.add_argument( '--cache_group', help='cache group', required=False )

        
    def run( self, *args, **kwargs ):
        
        init_loggers( **kwargs )
        
        # get list of commands from stdin
        commands = [ l.rstrip() for l in sys.stdin ]
        
        options = {}
        for i in ( 'profile', 'password', 'username', 'cache_group', 'profile' ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]

        mode = None
        # set up enable acess
        if kwargs['enable']:
            mode = 'enable'
        if kwargs['confterm']:
            mode = 'config'

        devices = get_array( kwargs['device'] )

        target_args = [ kwargs['config'], mode, commands, options ]
        res = self.map( pipe, devices, num_workers=kwargs['workers'], target_args=target_args )
        for hostname, status in self.fold( devices, res ):
            # print "%s\t%s" % (hostname, status)
            for s in status:
                # print '! %s' % s['command']
                for o in s['output']:
                    print "%s" % o
