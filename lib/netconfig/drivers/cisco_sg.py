from netconfig.drivers.cisco_ios import PortsCiscoIos, PromptCiscoIos
from netconfig.drivers import IncompatibleDeviceException, Device, System, Vlan, MacAddress, Config, Layer2 

from re import match, search
import logging

#######################################################################
# Cisco SG300
#######################################################################


    
class PortsCiscoSG( PortsCiscoIos ):

    int_status_fields = ( 'port', 'media', 'duplex', 'speed', 'autoneg', None, 'status', None, None )

    def _int_status( self, filter=None, ignore_case=True ):

        ports = {}

        # get general info
        for i in self.prompt.tell( 'show int status' ):
            a = i.split()
            logging.debug("  > %s (%s)" % (i,len(a)))
            d = {}
            if len(a) == len( self.int_status_fields ):
                for n in xrange(0,len(self.int_status_fields)):
                    v = a[n]
                    if v == '--':
                        v = None
                    if self.int_status_fields[n]:
                        d[self.int_status_fields[n]] = v
                
                # defaults
                logging.debug("    >: %s" % (d,))
                d['port'] = truncate_physical_port( d['port'] )
                ports[d['port']] = d
                
        # get alias
        for i in self.prompt.tell( 'show int desc' ):
            a = i.split()
            if len(a) and a[0] in ports:
                logging.debug("  >: %s -> %s" % (i,a))
                v = None
                if len(a) > 1:
                    v = a[1]
                ports[a[0]]['alias'] = v

        # logging.debug("PORTS: %s" % (ports,))

        for k,p in ports.iteritems():
            if search( r'\D+\d+', k ):
                logging.debug("  >: final: %s %s" % (k,p))
                # normalise
                if p['autoneg'] == None or p['autoneg'] == 'Enabled':
                    p['autoneg'] = True
                else:
                    p['autoneg'] = False
                if 'status' in p:
                    p['status'] = p['status'].lower()
                if not 'type' in p:
                    p['type'] = 'access'
                if not 'vlan' in p:
                    p['vlan'] = 1
                if not 'speed' in p or p['speed'] == None:
                    p['speed'] = 'auto'
                p['speed'] = p['speed'].lower()
                if not 'duplex' in p or p['duplex'] == None:
                    p['duplex'] = 'auto'
                p['duplex'] = p['duplex'].lower()
                if not 'alias' in p:
                    p['alias'] = None
                yield p

        return 
        
    # # overwrite as show run doesn't always give all ports
    # # TODO: vlans not right...
    # def _get( self, port=None ):
    #     ports = {}
    #     for i in self._int_status( filter=port ):
    #         ports[i['port']] = i
    #     
    #     system_vlans = {}
    #     for k,v in self.parent.layer2.vlan:
    #         system_vlans[k] = v
    #     logging.debug("vlans: %s" % system_vlans)
    #     
    #     if not port in ports:
    #         port = None
    #     # add suppliementary info from run        
    #     for j in self._int_run( port=port ):
    #         try:
    #             ports[j['port']] = self._merge_port_info( ports[j['port']], j, system_vlans )
    #         except Exception, e :
    #             logging.error("Error: %s" % (e,))
    #             pass
    # 
    #     for k,p in ports.iteritems():
    #         # logging.error("P: %s %s" % (k,p))
    #         try:
    #             q = self._merge_port_info( p, {}, system_vlans )
    #             yield k, q
    #         except Exception,e:
    #             logging.error("E: %s %s" % (e,p))
    #     return





class ConfigCiscoSG( Config ):
    def get_running_config(self):
        c = [ l.rstrip() for l in self.prompt.tell( 'show running-config', cursor=self.prompt.cursor('mode','enable') ) ][0:-1]
        if len(c):
            c.insert(0,'')
            return c
        return None
    def commit(self):
        pass

class SystemCiscoSG( System ):
    config = ConfigCiscoSG

class VlanCiscoSG( Vlan ):
    def _get( self ):
        tries = 0
        max_tries = 4
        n = 0
        while n == 0 and tries < max_tries:
            tries = tries + 1
            for d in self.prompt.tell_and_match( 
                    'show vlan', 
                    r'^\s*(?P<number>\d+)\s+(?P<name>\S+)\s+' ):
                n = n + 1
                d['number'] = int(d['number'])
                yield d['number'], d
        return
        
class MacAddressCiscoSG( MacAddress ):
    def _get( self ):
        for d in self.prompt.tell_and_match( 
            'show mac address-table',
            r'\s+(?P<vlan>\d+)\s+(?P<mac_address>[\w:]+)\s+(?P<interface>\w+)\s+(?P<type>\w+)'
        ):
            d['mac_address'] = sub( "(.{4})", "\\1.", d['mac_address'].replace(':',''), 0, DOTALL )[0:-1]
            d['vlan'] = int(d['vlan'])
            yield d['mac_address'], d
        return

class Layer2CiscoSG( Layer2 ):
    vlan = VlanCiscoSG
    # spanningtree = SpanningTreeCiscoIosSwitch
    mac_address = MacAddressCiscoSG

class CiscoSg( Device ):
    prompt = PromptCiscoIos
    system = SystemCiscoSG
    layer2 = Layer2CiscoSG
    ports = PortsCiscoSG
        
    interact = {
        # 'enable_password': 'Password: ',
        'pager'     : 'More: \<space\>,  Quit: q or CTRL+Z, One line: \<return\> ',
        # 'question'  : "\[.*\](\:|\?) $",
        # 'yes_no'    : "\? \[yes\/no\]\: $",
        # 'config_modified': 'System configuration has been modified\. Save\? \[yes\/no\]:', 
        # 'reload':   'Proceed with reload\? \[confirm\]',
    }
    
    def validate( self ):
        for o in self.prompt.tell( 'show system' ):
            if match( r'^\s*System Description: .*port Gigabit Managed Switch', o ):
                # set up no paging
                self.prompt.ask( 'terminal datadump' )
                return True
        raise IncompatibleDeviceException, 'not a Cisco SG Switch'
