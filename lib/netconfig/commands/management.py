import argparse

from slac_utils.command import CommandDispatcher, Command
from slac_utils.logger import init_loggers
from slac_utils.util import get_array

from netconfig import NewNetConfig as NetConfig
from netconfig.recipes.system import reload_and_monitor

from string import Template

import traceback
import sys
import logging



def delete_vlan_if_exists( device_obj, delete_vlan, other_vlan, **kwargs ):
    """
    if other_vlan exists, then prune the delete_vlan off all trunks and remove the vlan from the switch
    """
    conf_cursor = [ device_obj.prompt.cursor('mode','config') ]
    for p in device_obj.ports.filter( type='trunk' ):
        vlans = [ i for i in p['vlan'] ]
        logging.info("%s: %s" % (p['port'],vlans,))
        if other_vlan in vlans:
            if device_obj.prompt.ask( 'int %s' % (p['port'],), cursor=conf_cursor ):
                # add sequential possible cursors
                if len( conf_cursor )  == 1:
                    conf_cursor.append( device_obj.prompt.cursor('mode','config-if') )
                cmd = '  switchport trunk allowed vlan remove %s' % (delete_vlan,)
                logging.info( cmd )
                device_obj.prompt.ask( cmd )
    device_obj.prompt.ask( 'end' )
    
    # delete the vlan completely
    if other_vlan in dict(device_obj.layer2.vlan):
        # remove svi
        cmd = 'no int vlan %s' % delete_vlan
        logging.info(cmd)
        device_obj.prompt.ask( cmd, cursor=device_obj.prompt.cursor('mode','config') )

        # remove vlan
        cmd = 'no vlan %s' % delete_vlan
        logging.info(cmd)
        device_obj.prompt.ask( cmd, cursor=device_obj.prompt.cursor('mode','config') )

    # else:
    #     # rename the vlan 
    #     logging.info("renaming vlan %s" % (delete_vlan))
    #     ok = device_obj.layer2.vlan.add( delete_vlan, 'LCLSIOC' )
    #     pass

    device_obj.system.config.commit()    
    
    return


def create_vlan( device_obj, **kwargs ):
    enable_cursor = device_obj.prompt.cursor('mode','enable')
    new_vlan = int(kwargs['new_vlan']) 

    if not new_vlan in dict(device_obj.layer2.vlan):
        return device_obj.layer2.vlan.add( new_vlan, kwargs['new_vlan_name'] )
        
    return True


def add_vlan_to_uplinks( device_obj, **kwargs ):
    # enable_cursor = device_obj.prompt.cursor('mode','enable')
    conf_cursor = [ device_obj.prompt.cursor('mode','config') ]
    new_vlan = int(kwargs['new_vlan']) 

    ok = False
    for p in device_obj.ports.filter( type='trunk' ):
        vlans = [ i for i in p['vlan'] ]
        logging.info("%s: %s" % (p['port'],vlans,))
        try:

            if 'new_vlan' in kwargs:
                # add the new vlan to trunk
                if not new_vlan in vlans:
                    vlans.append( new_vlan )
                    logging.info("  adding new vlan to %s: %s -> %s" % (p['port'], new_vlan, vlans))
                    # device_obj.ports.set_type_trunk( p['port'], sorted(vlans), p )

                    if device_obj.prompt.ask( 'int %s' % (p['port'],), cursor=conf_cursor ):
                        
                        # add sequential possible cursors
                        if len( conf_cursor )  == 1:
                            conf_cursor.append( device_obj.prompt.cursor('mode','config-if') )
                        
                        cmd = '  switchport trunk allowed vlan add %s' % (new_vlan,)
                        logging.info( cmd )
                        device_obj.prompt.ask( cmd )
                        ok = True
                device_obj.prompt.ask( 'end' )
                # other side?
        except Exception,e:
            logging.error("ERR %s %s" % (type(e),e))
            ok = False
        
    return ok
    

def setup_management_ip( device_obj, **kwargs ):
    """
    change the management svi to supplied
    """
    logging.info("creating svi at %s" % (kwargs['new_ip'],))
    new_vlan = int(kwargs['new_vlan']) 
    with device_obj.prompt.stanza( 'interface vlan %s' % (new_vlan,), cursor=device_obj.prompt.cursor('mode','config') ) as p:
        for i in ( '  ip address %s %s' % (kwargs['new_ip'],kwargs['new_netmask']), ' no shut', ' end' ):
            p.ask( i )
        
    return True


def upload_management_ip( device_obj, **kwargs ):
    """
    write a config file to upload for merge
    """
    device_obj.prompt.tell( 'copy tftp://172.18.192.17/net/dmp/change_ip/crap running-conf', cursor=device_obj.prompt.cursor('mode','enable') )
    # confirm
    device_obj.prompt.tell('')
    
    
    

