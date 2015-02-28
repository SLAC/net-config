# from netconfig.drivers.cisco_ios import RoutesCisco, PortsCiscoIos, FRUCiscoIos, SystemCiscoIos, ArpsCisco, VlanCiscoIos, Layer2CiscoIos, PortChannelsCiscoIos

from netconfig.drivers import Prompt, System, Config, Layer3, Layer2, Device, ComponentList
from re import compile, match, search, sub, DOTALL, finditer
import logging

#######################################################################
# Palo Alto 5060
#######################################################################


class PromptPaloAltoNetworks( Prompt ):

    mode = {
        'exec':     "> $",
        'config':   '# $',
        'enable':   "> $",
        # 'config-if': "\(config-(sub)?if\)#",
        # 'config-vlan':   '\((config-)?vlan\)#',
        # 'config-line': '\(config-line\)\#',
    }

    interact = {
        # 'enable_password': 'Password: ',
        'pager'     : '--more--$',  # pager (press space for more)
        # 'question'  : "\[.*\](\:|\?) $",
        # 'yes_no'    : "\? \[yes\/no\]\: $",
        # 'config_modified': 'System configuration has been modified\. Save\? \[yes\/no\]:', 
        # 'reload':   'Proceed with reload\? \[confirm\]',
        # 'default_answer': " considered\):",
    }
    
    error = {
        'command': "Unknown command: ",
        'input': "Invalid syntax.",
        # 'incomplete': "% Incomplete command.",
        # 'denied': '% Access denied',
    }


    def terminal_buffer( self, size=0 ):
        return self.ask( 'set cli pager off' )

    def mode_exec( self ):
        logging.error("MODE_EXEC")
        return True
    
    def mode_enable( self ):
        # no such mode
        return True        

    def mode_config( self ):
        # logging.warn("entering mode config")
        res = self.request( 'configure', cursor=self.cursor('mode','enable') )
        if self.current_cursor == self.cursor('mode','config'):
            return True
        return False


class ConfigPaloAltoNetworks( Config ):
    
    def get_running_config( self ):
        c = [ i.rstrip() for i in self.prompt.tell( 'show config running', cursor=self.prompt.cursor( 'mode', 'enable' ), timeout=self.prompt.timeouts['long'] ) ]
        if len(c) > 0:
            return c
        return None
    

class SystemPaloAltoNetworks( System ):
    
    config = ConfigPaloAltoNetworks
    # model = ModelCiscoIos
    # firmware = FirmwareCiscoIos
    # fru = FRUCiscoIos
    # password = PasswordCiscoIos
    # users = UsersCiscoIos
    
    def get(self):
        pass
        # c = []
        # members = []
        # m = []
        # item = { 'number': 0 }
        # for l in self.prompt.tell( 'show version', cursor=self.prompt.cursor( 'mode', 'enable' ), output_wait=0.03, timeout=self.prompt.timeouts['medium'] ):
        #     if search( r'^\*?\s+\d+\s+\d+', l ):
        #         stuff = l.split()
        #         # logging.debug("found " + str(stuff))
        #         if len(stuff) > 4:
        #             item = {
        #                 'sw_image': stuff.pop(),
        #                 'sw_version':   stuff.pop(),
        #                 'model':    stuff.pop(),
        #                 None: stuff.pop(),
        #                 'number':   int(stuff.pop()) - 1,
        #             }
        #             del item[None]
        #             members.append( item )
        #     elif m.append( search( r'cisco ((\w|\-)+) ', l ) ) or m[-1]:
        #         item['model'] = m[-1].group(1)
        #     elif m.append( search( r'^Cisco ((\w|\-)+) \(PowerPC\) processor', l ) ) or m[-1]:
        #         item['model'] = m[-1].group(1)                    
        #     elif m.append( search( r'^Cisco IOS Software, .* Software \((.*)\), Version (.*),', l ) ) or m[-1]:
        #         item['sw_image'] = m[-1].group(1)
        #         item['sw_version'] = m[-1].group(2)
        # # logging.debug('model info: ' + str(members))
        # return sorted( members, key=lambda k: k['number'] )



class PaloAltoNetworks( Device ):

    prompt = PromptPaloAltoNetworks
    system = SystemPaloAltoNetworks

    def validate(self):
        # deactivate paging
        self.prompt.terminal_buffer()
        if self.prompt.ask('show system info | match "model: PA-"' ):
            return True
        return False
