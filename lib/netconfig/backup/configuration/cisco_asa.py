from netconfig.backup.configuration import Configuration

    
class CiscoAsa( Configuration ):

    comment_matches = [
        r'Cryptochecksum:',
    ]
    scrub_matches = [
        r'(passwd|password) (?P<redact>.*) encrypted',
        r'enable password (?P<redact>.*) encrypted',
    ]
