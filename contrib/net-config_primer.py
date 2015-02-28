#!/usr/local/bin/python2.7

# simple example of how to iterate through the trunks on a switch

from netconfig import NetConfig, config_file

# load default configuration files
config = config_file( '../etc/net-config/net-config.conf' )

# create a factory class 
factory = NetConfig( config )

# create a new network device
device = factory.get( 'swh-b050f1', options={} )

# initiate a connection to the device
device.connect()


# run the command with higher priv's (will auto move into mode)
answer = device.prompt.request( 'show run | inc hostname', cursor=device.prompt.cursor('mode','enable') )
print "HOST:\t" + str(answer)

# run a command on the device in the enable mode
answer = device.prompt.request( 'show version | inc uptime', cursor=device.prompt.cursor('mode','exec') )
print "UPTIME:\t" + str(answer)


# just run something, and see if there was an error
# note that because we moved into exec mode in the previous command, this will fail
answer = device.prompt.ask( 'show run | inc hostname' )
print "OK:\t" + str(answer)
# but this should be okay
answer = device.prompt.ask( 'show run | inc hostname', cursor=device.prompt.cursor('mode','enable') )
print "OK:\t" + str(answer)

# iterate through all of our ports
# this returns Port objects which are basically dict objects
#  keys of Port objects are: port (ie Gi1/0/1), alias, state, autoneg, speed, duplex, type, vlan, vlan_name
print "ALL PORTS:"
for i in device.ports.filter():
    print '  ' + str(i)

# get only those which are trunks; we can use any of the Port keys to filter
print "TRUNK PORTS:"
for i in device.ports.filter( type='trunk' ):
    print '  ' + str(i)

# we can change the stuff on the port with set( original_port, new_port )
# in this case we will change the alias on Gi3/0/1 to 'testing'
# the following are all equivalent
answer, state = device.ports.set( 'Gi3/0/1', { 'alias': 'testing'} )
print "SET:\t" + str(answer) + " -> " + str(state)
# device.ports.set( { 'port': 'Gi3/0/1'}, { 'port': 'Gi3/0/1', 'alias': 'testing'} )
# from netconfig.Device import Port
# device.ports.set( Port( { 'port': 'Gi3/0/1'} ), Port( { 'port': 'Gi3/0/1', 'alias': 'testing'} ) )



# disconnect from the device
device.disconnect()