import os
import struct
import sys
import Diameter

def blocking_read(length):
    ret = ''
    done_len = 0
    todo_len = length
    while 1:
        chunk = os.read(0, todo_len)
        ret += chunk
        done_len += len(chunk)
        if done_len < length:
            todo_len = length - done_len
        else:
            break
    return ret

if __name__ == "__main__":
    buf = ''
    while 1:
        data = blocking_read(4)
        result = struct.unpack('I', data)
        data = blocking_read(result[0]+2)
        data = struct.unpack(str(result[0]) + 's', data[1:-1])[0]
        buf += data
        total_msg = ''
        while 1:
            count = 0
            msg = ''
            while count <= 100 and buf:
                cmd_code, length, pack = Diameter.parse(buf)
                if pack is None:
                    break

                msg += struct.pack('II' + str(length+2) + 's', cmd_code, length, '\n' + pack + '\n')
                buf = buf[length:]
                count += 1
            if count == 0:
                break
            msg = struct.pack('Is', count, '\n') + msg

            total_msg += struct.pack('I', len(msg)) + msg
            if not buf:
                break
            cmd_code, length, pack = Diameter.parse(buf)
            if pack is None:
                break
            #count += 1
            #if count > 3000:
            #    sys.stderr.write(total_msg)
            #    total_msg = ''


        if total_msg:
            sys.stderr.write(total_msg)
            #with open('debug', 'a') as f:
            #    f.write(repr(total_msg))
            #print len(msg)

