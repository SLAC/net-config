from netconfig.drivers import Prompt, Port, Ports, Config, Model, Firmware, Layer1, Vlan, SpanningTree, MacAddress, Layer2, Routes, Arps, Layer3, Transceiver, FRU, Password, Users, System, Device, PortChannels, Module, Stats, Rfc2863

from slac_utils.net import prefixlen_to_netmask, truncate_physical_port, netmask_to_prefixlen, to_ip

from re import compile, match, search, sub, DOTALL, finditer

from netconfig.drivers import DeviceException, IncompatibleDeviceException

from os import path
import logging

#######################################################################
# Cisco IOS Switch
#######################################################################

class PromptCiscoIos( Prompt ):

    mode = {
        'exec':     "\>",
        'enable':   "\#",
        'config':   '\(config\)#',
        'config-if': "\(config-(sub)?if\)#",
        'config-vlan':   '\((config-)?vlan\)#',
        'config-line': '\(config-line\)\#',
        'config-sync-pre':   '\(config-sync\)#',
        'config-sync':   '\(config-sync-sp\)#',
        'config-sync-if': "\(config-sync-sp-if\)#",
    }

    interact = {
        'enable_password': 'Password: ',
        'pager'     : ' --More-- $',  # pager (press space for more)
        'question'  : "\[.*\](\:|\?) $",
        #'yes_no'    : "(\? \[yes\/no\]\:|\(y/n\)\?\[\w\]) $",
        'yes_no'    : "(\? \[yes\/no\]\:|\(y/n\)(\?\[\w\])?) $",
        'config_modified': 'System configuration has been modified\. Save\? \[yes\/no\]:', 
        'reload':   'Proceed with reload\? \[confirm\]',
        'confirm':  ' \[confirm?\]',
        'default_answer': " considered\):",
    }
    
    error = {
        'command': "Invalid command at",
        'input': "Invalid input detected at",
        'incomplete': "% Incomplete command",
        'denied': '% Access denied',
        'authorization': '(Error: AAA authorization failed|cmd not authorized: this incident has been reported|Command authorization failed)',
        'rejected: ': 'Command rejected:.*$'
    }

    wizard_responses = {
        r'Would you like to enter the initial configuration dialog\? \[yes/no\]:':   'no',
    }

    def terminal_buffer( self, size=0 ):
        return self.ask('terminal length %s' % (size,))

    def mode_exec( self ):
        n = 3
        while n > 0:
            if self.current_cursor == self.cursor( 'mode', 'exec' ):
                return True
            elif self.current_cursor == self.cursor( 'mode', 'enable' ):
                self.ask('disable')
            elif self.current_cursor in ( self.cursor('mode', 'config'), self.cursor('mode','config-if'), self.cursor('mode','config-vlan') ):
                # ios switches can stall the prompt sometimes after runnign end
                self.ask('end', timeout=self.prompt.timeouts['long'] )
            else:
                logging.debug('  trying to move to %s from current prompt %s' % ( self.cursor('mode','exec'), self.current_cursor) )
            n = n - 1
        logging.debug("could not change from cursor %s to mode exec" % (self.current_cursor) )
        return False
    
    def mode_enable( self ):
        n = 4
        logging.debug('attempting to get into enable mode')
        while n > 0:
            logging.debug('  current prompt ' + str(self.current_cursor))
            if self.current_cursor == self.cursor( 'mode', 'exec' ):
                self.new_line()
                res = self.ask( 'enable', preempt=False )
            elif self.current_cursor == self.cursor( 'interact', 'enable_password' ):
                logging.debug("    sending enable password")
                res = self.ask( self.connector.enable_password, preempt=False, suppress_command_output=True )
            elif self.current_cursor in ( self.cursor('mode','config'), self.cursor('mode','config-if' ), self.cursor('mode','config-vlan') ):
                res = self.ask( 'end' )
            elif self.current_cursor == self.cursor( 'mode', 'enable' ):
                return True
            elif self.current_cursor == self.cursor( 'error', 'denied' ):
                logging.error("access denied")
                return False
            else:
                logging.debug('trying to move to ' + self.cursor('mode','enable') + ' from current prompt ' + self.current_cursor)
                self.ask('exit')

            n = n - 1
        logging.warn("could not change from cursor " + str(self.current_cursor) + ' to mode enable')
        return False
        
    def mode_config( self ):
        # logging.warn("entering mode config")
        res = self.request( 'configure terminal', cursor=self.cursor('mode','enable') )
        if self.current_cursor == self.cursor('mode','config'):
            return True
        return False
        
