import socket
import struct
import xml.etree.ElementTree as ET

# code as key, info value
avp_info_dict = {}
# name as key, code as value
avp_dict = {}
# name as key, code value
diameter_cmd_dict = {}
# code as key, name value

avp_dict_info = {}

def init_dict(dict_file):
    tree = ET.parse(dict_file)
    root = tree.getroot()
    for chd in root:
        name = chd.text.strip()
        if name not in avp_dict_info:
            avp_dict_info[name] = chd.attrib

def gen_reply(recv_pack, desc):
    flags = None
    if 'flags' in desc:
        flags = "%02X" % int(desc['flags'])
    else:
        flags = "%02X" % 0
    code = "%06X" % int(desc['code'])
    app_id = recv_pack[8:12].encode('hex')
    hop_by_hop_id = recv_pack[12:16].encode('hex')
    end_to_end_id = recv_pack[16:20].encode('hex')
    if 'app_id' in desc:
        app_id = "%08X" % int(desc['app_id'])
    if 'hop_by_hop_id' in desc:
        hop_by_hop_id = "%08X" % int(desc['hop_by_hop_id'])
    if 'end_to_end_id' in desc:
        end_to_end_id = "%08X" % int(desc['end_to_end_id'])
    avp_info = desc['avps']
    avp_list = []
    recv_code = struct.unpack("!I", recv_pack[:4])[0]
    # CCR
    if recv_code == 272:
        recv_info = get_info(recv_pack, [263, 416, 415])
        avp_list.append(recv_info['263'])
        avp_list.append(recv_info['416'])
        avp_list.append(recv_info['415'])

    for info in avp_info:
        dict_info = avp_dict_info[info['name']]
        avp_list.append(encode_avp_new(dict_info, info))

    body = ''.join(avp_list)
    length = len(body) + 20
    header = "01" + "%06X" % length + flags + code + app_id + hop_by_hop_id + end_to_end_id
    header = header.decode('hex')
    return header + body

def encode_avp_new(dict_info, info):
    avp_code = "%08X" % int(dict_info['code'])
    avp_flags = int(info['flags'])
    vendor_id = ''
    if 'vendor_id' in info:
        avp_flags |= 0x80
        vendor_id = "%08X" % int(info['vendor_id'])
    elif 'vendor_id' in dict_info:
        avp_flags |= 0x80
        vendor_id = "%08X" % int(dict_info['vendor_id'])
    flags = "%02X" % avp_flags
    data = ''
    total_len = 0
    if isinstance(info['value'], list):
        for sub_info in info['value']:
            sub_dict_info = avp_dict_info[sub_info['name']]
            data += encode_avp_new(sub_dict_info, sub_info)
        total_len = len(data)
    else:
        data = encode_avp_value(dict_info, info['value'])
        total_len = len(data)
        if len(data) % 4 != 0:
            data += '\00' * (4 - (len(data) % 4))

    total_len += 8 + len(vendor_id) / 2
    header = avp_code + flags + "%06X" % total_len + vendor_id
    header = header.decode('hex')
    return header + data



def parse(data):
    if len(data) < 40:
        return None, None, None
    length = struct.unpack("!I","\00" + data[1:4])[0]
    if len(data) < length:
        return None, None, None
    cmd_code = struct.unpack("!I","\00" + data[5:8])[0]
    msg = data[:length]
    return cmd_code, length, msg

def get_info(data, avp_cond):
    ret = {}
    avp = []
    avp_data = data[20:]
    while len(avp_data) != 0:
        slen = "\00" + avp_data[5:8]
        mlen = struct.unpack("!I", slen)[0]
        plen = (mlen + 3) & ~3
        code = struct.unpack("!I", avp_data[:4])[0]
        if code in avp_cond:
            avp_cond.remove(code)
            ret[str(code)] = avp_data[:plen]
            if not avp_cond:
                break
        avp_data = avp_data[plen:]
    return ret

def set_length(data):
    len_str = "%06X" % len(data)
    return data[:1] + len_str.decode('hex') + data[4:]

