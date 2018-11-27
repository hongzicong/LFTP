# -*- coding: utf-8 -*-
import socket
import sys
import random

def sendFile(file):
    pass

def receiveFile():
    pass

def startTimer():
    pass

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Argument number should be 3 instead of %d" % (len(sys.argv) - 1))
        sys.exit(1)
    funcName = sys.argv[1]
    serverName = sys.argv[2]
    fileName = sys.argv[3]
    defaultPort = 5555

    fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if funcName == "lsend":
        with open(fileName, "r") as file:
            # TCP construction
            # First hand shake
            # For safety, seq is picked randomly
            SYN = 1
            ACK = 1
            SEQ = random.randint(-100, 100)

            # * is the character used to split
            # datagram format: SYN * seq
            fileSocket.sendto(b"%d*%d*%d" % (SYN, ACK, SEQ), (serverName, defaultPort))

            # Third hand shake
            data, addr = fileSocket.recvfrom(1024)
            SYN, ACK, SEQ = list(map(int, data.split(b"*")))
            SYN = 0
            ACK, SEQ = SEQ, ACK
            ACK += 1
            fileSocket.sendto(b"%d*%d*%d*%s" % (SYN, ACK, SEQ))

            sendFile(file)
    elif funcName == "lget":
        with open(fileName, "w") as file:
            fileSocket.sendTo("hello", (serverName, defaultPort))
            receiveData, addr = fileSocket.recvfrom(1024).decode('utf-8')
            receiveFile(file)
    else:
        print("Your input parameter is wrong!")
