from re import compile, match, search, sub, DOTALL
import logging

from netconfig.drivers.cisco_ios import RoutesCisco, PortsCiscoIos, FRUCiscoIos, SystemCiscoIos, ArpsCisco, VlanCiscoIos, PromptCiscoIos, Layer2CiscoIos, PortChannelsCiscoIos, ConfigCiscoIos
from netconfig.drivers import Layer3, Layer2, Device, ComponentList, Module, Transceiver, IncompatibleDeviceException, Stats, Rfc2863

from slac_utils.net import truncate_physical_port



#######################################################################
# Cisco Nexus
#######################################################################

class RoutesCiscoNexus( RoutesCisco ):
    matches = {
        'h': r'^(?P<prefix>\d+\.\d+\.\d+\.\d+)/(?P<prefix_len>\d+), ubest/mbest: ',
        'c': r'^\s+(\*)?via (?P<next_hop>\d+\.\d+\.\d+\.\d+), (?P<interface>\w+), \[(?P<metric>.*)\], (?P<uptime>(\w|\d|\:)+), (?P<type>.*)$'
    }
    command = 'show ip route'

    def _get(self):
        for k,v in super( RoutesCiscoNexus, self )._get():
            if 'type' in v:
                if v['type'] in ( 'direct', 'local' ):
                    # logging.error("TYPE: %s" % (v['type'],) )
                    v['local'] = True
            # logging.error("!!! %s" % (v,))
            yield k,v
        return

class Layer3CiscoNexus( Layer3 ):
    routes = RoutesCiscoNexus
    arps = ArpsCisco
    
class PortsCiscoNexus( PortsCiscoIos ):

    int_status_fields = ( 'port', 'alias', 'status', 'vlan', 'duplex', 'speed', None )
    int_status_port_types_ignore = ( 'Exte', )
    int_status_exclude = "Port          Name               Status    Vlan      Duplex  Speed   Type"

    conf_sync = None
    current_port = None

    def enter_port_mode( self, port ):
        """ deal with conf sync if present """
        # logging.debug("entering port mode from current %s" % (self.prompt.current_cursor,))
        # determine what kinda prompt we need to be in
        cursors = []
        if self.conf_sync:

            # switch to top level mode to change a port
            if not self.prompt.current_cursor in [ self.prompt.cursor('mode', 'config-sync'), self.prompt.cursor('mode', 'config-sync-if'), self.prompt.cursor('mode','config-if'), self.prompt.cursor('mode', 'config') ]:
                if not self.prompt.request( 'configure sync', cursor=self.prompt.cursor('mode','enable') ):
                    raise Exception, 'could not enter conf sync mode'
                if not self.prompt.request( 'switch-profile %s' % self.conf_sync ):
                    raise Exception, 'could not enter switch profile %s' % self.conf_sync

            cursors = [ self.prompt.cursor('mode','config-sync'),  self.prompt.cursor('mode','config-sync-if') ]

        else:
            cursors = [ self.prompt.cursor('mode','config-sync'), self.prompt.cursor('mode','config-sync-if'), self.prompt.cursor('mode','config'), self.prompt.cursor('mode','config-if') ]

        if self.current_port == None or not self.current_port == str(port):
            if self.prompt.ask( 'interface ' + str(port), cursor=cursors, output_wait=1.0 ):
                if self.prompt.current_cursor in [ self.prompt.cursor('mode', 'config-if'), self.prompt.cursor('mode','config-sync-if') ]:
                    self.current_port = str(port)
                    return True
        elif self.current_port == str(port):
            self.current_port = str(port)
            return True
        self.current_port = None
        raise Exception, 'could not enter port config mode'


    def exit_port_mode( self, port ):
        if self.conf_sync and self.enter_port_mode( port ):
            return self.prompt.ask( 'commit', timeout=self.prompt.timeouts['long'])

class PortChannelsNexus( PortChannelsCiscoIos ):
    show_cmd = 'show port-channel summary'
    regexes = [
        r'^\s*(?P<group>\d+)\s+(?P<port_channel>\S+)\((?P<port_channel_state>\S+)\)\s+(?P<type>\S+)\s+(?P<protocol>\S+)\s+(?P<members>.*)$',
        r'^\s+(?P<members>\D\S+)$'
    ]
    

