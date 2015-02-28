from netconfig.drivers.cisco_ios import PromptCiscoIos
from netconfig.drivers import Config, System, Device, IncompatibleDeviceException

#######################################################################
# Cisco Topspin IB Switch
#######################################################################

class PromptCiscoTopspin( PromptCiscoIos ):
    mode = {
        'exec'      : "> ",
        'enable'    : "\# ",
        'config'    : "\(config\)\# ",
    }

    interact = {
        'pager'     : "Press any key to continue \(Q to quit\)",    
    }

    timeouts = {
        'login': 10,
        'short': 5,
        'medium': 15,
        'long': 60,
        'very_long': 600,
    }

class ConfigCiscoTopspin( Config ):
    def get_running_config( self ):
        c = [ i.rstrip() for i in self.prompt.tell( 'show config', cursor=self.prompt.cursor('mode','enable') ) ]
        if len(c):
            c.insert(0,'')
            return c
    def commit(self):
        return self.prompt.ask( 'copy running-config startup-config', cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['long'] )
        
class SystemCiscoTopspin( System ):
    config = ConfigCiscoTopspin

class CiscoTopspin( Device ):
    name = 'topspin'
    prompt = PromptCiscoTopspin
    system = SystemCiscoTopspin
