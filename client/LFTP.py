# -*- coding: utf-8 -*-
import socket
import sys
import threading

count = 0

class Client:

    def __init__(self):
        # Create a socket for use
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.clientSEQ = 0

        self.MSSlen = 1000
        self.winSize = 10 * self.MSSlen
        self.lockForBase = threading.Lock()
        self.rtrwnd = 0

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
                global count
                count += 1
                print(timeoutErr)

    def receiveSegment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rtrwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rtrwnd))
        return SYN, ACK, SEQ, FUNC, rtrwnd, data, addr

    def sendFile(self, serverName, port, file, fileName):

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
        begin = 0
        while True:
            # flow control
            while self.clientSEQ + len(data[begin]) - self.rtACK > self.rtrwnd:
                print("flow control")
                self.reliableSendOneSegment(SYN, ACK, self.clientSEQ, 1, 0, serverName, port)

            self.reliableSendOneSegment(SYN, ACK, self.clientSEQ, 1, 0, serverName, port, data[begin])
            begin += 1

            # finish data transmission
            if begin == len(data):
                break

    def receiveFile(self, serverName, port, file, fileName):
        # TODO
        pass

    # If isSend is True, third handshake will include the file data
    # and the third handshake will be in charge of sendFile function
    def handshake(self, serverName, port, isSend=False):
        # First handshake
        # For safety, seq is picked randomly
        SYN = 1
        ACK = 1
        SEQ = self.clientSEQ

        self.reliableSendOneSegment(SYN, ACK, SEQ, 0, 0, serverName, port)

        return True

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
                client.sendFile(serverName, port, file, fileName)
                print(count)

    elif funcName == "lget":
        with open(fileName, "wb") as file:
            # TCP construction
            if client.handshake(serverName, port, False):
                print("TCP construct successfully")
                client.receiveFile(serverName, port, file, fileName)
    else:
        print("Your input parameter is wrong!")
