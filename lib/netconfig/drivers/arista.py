from netconfig.drivers.cisco_ios import PromptCiscoIos
from netconfig.drivers import Config, System, Device, IncompatibleDeviceException


from re import match, search

import logging

#######################################################################
# Arista
#######################################################################

class ConfigArista( Config ):
    def get_running_config(self):
        self.prompt.ask( 'term length 0')
        c = [ i.rstrip() for i in self.prompt.tell( 'show running-config', cursor=self.prompt.cursor( 'mode', 'enable' ), timeout=self.prompt.timeouts['long'] ) ]
        if len(c) > 0:
            c.pop()
            c.insert(0, '')
            return c
        return None
    
class SystemArista( System ):
    config = ConfigArista

class Arista( Device ):
    prompt = PromptCiscoIos
    system = SystemArista
    
    def validate( self ):
        ok = False
        for i in self.prompt.tell( 'show version | inc Arista '):
            if search( r'Arista ', i ):
                ok = True
        if not ok:
            raise IncompatibleDeviceException, 'not an arista'
        return ok