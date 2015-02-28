from netconfig.drivers import DeviceException, Prompt, Config, System, Device
from netconfig.backup.configuration import DeviceConfigurations

import logging

#######################################################################
# F5 BigIP
#######################################################################

class PromptF5Bigpipe( Prompt ):

    mode = {
        'exec'   : " \# ",
    }
    interact = {
        'pager': '\<\-\-\- More \-\-\-\>$',
    }
    error = {
        'tmsh_only': '/bin/bigpipe: bigpipe is no longer supported; please use tmsh.',
        'bigpipe_only': '-bash: tmsh: command not found'
    }
    
    # context_regex = r'^(?P<preamble>.*) (?P<context>.*)$'
    
    def mode_enable( self ):
        # no such thing on f5's
        pass

    def mode_exec( self ):
        # no such things on f5's
        pass
    
class ConfigF5Bigpipe( Config ):
    def get(self):
        c = []
        for l in self.prompt.tell( 'bigpipe export -', cursor=self.prompt.cursor('mode','exec'), timeout=self.prompt.timeouts['long'] ):
            # logging.debug("> " + str(l) )
            c.append(l)
        if len( c ):
            dc = DeviceConfigurations()
            dc.set_config( c, self )
            return dc
        raise DeviceException, 'could not get running configuration'
    
class SystemF5Bigpipe( System ):
    config = ConfigF5Bigpipe

class F5Bigpipe( Device ):
    prompt = PromptF5Bigpipe
    system = SystemF5Bigpipe
    
    def validate( self ):
        return self.prompt.ask( 'bigpipe system', output_wait=0.5)

        