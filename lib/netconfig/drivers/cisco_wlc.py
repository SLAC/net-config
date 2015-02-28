from netconfig.drivers import Prompt, System, Config, Layer3, Layer2, Device, ComponentList

from re import compile, match, search, sub, DOTALL


#######################################################################
# Cisco Nexus
#######################################################################

class PromptCiscoWlc( Prompt ):
    
    mode = {
        'exec'   : " >$",
        'config' : " config>$",
    }
    interact = {
        'pager': '--More-- or \(q\)uit$',
        'question': '\(y\/n\) $'
    }
    error = {
        'syntax': 'Incorrect input\!',
        'usage': 'Incorrect usage.'
    }

    def __exit__(self):
        self.ask('logout', cursor=self.cursor('mode','exec') )

    def mode_enable( self ):
        pass

    def mode_config(self):
        return self.ask('config')

    def mode_exec( self ):
        if self.current_cursor == self.cursor('mode','config'):
            return self.ask('end')
        elif self.current_cursor == self.cursor('mode','exec'):
            return True
        else:
            raise Exception, 'dunno now to get to mode exec from %s' % (self.current_cursor,)
            
    def terminal_buffer( self, size=0 ):
        return self.ask( 'config paging disable' )

class ConfigCiscoWlc( Config ):
    def get_running_config( self ):
        c = []
        ok = False
        for i in self.prompt.tell( "show tech-support", cursor=self.prompt.cursor( 'mode', 'enable' ), timeout=self.prompt.timeouts['long'] ):
            if ok == None:
                ok = True
            i = i.strip()
            if i == '---------------Show run-config commands---------------':
                # skip this line, do next
                ok = None
            elif i == '---------------Show msglog---------------':
                ok = False
            if ok:
                c.append( i )
        if len(c):
            return c
        return None
        
    def commit(self):
        return self.prompt.ask( 'save config', timeout=self.prompt.timeouts['long'], output_wait=2 )

class SystemCiscoWlc( System ):
    config = ConfigCiscoWlc
    
    
class CiscoWlc( Device ):

    prompt = PromptCiscoWlc
    system = SystemCiscoWlc

    def validate(self):
        # deactivate paging?
        for l in self.prompt.tell('show sysinfo'):
            if search( 'Cisco Controller', l):
                return True
        return False
    
