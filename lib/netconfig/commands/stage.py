import argparse

from slac_utils.command import Command, CommandDispatcher
from slac_utils.logger import init_loggers
from slac_utils.util import get_array
from slac_utils.time import now, sleep
from datetime import timedelta

from netconfig import NewNetConfig as NetConfig
from netconfig.recipes.system import reload_and_monitor, FirmwareHelper, upgrade_firmware
from string import Template

from multiprocessing import Process
from slac_utils.queues import MultiprocessQueue

from re import sub

from pprint import pformat
import traceback
import sys
import logging



def initiate_staging( netconfig, port_number, fields ):
    logging.info("connecting to staging network " + str(fields['switch']))
    switch = netconfig.get( fields['switch'] )
    netconfig.connect( switch )
    return switch
    
def initiate_console( netconfig, port_number, fields, profile=None ):
    # logging.info("connecting to console " + str(fields['console']))
    console_port = int(port_number) + int(fields['console_port_offset'])
    console = netconfig.get( fields['console'], options={ 'port': console_port, 'profile': profile } )
    logging.info("connecting to %s on port %s" % (fields['console'],console_port) )
    # may need to try twice
    try:
        netconfig.connect( console, prime=True )
    except:
        netconfig.connect( console, prime=True )
    # no paging
    console.prompt.terminal_buffer()
    return console


def setup_console( console, fields, console_cmds=[] ):
    """
    prepares the terminal console and switch to ready firmware update 
    """
    # bypass any prompts with ctrl-c
    if console.prompt.mode_config():
        logging.info("  configuring new device with ip %s/%s, gateway %s" % (fields['staging_ip'], fields['staging_netmask'], fields['staging_gateway']) )
        for l in console_cmds:
            console.prompt.ask( l )


def setup_staging( switch, fields, console_cmds=[], switch_port=None ):
    if 'port' in switch_port:
        logging.info("  configuring port %s for vlan %s" % (switch_port['port'],fields['staging_vlan']) )
        switch.ports.set( switch_port['port'], switch_port, initial_check=False )
    else:
        logging.error("no switch port defined")
        
    return switch_port



def teardown_console( console, console_cmds=[] ):
    # clean up
    logging.info('cleaning up')
    if console.prompt.mode_config():
        for l in console_cmds:
            console.prompt.ask( l )
    console.disconnect()
            
def teardown_staging( switch, switch_port ):
    # manually
    if not switch_port:
        switch.ports.set( switch_port['port'], switch_port, initial_check=False )
    switch.disconnect()


# def teardown( console, switch, fields, console_cmds=[], switch_port=None ):
#     # clean up
#     logging.info('cleaning up')
#     if console.prompt.mode_config():
#         for l in console_cmds:
#             console.prompt.ask( l )
#     
#     # manually
#     if not switch_port:
#         switch.ports.set( switch_port['port'], switch_port, initial_check=False )
#     
#     # finish
#     console.disconnect()
#     switch.disconnect()


    
def get_config( config, device ):
    # create hash for substitution
    m = {}
    for k,v in config.items( device ):
        # if k.startswith('staging_'):
        m[k] = v
    # logging.info("MAPPING: " + str(m))
    return m
    
    

def templater( mapping, line ):
    for h in mapping:
        line = sub( r'{{\s+'+str(h)+'\s+}}', str(mapping[h]), line )
    return line

def templater( mapping, line ):
    for h in mapping:
        line = sub( r'{{\s+'+str(h)+'\s+}}', str(mapping[h]), line )
    return line
    
def parse_commands( config, mapping ):
    cmds = {}
    # TODO: relative paths?
    # tmpl_path = dirname(__file__) + '/../templates/'
    for k,v in config.iteritems():
        if k.startswith( 'cmds_' ):
            cmds[k] = templater( mapping, v ).split("\n")
    # logging.info("CMDS: " + str(cmds))
    return cmds


    

