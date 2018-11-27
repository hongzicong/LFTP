# -*- coding: utf-8 -*-
import socket
import random

if __name__ == "__main__":
    fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fileSocket.bind(('127.0.0.1', 5555))

    print("============ Start LFTP server ============")

    addr_info = {}

    while True:
        data, addr = fileSocket.recvfrom(1024)

        # TCP construction : SYN is 1
        if data[0] == b'1':
            # Second hand shake
            SYN, ACK, SEQ = list(map(int, data.split(b"*")))
            ACK = SEQ + 1
            SEQ = random.randint(-100, 100)

            #  New a buffer for the address
            addr_info[addr] = b""

            fileSocket.sendto(b"%d*%d*%d" % (SYN, ACK, SEQ), addr)

            receiveData, addr = fileSocket.recvfrom(1024)

        # SYN is 0
        if data[0] == b'0':
            pass

    fileSocket.close()
