# -*- coding: utf-8 -*-
import socket
import sys

if __name__ == "__main__":
    funcName = sys.argv[1]
    serverName = sys.argv[2]
    fileName = sys.argv[3]

    fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if funcName == "lsend":
        fileSocket.sendto("Hello world!", (serverName, 5555))
        receiveData = fileSocket.recv(1024).decode('utf-8')
        pass
    elif funcName == "lget":
        pass
    else:
        print("Your input parameter is wrong!")
