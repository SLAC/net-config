from slac_utils.time import now, sleep
import slac_utils.net

from re import search

import logging


def set_name_and_group( wlc, name, mac_address, apgroup, options={}, wait=200, delay=15 ):
    """ configure the supplied access point (mac address) to given name and apgroup on the wlc """
    
    if not wlc.is_connected():
        wlc.connect()

    # ensure we see the access point first
    found = False
    logging.debug( 'looking for access point with mac address %s' % (mac_address,) )
    for i in wlc.prompt.tell( 'show ap summary' ):
        logging.debug(" > %s" % (i,))
        if search( mac_address, i ):
            found = True
    if not found:
        raise Exception, 'access point %s not available on wireless controller' % (mac_address,)

    # config the ap name
    cmd = 'ap name %s %s' % (name, mac_address)
    logging.warn("CMD: %s" % cmd )
    if wlc.prompt.ask( cmd, cursor=wlc.prompt.cursor('mode','config') ):
        logging.debug( 'renamed access point %s to %s' % (mac_address,name,) )

    # TODO: not falling through....
        
    cmd = 'ap static-ip disable %s' % (name,)
    if wlc.prompt.ask( cmd, cursor=wlc.prompt.cursor('mode','config'), interact={ 'question': 'y', 'yes_no': 'y\n'} ):
        logging.debug( 'removed static-ip configuration from ap')

    # config group
    if wlc.prompt.ask( 'ap group-name %s %s' % (apgroup,name), cursor=wlc.prompt.cursor('mode','config'), interact={ 'question': 'y', 'yes_no': 'y\n'} ):
        logging.debug( 'configured access point for %s group, rebooting access-point...' % (apgroup,) )
    
    # make sure ap comes back up
    while wait > 0:
        for i in wlc.prompt.tell( 'show ap summary', cursor=wlc.prompt.cursor('mode','exec') ):
            if search( mac_address, i ):
                logging.debug('done')
                return True
        sleep( delay )
        wait = wait - delay

    raise Exception, 'the access point could not be found'
    
        
