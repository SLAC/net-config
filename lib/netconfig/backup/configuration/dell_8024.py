from netconfig.backup.configuration import Configuration
        
class Dell8024( Configuration ):
    scrub_matches = [
        r'enable password (?P<redact>.*) encrypted',
    ]
