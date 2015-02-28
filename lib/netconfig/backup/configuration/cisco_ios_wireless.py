from netconfig.backup.configuration import Configuration


class CiscoIosWireless( Configuration ):
    for_component = 'ConfigCiscoIOSWireless'

    comment_matches = [
        r' Last configuration change at (?P<last_change>.*) by (?P<user>.*)$',
        r' Last configuration change at (?P<last_change>.*)$',
        r'NVRAM config last updated at (?P<last_save>.*) by (?P<user>.*)$',
        r'NVRAM config last updated at (?P<last_save>.*)$',
        r' No configuration change since last restart',
        r'ntp clock-period',
        r'spanning-tree uplinkfast max-update-rate ',
    ]

    scrub_matches = [
        r'enable (secret|password) (\d )?(?P<redact>.*)',
        r'username (\w|\-|\.)+ (privilege \d+)\s*secret (\d )?(?P<redact>.*)',
        r'password (\d )?(?P<redact>\S+)',
        r'tacacs-server host (\d|\.)+ key (\d )?(?P<redact>.*)',
        r'snmp-server community (?P<redact>.*) .*',
        r'snmp-server user (?P<redact>\S+\s\S+) .*',
        # radius-server host 172.18.241.21 auth-port 1812 acct-port 1813 key 7 blah
        r'radius-server host (\d|\.)+ auth-port \d+ acct-port \d+ key (\d )?(?P<redact>.*)$',
        # wlccp ap username netdev password 7 blah
        r'wlccp ap username (\w|\.|\-) password (\d )?(?P<redact>.*)',
        r'user (\S+) nthash (\d) (?P<redact>.*)',
        r'nas (\S+) key (\d) (?P<redact>.*)',
    ]