def encode_avp_value(avp_info, avp_value):
    avp_type = avp_info['type']
    ret = ''
    if   avp_type == 'UTF8String'         \
      or avp_type == 'OctetString'        \
      or avp_type == 'DiameterURI'        \
      or avp_type == 'DiameterIdentity':
        fs = "!" + str(len(avp_value)) + "s"
        ret = struct.pack(fs, str(avp_value))
    elif   avp_type == 'Unsigned32'       \
        or avp_type == 'Integer32'        \
        or avp_type == 'Enumerated':
        ret = struct.pack("!I", int(avp_value))
    elif avp_type == 'Time':
        seconds_between_1900_and_1970 = ((70*365)+17)*86400
        ret = struct.pack("!I", long(avp_value) + seconds_between_1900_and_1970)
    elif   avp_type == 'Unsigned64'       \
        or avp_type == 'Integer64':
        ret = struct.pack("!Q", long(avp_value))
    elif avp_type == 'Address':
        if avp_value.find('.') != -1:
            raw = socket.inet_pton(socket.AF_INET, avp_value);
            ret = struct.pack('!h4s', 1, raw)
        elif avp_value.find(':') != -1:
            raw = socket.inet_pton(socket.AF_INET6, avp_value);
            ret = struct.pack('!h16s', 2, raw)
    else:
        ret = avp_value

    return ret

def encode_avp(avp_info):
    total = ''
    if isinstance(avp_info, list):
        for item in avp_info:
            total += encode_avp(item)
        return total

    flags = 0
    vendor_id = ''
    avp_data = ''
    total_len = 0
    avp_code = avp_dict[avp_info['name']]
    if 'vendor' in avp_info and avp_info['vendor']:
        flags |= 0x80
        vendor_id = "%08X" % int(avp_info['vendor'])

    if 'vendor_id' in avp_info_dict[avp_code][avp_info['name']]:
        flags |= 0x80
        vendor_id = "%08X" % int(avp_info_dict[avp_code][avp_info['name']]['vendor_id'])
        vendor_id = vendor_id.decode('hex')

    #if 'mandatory' in avp_info and avp_info['mandatory']:
    flags |= 0x40

    if 'protected' in avp_info and avp_info['protected']:
        flags |= 0x20
    if isinstance(avp_info['value'], basestring):
        data = encode_avp_value(avp_info_dict[str(avp_code)][avp_info['name']], avp_info['value'])
        total_len = len(data)
        if len(data) % 4 != 0:
            data += '\00' * (4 - (len(data) % 4))
    else:
        data = encode_avp(avp_info['value'])
        total_len = len(data)

    total_len += 8
    if vendor_id:
        total_len += 4

    total = "%08X" % int(avp_code) + "%02X" % flags + "%06X" % total_len
    total = total.decode('hex')
    if vendor_id:
        total += vendor_id
    total += data
    return total


def generate_pack(pack_info):
    flags = 0
    if 'Request' in pack_info and pack_info['Request']:
        flags |= 0x80
    if 'Proxiable' in pack_info and pack_info['Proxiable']:
        flags |= 0x40
    if 'Error' in pack_info and pack_info['Error']:
        flags |= 0x20
    if 'Re-transmitted' in pack_info and pack_info['Re-transmitted']:
        flags |= 0x10
    header = "01" + "%06X" % 0 + "%02X" % flags + "%06X" % int(pack_info['code'])
    avp_list = []
    for avp in pack_info['avps']:
        avp_list.append(encode_avp(avp))

    return header.decode('hex'), ''.join(avp_list)

def decode_avp_value(avp_pack):
    avp_code = struct.unpack("!I", avp_pack[:4])[0]
    flag_and_len = struct.unpack("!I", avp_pack[4:8])[0]
    flag = flag_and_len >> 24
    data = avp_pack[8:]
    vendor_id = None
    avp_type = ''
    if flag & 0x80:
        data = avp_pack[12:]
        vendor_id = struct.unpack("!I", avp_pack[4:12])[0]

    for key, value in avp_info_dict[str(avp_code)].items():
        if    'vendor_id' in value \
          and vendor_id is not None    \
          and value['vendor_id'] == str(vendor_id):
            avp_type = avp_info_dict[str(avp_code)][key]['type']
            break
        elif vendor_id is None:
            avp_type = avp_info_dict[str(avp_code)][key]['type']
            break
    ret = ''
    if   avp_type == 'Unsigned32'       \
        or avp_type == 'Integer32'        \
        or avp_type == 'Enumerated':
        ret = struct.unpack("!I", data)[0]
    else:
        ret = data

    return ret


