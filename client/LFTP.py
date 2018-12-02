# -*- coding: utf-8 -*-
import socket
import sys
import threading
from time import clock


class Client:

    def __init__(self):
        # Create a socket for use
        self.fileSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.MSSlen = 1000

        self.rtSEQ = 0
        self.rtACK = 0
        self.ACK = 0
        self.SEQ = 0

        self.rwnd = self.buffer_size
        self.rtrwnd = 0

        # the size of congestion window
        self.cwnd = 0

        # seg begin to send file
        self.beginSEQ = 0

        self.drop_count = 0
        self.lockForBuffer = threading.Lock()
        self.buffer = {}
        self.buffer_size = 80 * self.MSSlen

    def send_segment(self, SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, rtrwnd, data), (serverName, port))
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rtrwnd: %d" % (serverName, port, SYN, ACK, SEQ, FUNC, rtrwnd))

    def reliable_send_one_segment(self, SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data=b""):
        dataComplete = False
        delayTime = 1
        while not dataComplete:
            self.send_segment(SYN, ACK, SEQ, FUNC, rtrwnd, serverName, port, data)
            self.fileSocket.settimeout(delayTime)
            try:
                rtSYN, self.rtACK, rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receive_segment()

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
        # ACK is useless so we set it as 0
        ACK = 0
        SEQ = self.SEQ
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
        self.reliable_send_one_segment(SYN, ACK, SEQ, FUNC, 0, serverName, port,
                                    b"%b %d" % (bytes(file_name, "UTF-8"), len(data)))

        # begin to send file
        print("send the file")
        self.beginSEQ = self.SEQ
        delay_time = 2
        self.cwnd = 1 * self.MSSlen
        self.ssthresh = 8 * self.MSSlen
        while True:
            init_time = clock()

            # pipeline
            while (self.SEQ - self.rtACK) < min(self.cwnd, self.rtrwnd) \
                    and (self.SEQ - self.beginSEQ) // self.MSSlen < len(data):
                temp_data = data[(self.SEQ - self.beginSEQ) // self.MSSlen]
                self.send_segment(SYN, ACK, self.SEQ, 1, 0, serverName, port, temp_data)
                self.SEQ += len(temp_data)

            # flow control
            if self.SEQ - self.rtACK >= self.rtrwnd:
                print("flow control")
                # check rwnd of the receiver
                self.send_segment(SYN, ACK, self.SEQ, 2, 0, serverName, port, b"flow")

            # set timer
            self.fileSocket.settimeout(1)
            while True:
                try:
                    rtSYN, self.rtACK, rtSEQ, rtFUNC, self.rtrwnd, rtData, addr = self.receive_segment()
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
                    self.drop_count += (1 + (self.SEQ - self.beginSEQ) // self.MSSlen)
                    print("time out")
                    self.SEQ = self.rtACK
                    self.ssthresh = self.cwnd / 2
                    self.cwnd = 1 * self.MSSlen
                    break

            # finish data transmission
            if (self.rtACK - self.beginSEQ) // self.MSSlen == len(data):
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
        self.beginACK = self.ACK
        self.lastACKRead = self.ACK

        file_thread = threading.Thread(target=self.read_into_file, args=(file_name, data_size,), name="fileThread")
        file_thread.start()

        begin = 0
        end = data_size
        while True:
            rtSYN, rtACK, rtSEQ, rtFUNC, rtrwnd, data, addr = self.receive_segment()
            if data == b"":
                self.send_segment(rtSYN, rtSEQ + 1, self.SEQ, rtFUNC, self.rwnd, serverName, port)
                continue
            if rtFUNC == 2:
                self.send_segment(rtSYN, rtSEQ, self.SEQ, rtFUNC, self.rwnd, serverName, port)
                continue
            # write to the buffer only when receiver need
            if (rtSEQ - self.beginACK) // self.MSSlen == begin:
                if self.lockForBuffer.acquire():
                    self.buffer[begin] = data
                    begin += 1
                    self.rwnd -= len(data)
                    self.lockForBuffer.release()
            if begin == end:
                print("finish receive file successfully")
            # answer
            self.send_segment(rtSYN, rtSEQ + len(data), 0, rtFUNC, self.rwnd, serverName, port)

    # The third handshake will be in charge of send_file function
    def handshake(self, serverName, port):
        # First handshake
        # For safety, seq is picked randomly
        SYN = 1
        ACK = 1
        SEQ = self.SEQ

        self.reliable_send_one_segment(SYN, ACK, SEQ, 0, 0, serverName, port)

        return True


if __name__ == "__main__":

    if len(sys.argv) != 5:
        print("Argument number should be 4 instead of %d" % (len(sys.argv) - 1))
        sys.exit(1)

    funcName = sys.argv[1]
    serverName = sys.argv[2]
    port = int(sys.argv[3])
    file_name = sys.argv[4]
    client = Client()

    if funcName == "lsend":
        with open(file_name, "rb") as file:
            # TCP construction
            if client.handshake(serverName, port, True):
                print("TCP construct successfully")
                client.send_file(serverName, port, file, file_name)
                print("%d packet have been dropped" % client.drop_count)

    elif funcName == "lget":
        with open(file_name, "wb") as file:
            # TCP construction
            if client.handshake(serverName, port, False):
                print("TCP construct successfully")
                client.receive_file(serverName, port, file, file_name)
    else:
        print("Your input parameter is wrong!")