class TransceiverCiscoNexus( Transceiver ):
    regexes = [
        r'^(?P<port>Ethernet.*)',
        r'\s{2,}type is (?P<type>.*)$', # don't pick up line "tranceiver type is X2 Medium"
        r'Temperature\s+(?P<temperature>\S+)',
        r'Tx Power\s+(?P<tx>\S+)',
        r'Rx Power\s+(?P<rx>\S+)',
        r'Voltage\s+(?P<voltage>\S+)',
        r'Current\s+(?P<current>\S+)',
    ]
    def _get(self, **kwargs ):
        for d in self.prompt.tell_and_match_block( 'show int transceiver details', self.regexes ):
            logging.debug("found %s" % (d,))
            if 'port' in d and 'rx' in d:
                d['port'] = truncate_physical_port( d['port'])
                yield d['port'], d
        return

class ModuleCiscoNexus( Module ):
    regexes = [ '^(?P<slot>\d+)\s+(?P<ports>\d+)\s+(?P<description>.*)\s+(?P<model>N\d.\-\S+)\s+(?P<status>\S+)\s*', '^(?P<slot>\d+)\s+(?P<mac_ranges>\S+ to \S+)\s+(?P<hardware_version>\S+)\s+(?P<firmware_version>\S+)\s*$', '^(?P<slot>\d+)\s+(?P<software_version>\S+)\s+(?P<hardware_version>\S+)\s*$', '^(?P<slot>\d+)\s+(?P<diag_status>\S+)\s*$' ]
    
    def _get( self, *args, **kwargs ):
        for d in self.prompt.tell_and_match_by_index( 
                'show module', 
                'slot',
                self.regexes,
                end='^Xbar', # stop on xbar stuff
                timeout=self.prompt.timeouts['medium'] ):
            yield d['slot'], d
            
        # xbar
        for d in self.prompt.tell_and_match_by_index( 
                'show module | beg Xbar', 
                'slot',
                self.regexes,
                timeout=self.prompt.timeouts['medium'] ):
            # we use prefix '1' as it's what the relative position of the snmp table returns
            d['slot'] = '1' + str(d['slot'])
            yield d['slot'], d
        
        # fex
        for d in self.prompt.tell_and_match(
            'show fex',
            '^(?P<slot>\d+)\s+(?P<description>.*)\s+(?P<status>\S+)\s+(?P<model>\S+)\s+(?P<serial>\S+)\s*$'
        ):
            yield d['slot'],d
        
        return

class FRUCiscoNexus( FRUCiscoIos ):
    transceiver = TransceiverCiscoNexus
    module = ModuleCiscoNexus
    

class ConfigCiscoNexus( ConfigCiscoIos ):
    header_skip_lines = 2

class SystemCiscoNexus( SystemCiscoIos ):
    fru = FRUCiscoNexus
    config = ConfigCiscoNexus



