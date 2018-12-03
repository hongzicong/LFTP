# -*- coding: utf-8 -*-
import socket
import threading
import time
import math


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
        self.ssthresh = 8 * self.MSSlen

        # seg begin to send file
        self.beginSEQ = 0

    def receive_segment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rtrwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rtrwnd))
        return SYN, ACK, SEQ, FUNC, rtrwnd, data, addr

    def send_segment(self, SYN, ACK, SEQ, FUNC, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, self.rwnd, data), self.addr)
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rwnd: %d" % (self.addr[0], self.addr[1], SYN, ACK, SEQ, FUNC, self.rwnd))

    def reliable_send_one_segment(self, SYN, FUNC, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.send_segment(SYN, self.ACK, self.SEQ, FUNC, data)
            self.fileSocket.settimeout(delayTime)
            try:
                rtSYN, self.rtACK, self.rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receive_segment()

                # TCP construction
                if len(data) == 0 and self.rtACK == self.SEQ + 1:
                    dataComplete = True
                    self.SEQ = self.rtACK
                    self.ACK = self.rtSEQ + 1
                # File data
                elif len(data) != 0 and self.rtACK == self.SEQ + len(data):
                    dataComplete = True
                    self.SEQ = self.rtACK
                    self.ACK = self.rtSEQ + len(data)

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
                        self.rwnd += len(self.buffer[begin])
                        self.buffer.pop(begin)
                        begin += 1
                        self.lockForBuffer.release()

    def receive_file(self, file_name, data_size):

        self.send_segment(0, self.ACK, self.SEQ, 1)

        self.beginACK = self.ACK
        self.lastACKRead = self.ACK

        file_thread = threading.Thread(target=self.read_into_file, args=(file_name, data_size,), name="fileThread")
        file_thread.start()

        begin = 0
        end = data_size
        while True:
            rtSYN, self.rtACK, self.rtSEQ, rtFUNC, rtrwnd, data, addr = self.receive_segment()
            if data == b"":
                self.ACK = self.rtSEQ + 1
            elif rtFUNC == 2:
                self.ACK = self.rtSEQ
            # write to the buffer only when receiver need
            elif self.ACK == self.rtSEQ:
                if self.lockForBuffer.acquire():
                    self.buffer[begin] = data
                    begin += 1
                    self.rwnd -= len(data)
                    self.ACK = self.rtSEQ + len(data)
                    self.lockForBuffer.release()
            # answer
            self.send_segment(rtSYN, self.ACK, self.SEQ, rtFUNC)
            if begin == end:
                print("finish receive file successfully")
                break

    def send_file(self, file_name):
        with open(file_name, 'rb') as file:

            # split file into MSS
            # data buffer
            data = []
            data_size = 0
            print("begin to split file into MSS")
            while True:
                temp = file.read(self.MSSlen)
                data_size += len(temp)
                if temp == b'':
                    break
                data.append(temp)
            print("finish")
            print(len(data))
            self.send_segment(0, self.ACK, self.SEQ, 0, b"%d" % len(data))

            # begin to send file
            print("send the file")
            self.beginSEQ = self.SEQ
            delay_time = 2
            self.cwnd = 1 * self.MSSlen
            self.ssthresh = 8 * self.MSSlen
            fastACK = 0
            dupACKcount = 0
            while True:
                init_time = time.time()

                # pipeline
                while (self.SEQ - self.rtACK) < min(self.cwnd, self.rtrwnd) \
                        and math.ceil((self.SEQ - self.beginSEQ) / self.MSSlen) < len(data):
                    temp_data = data[(self.SEQ - self.beginSEQ) // self.MSSlen]
                    self.send_segment(0, self.ACK, self.SEQ, 1, temp_data)
                    self.SEQ += len(temp_data)

                # flow control
                if self.SEQ - self.rtACK >= self.rtrwnd:
                    print("flow control")
                    # check rwnd of the receiver
                    self.send_segment(0, self.ACK, self.SEQ, 2, b"flow")

                # set timer
                self.fileSocket.settimeout(1)
                while True:
                    try:
                        rtSYN, self.rtACK, rtSEQ, rtFUNC, self.rtrwnd, self.rtData, addr = self.receive_segment()
                        # new ACK
                        if self.rtACK != fastACK:
                            self.cwnd = self.ssthresh
                            fastACK = self.rtACK
                            dupACKcount = 0
                        else:
                            dupACKcount += 1
                            if dupACKcount == 3:
                                self.ssthresh = self.cwnd / 2
                                self.cwnd = self.ssthresh + 3 * self.MSSlen
                    except socket.timeout as timeoutErr:
                        pass
                    if self.SEQ == self.rtACK:
                        if self.cwnd < self.ssthresh:
                            print("slow start")
                            self.cwnd *= 2
                        else:
                            print("congestion avoidance")
                            self.cwnd += 1 * self.MSSlen
                        self.SEQ = self.rtACK
                        break
                    elif time.time() - init_time > delay_time:
                        self.drop_count += (1 + (self.SEQ - self.rtACK) // self.MSSlen)
                        print("time out")
                        self.SEQ = self.rtACK
                        self.ssthresh = self.cwnd / 2
                        self.cwnd = 1 * self.MSSlen
                        break

                # finish data transmission
                if math.ceil((self.rtACK - self.beginSEQ) / self.MSSlen) == len(data):
                    break


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
        print("delete the interface")
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
            self.fileSocket.setblocking(True)
            SYN, ACK, SEQ, FUNC, rwnd, data, addr = self.receive_segment()
            self.fileSocket.setblocking(False)

            # TCP construction : SYN is 1
            if SYN == 1 and addr not in self.addr_info:

                # Second hand shake
                rtACK = SEQ + 1
                rtSEQ = 0

                self.new_interface(addr, rtACK, rtSEQ)
                self.get_interface(addr).send_segment(SYN, rtACK, rtSEQ, 0)

            # SYN is 0 and already TCP construction
            # FUNC 0 -- send file
            elif FUNC == 0 and addr in self.addr_info:
                file_name = data.split(b" ")[0].decode("UTF-8")
                print("send file %s to %s:%s" % (file_name, addr[0], addr[1]))
                self.get_interface(addr).SEQ = ACK
                self.get_interface(addr).ACK = SEQ + len(file_name)
                send_thread = threading.Thread(target=self.get_interface(addr).send_file,
                                               args=file_name)
                send_thread.start()
                send_thread.join()

            # SYN is 0 and already TCP construction
            # FUNC 1 -- receive file
            elif FUNC == 1 and addr in server.addr_info:
                file_name = data.split(b" ")[0].decode("UTF-8")
                data_size = int(data.split(b" ")[1])
                print("receive file %s from %s:%s" % (file_name, addr[0], addr[1]))
                self.get_interface(addr).SEQ = ACK
                self.get_interface(addr).ACK = SEQ + len(data)
                receive_thread = threading.Thread(target=self.get_interface(addr).receive_file,
                                                  args=(file_name, data_size))
                receive_thread.start()
                send_thread.join()

        fileSocket.close()


if __name__ == "__main__":

    print("============ Start LFTP server ============")
    server = Server()
    server.listen()
