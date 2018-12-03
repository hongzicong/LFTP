# -*- coding: utf-8 -*-
import socket
import sys
import threading
from time import clock
import math


class Client:

    def __init__(self):
        # Create a socket for use
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.MSSlen = 1000

        self.rtData = b""
        self.rtSEQ = 0
        self.rtACK = 0
        self.ACK = 0
        self.SEQ = 0

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


    def send_segment(self, SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, rtrwnd, data), (serverName, port))
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (serverName, port, SYN, ACK, SEQ, FUNC, rtrwnd))

    def reliable_send_one_segment(self, SYN, FUNC, rtrwnd, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.send_segment(SYN, self.ACK, self.SEQ, FUNC, rtrwnd, serverName, port, data)
            self.fileSocket.settimeout(delayTime)
            try:
                rtSYN, self.rtACK, self.rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receive_segment()

                # TCP construction
                if len(data) == 0 and self.rtACK == self.SEQ + 1:
                    dataComplete = True
                    self.SEQ = self.rtACK
                # File data
                elif len(data) != 0 and self.rtACK == self.SEQ + len(data):
                    dataComplete = True
                    self.SEQ = self.rtACK

            except socket.timeout as timeoutErr:
                # double the delay when time out
                delayTime *= 2
                self.drop_count += 1
                print(timeoutErr)

    def receive_segment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rtrwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rtrwnd))
        return SYN, ACK, SEQ, FUNC, rtrwnd, data, addr

    def send_file(self, serverName, port, file, file_name):

        SYN = 0
        FUNC = 1

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

        # send file name and data size to server for send
        print("send the file name and data size")
        self.reliable_send_one_segment(SYN, FUNC, 0, serverName, port, b"%b %d" % (bytes(file_name, "UTF-8"), len(data)))

        # begin to send file
        print("send the file")
        self.beginSEQ = self.SEQ
        delay_time = 2
        self.cwnd = 1 * self.MSSlen
        self.ssthresh = 8 * self.MSSlen
        fastACK = 0
        dupACKcount = 0
        while True:
            init_time = clock()

            # pipeline
            while (self.SEQ - self.rtACK) < min(self.cwnd, self.rtrwnd) \
                    and math.ceil((self.SEQ - self.beginSEQ) / self.MSSlen) < len(data):
                temp_data = data[(self.SEQ - self.beginSEQ) // self.MSSlen]
                self.send_segment(SYN, self.ACK, self.SEQ, 1, 0, serverName, port, temp_data)
                self.SEQ += len(temp_data)

            # flow control
            if self.SEQ - self.rtACK >= self.rtrwnd:
                print("flow control")
                # check rwnd of the receiver
                self.send_segment(SYN, self.ACK, self.SEQ, 2, 0, serverName, port, b"flow")

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
                elif clock() - init_time > delay_time:
                    self.drop_count += (1 + (self.SEQ - self.rtACK) // self.MSSlen)
                    print("time out")
                    self.SEQ = self.rtACK
                    self.ssthresh = self.cwnd / 2
                    self.cwnd = 1 * self.MSSlen
                    break

            # finish data transmission
            if math.ceil((self.rtACK - self.beginSEQ) / self.MSSlen) == len(data):
                break

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

    def receive_file(self, serverName, port, file_name, data_size):

        SYN = 0
        FUNC = 1

        # send file name to server for send
        print("send the file name")
        self.reliable_send_one_segment(SYN, FUNC, 0, serverName, port, b"%b" % (bytes(file_name, "UTF-8")))

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
            self.send_segment(rtSYN, self.ACK, 0, rtFUNC, self.rwnd)
            if begin == end:
                print("finish receive file successfully")
                break

    # The third handshake will be in charge of send_file function
    def handshake(self, serverName, port):
        SYN = 1
        # First handshake
        self.reliable_send_one_segment(SYN, 0, 0, serverName, port)
        return True


if __name__ == "__main__":

    if len(sys.argv) != 4:
        print("Argument number should be 3 instead of %d" % (len(sys.argv) - 1))
        sys.exit(1)

    funcName = sys.argv[1]
    serverName = sys.argv[2]
    port = 5555
    file_name = sys.argv[3]
    client = Client()

    if funcName == "lsend":
        with open(file_name, "rb") as file:
            # TCP construction
            if client.handshake(serverName, port):
                print("TCP construct successfully")
                client.send_file(serverName, port, file, file_name)
                print("File send successfully")
                print("%d packet have been dropped" % client.drop_count)

    elif funcName == "lget":
        with open(file_name, "wb") as file:
            # TCP construction
            if client.handshake(serverName, port):
                print("TCP construct successfully")
                client.receive_file(serverName, port, file, file_name)
    else:
        print("Your input parameter is wrong!")
