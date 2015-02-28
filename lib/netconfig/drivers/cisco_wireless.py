from netconfig.drivers.cisco_ios import PromptCiscoIos, ModelCiscoIos, FirmwareCiscoIos, PasswordCiscoIos, UsersCiscoIos, Layer1CiscoIos

from netconfig.drivers import Config, System, Device, IncompatibleDeviceException

from re import search, match
import logging


#######################################################################
# Cisco IOS Wireless Access Point
#######################################################################

class ModelCiscoIosWireless( ModelCiscoIos ):
    """
    Generic cisco wireless 'fat' access point
    """
    def get( self ):
        return [ m['model'] for m in self.parent.get() ]
        
class ConfigCiscoIosWireless( Config ):
    def get_running_config( self ):
        c = [ i.rstrip() for i in self.prompt.tell( 'show running-config ', cursor=self.prompt.cursor( 'mode', 'enable' ), timeout=self.prompt.timeouts['long'] ) ]
        if len(c) > 0:
            for x in xrange( 0, 3 ):
                c.pop(0)
            c.insert(0, '')
            return c

    def commit(self):
        return self.prompt.ask( 'copy running-config startup-config', cursor=self.prompt.cursor('mode','enable') )


class FirmwareCiscoWireless( FirmwareCiscoIos ):
    """
    Firmware components for a generic Cisco IOS switch
    """
    def firmware_filename( self, image, version ):
        # maps the image and version strings to a filename
        image = image.replace( '-m', '-' )
        if not image[-1] == '-':
            image = image + '-'
        return "%star.%s.tar" % (image, version)


class SystemCiscoIosWireless( System ):
    """
    Generic Cisco Fat AP System component
    """
    config = ConfigCiscoIosWireless
    model = ModelCiscoIosWireless
    firmware = FirmwareCiscoWireless
    password = PasswordCiscoIos
    users = UsersCiscoIos
    
    def get(self):
        info = {}
        for i in self.prompt.tell( 'show version' ):
            m = []
            # logging.debug(":> " + str(i))
            if m.append( match( r'Cisco IOS Software, C(\d+) Software \((?P<sw_image>(\w|\-)+)\), Version (?P<sw_version>(\w|\(|\)|\.)+), ', i ) ) or m[-1]:
                for k in ( 'sw_image', 'sw_version'):
                    info[k] = m[-1].group(k)
                # logging.debug("here! " + str(info))
            elif m.append( match( r'^cisco (?P<model>(\w|\-)+)\s+', i ) ) or m[-1]:
                info['model'] = m[-1].group('model')
                info['number'] = 1
        logging.debug("get: " + str(info))
        return [ info ]


    def reload( self, at=None ):
        for i in self.prompt.tell('reload', cursor=self.prompt.cursor('mode','enable') ):
            # logging.info(">> " + str(i))
            if self.prompt.current_cursor == self.prompt.cursor( 'interact', 'question' ):
                logging.info("enter question")

class CiscoWireless( Device ):
    """
    Generic Cisco Fat Access Point
    """
    prompt = PromptCiscoIos
    system = SystemCiscoIosWireless
    layer1 = Layer1CiscoIos
    
    def validate( self ):
        try:
            res = self.prompt.request( 'show version | inc cisco AIR-AP|AIR-SAP', cursor=[ self.prompt.cursor('mode','enable'), self.prompt.cursor('mode','exec') ], error_on_null_output=True )
            if res[0] == '':
                raise IncompatibleDeviceException, 'not a Cisco IOS Wireless device'
            else:
                return True
        except:
            raise IncompatibleDeviceException, 'not a Cisco IOS Wireless device'