class PortsCiscoIos( Ports ):
    
    ports = {}
    
    int_status_fields = ( 'port', 'alias', 'status', 'vlan', 'duplex', 'speed', None )
    int_status_port_types_ignore = ( 'SFP', 'Transceiver', 'Present', 'Connector', 'X2' )
    int_status_exclude = [ 'Port      Name               Status', '------- ------------------ ------------ -------- ------ ------- ----' ]

    # globals
    lldp = None
    cdp = None

    show_run_threshold = 8

    show_run_regexes = [
        r'^\s*interface (?P<port>.*)\s*$',
        r'^\s+description (?P<alias>.*)\s*$',
        r'^\s+switchport access vlan (?P<access_vlan>\d+)\s*$',
        r'^\s+switchport trunk allowed vlan add (?P<trunked_vlans_additional>[\d\,\-]+)\s*$', # TODO: add across multi
        r'^\s+switchport trunk allowed vlan (?P<trunked_vlans>[\d\,\-]+)\s*$', # 
        r'^\s+switchport trunk native vlan (?P<native_vlan>\d+)$',
        # TODO: deal with notag on native vlan?
        # r'^\s+no switchport trunk native vlan (?P<native_vlan>tag)$',
        r'^\s+switchport (?P<type>private-vlan host)\-association\s+(?P<private_vlan_one>\d+)\s(?P<private_vlan_two>\d+)\s*$',
        r'^\s+switchport mode (?P<type>.*)\s*$',
        r'^\s+switchport (?P<portnoneg>nonegotiate)',
        r'^\s+switchport voice vlan (?P<voice_vlan>\d+)$',
        r'^\s+duplex (?P<duplex>.*)$',
        r'^\s+speed (?P<speed>.*)$',
        r'^\s+(?P<shutdown>shutdown)',
        r'^\s+(?P<port_security>switchport port-security)\s*$',
        r'^\s+switchport port-security maximum (?P<port_security_max>\d+)',
        r'^\s+switchport port-security aging time (?P<port_security_aging_time>\d+)',
        r'^\s+switchport port-security violation (?P<port_security_violation>\w+)',
        r'^\s+switchport port-security aging type (?P<port_security_aging_type>\w+)',
        r'^\s+logging event (?P<logging_event_link_status>link-status)',
        r'^\s+logging event (?P<logging_event_trunk_status>trunk-status)',
        r'^\s+logging event (?P<logging_event_bundle_status>bundle-status)',
        # TODO: check against global?
        r'^\s+(?P<cdp>no cdp enable)',
        # TODO: lldp? check against global
        r'^\s+(?P<no_lldp_transmit>no lldp transmit)',
        r'^\s+(?P<no_lldp_receive>no lldp receive)',
        r'^\s+spanning-tree (?P<noportfast>portfast) disable',
        r'^\s+spanning-tree (?P<portfast>portfast)$',
        r'^\s+spanning-tree (?P<nobpduguard>bpduguard) disable',
        # TODO: 'spanning-tree portfast' on port
        r'^\s+storm-control broadcast level (?P<storm_control_broadcast>\S+)$',
        r'^\s+storm-control multicast level (?P<storm_control_multicast>\S+)$',
        r'^\s+ip dhcp snooping (?P<dhcp_snooping>\S+)\s*$',
    ]


    def initiate(self):
        # set global port values like cdp and lldp
        self.lldp = True if self.prompt.ask('show lldp', fail_okay=True ) else False
        self.cdp = None
        try:
            self.cdp = True if self.prompt.ask('show cdp', fail_okay=False ) else False
        except:
            # stupid nexus's
            try:
                self.cdp = True if self.prompt.ask('show cdp global') else False
            except:
                pass
        self.prompt.ask('')
        # logging.debug("LLDP: %s" % self.lldp)

    def _int_run( self, port=None ):
        
        # filter if necessary
        search_cmd = 'show running-config'
        if not port == None:
            if isinstance( port, dict ):
                logging.warn("DONT RUN WITH THIS AS ARG: %s" % (port,))
                search_cmd = '%s interface %s' % ( search_cmd, port['port'] )
            else:
                search_cmd = '%s interface %s' % ( search_cmd, port )

        try:

            for d in self.prompt.tell_and_match_block( search_cmd,  self.show_run_regexes, timeout=self.prompt.timeouts['long'] ):

                d['portnoneg'] = True if 'portnoneg' in d else False
                
                if 'type' in d:
                    d['type'] = d['type'].lower()
                
                # vlans
                if 'type' in d:
                    if d['type'] == 'access' \
                        and 'access_vlan' in d:
                        d['vlan'] = [ d['access_vlan'] ]
                        del d['access_vlan']
                    elif d['type'] == 'trunk':
                        if 'trunked_vlans' in d:
                            d['vlan'] = []
                            for i in d['trunked_vlans'].split(','):
                                g = match( r'^(?P<start>\d+)\-(?P<end>\d+)$', i )
                                if g:
                                    s,e = g.group('start','end')
                                    for n in xrange( int(s), int(e)+1 ):
                                        # vlans['trunk'][str(n)] = True
                                        d['vlan'].append( str(n) )
                                else:
                                    # vlans['trunk'][i] = True
                                    d['vlan'].append( str(i) )
                            del d['trunked_vlans']
                        if 'trunked_vlans_additional' in d:
                            for i in d['trunked_vlans_additional'].split(','):
                                g = match( r'^(?P<start>\d+)\-(?P<end>\d+)$', i )
                                if g:
                                    s,e = g.group('start','end')
                                    for n in xrange( int(s), int(e)+1 ):
                                        # vlans['trunk'][str(n)] = True
                                        d['vlan'].append( str(n) )
                                else:
                                    # vlans['trunk'][i] = True
                                    d['vlan'].append( str(i) )     
                            del d['trunked_vlans_additional']         
                        # if no native-vlan, assume 1
                        if not 'native_vlan'  in d:
                            d['native_vlan'] = 1         
                    elif d['type'] == 'private-vlan host' \
                        and 'private_vlan_one' in d and 'private_vlan_two' in d:
                        # logging.debug(" private vlan! %s %s " % (d['private_vlan_one'], d['private_vlan_two']))
                        # d['type'] = 'private-vlan host'
                        d['vlan'] = [ d['private_vlan_one'], d['private_vlan_two'] ]
                        del d['private_vlan_one']
                        del d['private_vlan_two']         
                    if d['type'] in ( 'fex-fabric', 'routed' ):
                        # clear trunked_vlans
                        del d['trunked_vlans']
                
                if 'shutdown' in d:
                    d['state'] = False
                    del d['shutdown']
                    
                if 'speed' in d:
                    # if not d['speed'] == 'nonegotiate':
                    if d['speed'].startswith('auto'):
                        s = d['speed'].replace( 'auto ', '')
                        d['speed'] = s.replace(' ', ',')
                if 'autoneg' in d:
                    if d['autoneg'] == None:
                        del d['autoneg']
                    else:
                        d['autoneg'] = True
                        
                # TOOD: globals?
                d['cdp'] = False if 'cdp' in d else self.cdp
                # lldp
                d['lldp'] = {}
                for i in ( 'no_lldp_transmit', 'no_lldp_receive' ):
                    a,b,c = i.split('_')
                    d[b][c] = False if i in d else self.lldp
                    if i in d:
                        del d[i]
                
                # spanningtree stuff: TODO: globals
                if 'portfast' in d:
                    d['portfast'] = True
                else:
                    d['portfast'] = False if 'noportfast' in d else True
                if 'noportfast' in d:
                    del d['noportfast'] 
                # bdpuguard
                d['bpduguard'] = False if 'nobpduguard' in d else True
                if 'nobpduguard' in d:
                    del d['nobpduguard']
                
                # voice stuff
                d['voice_vlan'] = int(d['voice_vlan']) if 'voice_vlan' in d else False
                
                # alias
                if not 'alias' in d:
                    d['alias'] = ''
                
                d['logging'] = {}
                for i in ( 'logging_event_bundle_status', 'logging_event_trunk_status', 'logging_event_link_status' ):
                    j = i.replace( 'logging_event_', '' ).replace('_','-')
                    if i in d:
                        d['logging'][j] = True
                        del d[i]
                    else:
                        d['logging'][j] = False
                    # 3550's don't report link-status... what to do?
                
                d['security'] = {}
                for i in ( 'port_security_max', 'port_security_aging_time', 'port_security_violation', 'port_security_aging_type' ):
                    if i in d:
                        j = i.replace('port_security_','').replace('_','-')
                        d['security'][j] = d[i]
                        del d[i]
                if not 'port_security' in d:
                    d['security'] = False
                if d['security']:
                    # set default values
                    if not 'max' in d['security'] and not 'port_security_max' in d:
                        d['security']['max'] = 1
                
                d['storm-control'] = {}
                for i in ( 'storm_control_multicast', 'storm_control_broadcast', 'storm_control_unicast' ):
                    j = i.replace('storm_control_','')
                    if i in d:
                        d['storm-control'][j] = d[i]
                        del d[i]
                    else:
                        d['storm-control'][j] = False
                
                # yield!
                if 'port' in d:
                    d['port'] = truncate_physical_port( d['port'] )
                    logging.debug("  >: show run output %s" % (d,))
                    yield d

        except Exception,e:
            logging.error("ERR: (%s) %s" % (type(e),e))

        return


    
    def _int_status_validate( self, info, k, v ):
        if k == 'vlan':
            logging.debug("      validating %s as %s: %s" % (k,v,info) )
            if v == 'trunk':
                info['vlan'] = []
                info['type'] = 'trunk'
            elif v == 'routed':
                info['vlan'] = []
                info['type'] = 'routed'
            elif v == 'unassigned':
                info['vlan'] = []
                info['type'] = 'unassigned'
            else:
                a = v.split(',')
                # logging.debug('      vlans: %s' % (a,))
                info['vlan'] = [ int(v) for v in a ]
                info['type'] = 'access'
        else:
            info[k] = v
        # logging.debug("       set to " + str(info))
        return info

    def _int_status( self, filter=None, ignore_case=True ):
        """ parse ports using show int status """
        this_f = [ f for f in self.int_status_fields ]
        n = 0
        
        # format the query line for the ports
        search_cmd = 'show int status '
        if not filter == None:
            if ignore_case:
                # do some regexp to avoid case sensitivity
                regexp = ''
                for s in filter:
                    bit = s
                    if s.isalpha():
                        bit = '[' + s.lower() + s.upper() + ']'
                    regexp = regexp + bit
                filter = regexp
            search_cmd = search_cmd + ' | inc ' + str(filter) 

        # run and parse
        for l in self.prompt.tell( search_cmd, cursor=[ self.prompt.cursor('mode', 'enable'), self.prompt.cursor('mode','exec')], timeout=self.prompt.timeouts['medium'] ):
            # logging.debug(" =: '%s'" % self.int_status_exclude )
            # logging.debug(" >: %s" % (l) )
            ignore = False
            if not self.int_status_exclude == None:
                excludes = self.int_status_exclude
                if not isinstance( self.int_status_exclude, list ):
                    excludes = [ self.int_status_exclude ]
                for e in excludes:
                    if match( sub(r'\s+','',e), sub(r'\s+','',l) ):
                        ignore = True
            if ignore:
                logging.debug("  skipping... %s" % (l,))
                continue;

            # use assume that 'alias' may have spaces, so splitting just by spaces will not work
            # so we scan through the arrays, and if we see an alias, we then work backwards
            info = Port()
            d = compile("\s{1,}").split(l.strip())
            # logging.debug("  d: " + str(len(d)))
            if len(d) < 2 or match(r'^\s+$',l):
                continue
            # logging.debug("  items " + str(len(d)) + ": " + str(d))
        
            # copy fields as we need to use these as index
            f = [ i for i in this_f ]

            # go through datalist and compare to field list
            for n in xrange(0,len(this_f)):
                i = this_f[n]
                # logging.debug("  n: " + str(n) + ", i: " + str(i) )
                # alias field may have spaces, so we always consider that one last
                if i == 'alias':
                    # logging.debug("   found alias")
                    break
                a = f.pop(0)
                b = d.pop(0)
                if not a == None or not a == 'None':
                    # logging.debug("    parsed " + str(a) + ' as ' + str(b))
                    # info[a] = b
                    info = self._int_status_validate( info, a, b )
            
            # reverse now
            # if we have a port that does not have a 'type', then ignore from list
            if b.startswith( 'Po' ) and not l.endswith('--'): # '--' = nexus
                logging.debug("  found port without a type")
                d.append('')
                
            for n in xrange(len(f), 0, -1):
                i = this_f[n]
                # logging.debug("   n: %s\ti: %s" %(n,i) )
                if i == 'alias':
                    break
                a = f.pop(-1)
                b = d.pop(-1)

                # deal with stupid no worded port type
                if i == None and ( b in ( '10G', 'auto', '100', '10' ) or b.startswith( 'a-' ) ):
                    d.append( b )

                # logging.debug("    a: " + str(a) + ", b: " + str(b) )
                # deal with stupid two worded port type
                if b in self.int_status_port_types_ignore:
                    b = d.pop(-1)
                if not a == None or not a == 'None':
                    # logging.debug("    parsing %s as %s" %(a,b))
                    # info[a] = b
                    info = self._int_status_validate( info, a, b )
            
            logging.debug("    >: " + str(info))
            
            # add placehoders for other variables
            if not 'autoneg' in info:
                info['autoneg'] = True
            if not 'speed' in self.int_status_fields:
                info['speed'] = 'auto'
            if not 'duplex' in self.int_status_fields:
                info['duplex'] = 'auto'
            if not 'type' in info:
                info['type'] = None
            if not 'vlan' in info:
                info['vlan'] = 1
                info['native_vlan'] = 1

            # add alias
            for i in f:
                # logging.debug("  cleaning remaining items: " + str(i) + " (f="+str(len(f))+",d="+str(len(d))+") from " + str(d))
                if len(d) == 0: info[i] = None
                elif len(f) == 1 and i == 'alias': info['alias'] = ' '.join(d)
                else: 
                    logging.debug("    i=%s, d=%s" % (i,d))
                    info[i] = d.pop(-1)
                # logging.debug("  cleaned")
            logging.debug("  found port (int status): %s" %(info,))
            yield info
        return
        
    def _normalise(self, info):
        """
        iterates through the keys in dict info, and cleans up the info about the interface 
        valid keys for info dict are:
        speed        duplex        autoneg        state        vlan        alias
        """
        # logging.debug('normalising ' + str(info))
        for k,v in info.iteritems():
            if not v == None and type(v) == str:
                info[k] = info[k].strip()
        
        if 'speed' in info and 'duplex' in info:
            # logging.error("SPEED/DUPLEX %s %s" % (info['speed'],info['duplex']))
            # determine autoneg of port
            if match( '(^a-|^A-)', info['speed'] ) \
                or match( '(^a-|^A-)', info['duplex'] ):
                if not 'autoneg' in info:
                    info['autoneg'] = True
                for i in [ 'speed', 'duplex' ]:
                    info[i] = info[i].replace( 'a-', '' )
                    # logging.debug( '  found true value of ' + str(i) + ' as ' + info[i] )
            else:
                if not 'autoneg' in info:
                    info['autoneg'] = False
        elif not 'autoneg' in info:
            info['autoneg'] = False

        # deal with show int desc where we have a protocol up/down
        if 'protocol' in info and 'state' in info:
            # logging.error("PROTOCOL: " + str(info['protocol']))
            if info['state'] == 'admin down':
                info['state'] = False
            else:
                info['state'] = True
            if info['protocol'] == 'up': info['protocol'] = True
            elif info['protocol'] == 'down': info['protocol'] = False
            else: info['protocol'] = None
            
            # logging.debug("  found true value of state as " + str(info['state']))

        # state
        if 'state' in info:
            if info['state'] == 'up':
                info['state'] = True
            elif info['state'] == 'down':
                info['state'] == False
            else:
                info['state'] = None

        if 'status' in info:
            if info['status'] in ( 'connected', 'connect', 'up' ):
                info['state'] = True
                info['protocol'] = True
            elif info['status'] in ( 'notconnect', 'notconnec' ):
                info['state'] = True
                info['protocol'] = False
            elif info['status'] in ( 'disabled', 'disable', 'down' ):
                info['state'] = False
                info['protocol'] = False
            elif info['status'] == 'err-disabled':
                info['state'] = 'err-disabled'
                info['protocol'] = False
            elif info['status'] in ( 'sfpAbsent', 'xcvrInval', 'sfpInvali', 'adminCfgC', 'xcvrAbsen' ):
                info['state'] = False
                info['protocol'] = False
            elif info['status'] in ( 'monitoring' ):
                info['state'] = 'monitoring'
                info['protocol'] = True
            elif info['status'] in ( 'noOperMem', 'suspndByV', 'suspnd', 'channelDo' ):
                info['state'] = 'suspended'
                info['protocol'] = False

            # BUG?
            # elif info['status'] == 'routed':
            #     info['type'] = 'routed'
                # info['protocol'] = False
            else:
                raise DeviceException, "do not know how to map port state '%s'" % (info['status'])

        # check vlan
        # TODO: check for numbers?
        if 'vlan' in info and info['vlan'] == 'routed':
            info['type'] = info['vlan']
            info['vlan'] = None

        # alias
        if not 'alias' in info:
            info['alias'] == None
        elif info['alias'] == '':
            info['alias'] == None
            
        return info
    
    
    def _match_vlan_name( self, number, vlans ):
        number = int(number)
        if number in vlans:
            return vlans[number]['name']
        else:
            logging.debug("could not determine vlan name for vlan %s from %s " % (number,vlans,))
        return None
    
    def _merge_port_info( self, i, j, vlans ):
        logging.debug("  merging: %s, %s" % (i,j) )
        k = dict( i.items() + j.items() )
        p = Port( self._normalise( k ) )

        # update vlan info
        if 'vlan' in p and not p['vlan'] == None:
            v = []
            # default is for vlan 1
            for k in p['vlan']:
                name = self._match_vlan_name( k, vlans )
                if name:
                    v.append( name )
                else:
                    v.append( str('unknown') )
            p['vlan_name'] = v
        else:
            p['vlan_name'] = None
        
        # native vlan name
        if 'native_vlan' in p and not p['native_vlan'] == None:
            p['native_vlan_name'] = self._match_vlan_name( p['native_vlan'], vlans )
        
        # update voice vlan name
        if 'voice_vlan' in p and p['voice_vlan']:
            p['voice_vlan_name'] = self._match_vlan_name( p['voice_vlan'], vlans )
        
        logging.debug("   merged: " + str(p))
        return p

    
    def _get( self, port=None, **kwargs ):
        ports = []
        # use int status to filter list
        if port == '/':
            port = None
        for i in self._int_status( filter=port ):
            ports.append( i )
        
        # if there is already a match, then use that
        if len(ports) > 0 and not port == None:
            logging.debug("narrowing down exact matching ports")
            found = []
            for p in ports:
                if p['port'].lower() == port.lower():
                    found.append( p )
            if len(found) == 1:
                ports = found

        # vlans
        system_vlans = dict(self.parent.layer2.vlan)
        
        # get extra detail from show run
        run_ports = {}
        run_with = []
        # do show run on all if too many ports
        # logging.error("PORTS LEN: %s (%s)" % (ports,len(ports)))
        if len(ports) > self.show_run_threshold:
            run_with = [ None ]
        else:
            run_with = [ p['port'] for p in ports ]
        for r in run_with:
            # logging.debug("R: (%s) %s" % (type(r),r,))
            for j in self._int_run( port=r ):
                # logging.error("JPORT: %s, %s" % (j['port'], j))
                run_ports[j['port']] = j

        # yield
        for p in ports:
            k = p['port']
            j = {}
            if k in run_ports:
                j = run_ports[k]
            x = self._merge_port_info( p, j, system_vlans )
            yield k, x
        return
        
    def get( self, port=None ):
        if self.lldp == None or self.cdp == None:
            self.initiate()
        logging.debug("getting port " + str(port))
        found = []
        for p,i in self._get( port=port ):
            found.append( i )
        logging.debug("  found ports ("+str(len(found))+"): " + str(found))
        if len( found ) == 0:
            raise Exception, 'no ports found '+ str(port)
        elif len( found ) == 1:
            return found[0]
        else:
            # find exact match
            for i in found:
                if i['port'].lower() == port.lower():
                    logging.debug("  found single match %s" % (i,))
                    return i
        raise Exception, 'not unique ' + str(port) + ", count: " + str(len(found))
        
    def filter(self, string=None, **kwargs):
        if self.lldp == None or self.cdp == None:
            self.initiate()
        for k,p in self._get( port=string ):
            f = self._filter( p, **kwargs )
            if f:
                yield f
        return

    def enter_port_mode( self, port ):
        # logging.warn('entering port mode')
        logging.debug("current %s" % (self.prompt.current_cursor,))
        if self.prompt.ask( 'interface ' + str(port), cursor=[ self.prompt.cursor('mode','config'), self.prompt.cursor('mode','config-if') ], output_wait=1.0 ):
            logging.debug(" %s == %s" % (self.prompt.current_cursor, self.prompt.cursor('mode', 'config-if')))
            if self.prompt.current_cursor == self.prompt.cursor('mode', 'config-if'):
                return True
        logging.debug('nope')
        raise Exception, 'could not enter port config mode'
        
    def stanza( self, port, **kwargs ):
        if not 'port' in port:
            raise SyntaxError, 'need port object'
        if self.prompt.ask( 'interface %s' %(port['port']), cursor=( self.prompt.cursor('mode','config'), self.prompt.cursor('mode','config-if') ) ):
            if self.prompt.current_cursor == self.prompt.cursor('mode', 'config-if'):
                self._enter_prompt = self.prompt.current_cursor
                return self.prompt
        raise Exception, 'could not enter port config mode'
        
    def set_alias( self, port, value, other, enter_port_mode=True ):
        logging.debug("set alias %s to %s" % (port,value) )
        cmd = None
        if value == '' or value == None or value == True or value == False:
            cmd = ' no description'
        else:
            cmd = ' description ' + str(value)
        if not enter_port_mode or self.enter_port_mode( port ):
            return self.prompt.ask( cmd )
        return False
        
    def set_state( self, port, value, other, enter_port_mode=True ):
        logging.debug("set state %s to %s" % (port,value) )
        cmd = None
        if value == True:
            cmd = ' no shut'
        elif value == False:
            cmd = ' shut'
        else:
            raise DeviceException, 'unknown port state %s' % (value)
        return self.prompt.ask( cmd )

    def set_autoneg( self, port, value, other, enter_port_mode=True ):
        if value in ( True, 'auto' ):
            if not enter_port_mode or self.enter_port_mode( port ):
                return self.prompt.ask( ' no duplex' ) and self.prompt.ask( ' no speed' )
        # should probably try to determine that a speed is defined or duplex
        else:
            if 'speed' in other:
                self.set_speed( port, other['speed'], other, enter_port_mode=False )
            else:
                # assume current speed is what is required (only for active ports)
                self.set_speed( port, '100', other, enter_port_mode=False )
            if 'duplex' in other:
                self.set_duplex( port, other['duplex'], other, enter_port_mode=False )
            else:
                self.set_duplex( port, 'full', other, enter_port_mode=False )
        return True

    def set_speed( self, port, value, other, enter_port_mode=True ):
        cmd = None
        if not value == None:
            value = value.replace( ',', ' ' )
        autoneg = False
        if 'autoneg' in other:
            autoneg = other['autoneg']

        # logging.debug('SPEED: %s, autoneg: %s->%s (other %s)' %(value,'',autoneg,repr(other)))
        if autoneg == True and value == None:
            cmd = ' no speed'
        elif autoneg == True and value:
            cmd = ' speed auto ' + value
        elif autoneg == False and value:
            cmd = ' speed ' + str(value)
        if not enter_port_mode or self.enter_port_mode( port ):
            return self.prompt.ask( cmd )
        return False
        
    def set_duplex( self, port, value, other, enter_port_mode=True ):
        cmd = ' duplex ' + str(value)
        if value == 'auto' or value == None:
            cmd = ' no duplex'
        if not enter_port_mode or self.enter_port_mode( port ):
            return self.prompt.ask( cmd )
        return False


    def set_type_clear( self, port, type, other, enter_port_mode=True ):
        """ clear the switchport types """
        logging.debug("clearing port type %s" % (type,))
        if not type == 'private-vlan host':
            self.prompt.ask( 'no switchport private-vlan host-association', fail_okay=True )
        if not type == 'trunk':
            self.prompt.ask("no switchport trunk native vlan") \
            and self.prompt.ask("no switchport trunk allowed vlan") \
            and self.prompt.ask('no switchport trunk native vlan tag', fail_okay=True )
        if not type == 'access':
            self.prompt.ask("no switch access vlan")
        return True

    def set_type_clear_post( self, port, type, other, enter_port_mode=True ):
        """ clear the switchport types after initial commands """
        logging.debug("clearing post port type %s" % (type,))
        if not type == 'trunk':
            self.prompt.ask("no switchport mode trunk", fail_okay=True)
            self.prompt.ask("no switchport trunk encapsulation", fail_okay=True)
        return True

    def set_type_access( self, port, value, other, enter_port_mode=True ):
        """ configure port for access on vlan value """
        logging.debug("set type access: %s" %(value))
        if len( value ) == 1:
            # older ios devices dont like the switchport command
            self.prompt.ask( ' switchport', fail_okay=True ) \
                and self.prompt.ask( ' switch mode access' )
            vlan = value[0]
            logging.debug("  access vlan %s (%s)" % (vlan, value))
            configured_vlans = dict(self.parent.layer2.vlan)
            if vlan in configured_vlans:
                return self.prompt.ask( ' switchport access vlan %s' %(vlan,) )
            else:
                raise DeviceException, 'vlan %s is not available on this device' % (vlan,)
        raise DeviceException, "input format '%s' incorrect" % (value,)

    def set_native_vlan( self, port, value, other, enter_port_mode=True ):
        """ configure port for native vlan """
        logging.debug("set native vlan: %s %s" %(type(value),value))
        if isinstance( value, int ):
            return self.prompt.ask( 'switchport trunk native vlan %s' % (value,) )
        elif isinstance( value, str ):
            vlan = None
            for i,v in dict(self.parent.layer2.vlan).iteritems():
                if 'name' in v  and search( value, v['name'] ):
                    vlan = i
            if vlan:
                return self.prompt.ask( ' switchport trunk native vlan %s ' %(vlan,) )
            else:
                raise DeviceException, 'vlan %s is not available on this device' % (vlan,)
        raise DeviceException, "input format '%s' incorrect" % (value,)


    def set_type_trunk( self, port, value, other, enter_port_mode=True ):
        """ set the list of vlans trunked on this port """
        logging.debug("set type trunk: %s" %(value))
        if len( value ):
            configured_vlans = dict(self.parent.layer2.vlan)
            cmd = ' switchport trunk allowed vlan %s' % ( ','.join([ str(i) for i in value ]) )
            #logging.error("  TRUNK: %s" % (cmd,))
            return True
            # for v in value:
            #     if not v in configured_vlans:
            #         raise DeviceException, 'vlan %s is not available' % (v,)
            # if self.enter_port_mode( port ):
            #     cmd = ' switchport trunk allowed vlan %s' % ( ','.join([ str(i) for i in value ]) )
            #     return self.prompt.ask( cmd )
            # return False
        raise DeviceException, 'cannot remove all vlans from trunk'

    def set_type_privatevlan_host( self, port, value, other, enter_port_mode=True ):
        """ set to private vlan """
        if type(value) == unicode:
            v = []
            for i in value.split(','):
                v.append( int(i) )
            value = v
        logging.debug('set private vlan: ' + str(value) + " ("+str(type(value))+")")
        if len(value) == 2:
            configured_vlans = dict(self.parent.layer2.vlan)
            if value[0] in configured_vlans and value[1] in configured_vlans:
                if self.enter_port_mode( port ):
                    return self.prompt.ask( ' no switchport noneg' ) \
                        and self.prompt.ask( ' no switchport access vlan' ) \
                        and self.prompt.ask( ' no switchport mode access' ) \
                        and self.prompt.ask( ' switchport private-vlan host-association ' + str(value[0]) + " " + str(value[1]) ) \
                        and self.prompt.ask( ' switchport mode private-vlan host' ) \
                        and self.prompt.ask( ' no cdp enable' )
                return False
            raise DeviceException, 'private vlans ' + str(value) + " does not exist"
        raise DeviceException, 'vlan format incorrect ('+str(value)+')'

    def set_voice_vlan( self, port, value, other, enter_port_mode=True ):
        """ set the voice vlan """
        logging.debug('set voice vlan: ' + str(value))
        if value == False:
            return self.prompt.ask( 'no switchport voice vlan' )
        elif value == True:
            # find vlan - assume ends in VOICE
            for i,v in dict(self.parent.layer2.vlan).iteritems():
                if 'name' in v  and search( r'-VOICE$', v['name'] ):
                    value = i
        return self.prompt.ask( 'switchport voice vlan %s' % (value,))

    def set_portnoneg( self, port, value, other, enter_port_mode=True ):
        """ set the port type negotiation """
        logging.debug('set port neg ')
        if value == True:
            self.prompt.ask( 'switchport nonegotiate')
        elif value == False:
            self.prompt.ask( 'no switchport nonegotiate')
        else:
            pass
        return True
    
    def set_logging( self, port, dict, other, enter_port_mode=True ):
        """ set the port logging """
        logging.debug('set port logging %s' % (dict,))
        for k,v in dict.iteritems():
            if v:
                self.prompt.ask( 'logging event %s' % (k,))
            elif v == False:
                self.prompt.ask( 'no logging event %s' % (k,))
            elif v == None:
                pass
        return True

    def set_security( self, port, value, other, enter_port_mode=True ):
        """ set the port security """
        logging.debug('set port security %s' % (value,))
        if isinstance(value,bool) and value == False:
            if self.prompt.ask( 'no switch port-security'):
                # clean up
                for i in ( 'aging', 'mac-address', 'maximum', 'violation' ):
                    self.prompt.ask( 'no switchport port-security %s' % i )
            else:
                return False
        elif isinstance(value,dict):

            if other['type'] in ( 'access', ):
                self.prompt.ask( 'switch mode %s' % (other['type'],) )
            else:
                raise Exception, 'unsupported type for port security enforcement'

            if not self.prompt.ask('switch port-security'):
                raise Exception, "could not enforce port security"
            
            for k,v in value.iteritems():
                key = k.replace('-',' ')
                if v:
                    self.prompt.ask( 'switchport port-security %s %s' % (key,v))
                elif v == False:
                    self.prompt.ask( 'no switchport port-security %s' % (key,))
                elif v == None:
                    pass
        else:
            raise Exception, 'unknown security state %s' % (value,)
        return True

    def set_storm_control( self, port, dict, other, enter_port_mode=True ):
        """ set the storm control """
        logging.debug('set storm control %s' % (dict,))
        for k,v in dict.iteritems():
            if v:
                self.prompt.ask( 'storm-control %s level %s' % (k,v))
            elif v == False:
                self.prompt.ask( 'no storm-control %s' % (k,))
            elif v == None:
                pass
        return True
        
    def set_cdp( self, port, value, other, enter_port_mode=True ):
        """ set cdp status """
        if value == True:
            self.prompt.ask( 'cdp enable' )
        elif value == False:
            self.prompt.ask( 'no cdp enable')
        else:
            pass
        return True
        
    def _set_lldp( self, key, value ):
        if value == True:
            return self.prompt.ask( 'lldp %s' % (key,)  )
        elif value == False:
            return self.prompt.ask( 'no lldp %s' % (key,))
        return
        
    def set_lldp( self, port, value, other, enter_port_mode=True ):
        """ set lldp transmit """
        keys = ( 'transmit', 'receive' )
        if isinstance( value, dict ):
            for k in keys:
                if k in value:
                    self._set_lldp( k, value[k] )
        elif isinstance( value, bool ):
            for k in keys:
                self._set_lldp( k, value )
        return True
          
    def set_bpduguard( self, port, value, other, enter_port_mode=True ):
        """ set_bpduguard """
        if value == True:
            # logging.error('no spanning-tree bpduguard disable' )
            return self.prompt.ask( 'no spanning-tree bpduguard disable' )
        elif value == False:
            # logging.error('spanning-tree bpduguard disable' )
            return self.prompt.ask( 'spanning-tree bpduguard disable')
        return True

    def set_portfast( self, port, value, other, enter_port_mode=True ):
        """ set_portfast """
        if value == True:
            # logging.error('no spanning-tree portfast disable' )
            return self.prompt.ask( 'no spanning-tree portfast disable' )
        elif value == False:
            # logging.error('spanning-tree portfast disable' )
            return self.prompt.ask( 'spanning-tree portfast disable')
        return True

    def set_dhcp_snooping( self, port, value, other, enter_port_mode=True ):
        """ set_dhcp_snooping """
        if value in ( 'trust', 'limit' ):
            logging.error('setting dhcp snooping to %s' % (value,) )
            return self.prompt.ask( 'ip dhcp snooping %s' % (value,) )
        elif value in ( None, False ):
            logging.error('removing dhcp snooping settings' )
            return self.prompt.ask( 'no ip dhcp snooping trust') and self.prompt.ask( 'no ip dhcp snooping limit')
        return False

