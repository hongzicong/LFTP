# -*- coding: utf-8 -*-
import socket
import random

class Server:

    def __init__(self):
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fileSocket.bind(('127.0.0.1', 5555))
        self.addr_info = {}

    def receiveSegment(self):
        return self.fileSocket.recvfrom(1024)

    def sendSegment(self, SYN, ACK, SEQ, addr):
        self.fileSocket.sendto(b"%d*%d*%d" % (SYN, ACK, SEQ), addr)

if __name__ == "__main__":

    print("============ Start LFTP server ============")
    server = Server()

    while True:
        data, addr = server.receiveSegment()

        # TCP construction : SYN is 1
        if data[0] == b'1':
            # Second hand shake
            SYN, ACK, SEQ = list(map(int, data.split(b"*")))
            ACK = SEQ + 1
            SEQ = random.randint(0, 100)

            #  New a buffer for the address
            server.addr_info[addr] = b""

            server.sendSegment(SYN, ACK, SEQ, addr)

        # SYN is 0
        elif data[0] == b'0':
            pass

    fileSocket.close()
