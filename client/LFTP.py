# -*- coding: utf-8 -*-
import socket
import sys
import random
import logging
import threading
import time


class Client:

    def __init__(self):
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fileSocket.bind(("127.0.0.1", 9999))
        self.clientSEQ = 0

        self.MSSlen = 100
        self.winSize = 10 * self.MSSlen
        self.lockForBase = threading.Lock()

    def sendSegment(self, SYN, ACK, SEQ, FUNC, serverName, port, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, data), (serverName, port))
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d" % (serverName, port, SYN, ACK, SEQ, FUNC))

    def reliableSendSegment(self, SYN, ACK, SEQ, FUNC, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.sendSegment(SYN, ACK, SEQ, FUNC, serverName, port, data)

            self.fileSocket.settimeout(delayTime)
            try:
                rtSYN, rtACK, rtSEQ, rtFUNC, rtData, addr = self.receiveSegnment()

                # TCP construction
                if len(data) == 0 and rtACK == SEQ + 1:
                    dataComplete = True
                # File data
                elif len(data) != 0 and rtACK == SEQ + len(data):
                    dataComplete = True
                    '''
                    # Send file
                    if FUNC == 1 and self.lockForBase.acquire():
                        self.sendFlag[SEQ // self.MSSlen] = True
                        self.lockForBase.release()
                    '''

            except socket.timeout as timeoutErr:
                # double the delay when time out
                delayTime *= 2
                print(timeoutErr)

    def receiveSegnment(self):
        seg, addr = self.fileSocket.recvfrom(1024)
        SYN, ACK, SEQ, FUNC = list(map(int, seg.split(b"*")[0:4]))
        data = seg.split(b"*")[4]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC))
        return SYN, ACK, SEQ, FUNC, data, addr

    def sendFile(self, serverName, port, file, fileName):

        self.clientSEQ += 1

        SYN = 0
        # ACK is useless so we set it as 0
        ACK = 0
        SEQ = self.clientSEQ
        FUNC = 1

        # send file name to server for send
        print("send the file name")
        self.reliableSendSegment(SYN, ACK, SEQ, FUNC, serverName, port, bytes(fileName, "UTF-8"))
        self.clientSEQ += len(fileName)

        # split file into MSS
        # data buffer
        data = []
        beginSEQ = self.clientSEQ
        endSEQ = beginSEQ
        print("begin to split file into MSS")
        while True:
            temp = file.read(self.MSSlen)
            endSEQ += len(temp)
            if temp == b'':
                break
            data.append(temp)
        print("finish")

        # begin to send file
        self.sendBase = self.clientSEQ
        self.nextSEQ = self.clientSEQ
        while True:
            self.reliableSendSegment(SYN, ACK, self.nextSEQ, 1, serverName, port, data[(self.nextSEQ - beginSEQ) // self.MSSlen])
            self.clientSEQ += len(data[(self.nextSEQ - beginSEQ) // self.MSSlen])
            self.nextSEQ = self.clientSEQ
            # finish data transmission
            if self.nextSEQ >= endSEQ:
                break

    def receiveFile(self, serverName, port, file, fileName):

        # data buffer
        data = []

        self.clientSEQ += 1

        SYN = 0
        # ACK is useless so we set it as 0
        ACK = 0
        SEQ = self.clientSEQ
        FUNC = 0

        # send file name to server for receive
        self.reliableSendSegment(SYN, ACK, SEQ, FUNC, serverName, port, b"%s" % bytes(fileName, "UTF-8"))

    # If isSend is True, third handshake will include the file data
    # and the third handshake will be in charge of sendFile function
    def handshake(self, serverName, port, isSend=False):
        # First handshake
        # For safety, seq is picked randomly
        SYN = 1
        ACK = 1
        SEQ = self.clientSEQ

        self.reliableSendSegment(SYN, ACK, SEQ, 0, serverName, port)

        return True


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Argument number should be 3 instead of %d" % (len(sys.argv) - 1))
        sys.exit(1)
    funcName = sys.argv[1]
    serverName = sys.argv[2]
    fileName = sys.argv[3]
    defaultPort = 5555
    client = Client()

    if funcName == "lsend":
        with open(fileName, "rb") as file:
            # TCP construction
            if client.handshake(serverName, defaultPort, True):
                print("TCP construct successfully")
                client.sendFile(serverName, defaultPort, file, fileName)

    elif funcName == "lget":
        with open(fileName, "wb") as file:
            # TCP construction
            if client.handshake(serverName, defaultPort, False):
                print("TCP construct successfully")
                client.receiveFile(serverName, defaultPort, file, fileName)
    else:
        print("Your input parameter is wrong!")
