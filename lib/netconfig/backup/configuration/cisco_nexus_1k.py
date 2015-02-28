from netconfig.backup.configuration import Configuration


class CiscoNexus1kConfiguration( Configuration ):
    for_component = 'ConfigCiscoNexus1k'
    
    scrub_matches = [
        # username admin password 5 blah role network-admin
        r'username (\w|\-|\_)+ password (\d )?(?P<redact>.*) role .*',
        # snmp-server user admin network-admin auth md5 blah priv 0x45d9cf93e35d0990172881d82842c115 localizedkey
        r'snmp-server user (\w|\-|\_)+ (\w|\-|\_)+ auth md5 (?P<redact>.*) priv .* localizedkey',
        r'snmp-server user (\S+) md5 (?P<redact>.*) priv (\S+) localizedkey',
        r'snmp-server user (\S+) md5 (\S+) priv (?P<redact>.*) localizedkey',
    ]
    