class PortChannelsCiscoIos( PortChannels ):    
    show_cmd = 'show etherchannel summary'

    regexes = [
        r'^\s*(?P<group>\d+)\s+(?P<port_channel>\S+)\((?P<port_channel_state>\S+)\)\s+(?P<protocol>\S+)\s+(?P<members>.*)$',
        r'^\s+(?P<members>\D\S+)$'
    ]
    members_regex = compile( r'\s*(?P<port>\S+)\((?P<state>\S+)\)\s*' )
    
    state_map = {
        'D': 'down',
        'U': 'up',
        'P': 'up',
        'I': 'stand-alone',
        'H': 'hot-standby',
        's': 'suspended',
        'r': 'removed',

        'S': 'layer2',
        'R': 'layer3',
        'M': 'min-links not met',
    }
    
    
    def _get( self, *args, **kwargs ):
        for b in self.prompt.tell_and_get_block( self.show_cmd ):
            this = {}
            po = None
            members = []
            for l in b:
                # logging.debug("  L: %s" % (l))
                for r in self.regexes:
                    m = match( r, l )
                    if m:
                        # logging.debug( "    matched (po %s): %s" % (po,r,))
                        d = m.groupdict()
                        if 'port_channel' in d:
                            po = d['port_channel']
                        if po:
                            for k,v in d.iteritems():
                                if k == 'members':
                                    members.append( v )
                                    # logging.debug("     appended: %s (%s)" % (v, members))
                                else:
                                    this[k] = v
                this['members'] = []
                # parse members
                for l in members:
                    # logging.debug("    members: %s" % (l,))
                    for m in self.members_regex.finditer( l ):
                        d = m.groupdict()
                        if not d['state'] in self.state_map:
                            raise 'port channel state %s not defined' % (d['state'])
                        d['state'] = self.state_map[ d['state'] ]
                        this['members'].append( d )

            if 'port_channel' in this:

                # logging.debug("  >= %s (%s)" % (this,this['port_channel_state'][0]))
                # parse po state
                this['layer'] = self.state_map[ this['port_channel_state'][0] ]
                this['state'] = self.state_map[ this['port_channel_state'][1] ]
                del this['port_channel_state']
                
                yield po, this
            