class Base( Command ):
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        up = parser.add_argument_group('upgrade')
        up.add_argument( 'device_type', help='device type upgrade', choices=[ k for k in settings ] )
        up.add_argument( 'port_number', help='staging port id' )

        up.add_argument( '-r', '--release', help='version to upgrade', default=None )
        up.add_argument( '-g', '--group', help='firmware group', default=None )

        post = parser.add_argument_group('action')

        post.add_argument( '--reload', help='reload device after transfer', action='store_true', default=False )
        post.add_argument( '--dry_run', help='do not actually do the upgrade but show actions', action='store_true', default=False )

        # post.add_argument( '--teardown', help='clear up after', action='store_false', default=True )
        
        fw = parser.add_argument_group('firmware')
        fw.add_argument( '--settings', default=settings )

    def setup( self, *args, **kwargs ):
        
        init_loggers( **kwargs )

        self.group = kwargs['group']
        self.release = kwargs['release']

        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]

        self.fw_helper = FirmwareHelper( kwargs['settings']['server'], kwargs['settings']['firmware'] )

        self.netconfig = NetConfig( kwargs['config'] )   
        self.options = options


class UpgradeFirmware( Base ):
    """
    upgrade staging device to registered firmware versions
    """

    def run( self, *args, **kwargs ):

        self.setup( *args, **kwargs )

        t = kwargs['device_type']
        logging.info("preparing a %s device" % (t,))
        port_number = kwargs['port_number']
        
        settings = kwargs['settings'][t]
        
        group = kwargs['group']
        if group == None:
            group = t
        release = kwargs['release']
        
        cmds = parse_commands( settings, settings )
        
        # do it!
        logging.info("staging new %s device at position %s..." %(t,port_number))

        # setup staging switch
        switch = None
        try:
            switch = initiate_staging( self.netconfig, port_number, settings )
            port = switch.ports.get( settings['switch_port_prefix'] + str(port_number) )
            port_setup = { 
                'port':     port['port'],
                'alias':    'staging',
                'state':    True,
                'vlan':     settings['staging_vlan'],
                'type':     'access',
            }
            setup_staging( switch, settings, console_cmds=cmds['cmds_console_setup'], switch_port=port_setup )
        except Exception,e:
            raise Exception( 'Failed to connect to staging switch: %s' % (e,))
        
        # setup staging console
        console = None
        try:

            # set up console
            console = initiate_console( self.netconfig, port_number, settings, profile=settings['console_profile'] )    
            setup_console( console, settings, console_cmds=cmds['cmds_console_setup'] )

        except Exception, e:
            raise Exception('Failed to connect to staging console: %s' % (e,) )

        # update firmware!
        try:
            # try to ping twice just in case
            for i in xrange(2):
                test = console.prompt.request('ping ' + kwargs['settings']['server']['host'] )
                if str(test).find('!') == -1 and i == 2:
                    raise Exception, "no network connectivity"
                else:
                    continue

            ok = upgrade_firmware( self.netconfig, console, group, release, self.fw_helper, dry_run=kwargs['dry_run'] )
            if len(ok):
                if 'reload' in kwargs and kwargs['reload']:
                    for m in reload_and_monitor( self.netconfig, console ):
                        logging.info("%s"%(m,))

        except Exception, e:
            # raise Exception("Failed to update firmware: %s, %s" %(e, traceback.format_exc()))
            raise Exception("Failed to update firmware: %s" %(e,))

    
        # cleanup
        # if kwargs['teardown']:
        port_teardown = {
            'port':     port['port'],
            'alias':    '',
            'state':    False, 
            'vlan':     1,
            'type':     'access'
        }
        # teardown( console, switch, settings, console_cmds=cmds['cmds_console_teardown' ], switch_port=port_teardown )
        if console:
            teardown_console( console, console_cmds=cmds['cmds_console_teardown' ] )
        if switch:
            teardown_staging( switch, switch_port=port_teardown )
    

class Stage( CommandDispatcher ):
    """
    Network device staging commands
    """
    commands = [ UpgradeFirmware ]
