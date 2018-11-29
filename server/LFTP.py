# -*- coding: utf-8 -*-
import socket
import random
import logging
import threading


class Interface:

    def __init__(self, fileSocket, addr, ACK, SEQ):
        self.fileSocket = fileSocket
        self.addr = addr
        self.ACK = ACK
        self.SEQ = SEQ
        self.data = []
        self.lockForBase = threading.Lock()

    def sendSegment(self, SYN, FUNC, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%b" % (SYN, self.ACK, self.SEQ, FUNC, data), self.addr)
        print(b"%d*%d*%d*%d*%b" % (SYN, self.ACK, self.SEQ, FUNC, data))

    def reliableSendSegment(self, SYN, FUNC, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.sendSegment(SYN, FUNC, data)

            self.fileSocket.settimeout(delayTime)
            try:
                rtData, addr = self.fileSocket.recvfrom(1024)
                rtSYN, rtACK, rtSEQ, rtFUNC = list(map(int, rtData.split(b"*")[0:4]))

                # There are currently any not-yet-acknowledged segments
                if (len(data) == 0 and rtACK == SEQ + 1) or (len(data) != 0 and rtACK == SEQ + len(data)):
                    dataComplete = True
                    if FUNC == 1 and self.lockForBase.acquire():
                        if rtACK == self.sendBase + len(data) + 1:
                            self.sendBase += rtACK
                        self.lockForBase.release()

            except socket.timeout as timeoutErr:
                # double the delay when time out
                delayTime *= 2
                print(timeoutErr)


class Server:

    def __init__(self):
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fileSocket.bind(('127.0.0.1', 5555))
        self.addr_info = {}

    def newInterface(self, addr, ACK, SEQ):
        #  New a buffer for the address
        clientInterface = Interface(self.fileSocket, addr, ACK, SEQ)
        self.addr_info[addr] = clientInterface

    def getInterface(self, addr):
        return self.addr_info[addr]

    def receiveSegment(self):
        return self.fileSocket.recvfrom(1024)


if __name__ == "__main__":

    print("============ Start LFTP server ============")
    server = Server()

    while True:
        data, addr = server.receiveSegment()

        # TCP construction : SYN is 1
        if list(map(int, data.split(b"*")[0:3]))[0] == 1 and addr not in server.addr_info:

            # Second hand shake
            SYN, ACK, SEQ = list(map(int, data.split(b"*")[0:3]))
            ACK = SEQ + 1
            SEQ = random.randint(0, 100)

            server.newInterface(addr, ACK, SEQ)
            server.getInterface(addr).reliableSendSegment(SYN, 0)
            print("TCP construction successful")

        # SYN is 0 and already TCP construction
        elif list(map(int, data.split(b"*")[0:3]))[0] == 0 and addr in server.addr_info:
            if data.split(b"*")[3][0:4] == b"SEND":
                pass
            elif data.split(b"*")[3][0:5] == b"RECEIVE":
                pass
            else:
                pass

    fileSocket.close()
