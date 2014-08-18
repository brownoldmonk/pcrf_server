import Diameter
Diameter.init_dict('properties.xml')
x = '\x01\x00\x00\xec\x80\x00\x01\x10\x00\x00\x00\x00S\xe1\xd6\xf2+x\x80\x01\x00\x00\x01\x08@\x00\x00\x1bpgw.myrealm.example\x00\x00\x00\x01\x07@\x00\x00;pgw.myrealm.example;1094791309121_1385989500_428022\x00\x00\x00\x00\x1e@\x00\x00\x10test.apn\x00\x00\x01(@\x00\x00\x17myrealm.example\x00\x00\x00\x01\x1b@\x00\x00\x17myrealm.example\x00\x00\x00\x01%@\x00\x00\x1cpcrf.myrealm.example\x00\x00\x01\x02@\x00\x00\x0c\x01\x00\x00\x16\x00\x00\x01\xa0@\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x01\x9f@\x00\x00\x0c\x00\x00\x00\x00'
info = {u'avps': [{u'flags': 64, u'name': u'Origin-Host', u'value': u'pcrf.bytemobile.com'}, {u'flags': 192, u'name': u'Charging-Rule-Install', u'value': [{u'vendor_id': 123, u'flags': 192, u'name': u'Charging-Rule-Base-Name', u'value': u'policy1'}, {u'vendor_id': 123, u'flags': 192, u'name': u'Charging-Rule-Base-Name', u'value': u'policy3'}]}], u'code': 272, u'flags': 123}
reply = Diameter.gen_reply(x, info)
print repr(reply)