class ConfigCiscoIos( Config ):
    
    header_skip_lines = 3
    
    def get_running_config( self  ):
        # commands = [ 'show running-config all', 'show running-config' ]
        commands = [ 'show running-config', ]
        for cmd in commands: 
            c = [ i.rstrip() for i in self.prompt.tell( cmd, cursor=self.prompt.cursor( 'mode', 'enable' ), timeout=self.prompt.timeouts['long'] ) ]
            if self.prompt.current_cursor == self.prompt.cursor( 'error', 'input' ):
                continue
            if len(c) > self.header_skip_lines + 1:
                for x in xrange( 0, self.header_skip_lines ):
                    c.pop(0)
                c.insert(0, '')
                # print "%s"%c
                return c
        return None
        
    def commit(self):
        # try wr mem first (copy run start doesn't update the headers on the show run)
        okay = self.prompt.ask( 'wr mem', 
            fail_okay=True, 
            cursor=self.prompt.cursor('mode','enable'), 
            timeout=self.prompt.timeouts['long']
        )
        if not okay:
            okay = self.prompt.request( 'copy running-config startup-config', 
                        cursor=self.prompt.cursor('mode','enable'), 
                        timeout=self.prompt.timeouts['long'], 
                        interact={
                            'question': "" # take default
                        }
                    )
        return okay

