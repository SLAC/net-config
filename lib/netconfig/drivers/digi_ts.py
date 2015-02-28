from netconfig.drivers import Prompt, Config, System, Device

#######################################################################
# Digi Terminal Server
#######################################################################

class PromptDigiTS( Prompt ):
    mode = {
        'exec'  : "\#\> ",
    }
    interact = {
        'pager' : '--More--$',
    }

class ConfigDigiTS( Config ):
    def get_running_config(self):
        c = [ l.rstrip() for l in self.prompt.tell( "cpconf term", cursor=self.prompt.cursor('mode','exec') ) ]
        if len( c ):
            return c
        return None

class SystemDigiTS( System ):
    config = ConfigDigiTS


class DigiTs( Device ):
    name = 'digi'
    prompt = PromptDigiTS
    system = SystemDigiTS