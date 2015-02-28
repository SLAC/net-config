import argparse

from slac_utils.command import Command
from slac_utils.logger import init_loggers
from slac_utils.util import get_array

from netconfig import NewNetConfig as NetConfig
import sys
import logging

class Edit( Command ):
    """
    Log on to device and enter an interactive terminal session
    """
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( '-f', '--profile', help='profile to use', default=None )
        parser.add_argument( 'device', help='device to log onto' )
        parser.add_argument( '--no_user_check', help='do not check for conflicting sign-ons', action='store_false', default=True )
        parser.add_argument( '-e', '--enable', help='enter privileged mode', action='store_true', default=True )
        parser.add_argument( '--port', help='port number for connection', required=False )
        parser.add_argument( '--prime', help='send carriage return prior to login', action='store_true', default=False )
        parser.add_argument( '--cache_group', help='cache group', required=False )

        
    def run( self, *args, **kwargs ):
        
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', 'port', 'prime', 'password', 'username', 'cache_group' ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]

        netconfig = NetConfig( kwargs['config'] )
        device = None
        try:
    
            device = netconfig.get( kwargs['device'], options=options )
            netconfig.connect( device, **options )
        
            # init
            if kwargs['no_user_check']:
                try:
                    users = {}
                    t = device.system.users.get()
                    if not t == None:
                        for i in t:
                            if not 'user' in i:
                                i['user'] = 'unknown'
                            if not i['user'] in users:
                                users[i['user']] = []
                            users[i['user']].append( i['line'] )
                        for k,v in users.iteritems():
                            print('WARNING: %s is connected on %s' %(k,', '.join(v)) )
                except:
                    pass
                    
            if device.ports.conf_sync:
                print("NOTICE: device is using conf sync profile %s" % device.ports.conf_sync )
                
            # set up enable acess
            if kwargs['enable']:
                device.prompt.mode_enable()
        
            device.prompt.mode_interactive()
        except Exception, e:
            logging.error("%s: %s" %(type(e),e))
        finally:
            if device:
                device.disconnect()