from netconfig.backup.configuration import Configuration
        
        
class Arista( Configuration ):
    scrub_matches = [
        r'secret (\d+) (?P<redact>.*)',
        r'password-label (?P<redact>.*)',
        r'key "(?P<redact>.*)"',
    ]
    
