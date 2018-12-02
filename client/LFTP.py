# -*- coding: utf-8 -*-
import socket
import sys
import threading
from time import clock


class Client:

    def __init__(self):
        # Create a socket for use
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.MSSlen = 1000
        self.lockForBase = threading.Lock()
        self.rtrwnd = 0

        self.rtACK = 0
        self.clientSEQ = 0
        # the begin of window
        self.baseSEQ = 0
        # the next seq will be sent
        self.nextSEQ = 0
        # the size of window
        self.winSize = 10 * self.MSSlen

        self.drop_count = 0

    def sendSegment(self, SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, rtrwnd, data), (serverName, port))
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (serverName, port, SYN, ACK, SEQ, FUNC, rtrwnd))

    def reliableSendOneSegment(self, SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.sendSegment(SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data)
            self.fileSocket.settimeout(delayTime)
            try:
                rtSYN, self.rtACK, rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receiveSegment()

                # TCP construction
                if len(data) == 0 and self.rtACK == self.clientSEQ + 1:
                    dataComplete = True
                    self.clientSEQ = self.rtACK
                # File data
                elif len(data) != 0 and self.rtACK == self.clientSEQ + len(data):
                    dataComplete = True
                    self.clientSEQ = self.rtACK

            except socket.timeout as timeoutErr:
                # double the delay when time out
                delayTime *= 2
                self.drop_count += 1
                print(timeoutErr)

    def receiveSegment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rtrwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rtrwnd))
        return SYN, ACK, SEQ, FUNC, rtrwnd, data, addr

    def send_file(self, serverName, port, file, fileName):

        SYN = 0
        # ACK is useless so we set it as 0
        ACK = 0
        SEQ = self.clientSEQ
        FUNC = 1

        # split file into MSS
        # data buffer
        data = []
        data_size = 0
        print("begin to split file into MSS")
        while True:
            temp = file.read(self.MSSlen)
            data_size += len(temp)
            if temp == b'':
                break
            data.append(temp)
        print("finish")

        # send file name and data size to server for send
        print("send the file name and data size")
        self.reliableSendOneSegment(SYN, ACK, SEQ, FUNC, 0, serverName, port,
                                    b"%b %d" % (bytes(fileName, "UTF-8"), len(data)))

        # begin to send file
        print("send the file")
        self.baseSEQ = self.clientSEQ
        self.beginSEQ = self.clientSEQ
        delay_time = 3
        while True:
            init_time = clock()

            while (self.clientSEQ - self.baseSEQ) < self.winSize \
                    and (self.clientSEQ - self.beginSEQ) // self.MSSlen < len(data):
                temp_data = data[(self.clientSEQ - self.beginSEQ) // self.MSSlen]

                # flow control
                if self.clientSEQ + len(temp_data) - self.rtACK > self.rtrwnd:
                    break

                self.sendSegment(SYN, ACK, self.clientSEQ, 1, 0, serverName, port, temp_data)
                self.clientSEQ += len(temp_data)
                if self.rtACK >= self.baseSEQ:
                    self.baseSEQ = self.rtACK

            # flow control
            while self.clientSEQ + len(temp_data) - self.rtACK > self.rtrwnd \
                and (self.clientSEQ - self.beginSEQ) // self.MSSlen < len(data):
                print("flow control")
                # check rwnd of the receiver
                self.sendSegment(0, 0, self.clientSEQ, 2, 0, serverName, port, b"flow")
                try:
                    # update rwnd of the receiver
                    rtSYN, self.rtACK, rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receiveSegment()
                except socket.timeout as timeoutErr:
                    pass

            while True:
                if clock() - init_time > delay_time or self.clientSEQ == self.baseSEQ:
                    if self.clientSEQ != self.baseSEQ:
                        self.drop_count += (1 + (self.clientSEQ - self.beginSEQ) // self.MSSlen)
                        print("time out")
                    self.clientSEQ = self.baseSEQ
                    break
                self.fileSocket.settimeout(1)
                try:
                    rtSYN, self.rtACK, rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receiveSegment()
                    if self.rtACK >= self.baseSEQ:
                        self.baseSEQ = self.rtACK
                except socket.timeout as timeoutErr:
                    pass

            # finish data transmission
            if (self.baseSEQ - self.beginSEQ) // self.MSSlen == len(data):
                break

    def receiveFile(self, serverName, port, file, fileName):
        # TODO
        pass

    # If isSend is True, third handshake will include the file data
    # and the third handshake will be in charge of send_file function
    def handshake(self, serverName, port, isSend=False):
        # First handshake
        # For safety, seq is picked randomly
        SYN = 1
        ACK = 1
        SEQ = self.clientSEQ

        self.reliableSendOneSegment(SYN, ACK, SEQ, 0, 0, serverName, port)

        return True

    def goodbye(self, serverName, port):
        # TODO
        pass

if __name__ == "__main__":

    if len(sys.argv) != 5:
        print("Argument number should be 4 instead of %d" % (len(sys.argv) - 1))
        sys.exit(1)

    funcName = sys.argv[1]
    serverName = sys.argv[2]
    port = int(sys.argv[3])
    fileName = sys.argv[4]
    client = Client()

    if funcName == "lsend":
        with open(fileName, "rb") as file:
            # TCP construction
            if client.handshake(serverName, port, True):
                print("TCP construct successfully")
                client.send_file(serverName, port, file, fileName)
                print("%d packet have been dropped" % client.drop_count)
                client.goodbye(serverName, port)

    elif funcName == "lget":
        with open(fileName, "wb") as file:
            # TCP construction
            if client.handshake(serverName, port, False):
                print("TCP construct successfully")
                client.receiveFile(serverName, port, file, fileName)
    else:
        print("Your input parameter is wrong!")
