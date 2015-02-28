import argparse

from slac_utils.command import Command, CommandDispatcher, MultiprocessMixin
from slac_utils.logger import init_loggers
from slac_utils.util import get_array
import slac_utils.net

from multiprocessing import Manager

from netconfig import NewNetConfig as NetConfig
from netconfig.recipes.system import FirmwareHelper, upgrade_firmware
from netconfig.recipes.wireless import set_name_and_group
from slac_utils.time import sleep

from re import search, match, compile
import sys
import logging
import traceback

#gcx
def eth_mac( hostname, netconfig_conf, options, quiet ):
    """
    Get mac address of the eth interface
    """
    try:
        netconfig = NetConfig( netconfig_conf )
        ap = netconfig.get( hostname, options=options )
        ap.connect()
        ap_mac_address = None
        for interface in ( 'Gi', 'Fa' ):
            for i in ap.tell( 'show interface | beg %s' % interface ):
                m = search( r'\(bia (?P<bia>\S+)\)', i )
                if m:
                    ap_mac_address = slac_utils.net.mac_address( m.group('bia') )
                    break
        ap.disconnect()

        if ap_mac_address == None:
            raise Exception, 'could not determine ap mac address'
#        logging.info('found %s mac address as: %s' % (hostname,ap_mac_address,))

        return ap_mac_address
    except Exception,e:
        logging.error("%s %s" % (type(e),e))
        error = str(e)

class EthMac( Command, MultiprocessMixin ):
    """
    Get eth mac addresses of access points
    """

    netconfig = None
    options = {}
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'device', help='device(s)/text file of devices to query', nargs="+")

        parser.add_argument( '-w', '--workers', type=int, help='number of concurrent workers', default=1 )
        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )

        
    def run(self, *args, **kwargs):
        init_loggers( **kwargs )
        options = {}
        for i in ( 'profile', 'password' ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        self.netconfig = NetConfig( kwargs['config'] )   
        self.options = options

        results = {}

        target_args = [ kwargs['config'], options, kwargs['quiet'] ]
        res = self.map( eth_mac, kwargs['device'], num_workers=kwargs['workers'], target_args=target_args )
        for hostname, mac in self.fold( kwargs['device'], res ):
            print "%s\t%s" % (hostname,mac)

def bssid( hostname, netconfig_conf, options, quiet ):
    """
    just logs onto the device and grabs out bssids
    """
    found = {}
    error = None
    try:
        netconfig = NetConfig( netconfig_conf )
        device = netconfig.get( hostname, options=options )
        device.connect()    
        cmd = 'show int | inc Radio,'
        for i in device.prompt.tell( cmd ):
            m = search( r'Hardware is (?P<hardware>.*), address is (?P<addr>.*) \(bia (?P<bia>.*)\)$', i )
            if m:
                d = m.groupdict()
                found[d['bia']] = d
    except Exception,e:
        logging.error("%s %s" % (type(e),e))
        error = str(e)
    finally:
        if device:
            device.disconnect()
    # if not quiet:
    #     log = getattr( logging, 'info' )
    #     if error:
    #         log = getattr( logging, 'warn' )
    #     log("%s\t%s" % (hostname,found))

    return { 'interfaces': found, 'error': error }

class Bssids( Command, MultiprocessMixin ):
    """
    Query wireless access points for their wireless bssids
    """

    netconfig = None
    options = {}
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'device', help='device(s)/text file of devices to query', nargs="+")

        parser.add_argument( '-w', '--workers', type=int, help='number of concurrent workers', default=1 )
        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )

        
    def run(self, *args, **kwargs):
        init_loggers( **kwargs )
        options = {}
        for i in ( 'profile', 'password' ):
            if i in kwargs and kwargs[i]:
                options[i] = kwargs[i]
        self.netconfig = NetConfig( kwargs['config'] )   
        self.options = options

        results = {}

        target_args = [ kwargs['config'], options, kwargs['quiet'] ]
        res = self.map( bssid, kwargs['device'], num_workers=kwargs['workers'], target_args=target_args )
        for hostname, status in self.fold( kwargs['device'], res ):
            msg = ''
            if status['error']:
                msg = status['error']
            else:
                msg = '\t'.join( v['bia'] for k,v in status['interfaces'].iteritems() )
            print "%s\t%s" % (hostname,msg)


