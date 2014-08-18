import argparse
import os
import sys

import PollIOLoop
import TCPServer

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PCRF server.')
    parser.add_argument('--dict', dest='dict_file', required=True,
                        help='the file contain all avp infomation, such like encoding type and so on')
    parser.add_argument('--reply', dest='reply_file', default=None,
                        help='the file contain reply message')
    parser.add_argument('--port', dest='port', default=3868, type=int,
                        help='pcrf listen port')
    args = parser.parse_args()
    if not os.path.exists(args.dict_file):
        print "the avp dictionary file doesn't exist"
        sys.exit(1)
    if args.reply_file is not None and not os.path.exists(args.reply_file):
        print "the reply file doesn't exist"
        sys.exit(1)

    io_loop = PollIOLoop.PollIOLoop()
    io_loop.initialize()
    svr = TCPServer.TCPServer('0.0.0.0', args.port, io_loop, args.dict_file, args.reply_file)
    svr.listen(10)
    io_loop.start()
