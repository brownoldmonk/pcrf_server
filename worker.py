# coding=utf-8

import os
import struct
import argparse
import xml.etree.ElementTree as ET
import sys

import Diameter

diameter_code_dict = {'257': 'CEA', '280': 'DWR'}
diameter_head_id = os.getpid()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process diameter pacakgeh.')
    parser.add_argument('--dict', dest='dict_file', required=True,
                        help='the file contain all avp infomation, such like encoding type and so on')
    parser.add_argument('--reply', dest='reply_file', required=True,
                        help='the file contain reply message')
    args = parser.parse_args()
    tree = ET.parse(args.dict_file)
    root = tree.getroot()
    for chd in root:
        if not (chd.attrib['code'] in Diameter.avp_info_dict):
            Diameter.avp_info_dict[chd.attrib['code']] = {}
        Diameter.avp_info_dict[chd.attrib['code']][chd.text.strip()] = chd.attrib
        Diameter.avp_dict[chd.text.strip()] = chd.attrib['code']

    template = {}
    tree = ET.parse(args.reply_file)
    root = tree.getroot()
    for chd in root:
        info = chd.attrib
        info['avps'] = []
        for avp in chd:
            if len(avp):
                avp_info = avp.attrib
                avp_info['value'] = []
                for sub_avp in avp:
                    avp_info['value'].append(sub_avp.attrib)
                info['avps'].append(avp_info)
            else:
                info['avps'].append(avp.attrib)

        header, avp_data = Diameter.generate_pack(info)
        template[chd.tag] = {'header': header, 'avp': avp_data}
        if 'delay' in info:
            template[chd.tag]['delay'] = int(info['delay'])
        else:
            template[chd.tag]['delay'] = 0

        if 'enable' in info:
            template[chd.tag]['enable'] = info['enable'] == 'true'
        else:
            template[chd.tag]['enable'] = True

    while 1:
        data = os.read(0, 5)
        result = struct.unpack('Is', data)
        count = result[0]
        total_msg = ''
        while count > 0:
            count -= 1
            data = os.read(0, 8)
            result = struct.unpack('II', data)
            cmd_code = result[0]
            data = os.read(0, result[1]+2)
            data = struct.unpack(str(result[1]) + 's', data[1:-1])[0]
            #data = data.decode('hex')
            avp_info = {}
            reply_list = []
            flag = struct.unpack("!I", data[4:8])[0]
            flag = flag >> 24
            if not (flag & 0x80):
                continue
            # CCR
            if cmd_code == 272:
                # Session-Id, CC-Request-Type, CC-Request-Number, Destination-Realm, Destination-Host
                #avp_info = Diameter.get_info(data, [263, 416, 415, 283, 293])
                avp_info = Diameter.get_info(data, [263, 416, 415])
                ccr_value = Diameter.decode_avp_value(avp_info['416'])
                # CCR-I
                if ccr_value == 1:
                    if template['CCA-I']['enable']:
                        pack = template['CCA-I']['header'] + data[8:20]         \
                               + avp_info['263'] + avp_info['416'] + avp_info['415'] + template['CCA-I']['avp']
                        pack = Diameter.set_length(pack)
                        reply_list.append({'data': pack, 'timeout': template['CCA-I']['delay']})
                    #if template['RAR-U']['enable']:
                    #    diameter_head_id = (diameter_head_id + 1) & 0xFFFFFFFF
                    #    pack = template['RAR-U']['header'] + data[8:12]                                    \
                    #           + Diameter.get_next(diameter_head_id) + Diameter.get_next(diameter_head_id) \
                    #           + avp_info['283'] + avp_info['293'] + template['RAR-U']['avp']
                    #    pack = Diameter.set_length(pack)
                    #    reply_list.append({'data': pack, 'timeout': template['RAR-U']['delay']})
                    #if template['RAR-T']['enable']:
                    #    diameter_head_id = (diameter_head_id + 1) & 0xFFFFFFFF
                    #    pack = template['RAR-T']['header'] + data[8:12]                                    \
                    #           + Diameter.get_next(diameter_head_id) + Diameter.get_next(diameter_head_id) \
                    #           + avp_info['283'] + avp_info['293'] + template['RAR-T']['avp']
                    #    pack = Diameter.set_length(pack)
                    #    reply_list.append({'data': pack, 'timeout': template['RAR-T']['delay']})
            elif str(cmd_code) in diameter_code_dict:
                name = diameter_code_dict[str(cmd_code)]
                pack = template[name]['header'] + data[8:20] + template[name]['avp']
                pack = Diameter.set_length(pack)
                reply_list.append({'data': pack, 'timeout': template[name]['delay']})

            #msg = ''
            for item in reply_list:
                total_msg += struct.pack('II' + str(len(item['data'])) +  's', item['timeout'], len(item['data']), item['data'])
            #msg = struct.pack('I', len(msg)) + msg
                #sys.stderr.write(msg)
            #os.write(2, msg)

        sys.stderr.write(total_msg)



