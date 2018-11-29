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

    def receiveSegnment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC = list(map(int, seg.split(b"*")[0:4]))
        data = seg[sum(map(len, seg.split(b"*")[0:4])) + 4:]
        print(len(data))
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC))
        return SYN, ACK, SEQ, FUNC, data, addr

    def sendSegment(self, SYN, ACK, SEQ, FUNC, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, data), self.addr)
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d" % (self.addr[0], self.addr[1], SYN, ACK, SEQ, FUNC))

    def reliableSendSegment(self, SYN, ACK, SEQ, FUNC, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.sendSegment(SYN, ACK, SEQ, FUNC, data)

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

    def receiveFile(self, fileName, data_size):
        beginACK = self.ACK
        with open(fileName, 'wb') as file:
            while True:
                rtSYN, rtACK, rtSEQ, rtFUNC, data, addr = self.receiveSegnment()
                if rtSEQ == self.ACK:
                    file.write(data)
                    self.ACK += len(data)
                    self.sendSegment(SYN, self.ACK, self.SEQ, rtFUNC)
                if self.ACK == data_size + beginACK:
                    print("finish receive file")
                    break

    def sendFile(self, file_name):
        with open(file_name, 'rb') as file:
            pass


class Server:

    def __init__(self):
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fileSocket.bind(('127.0.0.1', 5555))
        self.addr_info = {}

    def newInterface(self, addr, ACK, SEQ):
        #  New a buffer for the address
        clientInterface = Interface(self.fileSocket, addr, ACK, SEQ)
        self.addr_info[addr] = clientInterface

    def deleteInterface(self, addr):
        self.addr_info.pop(addr)

    def getInterface(self, addr):
        return self.addr_info[addr]

    def receiveSegment(self):
        seg, addr = self.fileSocket.recvfrom(1024)
        SYN, ACK, SEQ, FUNC = list(map(int, seg.split(b"*")[0:4]))
        data = seg.split(b"*")[4]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC))
        return SYN, ACK, SEQ, FUNC, data, addr


if __name__ == "__main__":

    print("============ Start LFTP server ============")
    server = Server()

    while True:
        SYN, ACK, SEQ, FUNC, data, addr = server.receiveSegment()

        # TCP construction : SYN is 1
        if SYN == 1 and addr not in server.addr_info:

            # Second hand shake
            rtACK = SEQ + 1
            rtSEQ = random.randint(0, 100)

            server.newInterface(addr, rtACK, rtSEQ)
            server.getInterface(addr).sendSegment(SYN, rtACK, rtSEQ, 0)

        # SYN is 0 and already TCP construction
        # FUNC 1
        elif FUNC == 1 and addr in server.addr_info:
            fileName = data.split(b" ")[0].decode("UTF-8")
            data_size = int(data.split(b" ")[1])
            print("receive file %s from %s:%s" % (fileName, addr[0], addr[1]))
            server.getInterface(addr).ACK = SEQ + len(data)
            server.getInterface(addr).sendSegment(SYN, server.getInterface(addr).ACK, server.getInterface(addr).SEQ, FUNC)
            server.getInterface(addr).receiveFile(fileName, data_size)
            server.deleteInterface(addr)

        # SYN is 0 and already TCP construction
        # FUNC 0
        elif FUNC == 0 and addr in server.addr_info:
            server.getInterface(addr).sendFile(data.split(b"*")[3])

    fileSocket.close()
