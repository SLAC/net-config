from netconfig.drivers.cisco_ios import PromptCiscoIos
from netconfig.drivers import Config, Password, System, Device, IncompatibleDeviceException

from re import match, search
import logging

#######################################################################
# Cisco CATOS Switch
#######################################################################

class PromptCiscoCATOS( PromptCiscoIos ):
    mode = {
        'exec'  : '> $',
        'enable': '> \(enable\) $',
    }
    
    interact = {
        'enable_password': '(Enter )?(P|p)assword: $',
        'enter_old_password': 'Enter old password:',
        'retype_new_password': 'Retype new password:',
        'pager' : '--More--$',
    }

    error = {
        'input_error': "Unknown command \"",
        'no_file_or_dir': "\(No such file or directory\)",
    }

    output_wait = 0.02
    flush_wait = 0.02

    def terminal_buffer( self, length=0 ):
        return self.ask( 'set length ' + str(length) )


class ConfigCiscoCATOS( Config ):
    def get_running_config(self):
        config = []
        okay = False
        for l in self.prompt.tell( 'show config', cursor=self.prompt.cursor('mode','enable'), timeout=self.prompt.timeouts['long'] ):
            # strip out header (before begin)
            if match( '^begin', l ):
                okay = True
            if okay:
                config.append( l.rstrip() )
        return config
    def commit(self):
        # no need normally unless the config text is set
        return True

class PasswordCiscoCATOS( Password ):
    
    def _change_password( self, password, enable=True ):
        cmd = 'set password '
        if enable:
            cmd = 'set enablepassword '
        for l in self.prompt.ask( str(cmd) + str(password), cursor=self.prompt.cursor('mode','enable')):
            if self.prompt.current_cursor == self.prompt.cursor('interact','enter_old_password'):
                res = self.promopt.ask( self.connector.enable_password, preempt=False, suppress_command_output=True )
                if self.prompt.current_cursor == self.prompt.cursor( 'interact', 'retype_new_password' ):
                    res = self.promopt.ask( self.connector.enable_password, preempt=False, suppress_command_output=True )
                    if search( 'Password changed', res ):
                        return True
                    else:
                        return False
    
    def console_login( self, password, clear_existing=True ):
        return _change_password( password ) 
        
    def vty_login( self, password, clear_existing=True ):
        return _change_password( password )
            
    def login( self, user, password, level=15, clear_existing=True ):
        pass
        
    def enable( self, password, level=15, clear_existing=True ):
        return _change_password( password, enable=True )
    
    def snmp_ro(self, community, access_list=None, clear_existing=None ):
        cmd = 'set snmp community read-only ' + str(community)
        return self.prompt.ask( cmd, cursor=self.prompt.cursor('mode','enable') )

    def snmp_rw(self, community, access_list=None, clear_existing=None ):
        res = True
        for a in ( 'read-write', 'read-write-all'):
            cmd = 'set snmp community ' +str(a) + ' ' + str(community)
            res = res and self.prompt.ask( cmd, cursor=self.prompt.cursor('mode','enable') )
        return res

class SystemCATOS( System ):
    config = ConfigCiscoCATOS

class CiscoCatos( Device ):
    prompt = PromptCiscoCATOS
    system = SystemCATOS