class ModelCiscoIos( Model ):
    """
    Model information for a generic Cisco IOS Switch
    """
    def get( self, cached=False ):
        return [ m['model'] for m in self.parent.get(cached=cached) ]

class FirmwareCiscoIos( Firmware ):
    """
    Firmware components for a generic Cisco IOS switch
    """

    def __is_3850(self):
        is_3850 = False
        for m in self.parent.model.get(cached=True):
            if '3850' in m:
                is_3850 = True
        # 3850's
        return is_3850

    def transfer_firmware_image( self, *paths, **kwargs ):
        # overwrite=True, image_only=True, dry_run=False, *paths ):
        """
        copy the list of files over to the switch
        """
        err = []
        okay = []
        
        is_3850 = self.__is_3850()
        if not is_3850:
            
            # create command line
            cmd = 'archive download-sw '
            if not 'overwrite' in kwargs:
                kwargs['overwrite'] = True
        
            if 'overwrite' in kwargs and kwargs['overwrite']:
                cmd = cmd + ' /overwrite '
            if 'image_only' in kwargs and kwargs['image_only']:
                cmd = cmd + ' /imageonly '
            cmd = cmd + ' '.join( paths )
        
            if 'dry_run' in kwargs and kwargs['dry_run']:
                logging.info('%s' % (cmd,))
                return False
            
            t = len(paths)*self.prompt.timeouts['very_long']
            # logging.warn("CMD: %s" % cmd )
            for l in self.prompt.tell( cmd, cursor=self.prompt.cursor('mode','enable'), timeout=t ):
                logging.debug(" downloading...")
                if match( '(\%)?(?i)Error\:? (?P<message>.*$)', l ):
                    err.append( l )
                elif match( 'New software image installed in ', l ):
                    okay.append( l )
                elif match( 'examining image...', l ):
                    logging.debug(' downloaded')
                elif match( 'Deleting ', l ):
                    logging.debug(' clearing')
                elif match( 'Installing ', l ):
                    logging.debug(' installing')
                    
        elif is_3850:
            
            # interact={ 'Destination filename': "\n", 'Do you want to over write? [confirm]': 'y' }
            
            # logging.error("INSTALL paths=%s, kwargs=%s" % (paths, kwargs))
            filepath = paths[-1]
            cmd = "copy %s flash:" % (filepath,)
            # logging.error("CMD: %s" % (cmd, ))
            logging.info(" downloading firmware...")
            for l in self.prompt.tell( cmd, cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['very_long'] ):
                logging.debug("> %s" % (l,) )
                if match( 'Accessing ', l ):
                    logging.debug("accessing...")
                elif match( '\[OK', l ):
                    logging.debug('done')
            
            # install
            file = path.basename( filepath )
            # cat3k_caa-universalk9.SPA.03.03.05.SE.150-1.EZ5.bin
            cmd = 'software install file flash:%s on-reboot verbose' % (file,)
            # logging.error("CMD: %s" % (cmd,) )
            logging.info("installing firmware...")
            for l in self.prompt.tell( cmd, cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['very_long'] ):
                logging.debug("> %s" % (l,) )
                if search( 'SUCCESS: ', l ):
                    logging.debug('success')
                elif search( 'Error', l ):
                    err.append( l )
            
        if len(err):
            raise DeviceException, ' '.join( err )
        return len( okay ) > 0


    def check_boot_variable( self, set_to=None ):
        # show boot 
        boot_list = []
        for l in self.prompt.tell( 'show boot', cursor=self.prompt.cursor('mode','enable') ):
            m = search( r'^BOOT path-list\s*\:\s+(?P<path>.*)$', l )
            if m:
                boot_list.append(m.group('path'))

        # TODO: compare bootlist variables against what is requested
        logging.debug("BOOTLIST: " + str(boot_list))
        
        return boot_list

    def firmware_image_to_version( self, image_path ):
        """ works out what the IOS version number is from the filename """
        m = []
        version = None
        if m.append( search( r'(\d{3})\-(\d{2})\.(\w+)\.(tar|bin)$', image_path ) ) or m[-1]:
            # major minor
            this = m[-1].group(1)
            version = this[0] + this[1] + '.' + this[2]
            # bracket
            this = m[-1].group(2)
            version = version + '(' + this + ')'
            # final
            version = version + m[-1].group(3)
        # 3850's
        elif m.append( search( r'(\d{2}\.\d{2}\.\d{2}\.SE)\.(tar|bin)$', image_path ) ) or m[-1]:
            version = m[-1].group(1)
            version = version.replace( '.SE', 'SE' )
        return version

    def firmware_filename( self, image, version ):
        if self.__is_3850():
            # logging.error("IMAGE %s %s" % (image,version))
            # cat3k_caa-universalk9.SPA.03.03.05.SE.150-1.EZ5.bin
            # cat3k_caa-universalk9 03.03.05SE
            v = version.replace('SE','.SE')
            return "%s.SPA.%s.150-1.EZ5.bin" % (image,v)
        else:
            # maps the image and version strings to a filename
            image = image.replace( '-m', '-' )
            if not image[-1] == '-':
                image = image + '-'
            version = version.replace('.','').replace('(','-').replace(')','.')
        return "%star.%s.tar" % (image, version)

    def image( self ):
        return [ m['sw_image'] for m in self.parent.get() ]
        
    def version(self):
        return [ m['sw_version'] for m in self.parent.get() ]

    # def upgrade(self):
    
