from slac_utils.time import now, sleep
from datetime import timedelta
from pexpect import EOF
from netconfig.Connector import TimeoutException

from string import Template

import logging



class FirmwareHelper(object):

    def __init__( self, server, firmware ):
        self.server = server
        self.firmware = firmware
        
    def is_current( self, model, group, current_fw ):
        if not model in self.firmware:
            raise Exception, 'unregistered model %s' % (model)
        if not group in self.firmware[model]:
            raise Exception, 'unregistered group %s for model %s' % (group, model)
        
    def group( self, model, group ):
        if model in self.firmware:
            if group in self.firmware[model]:
                return self.firmware[model][group]
        return None
    
    def firmware_path( self, image_filename, model, group ):
        t = Template( self.server['firmware_path'] )
        d = self.server.copy()
        d['path'] = self.firmware[model][group]['path']
        return t.substitute( **d ) + image_filename
        

def reload_and_monitor( netconfig, device, options={}, wait=900, delay=15, message_per_loop='.' ):
    # reload it!
    try:
        yield 'reloading %s' % device.hostname
        device.system.reload()
    except EOF,e:
        # this error is fine
        pass
    except TimeoutException,e:
        pass

    # check to make sure it comes back up
    n = now()             
    try_until = n + timedelta( seconds=wait )
    success = False

    sleep( delay )
    while n < try_until:
        try:
            yield message_per_loop
            netconfig.connect( device, **options )
            success = True
            break
        except:
            pass
        sleep( delay )
        n = now()

    # darn!
    if not success:
        raise Exception, 'device did not come back up after firmware upgrade'

    yield 'device is back up'
    return
    


def upgrade_firmware( netconfig, device, group, release, fw_helper, options={}, dry_run=False, image_only=True ):
    """
    function to upgrade a device to registered firmware group and release versions
    """
    logging.info("setting firmware for %s to group %s (force release? %s)" % (device.hostname,group,release))
    upgradable = []
    
    # 0) log on to the device
    if not device.is_connected():
        netconfig.connect( device, **options )

    # 1) get the model
    models = device.system.get()
    # logging.debug("  models: %s" % (models,))
    if len( models ) < 1:
        raise Exception, 'could not determine hardware model numbers'

    upgrade = {}
    to_release = None
    for m in models:
        
        logging.debug("  model: %s" % (m,))
        stanza = fw_helper.group( m['model'], group )
        if not stanza:
            raise Exception, 'group %s is not registered for model %s' % (group,m['model'])
        logging.debug("  stanza: %s" % (stanza,))

        to_image = stanza['image'].lower()
        to_release_this = stanza['release']
        fm_image = m['sw_image'].lower()
        fm_release = m['sw_version']
        
        logging.debug("    (%s) %s -> (%s) %s/%s " % (fm_image,fm_release,to_image,to_release,to_release_this))
        
        # todo: check for version differences in to/frm            
        if to_release == None:
            to_release = to_release_this
        elif not to_release_this == to_release:
            raise Exception, 'cannot upgrade mixed stack to mixed firmware: %s' % (m,)
        to_release = to_release_this
        
        if not to_image == fm_image:
            logging.warn('changing image %s -> %s' % (fm_image,to_image))
            # raise Exception, 'running unregistered image %s' % (fm_image,)
            
        if not to_release == fm_release:
            this = {
                'model': m['model'],
                'image': to_image,
                'fm': fm_release,
                'to': to_release,
            }
            for i in ( 'number', ):
                if i in m:
                    this[i] = m[i]
            for i in ( 'file_image', ):
                if i in stanza:
                    this[i] = stanza[i]
            logging.debug("    %s" % (this,))
            upgradable.append(this)

    # fine!
    if len(upgradable) == 0:
        raise Exception, 'no firmware upgrade required'
        
    # 3) determine the firwmare to use for upgrade
    logging.debug("determining upgrade: %s" % (upgradable,))
    # need to flatten ie assume device knows how to upgrade all individual components
    for u in upgradable:
        # sometimes the name of the file is different to that of the running image
        i = u['image']
        if 'file_image' in u:
            i = u['file_image']
        f = device.system.firmware.firmware_filename( i, u['to'] )
        p = fw_helper.firmware_path( f, u['model'], group )
        upgrade[u['image']] = p
        
    if len(upgrade.keys()) == 0:
        raise Exception, 'no upgrades required'
        
    # 5) push the new firmware over
    logging.debug("images to transfer: %s" % (upgrade,))
    images = [ upgrade[i] for i in upgrade.keys() ]
    device.system.firmware.transfer_firmware_image( *images, dry_run=dry_run, image_only=image_only )

    # 4: check boot bits
    # device.system.firmware.check_boot_variable()
        
    return upgradable
    
