import pysvn
client = pysvn.Client()
entry = client.info('.')
print 'Url:',entry.url
