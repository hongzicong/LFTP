# -*- coding: utf-8 -*-
import socket
import sys
import random


class Client:

    def __init__(self, serverName):
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.defaultPort = 5555

    def sendSegment(self, SYN, ACK, SEQ):
        self.fileSocket.sendto(b"%d*%d*%d" % (SYN, ACK, SEQ), (serverName, self.defaultPort))

    def receiveSegnment(self):
        pass

    def handshake(self):
        # First handshake
        # For safety, seq is picked randomly
        SYN = 1
        ACK = 1
        SEQ = random.randint(0, 100)

        firstComplete = False
        while not firstComplete:
            self.sendSegment(SYN, ACK, SEQ)

            # * is the character used to split
            # datagram format: SYN * seq
            client.send(SYN, ACK, SEQ)

            # Third hand shake
            self.fileSocket.settimeout(1)
            try:
                data, addr = self.fileSocket.recvfrom(1024)
                SYN, ACK, SEQ = list(map(int, data.split(b"*")))

                if SYN == 1 and ACK == SEQ + 1:
                    firstComplete = True
            except socket.timeout as timeout:
                pass

        # Third handshake
        SYN = 0
        ACK, SEQ = SEQ, ACK
        ACK += 1
        client.sendSegment(SYN, ACK, SEQ)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Argument number should be 3 instead of %d" % (len(sys.argv) - 1))
        sys.exit(1)
    funcName = sys.argv[1]
    serverName = sys.argv[2]
    fileName = sys.argv[3]

    client = Client(serverName)

    if funcName == "lsend":
        with open(fileName, "r") as file:
            # TCP construction
            client.handshake()

    elif funcName == "lget":
        with open(fileName, "w") as file:
            pass
    else:
        print("Your input parameter is wrong!")
