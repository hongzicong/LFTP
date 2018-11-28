# -*- coding: utf-8 -*-
import socket
import sys
import random
import logging


class Client:

    def __init__(self):
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.clientSEQ = random.randint(0, 100)

    def sendSegment(self, SYN, ACK, SEQ, serverName, port, data = b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%b" % (SYN, ACK, SEQ, data), (serverName, port))
        print("send TCP %d*%d*%d*%s to %s:%s" % (SYN, ACK, SEQ, data, serverName, port))

    def receiveSegnment(self):
        pass

    def sendFile(self, serverName, port, file, fileName):

        MSSlen = 1000
        self.clientSEQ += 1

        while True:
            # MSS is 1000
            data = file.read(MSSlen)

            # End of file
            if data == "":
                return True

            SYN = 0
            # ACK is useless so we set it as 0
            ACK = 0
            SEQ = self.clientSEQ
            sendBase = 0

            dataComplete = False
            delayTime = 0.75
            while not dataComplete:
                self.sendSegment(SYN, ACK, SEQ, fileName + data[sendBase:MSSlen], serverName, port)

                self.fileSocket.settimeout(delayTime)
                try:
                    data, addr = self.fileSocket.recvfrom(1024)
                    SYN, ACK, SEQ = list(map(int, data.split(b"*")[0:3]))

                    # There are currently any not-yet-acknowledged segments
                    if ACK > self.clientSEQ + sendBase:
                        sendBase = ACK - self.clientSEQ
                    # The segment has been sent
                    elif ACK == self.clientSEQ + MSSlen:
                        dataComplete = True

                except socket.timeout as timeout:
                    # double the delay when time out
                    delayTime *= 2
                    print(timeout)

    def receiveFile(self, serverName, port, file, fileName):
        pass

    # If isSend is True, third handshake will include the file data
    # and the third handshake will be in charge of sendFile function
    def handshake(self, serverName, port, isSend = False):
        # First handshake
        # For safety, seq is picked randomly
        SYN = 1
        ACK = 1
        SEQ = -1

        firstComplete = False
        delayTime = 0.75
        while not firstComplete:
            self.sendSegment(SYN, ACK, self.clientSEQ, serverName, port)

            self.fileSocket.settimeout(delayTime)
            try:
                data, addr = self.fileSocket.recvfrom(1024)
                SYN, ACK, SEQ = list(map(int, data.split(b"*")[0:3]))

                if SYN == 1 and ACK == self.clientSEQ + 1:
                    firstComplete = True
                    self.serverSEQ = SEQ
            except socket.timeout as timeout:
                delayTime *= 2
                print(timeout)

        if not isSend:
            # Third handshake
            SYN = 0
            ACK = SEQ + 1
            self.clientSEQ += 1
            client.sendSegment(SYN, ACK, self.clientSEQ, serverName, port)

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
                client.sendFile(serverName, defaultPort, file)

    elif funcName == "lget":
        with open(fileName, "w") as file:
            # TCP construction
            if client.handshake(serverName, defaultPort, False):
                print("TCP construct successfully")
                client.receiveFile(serverName, defaultPort, file, fileName)
    else:
        print("Your input parameter is wrong!")
