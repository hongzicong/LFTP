# -*- coding: utf-8 -*-
import socket
import random
import threading


class Interface:

    def __init__(self, fileSocket, addr, ACK, SEQ):
        self.fileSocket = fileSocket
        self.addr = addr
        self.MSSlen = 1000

        self.rtSEQ = 0
        self.rtACK = 0
        self.ACK = ACK
        self.SEQ = SEQ

        self.drop_count = 0
        self.lockForBuffer = threading.Lock()
        self.buffer = {}
        self.buffer_size = 20 * self.MSSlen

        self.rwnd = self.buffer_size
        self.rtrwnd = 0

        # the size of congestion window
        self.cwnd = 1 * self.MSSlen

        # seg begin to send file
        self.beginSEQ = 0

    def receive_segment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rtrwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rtrwnd))
        return SYN, ACK, SEQ, FUNC, rtrwnd, data, addr

    def send_segment(self, SYN, ACK, SEQ, FUNC, rwnd, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, rwnd, data), self.addr)
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rwnd: %d" % (self.addr[0], self.addr[1], SYN, ACK, SEQ, FUNC, rwnd))

    def reliable_send_one_segment(self, SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.send_segment(SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data)
            self.fileSocket.settimeout(delayTime)
            try:
                rtSYN, self.rtACK, self.rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receive_segment()

                # TCP construction
                if len(data) == 0 and self.rtACK == self.clientSEQ + 1:
                    dataComplete = True
                    self.clientSEQ = self.rtACK
                # File data
                elif len(data) != 0 and self.rtACK == self.clientSEQ + len(data):
                    dataComplete = True
                    self.clientSEQ = self.rtACK

            except socket.timeout as timeoutErr:
                # double the delay when time out
                delayTime *= 2
                self.drop_count += 1
                print(timeoutErr)

    def read_into_file(self, file_name, data_size):
        begin = 0
        end = data_size
        with open(file_name, 'wb') as file:
            while True:
                if begin == end:
                    print("finish write to file successfully")
                    break

                while begin in self.buffer:
                    if self.lockForBuffer.acquire():
                        print("read from buffer write into file")
                        file.write(self.buffer[begin])
                        data_len = len(self.buffer[begin])
                        self.buffer.pop(begin)
                        self.rwnd += data_len
                        begin += 1
                        self.lockForBuffer.release()

    def receive_file(self, file_name, data_size):
        self.beginACK = self.ACK
        self.lastACKRead = self.ACK

        file_thread = threading.Thread(target=self.read_into_file, args=(file_name, data_size,), name="fileThread")
        file_thread.start()

        begin = 0
        end = data_size
        while True:
            rtSYN, rtACK, rtSEQ, rtFUNC, rtrwnd, data, addr = self.receive_segment()
            if data == b"":
                self.send_segment(rtSYN, rtSEQ + 1, self.SEQ, rtFUNC, self.rwnd)
                continue
            if rtFUNC == 2:
                self.send_segment(rtSYN, rtSEQ, self.SEQ, rtFUNC, self.rwnd)
                continue
            # write to the buffer only when receiver need
            if self.ACK == rtSEQ:
                if self.lockForBuffer.acquire():
                    self.buffer[begin] = data
                    begin += 1
                    self.rwnd -= len(data)
                    self.lockForBuffer.release()
                    self.ACK = rtSEQ + len(data)
            # answer
            self.send_segment(rtSYN, self.ACK, 0, rtFUNC, self.rwnd)
            if begin == end:
                print("finish receive file successfully")
                break

    def send_file(self, file_name):
        with open(file_name, 'rb') as file:
            pass

class Server:

    def __init__(self):
        # Create a socket for use
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.fileSocket.bind((socket.gethostbyname(socket.gethostname()), 5555))

        self.fileSocket.setblocking(True)

        self.addr_info = {}

    def new_interface(self, addr, ACK, SEQ):
        #  New a buffer for the address
        clientInterface = Interface(self.fileSocket, addr, ACK, SEQ)
        self.addr_info[addr] = clientInterface

    def delete_interface(self, addr):
        self.addr_info.pop(addr)

    def get_interface(self, addr):
        return self.addr_info[addr]

    def receive_segment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rwnd))
        return SYN, ACK, SEQ, FUNC, rwnd, data, addr

    def listen(self):
        while True:
            SYN, ACK, SEQ, FUNC, rwnd, data, addr = self.receive_segment()

            # TCP construction : SYN is 1
            if SYN == 1 and addr not in self.addr_info:

                # Second hand shake
                rtACK = SEQ + 1
                rtSEQ = random.randint(0, 100)

                self.new_interface(addr, rtACK, rtSEQ)
                self.get_interface(addr).send_segment(SYN, rtACK, rtSEQ, 0, self.get_interface(addr).buffer_size)

            # SYN is 0 and already TCP construction
            # FUNC 1
            elif FUNC == 1 and addr in server.addr_info:
                file_name = data.split(b" ")[0].decode("UTF-8")
                data_size = int(data.split(b" ")[1])
                print("receive file %s from %s:%s" % (file_name, addr[0], addr[1]))
                self.get_interface(addr).ACK = SEQ + len(data)
                self.get_interface(addr).send_segment(SYN, self.get_interface(addr).ACK, self.get_interface(addr).SEQ,
                                                      FUNC, self.get_interface(addr).buffer_size)
                self.get_interface(addr).receive_file(file_name, data_size)
                self.delete_interface(addr)

            # SYN is 0 and already TCP construction
            # FUNC 0
            elif FUNC == 0 and addr in self.addr_info:
                self.get_interface(addr).send_file(data.split(b"*")[3])

        fileSocket.close()

if __name__ == "__main__":

    print("============ Start LFTP server ============")
    server = Server()
    server.listen()
