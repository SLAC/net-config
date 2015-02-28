import logging
from slac.pxssh import pxssh


f = open( '/afs/slac.stanford.edu/g/scs/net/cisco/config/etc/login.password' )
password = f.readline()
f.close()
password = password.rstrip()


prompt = "SWH-IBFARMCORE1> ";
prompt_en = "(SWH|swh)\-.*\#";
array_prompt = [ 'Password:', prompt, prompt_en, '\#' ]

# create connector
connector = pxssh()
_status = connector.login( 'swh-ibfarmcore1', 'super', password, login_timeout=3, original_prompts=prompt )
print "CONNECTED: " + str(_status)

print "Sending enable:"
connector.sendline( "enable" )
connector.send( '\x0d' )
i = connector.expect( array_prompt )
print "AFTER EXPECT: (" + str(i) + ") " + connector.before + ", after " + connector.after

print "Sending terminal:"
connector.sendline( "terminal length 0" )
connector.send( '\x0d' )
i = connector.expect( array_prompt )
print "AFTER EXPECT: (" + str(i) + ") " + connector.before + ", after " + connector.after


print "Sending show conf:"
connector.sendline( "show config" )
connector.send( '\x0d' )
i = connector.expect( array_prompt )
print "AFTER EXPECT: (" + str(i) + ") " + connector.before + ", after " + connector.after