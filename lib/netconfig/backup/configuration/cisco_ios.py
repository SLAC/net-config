from netconfig.backup.configuration import Configuration

class CiscoIos( Configuration ):

    comment_matches = [
        r' Last configuration change at (?P<last_change>.*) by (?P<change_user>.*)$',
        r' Last configuration change at (?P<last_change>.*)$',
        r'NVRAM config last updated at (?P<last_save>.*) by (?P<save_user>.*)$',
        r'NVRAM config last updated at (?P<last_save>.*)$',
        r' No configuration change since last restart',
        r'ntp clock-period',
        r'spanning-tree uplinkfast max-update-rate ',
        r'ip sla low-memory ',
        r'scripting tcl low-memory ',
        r'subscribe-to-alert-group configuration periodic monthly ',
        r'^!Time: ',
    ]

    scrub_matches = [
        r'enable (secret|password) (\d+ )?(?P<redact>.*)$',
        r'secret (\d) (?P<redact>.*)$',
        #username net-admin secret 5 blah
        r'username (\w|\-|\.)+ secret (\d )?(?P<redact>.*)$',
        r'password \d? (?P<redact>\S+)',
        r'tacacs-server host (\d|\.)+ key (\d )?(?P<redact>.*)',
        r'tacacs-server key (\d+) (?P<redact>.*)',
        # snmp-server community blashdefault RO 20
        r'snmp-server community (?P<redact>.*) .*',
        r'snmp-server user (?P<redact>\S+\s\S+) .*',
        # snmp mib community-map blah engineid 800000090300000D2832CAC0
        r'snmp mib community-map (?P<redact>.*)(@\d+)? engineid .*',
        r'ip ospf message-digest-key (\d+) md5 (\d+) (?P<redact>.*)',
        r'key (\d+) (?P<redact>.*)',
        r'server-private (\S+) key (\d+ )?(?P<redact>.*)',
        r'standby (\d+) authentication md5 key-string (\d+ )?(?P<redact>.*)',
    ]
                
