from netconfig.backup.configuration import Configuration
    
class DigiConfiguration( Configuration ):
    for_component = 'ConfigDigiTS'
    
    def getCommentLineInfo( self ):
        array = []
        return array, None, None, None
        
        
