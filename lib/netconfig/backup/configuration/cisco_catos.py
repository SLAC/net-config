from netconfig.backup.configuration import Configuration



class CiscoCATOSConfiguration( Configuration ):

    for_component = 'ConfigCiscoCATOSSwitch'
    stanza_prefix = None
    
    comment_matches = [
        r'#time: ',
    ]
    
    scrub_matches = [
        r'set (password|enablepass) (?P<redact>.*)',
        r'set tacacs key (?P<redact>.*)',
        r'set localuser user (\S+) password (?P<redact>.*) privilege (\d+)',
        r'set snmp community (read-only|read-write|read-write-all)\s+(?P<redact>.*)',
        r'enablepass (?P<redact>.*)',
    ]
    