class RemoveVlanOnTrunks( Command ):
    """
    removes a vlan on a switch (and trunks) if this other vlan exists
    """

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        # subparser.add_argument( '-v', '--verbose', help='verbosity', action='store_true', default=False )
        subparser.add_argument( '-f', '--profile', help='profile to use', default=None )
        subparser.add_argument( 'device', help='device name', nargs="+" )
        subparser.add_argument( '--delete_vlan', help='new vlan', required=700 )
        subparser.add_argument( '--other_vlan', help='new vlan name', required=702 )
        
    def run( self, *args, **kwargs ):
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        netconfig = NetConfig( kwargs['config'] )        

        # logging.error("EL %s " % (kwargs['device'],))
        for d in kwargs['device']:

            try:

                # get device
                device = netconfig.get( d, options=kwargs )
                netconfig.connect( device, **kwargs )     
                
                # do it
                delete_vlan_if_exists( device, int(kwargs['delete_vlan']), int(kwargs['other_vlan']) )
                
                
            except Exception,e:
                t = traceback.format_exc()
                logging.error("%s: %s\n%s" % (type(e),e,t))
                


class AddVlanToTrunks( Command ):
    """
    Changes the management ip address of the switch
    """

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        # subparser.add_argument( '-v', '--verbose', help='verbosity', action='store_true', default=False )
        subparser.add_argument( '-f', '--profile', help='profile to use', default=None )
        subparser.add_argument( 'device', help='device name', nargs="+" )
        subparser.add_argument( '--new_vlan', help='new vlan', required=True )
        subparser.add_argument( '--new_vlan_name', help='new vlan name', required=True )

        
    def run( self, *args, **kwargs ):
        """
        plan:
          1) log onto device to determine current settings
          2) write new config partial to tftp
          3) upload new management config to switch
          4) try to log onto new device
        """
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        netconfig = NetConfig( kwargs['config'] )        

        # logging.error("EL %s " % (kwargs['device'],))
        for d in kwargs['device']:

            try:
                
                # get device
                device = netconfig.get( d, options=kwargs )
                netconfig.connect( device, **kwargs )     
                # create
                create_vlan( device, **kwargs )
                # add vlans
                add_vlan_to_uplinks( device, **kwargs )

                
            except Exception,e:
                t = traceback.format_exc()
                logging.error("%s: %s\n%s" % (type(e),e,t))
                




class ChangeIp( Command ):
    """
    Changes the management ip address of the switch
    """
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        # subparser.add_argument( '-v', '--verbose', help='verbosity', action='store_true', default=False )
        subparser.add_argument( '-f', '--profile', help='profile to use', default=None )
        subparser.add_argument( 'device', help='device name', nargs="+" )
        subparser.add_argument( '--new_ip', help='new ip address', required=True )
        subparser.add_argument( '--new_netmask', help='new netmask', default='255.255.255.0' )
        subparser.add_argument( '--new_gateway', help='new gateway', default='172.18.214.1' )
        subparser.add_argument( '--old_vlan', help='old vlan', default=700 )
        subparser.add_argument( '--new_vlan', help='new vlan', default=522 )
        subparser.add_argument( '--new_vlan_name', help='new vlan name', default='NETMGMT-MCC' )

        # subparser.add_argument( '--tftp_server', help='tftp server', default='172.18.192.17' )
        # subparser.add_argument( '--tftp_root', help='root tftp directory', default='/tftpboot' )
        # subparser.add_argument( '--tftp_path', help='directory for temp config files', default='net/dmp/change_ip/' )
        
    def run( self, *args, **kwargs ):
        """
        plan:
          1) log onto device to determine current settings
          2) write new config partial to tftp
          3) upload new management config to switch
          4) try to log onto new device
        """
        init_loggers( **kwargs )
        
        options = {}
        for i in ( 'profile', ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        netconfig = NetConfig( kwargs['config'] )        

        # logging.error("EL %s " % (kwargs['device'],))
        for d in kwargs['device']:

            try:
                
                # get device
                device = netconfig.get( d, options=kwargs )
                netconfig.connect( device, **kwargs )        

                # create vlan
                if not create_vlan( device, **kwargs ):
                    raise Exception, 'could not create vlan'
                    
                # add to uplinks and add svi
                if not add_vlan_to_uplinks( device, **kwargs ):
                    raise Exception, 'did not add vlan to any new uplinks'
                    
                # prepare the svi
                if not setup_management_ip( device, **kwargs ):
                    raise Exception, 'could not create new svi'
                        
                # switch the old and new svi's
                

                # # change default gateway
                # try:
                #     device.prompt.ask( 'ip default-gateway %s' % (kwargs['new_gateway'],), cursor=device.prompt.cursor('mode','config'), timeout=2 )
                # except Exception, e:
                #     logging.debug("required timeout... %s %s" % (type(e),e))
                
                # we're now kicked out because of change in default gateway, so try to reconnect to new ip      
                # new_device = netconfig.get( kwargs['new_ip'], options=kwargs, profiles=[ 'ios' ], use_cache=True )
                # netconfig.connect( new_device )

                # if 'old_vlan' in kwargs:
                #     new_device.prompt.ask('no interface vlan %s' % (kwargs['old_vlan'],))
                # new_device.system.config.commit()
            
            
            except Exception,e:
                logging.error("%s: %s" % (type(e),e))
                


class Management( CommandDispatcher ):
    """
    Generic switch management commands
    """
    subcommands = [ ChangeIp, AddVlanToTrunks, RemoveVlanOnTrunks ]
                