class WlcBssids( Command ):
    """
    Query for all BSSIDs from WLC
    """
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( '--device', help='WLC hostname', default='swh-wlc' )
        parser.add_argument( '--slots', help="radio types to query", default=( '802.11b','802.11a'), nargs="+" )
        
    def run( self, *args, **kwargs ):
        init_loggers( **kwargs )
        nc = NetConfig( kwargs['config'] )   
        
        wlc = nc.get( kwargs['device'] )
        wlc.connect()
        
        # 1) get list of all registered ap's
        aps = []
        for i in wlc.tell( 'show ap summary' ):
            m = search( '(?P<name>\S+)\s+\d+\s+(?P<model>\S+)\s+(?P<mac>\S+)\s+', i )
            if m:
                d = m.groupdict()
                aps.append(d)
        logging.debug("%s" % (aps,))
    
        # 2) for each, determine for each 'slot' it's bssid
        for ap in aps:
            for slot in kwargs['slots']:
                for i in wlc.tell( 'show ap wlan %s %s' % (slot,ap['name']) ):
                    m = search( r'(?P<wlan_id>\d+)\s+(?P<interface>\S+)\s+(?P<bssid>\S+)\s*$', i )
                    if m:
                        d = m.groupdict()
                        ap[slot] = d['bssid']
        logging.debug("%s" % (aps,))
        
        # 3) report!
        print "# ap\t%s" % '\t'.join(s for s in kwargs['slots'])
        for ap in aps:
            bssids = "%s" % '\t'.join( [ ap[s] for s in kwargs['slots'] ] )
            print "%s\t%s" % (ap['name'],bssids)
            

def rename_ap_on_wlc( controller, ap_name, ap_mac_address, netconfig, options, quiet, apgroup='default-group', dry_run=False, timeout=600, dur=200 ):
    """
    set the name of the ap in wlc and optionally the apgroup
    """
    wlc = None
    try:
    # log onto wlc
        wlc = netconfig.get(controller)
        if not dry_run:
            wlc.connect()
            while timeout > 0:
                try:
                    success = set_name_and_group( wlc, ap_name, ap_mac_address, apgroup )
                    break
                except:
                    logging.info("... access point hasn't shown up yet")
                sleep( dur )
                timeout = timeout - dur
            if timeout <= 0:
                raise Exception, 'could not assign %s (%s) to group %s' % (ap_name, ap_mac_address, apgroup )
    except Exception,e:
        raise e
    finally:
        if wlc:
            wlc.disconnect()
    return True


def migrate( hostname, netconfig_conf, mutex, firmware_helper, options, quiet, apgroup='default-group', dry_run=False ):
    """
    just logs onto the device and grabs out bssids
    """
    success = False
    error = None
    ap = None
    switch = None
    wlc = None
    try:
        netconfig = NetConfig( netconfig_conf, mutex=mutex )

        # ap connections
        ap = netconfig.get( hostname, options=options )
        ap.connect()
        
        # 1) log onto ap and determine mac address
        ap_mac_address = None
        for interface in ( 'Gi', 'Fa' ):
            for i in ap.tell( 'show interface | beg %s' % interface ):
                m = search( r'\(bia (?P<bia>\S+)\)', i )
                if m:
                    ap_mac_address = slac_utils.net.mac_address( m.group('bia') )
                    break
        if ap_mac_address == None:
            raise Exception, 'could not determine ap mac address'
        logging.info('found %s mac address as: %s' % (hostname,ap_mac_address,))
        
        # 2) see where it's connected to via cdp
        peer = {}
        for ap_port,d in ap.layer1:
            # assume only one connection
            peer = {
                'name': d['peer_device'].split('.')[0],
                'port': d['peer_physical_port']
            }
        if peer == {}:
            raise Exception, 'could not determine where access point is connected to'
            
        # 3) upload new firmware to ap
        try:
            # don't do image only as it will deactivate wireless interfaces
            upgrade_firmware( netconfig, ap, 'wlc', None, firmware_helper, options={}, image_only=False, dry_run=dry_run )
        except Exception,e :
            raise Exception, 'could not upgrade firmware: %s' % e
            
        # 4) clear the configs on the ap
        if not dry_run:
            try:
                logging.info('clearing configs')
                # do an write erase to clear config and delete the bvi cache to enable dhcp booting (faster)
                for c in ( 'erase /all nvram:', 'del env_vars', 'del private-config', 'del config.txt', 'wr erase', ):
                    ap.prompt.ask( c, interact={ 'confirm': '\n', 'question': '\n' } )
            except Exception, e:
                logging.error("could not clear configuration: %s" % (e,))
                raise e

            try:
                #sleep(20)
                ap.system.reload( force=True, commit=False )
            except Exception,e:
                logging.error("could not reload: %s" % (e,))
                raise e

        # 5) change switch port to private with cdp
        switch = netconfig.get( peer['name'] )
        switch.connect()
        # get the private vlan name
        vlan = None
        for v,d in dict( switch.layer2.vlan ).iteritems():
            if 'name' in d and match( '.*PRIVATE', d['name'] ):
                vlan = v
        
        if vlan == None:  # gcx default on PUB4 subnet if no private vlan
            vlan = 56
