import paramiko
import time
import pickle
import struct

#client = paramiko.SSHClient()
#client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#client.connect('10.153.7.110', 22, 'root', 'pass#$123')
#channel = client.invoke_shell()
#channel.send('cd work;python main.py --dict properties.xml\r')
#time.sleep(20)
info_str = pickle.dumps({'code': 272, 'flags': 123, 'avps': [{'name': 'Origin-Host', 'flags': 0x40, 'value': 'pcrf.bytemobile.com'}, {'name': 'Charging-Rule-Install', 'flags':0xc0, 'value': [ {'name': 'Charging-Rule-Base-Name', 'flags': 0xc0, 'value': 'policy1', 'vendor_id': 123}, {'name': 'Charging-Rule-Base-Name', 'flags': 0xc0, 'value': 'policy3', 'vendor_id': 123}  ]}]})
length = struct.pack('I', len(info_str))
with open('file.txt', 'a') as f:
    f.write(length + '\n' + info_str + '\n')

#channel.send(length + '\n' + info_str + '\n')
#time.sleep(200)
