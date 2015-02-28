from netconfig.drivers.f5_bigpipe import PromptF5Bigpipe
from netconfig.drivers import Prompt, Config, System, Device, Module, FRU, DeviceException

from netconfig.Connector import SCP
from netconfig.backup.configuration import DeviceConfigurations

from re import match
import logging

#######################################################################
# F5 BigIP
#######################################################################


class ConfigF5Tmsh( Config ):
    def get(self):
        # only save save to get the config is via the binary produced from tmsh save sys, so we copy it over via scp
        remote_file = '/tmp/' + str(self.prompt.connector.host) + '_config.ucs'
        local_file = remote_file
        for l in self.prompt.tell( 'tmsh save sys ucs ' + str(remote_file), cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['long'] ):
            if match( str(remote_file)+' is saved.', l ):
                # copy over to here via scp
                try:
                    scp = SCP( self.prompt.connector.host, self.prompt.connector.user, self.prompt.connector.password, self.prompt.connector.enable_password, port=self.prompt.connector.port )
                    scp.connect( frm=remote_file, to=local_file )
                except Exception, e:
                    raise e
                finally:
                    self.prompt.ask( 'rm -rf ' + str(remote_file), cursor=self.prompt.cursor('mode','enable') )
                # todo check file exists
                dc = DeviceConfigurations( )
                dc.setConfig( local_file, config_type=self )
                return dc
        # fail
        raise DeviceException, 'could not get configuration file'
        
class ModuleF5Tmsh( Module ):
    regexes = [ '^(?P<slot>\d+)\s+(?P<ports>\d+)\s+(?P<description>.*)\s+(?P<model>N\dK\-\S+)\s+(?P<status>\S+)\s*', '^(?P<slot>\d+)\s+(?P<mac_ranges>\S+ to \S+)\s+(?P<hardware_version>\S+)\s+(?P<firmware_version>\S+)\s*$', '^(?P<slot>\d+)\s+(?P<software_version>\S+)\s+(?P<hardware_version>\S+)\s*$', '^(?P<slot>\d+)\s+(?P<diag_status>\S+)\s*$' ]
    
    def _get( self, *args, **kwargs ):
        for b in self.prompt.tell_and_get_block(
            'tmsh show sys hardware',
        ):
            logging.error("b: %s" % b)

        
        return
    
class FRUF5Tmsh( FRU ):
    module = ModuleF5Tmsh
        
class SystemF5Tmsh( System ):
    config = ConfigF5Tmsh
    fru = FRUF5Tmsh
    
class F5Tmsh( Device ):
    prompt = PromptF5Bigpipe
    system = SystemF5Tmsh
    
    def validate( self ):
        """
        try to run tmsh
        """
        return self.prompt.ask( 'tmsh sys version' )