class Layer1CiscoIos( Layer1 ):
    """ returns cdp and lldp information from the switch """
    cdp_matches = {
        'neighbour': r'^Device ID:\s*(?P<peer_device>\S+)',
        'ip_address': r'\s+IP(v4)? (a|A)ddress: (?P<peer_address>\S+)',
        'platform': r'^Platform: (?P<peer_platform>.*)\s*,\s+Capabilities: (?P<peer_capabilities>.*)',
        'interfaces': r'^Interface: (?P<physical_port>\S+),\s+Port ID \(outgoing port\): (?P<peer_physical_port>\S+)',
        'holdtime':   r'^Holdtime\s*: (?P<holdtime>\d+) sec',
        'new':  r'^---------',
    }
    lldp_matches = {
        'peer_ip_address':    r'Chassis id: (?P<peer_ip_address>\S+)',
        'peer_mac_address':   r'Port id: (?P<peer_mac_address>\S+)',
        'capabilities':       r'Enabled Capabilities: (?P<peer_capabilities>\S+)',
        'platform':           r'\s+Model: (?P<peer_platform>.*)\s*',
        'vendor':             r'\s+Manufacturer: (?P<peer_vendor>.*)\s*',
        'new':                r'^----------'
    }
    
    
    def parse_item(self,d):
        # logging.warn('parsing %s' % (d,))
        if 'peer_device' in d:
            d['peer_device'] = d['peer_device'].lower()
            if '(' in d['peer_device']:
                bits = d['peer_device'].replace(')','').split('(')
                d['peer_device'] = bits.pop(0)
                try:
                    d['peer_serial'] = bits.pop(0)
                except:
                    pass
        if 'peer_address' in d and to_ip( d['peer_address'] ):
            d['peer_ip_address'] = d['peer_address']
        if 'peer_capabilities' in d:
            for c in d['peer_capabilities'].split():
                if c == 'Trans-Bridge':
                    d['capability_bridge'] = True
            for c in d['peer_capabilities'].split(','):
                if c == 'B':
                    d['capability_bridge'] = True
                elif c == 'T':
                    d['capability_telephone'] = True
        for p in ( 'peer_physical_port', 'physical_port' ):
            if p in d:
                d[p] = truncate_physical_port( d[p] )
        for i in ( 'peer_capabilities', 'peer_address' ):
            if i in d:
                del d[i]
        return d
    
    def add_item( self, items, d ):
        if 'physical_port' in d:
            d['physical_port'] = truncate_physical_port( d['physical_port'] )
            if not d['physical_port'] in items:
                items[d['physical_port']] = {}
            items[ d['physical_port'] ].update( self.parse_item( d ) )
    
    def _get( self, *args, **kwargs ):
        items = {}
        this = {}
        for l in self.prompt.tell( 'show cdp nei detail', cursor=[self.prompt.cursor('mode','enable'), self.prompt.cursor('mode','exec')] ):
            # logging.warn("> %s" % l,)
            for n in self.cdp_matches:
                m = match( self.cdp_matches[n], l )
                if m:
                    # new item, clear
                    if n == 'new':
                        if len(this.keys()):
                            self.add_item( items, this )
                        this = {}
                    else:
                        d = m.groupdict( m )
                        this.update( d )
                        # logging.warn(" - %s: %s" % (n,this))
        # don't forget last item
        self.add_item( items, this )

        # do lldp
        try:
            this = {}
            # stupid cmd output doesn't support showing the local interface witth detail,
            # so we have to run two commands
            lldp_lookup = {}
            for l in self.prompt.tell( 'show lldp nei', cursor=[self.prompt.cursor('mode','enable'), self.prompt.cursor('mode','exec')] ):
                m = match( r'(?P<peer_ip_address>\S+) \s+ (?P<physical_port>\S+) \s+ (?P<holdtime>\d+) \s+ (?P<peer_capability>\S+) \s+ (?P<peer_mac_address>\S+)', l )
                if m:
                    d = m.groupdict()
                    lldp_lookup[ d['peer_mac_address'] ] = d
            # logging.error("LLDP LOOKUP %s" % (lldp_lookup,))
            for l in self.prompt.tell( 'show lldp nei detail', cursor=[self.prompt.cursor('mode','enable'), self.prompt.cursor('mode','exec')] ):
                for n in self.lldp_matches:
                    m = match( self.lldp_matches[n], l )
                    if m:
                        if n == 'new':
                            # lookup the physical port for this
                            if len(this.keys()):
                                if this['peer_mac_address'] in lldp_lookup:
                                    this['physical_port'] = lldp_lookup[ this['peer_mac_address' ] ]['physical_port']
                                    # check others?
                                self.add_item( items, this )
                        else:
                            d = m.groupdict(m)
                            this.update(d)
            # don't forget last item
            self.add_item( items, this )
        except:
            logging.debug("no lldp support")
            pass

        # return all
        for k,v in items.iteritems():
            yield k,v
        return
    
    def on_peer_device(self):
        return self._on('peer_device')
    def on_physical_port(self):
        return self._on('physical_port')
    def on_peer_physical_port(self):
        return self._on('peer_physical_port')
    def on_peer_ip_address(self):
        return self._on('peer_ip_address')
    def on_peer_mac_address(self):
        return self._on('peer_mac_address')
    def on_capability_bridge(self):
        return self._on('capability_bridge')
    def on_capability_telephone(self):
        return self._on('capability_telephone')




class VlanCiscoIos( Vlan ):
    def _get( self, *args, **kwargs ):
        tries = 0
        max_tries = 4
        n = 0
        # for i in self.prompt.tell( 'show vlan brief'):
        #     logging.error('%s' % (i,))
        while n == 0 and tries < max_tries:
            tries = tries + 1
            for d in self.prompt.tell_and_match( 
                    'show vlan brief', 
                    r'^(?P<number>\d+)\s+(?P<name>\S+)\s+(?P<status>[/a-z]+)\s*' ):
                n = n + 1
                d['number'] = int(d['number'])
                yield d['number'], d
        return
    def add( self, number, name ):
        ok = False
        if self.prompt.ask( 'vlan %s' % (number,), cursor=self.prompt.cursor('mode','config') ):
            ok = self.prompt.ask( ' name %s' % (name,), cursor=self.prompt.cursor('mode','config-vlan'))
        else:
            # old xl's, need vlan database
            if self.prompt.ask( 'vlan database', cursor=self.prompt.cursor('mode','enable') ):
                ok = self.prompt.ask('  vlan %s name %s' % (number, name), cursor=self.prompt.cursor('mode','config-vlan'))
                self.prompt.ask("exit")
        if ok:
            # force refresh on next poll
            self._cache = None
        return ok
    def remove( self, number ):
        if not int(number) in dict(self):
            raise DeviceException, 'vlan %s does not exist' % (number)
        self._cache = None
        return self.prompt.ask( 'no vlan %s' % (number,), cursor=self.prompt.cursor('mode','config') )

class SpanningTreeCiscoIos( SpanningTree ):
    matches = [
        r'^ Port \d+ \((?P<port>(\w|\/)+)\) of VLAN(?P<vlan>\d+) is (?P<mode>.*)$',
        # { 'regex': r'^   Designated root has priority (?P<root_priority>\d+), address (?P<root_address>.*)$', 'fields': ['root_priority', 'root_address'] },
        r'^   The port is in the (?P<portfast>portfast) mode',
        r'^   BPDU: sent \d+, received \d+$',
    ]
    
    other_matches = {
        'vlan': r'^VLAN0{0,}(?P<vlan>\d+)',
        'protocol': r'^  Spanning tree enabled protocol (?P<protocol>\S+)\s*',
        'priority': r'\s+(?P<group>\w+)\s+ID\s+Priority\s+(?P<priority>\d+)\s*',
        'address':  r'\s+Address\s+(?P<address>\w+\.\w+\.\w+)\s*',
        'cost':     r'\s+Cost\s+(?P<cost>\d+)\s*',
        'is_root':  r'\s+This bridge is the root',
        'port':     r'\s+Port\s+(?P<port_number>\d+)\s+\((?P<physical_port>.*)\)\s*',
        'int':      r'(?P<physical_port>\S+)\s+(?P<role>\w+) (?P<status>\w+) (?P<cost>\d+)\s+(?P<port_priority>\d+)\.(?P<port_number>\d+)\s+(?P<port_type>.*)\s*',
    }
    
    def _get(self, *args, **kwargs ):
        item = {}
        got_vlan = False
        got_interface = False # mark end of all interfaces, during find should be None
        for l in self.prompt.tell('show spanning-tree', cursor=self.prompt.cursor('mode','enable') ):
            logging.debug(">: " + str(l))            
            for t,r in self.other_matches.iteritems():
                # logging.debug(" t: %s" % t)
                m = search( r, l )
                if m:
                    if t == 'vlan':
                        if 'vlan' in item:
                            if 'group' in item:
                                del item['group']
                            # logging.debug("YIELD1: %s"%(item,) )
                            yield item['vlan'], item
                        logging.debug('clearing')
                        item = {}
                        got_vlan = True
                    elif t == 'is_root':
                        logging.debug("  setting as root bridge")
                        item['root_cost'] = 0
                        item['root_port'] = 0

                    # pre find the group
                    d = m.groupdict()
                    if 'group' in d:
                        item['group'] = d['group']
                        
                    # add ports to an array
                    if t == 'int':
                        got_interface = None
                        if not 'ports' in item:
                            item['ports'] = []
                        item['ports'].append( d )
                        logging.debug('  >= %s' % (d,))
                        
                    else:
                        
                        for k,v in d.iteritems():
                            g = str(k)
                            if 'group' in item:
                                g = item['group'].lower() + '_' + str(k)
                            item[g] = v
                            logging.debug('  >= %s\t: %s' % (g,v))


            # mark end
            if got_interface == None and l == '':
                got_interface = True

            if got_vlan and got_interface:
                got_vlan = False
                got_interface = False
                if 'group' in item:
                    del item['group']
                # logging.debug("YIELD2: %s"%(item,) )
                yield item['vlan'], item
        return
    
    def on_root(self):
        return self._on('root_address')
        
    def on_cost(self):
        return self._on('root_cost')
    
    def on_vlan(self):
        return self._on('vlan')    

    def on_priority(self):
        return self._on('root_priority')

    def on_port(self):
        return self._on('root_port')

    def on_port_number(self):
        return self._on('root_port_number')

    def on_root_physical_port(self):
        return self._on('root_physical_port')

    def on_bridge_priority(self):
        return self._on('bridge_priority')

    
    def get(self, port=None ):
        for o in self.prompt.tell( 'show spanning-tree interface ' + str(port) + ' detail', cursor=self.prompt.cursor('mode','enable') ):
            for m in self.matches:
                # logging.debug("  looking for: " + str(d['fields']))
                ok = match( m, o )
                if ok:
                    g = ok.groupdict()
                    # create new set if necessary
                    if len(g) == 0:
                        logging.debug("new spanning tree found " + str(this))
                        # commit last set
                        if len(this.keys()) > 0:
                            if not 'portfast' in this:
                                this['portfast'] = False
                            else:
                                this['portfast'] = True
                            logging.debug('THIS: ' + str(this))
                            k = this['port'].lower() + '-' + this['vlan'].lower()
                            yield this
                        this = {}
                    # grab info
                    for f in g:
                        # if found new set
                        this[f] = g[f]
                        logging.debug("    >: found " + str(f) + " = " + str(this[f]))
        return




class MacAddressCiscoIos( MacAddress ):
    regexes = [
        r'\*?\s*(?P<vlan>\d+)\s+(?P<mac_address>\w{4}\.\w{4}\.\w{4})\s+(?P<type>\w+( pv)?)\s*(?P<learned>\w+)?\s+(?P<age>(\d+|-))?\s*(?P<physical_port>(\w+|\/)+)$', # 'ios'
        r'^(?P<source>.*)\s+(?P<vlan>\d+)\s+(?P<mac_address>\w{4}\.\w{4}\.\w{4})\s+(?P<type>\w+)\s+(?P<age>(\d|\-)+)\s+.*\s+.*\s+(?P<physical_port>.*)\s*$', # 'nexus'
        r'^(?P<mac_address>\w{4}\.\w{4}\.\w{4})\s+(?P<type>\w+)\s+(?P<vlan>\d+)\s+(?P<physical_port>(\w+|\/)+)$', # 'ios-xl'
    ]

    def _get( self, *args, **kwargs ):
        self._cache = {}
        cmd = 'show mac address-table '
        for o in self.prompt.tell( 'show version | inc Internetwork|-XL'):
            # old sup's
            if o == 'Cisco Internetwork Operating System Software':
                cmd = 'show mac-address-table'
            # old xl's
            elif '-XL' in o:
                cmd = 'show mac'

        if 'port' in kwargs:
            cmd = cmd + ' | inc ' + str(kwargs['port'])

        for d in self.prompt.tell_and_match( cmd, self.regexes, timeout=self.prompt.timeouts['long'] ):
            for i in ( 'mac_address', 'type' ):
                d[i] = d[i].lower()
            d['vlan'] = int( d['vlan'] )
            if 'learned' in d and d['learned'] == 'Yes':
                d['status'] = 'learned'
            if not 'status' in d or d['status'] == None:
                d['status'] = 'learned'
            # logging.warn("HERE: %s" % (d,))
            yield d['mac_address'], d
        return

