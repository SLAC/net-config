from netconfig.drivers import Device, System, Prompt

#######################################################################
# HP 
#######################################################################

class PromptH3C( Prompt ):
    mode = {
        'exec': ">"
    }
    interact = {
        'pager': "  ---- More ----$",
    }

    def terminal_buffer( self, size=0 ):
        return self.ask('screen-length disable')
    
class SystemH3C( System ):
    def get_running_config(self):
        c = [ l.rstrip() for l in self.prompt.tell( 'display current', output_wait=2 ) ]
        if len(c):
            return c
        return None
        
class H3C( Device ):
    name = 'h3c'
    prompt = PromptH3C
    system = SystemH3C
