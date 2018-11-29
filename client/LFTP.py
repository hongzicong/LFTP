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
        self.clientSEQ = random.randint(0, 100)
        self.fileSocket.bind(("127.0.0.1", 9999))
        # SR
        self.MSSlen = 100
        self.winSize = 10 * self.MSSlen
        self.sendBase = 0
        self.nextSeq = 0
        self.lockForBase = threading.Lock()

    def sendSegment(self, SYN, ACK, SEQ, FUNC, serverName, port, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, data), (serverName, port))
        print(b"%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, data))

    def reliableSendSegment(self, SYN, ACK, SEQ, FUNC, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.sendSegment(SYN, ACK, SEQ, FUNC, serverName, port, data)

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

    def receiveSegnment(self):
        pass

    def sendFile(self, serverName, port, file, fileName):

        # data buffer
        data = []

        self.clientSEQ += 1

        SYN = 0
        # ACK is useless so we set it as 0
        ACK = 0
        SEQ = self.clientSEQ

        # send file name to server
        self.reliableSendSegment(SYN, ACK, SEQ, serverName, port, b"SEND %s" % bytes(fileName, "UTF-8"))

        # split file into MSS
        while True:
            temp = file.read(self.MSSlen)
            if temp == '':
                break
            data.append(bytes(temp, "UTF-8"))

        # send file
        while True:
            if self.nextSeq - self.sendBase < self.winSize and self.nextSeq < len(data):
                t = threading.Thread(target=self.reliableSendSegment(SYN, ACK, SEQ, serverName, port, data[self.nextSeq]))
                t.start()
                self.nextSeq += self.MSSlen
            # finish data transmission
            if self.sendBase >= len(data) * self.MSSlen:
                break
            # the main thread sleep for 0.5 second
            time.sleep(0.5)

    def receiveFile(self, serverName, port, file, fileName):
        pass

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
        with open(fileName, "r") as file:
            # TCP construction
            if client.handshake(serverName, defaultPort, True):
                print("TCP construct successfully")
                # client.sendFile(serverName, defaultPort, file, fileName)

    elif funcName == "lget":
        with open(fileName, "w") as file:
            # TCP construction
            if client.handshake(serverName, defaultPort, False):
                print("TCP construct successfully")
                client.receiveFile(serverName, defaultPort, file, fileName)
    else:
        print("Your input parameter is wrong!")
