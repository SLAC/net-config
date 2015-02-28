from netconfig.drivers.cisco_ios import PromptCiscoIos, ModelCiscoIos
from netconfig.drivers import IncompatibleDeviceException, Config, System, Device

from re import search
import logging

#######################################################################
# Dell Switch
#######################################################################


class PromptDell8024( PromptCiscoIos ):

    mode = {
        'exec'      : ">$",
        'enable'    : "#$",
        'config'    : '\(config\)#',
        'config-if' : "\(config-if\)#",
    }

    interact = {
        'enable_password': 'Password:$',
        'pager'     : "\n--More-- or \(q\)uit.*$",  # pager (press space for more)
        'question'  : "Are you sure you want to save? (y/n) $",
    }
    
    error = {
        'input'     : "% Invalid input detected at '^' marker.",
        'incomplete': "% Incomplete command.",
        'denied'    : 'Incorrect Password\!',
    }

    flush_wait = 0.05
    output_wait = 0.1

    def terminal_buffer( self, size=0 ):
        pass

    def mode_exec( self ):
        n = 3
        while n > 0:
            if self.current_cursor == self.cursor( 'mode', 'exec' ):
                return True
            elif self.current_cursor in ( self.cursor( 'mode', 'enable' ), self.cursor('mode', 'config'), self.cursor('mode','config-if') ):
                self.ask('end')
            else:
                logging.debug('trying to move to ' + self.cursor('mode','exec') + ' from current prompt ' + self.current_cursor)
            n = n - 1
        logging.warn("dunno how to deal with " + str(self.current_cursor) + " to mode exec ")
        return False

    def mode_config( self ):
        # logging.warn("entering mode config")
        res = self.request( 'configure', cursor=self.cursor('mode','enable') )
        if self.current_cursor == self.cursor('mode','config'):
            return True
        return False


class ModelDell8024( ModelCiscoIos ):
    """
    Generic cisco wireless 'fat' access point
    """
    def get( self ):
        return [ i['model'] for i in self.parent.get() ]
        


class ConfigDell8024( Config ):
    def get_running_config(self):
        c = []
        for l in self.prompt.tell( 'show running-config', cursor=self.prompt.cursor('mode', 'enable') ):
            if not search( "\015\015", l ):
                c.append( l.rstrip() )
        if len(c) > 0:
            for j in xrange(0,3):
                c.pop(0)
            c.insert(0, '')
            return c
        return None
        
class SystemDell8024( System ):
    
    config = ConfigDell8024
    model = ModelDell8024
    
    def get( self ):
        info = []
        item = {}
        for i in self.prompt.tell( 'show system', cursor=[self.prompt.cursor('mode','exec'),self.prompt.cursor('mode','enable')] ):
            # logging.debug("> " + str(i))
            m = []
            if m.append( match(r'System Model ID: (?P<model>\w+)$', i) ) or m[-1]:
                model = m[-1].group('model')
                # logging.debug("  MODEL: '" + str(model) + "'")
                item['model'] = model
            # TODO: parse fans, power supplies and temp
        info.append(item)
        return info
            
class Dell( Device ):
    prompt = PromptDell8024
    system = SystemDell8024
    
    def validate( self ):
        logging.debug('validating...')
        i = 0
        while i < 2:
          res = self.prompt.request( 'show switch ')
          if search( r' PC8024F ', str(res) ):
              return True
          i = i + 1
        raise IncompatibleDeviceException, 'not a dell'