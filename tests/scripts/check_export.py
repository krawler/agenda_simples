import urllib.request
u = urllib.request.urlopen('http://127.0.0.1:8080/export')
print('status', u.getcode())
print('Content-Disposition:', u.getheader('Content-Disposition'))
print('Content-Length header:', u.getheader('Content-Length'))
data = u.read()
print('read bytes:', len(data))
open('export_test.json','wb').write(data)
print('saved to export_test.json')