class Rfc2863CiscoNexus( Rfc2863 ):
    port_regexes = [
        r'^(?P<port>\S+) is (?P<oper_status>\S+)( \(Administratively (?P<admin_status>\S+)\))?',
        r'^\s+Description: (?P<alias>.*)\s*$',
        r'^\s+MTU (?P<mtu>\d+) bytes, BW (?P<speed>\d+) ',
        r'^\s+(?P<duplex>\S+)-duplex, (?P<speed_neg>\S+)-speed',
        r'^\s+Input flow-control is (?P<input_flow_control>\S+), output flow-control is (?P<output_flow_control>\S+)',
        r'^\s+(?P<interface_resets>\d+) interface resets',
        
        #4315335291 unicast packets  0 multicast packets  4 broadcast packets

        #    20367999 input packets  14967249269 bytes
        r'\s+(?P<input_pkts>\d+) input packets\s* (?P<input_bytes>\d+) bytes',
        # 0 jumbo packets  0 storm suppression bytes
        r'\s+(?P<input_jumbo>\d+) jumbo packets\s* (?P<storm_suppression_bytes>\d+) storm suppression bytes',

        # 0 runts  0 giants  0 CRC  0 no buffer
        r'\s+(?P<input_runts>\d+) runts\s* (?P<input_giants>\d+) giants\s* (?P<input_crc>\d+) CRC\s* (?P<input_no_buffer>\d+) no buffer',
        # 0 input error  0 short frame  0 overrun   0 underrun  0 ignored
        r'\s+(?P<input_errors>\d+) input error\s* (?P<input_frame_error>\d+) short frame\s* (?P<input_overrun>\d+) overrun\s* (?P<input_underrun>\d+) underrun\s* (?P<input_ignored>\d+) ignored',

        # 0 watchdog  0 bad etype drop  0 bad proto drop  0 if down drop
        r'\s+(?P<input_watchdog>\d+) watchdog\s* (?P<input_bad_etype>\d+) bad etype drop\s* (?P<input_bad_proto>\d+) bad proto drop\s* (?P<input_if_down>\d+) if down drop',
        
        # 0 input with dribble  0 input discard
        r'\s+(?P<input_dribble>\d+) input with dribble\s* (?P<input_discard>\d+) input discard',
        r'\s+(?P<pause_input>\d+) Tx pause',
        
        # 36108200 output packets  20595729265 bytes
        r'\s+(?P<output_pkts>\d+) output packets\s* (?P<output_bytes>\d+) bytes',
        # 0 jumbo packets
        r'\s+(?P<output_jumbo>\d+) jumbo packets$',
        # 0 output error  0 collision  0 deferred  0 late collision
        r'\s+(?P<output_errors>\d+) output error\s* (?P<output_collisions>\d+) collision\s* (?P<output_deferred>\d+) deferred\s* (?P<output_late_collision>\d+) late collision',
        # 0 lost carrier  0 no carrier  0 babble 0 output discard
        r'\s+(?P<lost_carrier>\d+) lost carrier\s* (?P<no_carrier>\d+) no carrier\s* (?P<output_babbles>\d+) babble\s* (?P<output_discards>\d+) output discard',
        # 0 Tx pause
        r'\s+(?P<pause_output>\d+) Tx pause',
        
        # TODO:
        #     4315335291 unicast packets  0 multicast packets  4 broadcast packets
        # appears twice, first for RX, then TX... how to parse?

    ]
    
    def _get( self, *args, **kwargs ):
        for b in self.prompt.tell_and_get_block( 'show int', output_wait=5, timeout=3*self.prompt.timeouts['long'] ):
            logging.debug("="*80)
            d = self.prompt.parse_block( b, self.port_regexes )
            # get the stupid same lines for rx and tx packets
            direction = 'in'
            for l in b:
                #4315335291 unicast packets  0 multicast packets  4 broadcast packets
                if match( r'^\s+TX', l ):
                    logging.debug("switching to output")
                    direction = 'out'
                m = match( r'^\s+(?P<ucast_pkt>\d+) unicast packets\s* (?P<mcast_pkt>\d+) multicast packets\s* (?P<bcasts>\d+) broadcast packets', l )
                if m:
                    _d = m.groupdict()
                    for k,v in _d.iteritems():
                        this_direction = direction
                        if not k == 'bcasts':
                            this_direction = 'l3_%s' % (direction,)
                        else:
                            this_direction = '%sput' % (direction,)
                        this_k = '%s_%s' % ( this_direction, k )
                        d[this_k] = v
                        logging.debug("got %s = %s" % (this_k, v))
            if 'port' in d and d['port']:
                p = truncate_physical_port( d['port'] )
                d['port'] = p
                if d['admin_status'] == None:
                    d['admin_status'] = d['oper_status']
                yield p, d

class StatsCiscoNexus( Stats ):
    rfc2863 = Rfc2863CiscoNexus

class CiscoNexus( Device ):

    prompt = PromptCiscoIos
    system = SystemCiscoNexus
    stats = StatsCiscoNexus
    ports = PortsCiscoNexus
    portchannels = PortChannelsNexus
    layer2 = Layer2CiscoIos
    layer3 = Layer3CiscoNexus

    def validate(self):
        # deactivate paging
        for l in self.prompt.tell('show version | inc Nexus'):
            if match( 'Cisco Nexus Operating System', l):
                # let's check out the switch profiles
                try:
                    for d in self.prompt.tell_and_match('show switch-profile', [ r'^(?P<profile_name>\w+)\s+(?P<rev_num>\d+)$']):
                        # logging.error("REV: %s" % d )
                        self.ports.conf_sync = d['profile_name']
                except:
                    pass
                
                # NB: required as paging doens't work very well
                return self.prompt.terminal_buffer(size=0)
        return False
    