class Layer2CiscoIos( Layer2 ):
    vlan = VlanCiscoIos
    spanningtree = SpanningTreeCiscoIos
    mac_address = MacAddressCiscoIos
    


class RoutesCisco( Routes ):
    matches = {
        'o' : r'^O (?P<ospf_type>\w+)?\s+ (?P<prefix>\d+\.\d+\.\d+\.\d+)/(?P<prefix_len>\d+)',
        'o2': r'^O(\s+|\*)(?P<ospf_type>\w+)?\s+(?P<prefix>\d+\.\d+\.\d+\.\d+)(/(?P<prefix_len>\d+))?( \[\d+/\d+\] via (?P<next_hop>\d+\.\d+\.\d+\.\d+), )?',
        'p': r'^\s+\[\d+/\d+\] via (?P<next_hop>\d+\.\d+\.\d+\.\d+), ',
        'h' : r'^\s+(?P<prefix>\d+\.\d+\.\d+\.\d+)(/(?P<prefix_len>\d+))',
        'c' : r'^(C|L)\s* (?P<prefix>\d+\.\d+\.\d+\.\d+)(/(?P<prefix_len>\d+))? is directly connected, (?P<interface>.*)$',
        's' : r'^S\s+(?P<prefix>\d+\.\d+\.\d+\.\d+)(/(?P<prefix_len>\d+) .*via (?P<next_hop>\d+\.\d+\.\d+\.\d+))',
    }
    command = 'show ip route'
    
    def vrfs( self ):
        vrfs = {}
        try:
            for o in self.prompt.tell( 'show vrf brief | inc ip', cursor=self.prompt.cursor('mode','enable') ):
                # logging.info("O %s" % (o,) )
                m = match( r'^\s+(?P<name>\w+)\s+(?P<rd>(\d|\:)+)\s+', o )
                if m:
                    d = m.groupdict()
                    # logging.info("  found %s" % (d,))
                    vrfs[d['name']] = d['rd']
        except:
            pass
        return vrfs
            
    
    def _get( self, *args, **kwargs ):
        this = {}
        indent = 0
        last_indent = None
        # determine vrfs
        vrfs = self.vrfs()
        if len(vrfs.keys()):
            for vrf in vrfs:
                for k, v in self.do( self.command + ' vrf ' + vrf ):
                    # add vrf info
                    v['vrf'] = vrf
                    v['vrf_rd'] = vrfs[vrf]
                    yield k, v
        else:
            for k,v in self.do( self.command ):
                yield k,v
        return


    def do( self, command ):
        this = {}
        indent = 0
        last_indent = None
        for o in self.prompt.tell( command, cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['long'] ):
            # use the fact that the indentation levels represent how the lines relate
            logging.debug("")
            logging.debug('%s'%(o,))
            matched = []
            t = {}
            for k,r in self.matches.iteritems():
                m = match( r, o )
                if m:
                    matched.append( k )
                    for x,y in m.groupdict().iteritems():
                        # remove any NOnes
                        if y:
                            t[x] = y

            if len(matched) > 0:
                # only the prefix defiens how indented it is, get the number of chars from the start
                if 'prefix' in t:
                    indent = o.index(t['prefix'])
                    # logging.debug("indent: %s" % (indent,))
                # else:
                    # logging.debug("no index - inherit")

                logging.debug("%s%s> %s" % (indent, matched,t,))
                
                # assume all not local for now
                t['local'] = False
                
                # if indented less, then wipe out
                if last_indent == None or 'h' in matched: # initial or header
                    this = t
                elif indent > last_indent or not 'prefix' in t:
                    this = dict( this.items() + t.items() )
                elif indent == last_indent and 'c' in matched:
                    # directly connected needs to inhereit ('c')
                    this = dict( this.items() + t.items() )
                    this['local'] = True
                else:
                    this = t

                # don't return the subnet headers
                if not 'h' in matched and not 'o' in matched:
                    # logging.debug(">>> %s" % (this))
                    if 'netmask' in this and not 'prefix_len' in this:
                        this['prefix_len'] = str(netmask_to_prefixlen( this['netmask'] ))
                    if 'prefix_len' in this and ( not 'netmask' in this or this['netmask'] == 'None'):
                        this['netmask'] = str( prefixlen_to_netmask( this['prefix_len'] ) )
                    if not 'next_hop' in this:
                        this['next_hop'] = '0.0.0.0'
                    n = this['prefix']
                    yield n, this
                
            last_indent = indent

        return



class ArpsCisco( Arps ):
    matches = {
        'show ip arp': r'^(\w+\s+)?(?P<ip_address>\d+\.\d+\.\d+\.\d+)\s+(?P<age>(\d|\:|\-)+)\s+(?P<mac_address>\w+\.\w+\.\w+) .* (?P<interface>(\w|\-|\+|\/|\.)+)\s*$',
        'show ipv6 neighbors': r'^(?P<ip_address>(\w|\:)+)\s+(?P<age>\d+)\s+(?P<mac_address>\w+\.\w+\.\w+)\s+(?P<state>\w+)\s+(?P<interface>\w+)',
    }

    def _get( self, *args, **kwargs ):
        for cmd in self.matches.keys():
            for d in self.prompt.tell_and_match_block( cmd, [self.matches[cmd]], timeout=self.prompt.timeouts['medium'], all_matches=True, error_okay=True ):
                logging.debug(" d: %s" % d)
                if 'mac_address' in d and 'ip_address' in d:
                    d['mac_address'] = d['mac_address'].lower()
                    d['ip_address'] = d['ip_address'].lower()
                    yield d['mac_address'] + '-' + d['ip_address'], d
        return

class Layer3CiscoIos( Layer3 ):
    routes = RoutesCisco
    arps = ArpsCisco
    

class TransceiverCiscoIos( Transceiver ):

    def _get( self, *args, **kwargs ):
        
        t = {}
        for d in self.prompt.tell_and_match( 
                'show int transceiver', 
                r'^(?P<port>(\w|\/)+) \s+ (?P<temp>\d+\.\d+) .* (?P<tx>(-)?\d+\.\d+) \s+ (?P<rx>(-)?\d+\.\d+)\s*$', 
                timeout=self.prompt.timeouts['long'] ):
            # yield d['port'], d
            t[d['port']] = d
            
        # get the type for each
        for i in self.prompt.tell( 'show int status' ):
            a = i.split()
            for n,v in enumerate(a):
                # for the 'base' for ethernet type transceivers
                if search(r'ase',v):
                    if a[0] in t:
                        logging.debug("found on %s a %s"%(a[0],a[n:]))
                        t[a[0]]['type'] = ' '.join(a[n:])
        
        for k,v in t.iteritems():
            yield k,v
        return


class ModuleCiscoIos( Module ):
    def _get( self, *args, **kwargs ):
        for d in self.prompt.tell_and_match_by_index( 
                'show module', 
                'slot',
                [ '^\s+(?P<slot>\d+)\s+(?P<ports>\d+)\s+(?P<description>.*)\s+(?P<model>WS\S+)\s+(?P<serial>\S+)\s*$', '^\s+(?P<slot>\d+)\s+(?P<mac_ranges>\S+ to \S+)\s+(?P<hardware_version>\S+)\s+(?P<firmware_version>\S+)\s+(?P<software_version>\S+)\s+(?P<status>\S+)\s*$', '^\s+(?P<slot>\d+)\s+(?P<diag_status>\S+)\s*$' ], 
                timeout=self.prompt.timeouts['medium'] ):
            yield d['slot'], d
            
        # need a point index for the sub modules
        sub_index = {}
        for d in self.prompt.tell_and_match( 
                'show module', 
                r'^\s+(?P<slot>\d+)\s+(?P<description>.*)\s+(?P<model>(W|V)S\-\S+)\s+(?P<serial>\S+)\s+(?P<hardware_version>\S+)\s+(?P<status>\S+)\s*$'
                ):
            s = d['slot']
            # logging.error("SLOT: %s" % s)
            if not s in sub_index:
                sub_index[s] = 1
            else:
                sub_index[s] = sub_index[s] + 1
            d['slot'] = str(d['slot']) + '.' + str(sub_index[s])
            yield d['slot'], d
        return

class FRUCiscoIos( FRU ):
    transceiver = TransceiverCiscoIos
    module = ModuleCiscoIos

