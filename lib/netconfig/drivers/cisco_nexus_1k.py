from netconfig.drivers.cisco_nexus import CiscoNexus
from netconfig.drivers import IncompatibleDeviceException

from re import compile, match, search, sub, DOTALL


#######################################################################
# Cisco Nexus 1k Vswitch
#######################################################################

class CiscoNexus1K( CiscoNexus ):
    # name = 'nexus1k'
    
    def validate( self ):
        if not self.prompt.ask( "show version | inc 'Virtual Supervisor Module'", cursor=[ self.prompt.cursor('mode','enable'), self.prompt.cursor('mode','exec') ], error_on_null_output=True ):
            raise IncompatibleDeviceException, 'Not a Cisco Nexus 1000v device'
        return True

