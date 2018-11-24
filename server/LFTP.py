# -*- coding: utf-8 -*-
import socket


if __name__ == "__main__":
    fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fileSocket.bind(('127.0.0.1', 5555))
    while True:
        data, addr = fileSocket.recvfrom(1024)
        fileSocket.sendto(b'Hello!', addr)
    fileSocket.close()
