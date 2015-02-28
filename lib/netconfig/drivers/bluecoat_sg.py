from netconfig.drivers.cisco_ios import PromptCiscoIos
from netconfig.drivers import Config, System, Device, IncompatibleDeviceException


#######################################################################
# BlueCoat Proxy SG
#######################################################################

class PromptBluecoatSg( PromptCiscoIos ):
    mode = {
        'exec'      : ">",
        'enable'    : "#",
        'config'    : "#(config)", # hmmm.. this might not work
    }
    interact = {
        'pager': "--More--",
        'enable_password': 'Enable Password:$',
    }
    error = {
        'denied': '% Invalid password. Please try again.',
    }
    
    
class ConfigBluecoatSg( Config ):
    def get_running_config(self):
        c = [ l.rstrip() for l in self.prompt.tell( 'show configuration expanded noprompts', cursor=self.prompt.cursor('mode','enable') ) ][0:-1]
        if len(c):
            c.insert(0,'')
            return c
        return None
    def commit(self):
        pass


class SystemBluecoatSg( System ):
    config = ConfigBluecoatSg
    
class BluecoatSg( Device ):
    prompt = PromptBluecoatSg
    system = SystemBluecoatSg
