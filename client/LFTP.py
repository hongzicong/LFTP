# -*- coding: utf-8 -*-
import socket
import sys
import random


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

    def sendFile(self, serverName, port, file):
        pass

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
        while not firstComplete:
            self.sendSegment(SYN, ACK, self.clientSEQ, serverName, port)

            self.fileSocket.settimeout(3)
            try:
                data, addr = self.fileSocket.recvfrom(1024)
                SYN, ACK, SEQ = list(map(int, data.split(b"*")))

                if SYN == 1 and ACK == self.clientSEQ + 1:
                    firstComplete = True
            except socket.timeout as timeout:
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
            if client.handshake(serverName, defaultPort):
                print("TCP construct successfully")
                client.sendFile(serverName, defaultPort, file)

    elif funcName == "lget":
        with open(fileName, "w") as file:
            # TCP construction
            if client.handshake(serverName, defaultPort):
                print("TCP construct successfully")
                client.receiveFile(serverName, defaultPort, file, fileName)
    else:
        print("Your input parameter is wrong!")