#            for v,d in dict( switch.layer2.vlan ).iteritems():
#                if 'name' in d and match( 'PUB4', d['name'] ): # Not working
#                    vlan = v
        print "Vlan is set to ", vlan
        if vlan == None:
            raise Exception, 'could not determine private vlan number'
        # change the port
        port = {
            'alias': hostname,
            'type': 'access',
            'vlan': vlan,
            'cdp': True,
            'portfast': True,
            'bpduguard': True,
        }
        if not dry_run:
            logging.info("configuring switch port %s %s for %s" % (peer['name'],peer['port'],port) )
            ok, port = switch.ports.set( peer['port'], port )
            if ok == None:
                # no changes required
                pass
            elif not ok:
                raise Exception, 'could not configure switch port %s %s for access point' % (peer['name'],peer['port'])
        else:
            logging.info("would have configured switch port %s %s for %s" % (peer['name'],peer['port'],port) )

        # 6) determine mac address on access port for double check?
# gcx not working so skip it
#        rename_ap_on_wlc( 'swh-wlc', hostname, ap_mac_address, netconfig, mutex, options, quiet, apgroup, dry_run )
        # # log onto wlc
        # if not dry_run:
        #     wlc = netconfig.get('swh-wlc')
        #     wlc.connect()
        #     timeout = 600
        #     dur = 15
        #     while timeout > 0:
        #         try:
        #             success = set_name_and_group( wlc, hostname, ap_mac_address, apgroup )
        #             break
        #         except:
        #             logging.info("... access point hasn't shown up yet")
        #         sleep( dur )
        #         timeout = timeout - dur
        #     if timeout <= 0:
        #         raise Exception, 'could not assign %s (%s) to group %s' % (hostname, ap_mac_address, apgroup )
        
    except Exception,e:
        logging.error("%s %s; %s" % (type(e),e,traceback.format_exc()))
        error = str(e)
    finally:
        for i in ( ap, switch, wlc ):
            if i is not None:
                i.disconnect()
                
    return { 'state': success, 'error': error }

class MigrateToWlc( Command, MultiprocessMixin ):
    """
    Migrate an access point from Fat AP to Thin AP
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'device', help='device(s)/text file of access points to migrate', nargs="+")
        parser.add_argument( '-w', '--workers', type=int, help='number of concurrent workers', default=1 )
        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )
        parser.add_argument( '--dry_run', help='do not make any changes', default=False, action="store_true" )

        parser.add_argument( '--apgroup', help='apgroup for access point', default='default-group' )


        fw = parser.add_argument_group('firmware')
        fw.add_argument( '--settings', default=settings )
        
    def run(self, *args, **kwargs):
        init_loggers(**kwargs)
        self.netconfig = NetConfig( kwargs['config'] )
        
        # get lock
        manager = Manager()
        mutex = manager.Lock()
        
        fw = FirmwareHelper( kwargs['settings'].server, kwargs['settings'].firmware )
        
        options = {}
        target_args = [ kwargs['config'], mutex, fw, options, kwargs['quiet'], kwargs['apgroup'], kwargs['dry_run'] ]
        res = self.map( migrate, kwargs['device'], num_workers=kwargs['workers'], target_args=target_args )
        for hostname, status in self.fold( kwargs['device'], res ):
            msg = ''
            # if status['error']:
            #     msg = status['error']
            # else:
            msg = status
            print "%s\t%s" % (hostname,msg)

class NameAndGroup( Command ):
    """
    Set ap name and group
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( 'ap_mac_address', help='mac address of ap' )
        parser.add_argument( 'ap_name', help='name of ap' )
        parser.add_argument( '-g', '--apgroup', help='desired group wlc group name',  default='default-group' )
        parser.add_argument( '--controller', help='controller address',  default='swh-wlc' )
        parser.add_argument( '--quiet', help='silent output', default=False, action="store_true" )
        parser.add_argument( '--dry_run', help='do not make any changes', default=False, action="store_true" )

    def run(self, *args, **kwargs):
        init_loggers(**kwargs)
        self.netconfig = NetConfig( kwargs['config'] )
        options = {}
        rename_ap_on_wlc( kwargs['controller'], kwargs['ap_name'], kwargs['ap_mac_address'], self.netconfig, options, kwargs['quiet'], kwargs['apgroup'], kwargs['dry_run'] )

    
class Wireless( CommandDispatcher ):
    """
    Wireless device information
    """
    commands = [ Bssids, MigrateToWlc, WlcBssids, EthMac, NameAndGroup ]