class PasswordCiscoIos( Password ):

    def _login( self, interface, password ):
        if self.prompt.ask(str(interface), cursor=self.prompt.cursor('mode','enable')):
            if self.prompt.current_cursor == self.prompt.cursor('mode','config-line'):
                return self.prompt.ask( ' password ' + str(password) )
    
    def console_login( self, password, clear_existing=True ):
        self._login( 'con 0', password )

    def vty_login( self, password, clear_existing=True ):
        self._login( 'vty 0 4', password )
        self._login( 'vty 5 15', password )
            
    def login( self, user, password, level=15, clear_existing=True ):
        self.prompt.ask('username ' + str(user) + " privilege " + str(level) + ' secret ' + str(password), cursor=self.prompt.cursor('mode','enable') )
        
    def enable( self, password, level=15, clear_existing=True ):
         return self.prompt.ask( 'enable secret ' + str(password), cursor=self.prompt.cursor('mode','config') )
        
    def get_snmp_community( self, type=None ):
        cmd = 'show run '
        if not type == None:
            cmd = cmd + '| inc RO '
        cmd = cmd + '| inc snmp-server community'
        for l in self.prompt.tell( cmd, cursor=self.prompt.cursor('mode','enable') ):
            yield l
        return

    def snmp( self, community, type='RO', access_list=None, clear_existing=True ):
        if clear_existing:
            cur = [ s for s in self.get_snmp( type=type )]
            for c in cur:
                self.prompt.ask( 'no ' + str(c) )
        cmd = 'snmp-server community ' + str(community) + ' ' + str(type)
        if not access_list == None:
            cmd = cmd + ' ' + str(access_list)
        return self.prompt.ask( cmd, cursor=self.prompt.cursor('mode','enable') )
    
    def snmp_ro(self, community, access_list=20, clear_existing=True):
        return self.snmp( community, type='RO' )

    def snmp_rw(self, community, access_list=21, clear_existing=True):
        return self.snmp( community, type='RW' )

class UsersCiscoIos( Users ):
    matches = [
        r'^\s+\d (?P<line>\w+\s\d) \s+ (?P<user>(\w|\.|\-\@)+) \s+ \w+ \s+ \d+',
        r'^\s+\d (?P<line>\w+\s\d) \s+ \w+ \s+ \d+',
    ]
    
    def get( self ):
        return self._yield_matches( 'show users | exc \*', cursor=self.prompt.cursor('mode','enable'), regex_matches=self.matches )

class SystemCiscoIos( System ):
    
    config = ConfigCiscoIos
    model = ModelCiscoIos
    firmware = FirmwareCiscoIos
    fru = FRUCiscoIos
    password = PasswordCiscoIos
    users = UsersCiscoIos
    
    __cache = None
    
    def get(self, cached=False ):
        if cached and self.__cache:
            return self.__cache
        c = []
        members = []
        m = []
        item = { 'number': 0 }
        for l in self.prompt.tell( 'show version', cursor=self.prompt.cursor( 'mode', 'enable' ), output_wait=0.03, timeout=self.prompt.timeouts['medium'] ):
            # logging.debug(" > " + str(l))
            if search( r'^\*?\s+\d+\s+\d+', l ):
                stuff = l.split()
                logging.debug("   match search %s: %s" % (l,stuff))
                if len(stuff) > 4:
                    # remove state for 3850's
                    if stuff[-1] == 'INSTALL':
                        _ = stuff.pop()
                    item = {
                        'sw_image':     stuff.pop(),
                        'sw_version':   stuff.pop(),
                        'model':    stuff.pop(),
                        None: stuff.pop(),
                        'number':   int(stuff.pop()) - 1,
                    }
                    del item[None]
                    members.append( item )
            elif m.append( search( r'cisco ((\w|\-)+) ', l ) ) or m[-1]:
                # logging.debug("  match model number")
                item['model'] = m[-1].group(1)
            elif m.append( search( r'^Cisco ((\w|\-)+) \(PowerPC|MIPS\) processor', l ) ) or m[-1]:
                item['model'] = m[-1].group(1)                    
            elif m.append( search( r'^Cisco IOS Software, .* Software \((.*)\), Version (.*),', l ) ) or m[-1]:
                # logging.debug("   match versions")
                item['sw_image'] = m[-1].group(1)
                item['sw_version'] = m[-1].group(2)
        # logging.debug('model info: ' + str(members))
        if len(members) == 0:
            members.append( item )
        output = sorted( members, key=lambda k: k['number'] )
        if cached:
            self.__cache = output
        return output
    
    def reload( self, at=None, force=False, commit=False ):
        """ reload a device """
        return self.prompt.ask('reload', interact={ 
                'reload': '\n' if force else 'n', 
                'config_modified': 'y' if commit else 'n',
            })


class Rfc2863CiscoIos( Rfc2863 ):
    port_regexes = [
        r'^(?P<port>\S+) is (?P<admin_status>\S+), line protocol is (?P<oper_status>\S+)',
        r'^\s+Description: (?P<alias>.*)\s*$',
        r'^\s+MTU (?P<mtu>\d+) bytes, BW (?P<speed>\d+) ',
        r'^\s+(?P<duplex>\S+)-duplex, ',
        r'^\s+Input queue: (?P<in_queue_size>\d+)/(?P<in_queue_max>\d+)/(?P<in_queue_drops>\d+)/(?P<in_queue_flushes>\d+) \(size/max/drops/flushes\); Total output drops: (?P<total_output_drops>\d+)',
        r'^\s+Queueing strategy: (?P<queueing_strategy>\S+)',
        r'^\s+Output queue: (?P<output_queue_size>\d+)/(?P<output_queue_max>\d+) \(size/max\)',
        
        #'  L2 Switched: ucast: 324264128 pkt, 32732949957 bytes - mcast: 13703676 pkt, 1733488346 bytes', 
        r'^\s+L2 Switched: ucast: (?P<l2_ucast_pkt>\d+) pkt, (?P<l2_ucast_bytes>\d+) bytes - mcast: (?P<l2_mcast_pkt>\d+) pkt, (?P<l2_mcast_bytes>\d+) ',
        #'  L3 in Switched: ucast: 138697005099 pkt, 166511592421731 bytes - mcast: 0 pkt, 0 bytes mcast',
        r'^\s+L3 in Switched: ucast: (?P<l3_in_ucast_pkt>\d+) pkt, (?P<l3_in_ucast_bytes>\d+) bytes .*mcast: (?P<l3_in_mcast_pkt>\d+) pkt, (?P<l3_in_mcast_bytes>\d+) ',
        #'  L3 out Switched: ucast: 112629132385 pkt, 59993629187096 bytes mcast: 0 pkt, 0 bytes', 
        r'^\s+L3 out Switched: ucast: (?P<l3_out_ucast_pkt>\d+) pkt, (?P<l3_out_ucast_bytes>\d+) bytes .*mcast: (?P<l3_out_mcast_pkt>\d+) pkt, (?P<l3_out_mcast_bytes>\d+) ',

        #'     146265544928 packets input, 167308815553548 bytes, 0 no buffer',
        r'\s+(?P<input_pkts>\d+) packets input, (?P<input_bytes>\d+) bytes, (?P<input_no_buffer>\d+) no buffer',
        #'     Received 14764021 broadcasts (0 IP multicasts)',
        r'\s+Received (?P<input_bcasts>\d+) broadcasts \((?P<input_ip_mcast>\d+) IP multicasts',
        #'     0 runts, 6380 giants, 0 throttles',
        r'\s+(?P<input_runts>\d+) runts, (?P<input_giants>\d+) giants, (?P<input_throttles>\d+) throttles',
        #'     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored',
        r'\s+(?P<input_errors>\d+) input errors, (?P<input_crc>\d+) CRC, (?P<input_frame_errors>\d+) frame, (?P<input_overrun>\d+) overrun, (?P<input_ignored>\d+) ignored',
        #'     0 watchdog, 0 multicast, 0 pause input',
        r'\s+(?P<input_watchdog>\d+) watchdog, (?P<input_mcast>\d+) multicast, (?P<input_pause>\d+) pause input',
        #'     0 input packets with dribble condition detected',
        r'\s+(?P<input_dribble>\d+) input packets with dribble condition detected',
        
        # #'     113214434454 packets output, 60416695779182 bytes, 0 underruns',
        r'\s+(?P<output_pkts>\d+) packets output, (?P<output_bytes>\d+) bytes, (?P<output_underruns>\d+) underruns',
        # #'     0 output errors, 0 collisions, 1 interface resets',
        r'\s+(?P<output_errors>\d+) output errors, ((?P<output_collisions>\d+) collisions, )?(?P<interface_resets>\d+) interface resets',
        # #'     0 babbles, 0 late collision, 0 deferred',
        r'\s+(?P<output_babbles>\d+) babbles, (?P<output_late_collisions>\d+) late collision, (?P<output_deferred>\d+) deferred',
        # #'     0 lost carrier, 0 no carrier, 0 PAUSE output',
        r'\s+(?P<lost_carrier>\d+) lost carrier, (?P<no_carrier>\d+) no carrier, (?P<pause_output>\d+) PAUSE output',
        # #'     0 output buffer failures, 0 output buffers swapped out']
        r'\s+(?P<output_buffer_failures>\d+) output buffer failures, (?P<output_buffers_swapped_out>\d+) output buffers swapped out',

    ]
    
    def _get( self, *args, **kwargs ):
        for d in self.prompt.tell_and_match_block( 'show int', self.port_regexes, output_wait=5, timeout=self.prompt.timeouts['medium'] ):
            logging.debug("="*80)
            if 'port' in d and d['port']:
                p = truncate_physical_port( d['port'] )
                d['port'] = p
                yield p, d


class StatsCiscoIos( Stats ):
    
    rfc2863 = Rfc2863CiscoIos
    

class CiscoIos( Device ):
    """
    Device definition for a generic cisco ios switch
    """
    prompt = PromptCiscoIos
    
    system = SystemCiscoIos
    stats = StatsCiscoIos
    ports = PortsCiscoIos
    portchannels = PortChannelsCiscoIos
    layer1 = Layer1CiscoIos
    layer2 = Layer2CiscoIos
    layer3 = Layer3CiscoIos

    def _validate( self ):
        for l in self.prompt.tell( 'show version '):
            # logging.error("> %s" % l)
            if match( r'^Cisco ', l ) and ( search( r'IOS', l ) or search( r'Internetwork Operating System', l ) ):
                # logging.error("OK")
                return True
            # FAT cisco access points have their own driver
            elif search( r' Radio', l ) or search( r' AIR-', l ):
                return False
        return False

    def validate( self ):
        logging.debug('validating...')
        if self._validate():
            return True
        # try again, as sometimes ios doesn't work first time
        elif self._validate():
            return True 
        raise IncompatibleDeviceException, 'not a cisco_ios'
