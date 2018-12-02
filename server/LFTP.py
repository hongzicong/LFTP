# -*- coding: utf-8 -*-
import socket
import random
import threading


class Interface:

    def __init__(self, fileSocket, addr, ACK, serverSEQ):
        self.fileSocket = fileSocket
        self.addr = addr
        self.ACK = ACK
        self.serverSEQ = serverSEQ
        self.MSSlen = 1000

        self.lockForBuffer = threading.Lock()
        self.buffer = {}
        self.buffer_size = 50000

        self.rwnd = self.buffer_size
        self.rtrwnd = 0

    def receiveSegnment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rwnd))
        return SYN, ACK, SEQ, FUNC, rwnd, data, addr

    def sendSegment(self, SYN, ACK, SEQ, FUNC, rwnd, data=b""):
        # * is the character used to split
        self.fileSocket.sendto(b"%d*%d*%d*%d*%d*%b" % (SYN, ACK, SEQ, FUNC, rwnd, data), self.addr)
        print("send segment to %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rwnd: %d" % (self.addr[0], self.addr[1], SYN, ACK, SEQ, FUNC, rwnd))

    def reliableSendOneSegment(self, SYN, ACK, SEQ, FUNC, rwnd, data=b""):
        # TODO
        pass

    def readIntoFile(self, file_name, data_size):
        begin = 0
        end = data_size
        with open(file_name, 'wb') as file:
            while True:
                if begin == end:
                    print("finish write to file successfully")
                    break

                while begin in self.buffer:
                    if self.lockForBuffer.acquire():
                        file.write(self.buffer[begin])
                        data_len = len(self.buffer[begin])
                        self.buffer.pop(begin)
                        self.rwnd += data_len
                        begin += 1
                        self.lockForBuffer.release()

    def receiveFile(self, fileName, data_size):
        self.beginACK = self.ACK
        self.lastACKRead = self.ACK

        file_thread = threading.Thread(target=self.readIntoFile, args=(fileName, data_size,), name="fileThread")
        file_thread.start()

        begin = 0
        end = data_size
        while True:
            rtSYN, rtACK, rtSEQ, rtFUNC, rtrwnd, data, addr = self.receiveSegnment()
            if data == b"":
                self.ACK += 1
                self.sendSegment(rtSYN, self.ACK, self.serverSEQ, rtFUNC, self.rwnd)
                continue
            # write to the buffer only when receiver need
            if (rtSEQ - self.beginACK) // self.MSSlen == begin:
                if self.lockForBuffer.acquire():
                    self.buffer[begin] = data
                    begin += 1
                    self.rwnd -= len(data)
                    self.lockForBuffer.release()
            # answer
            self.sendSegment(rtSYN, rtSEQ + len(data), 0, rtFUNC, self.rwnd)
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

    def newInterface(self, addr, ACK, SEQ):
        #  New a buffer for the address
        clientInterface = Interface(self.fileSocket, addr, ACK, SEQ)
        self.addr_info[addr] = clientInterface

    def deleteInterface(self, addr):
        self.addr_info.pop(addr)

    def getInterface(self, addr):
        return self.addr_info[addr]

    def receiveSegment(self):
        seg, addr = self.fileSocket.recvfrom(4096)
        SYN, ACK, SEQ, FUNC, rwnd = list(map(int, seg.split(b"*")[0:5]))
        data = seg[sum(map(len, seg.split(b"*")[0:5])) + 5:]
        print("receive segment from %s:%d --- SYN: %d ACK: %d SEQ: %d FUNC: %d rwnd: %d" % (addr[0], addr[1], SYN, ACK, SEQ, FUNC, rwnd))
        return SYN, ACK, SEQ, FUNC, rwnd, data, addr

    def listen(self):
        while True:
            SYN, ACK, SEQ, FUNC, rwnd, data, addr = self.receiveSegment()

            # TCP construction : SYN is 1
            if SYN == 1 and addr not in self.addr_info:

                # Second hand shake
                rtACK = SEQ + 1
                rtSEQ = random.randint(0, 100)

                self.newInterface(addr, rtACK, rtSEQ)
                self.getInterface(addr).sendSegment(SYN, rtACK, rtSEQ, 0, self.getInterface(addr).buffer_size)

            # SYN is 0 and already TCP construction
            # FUNC 1
            elif FUNC == 1 and addr in server.addr_info:
                fileName = data.split(b" ")[0].decode("UTF-8")
                data_size = int(data.split(b" ")[1])
                print("receive file %s from %s:%s" % (fileName, addr[0], addr[1]))
                self.getInterface(addr).ACK = SEQ + len(data)
                self.getInterface(addr).sendSegment(SYN, self.getInterface(addr).ACK, self.getInterface(addr).serverSEQ,
                                                      FUNC, self.getInterface(addr).buffer_size)
                self.getInterface(addr).receiveFile(fileName, data_size)
                self.deleteInterface(addr)

            # SYN is 0 and already TCP construction
            # FUNC 0
            elif FUNC == 0 and addr in self.addr_info:
                self.getInterface(addr).send_file(data.split(b"*")[3])

        fileSocket.close()

if __name__ == "__main__":

    print("============ Start LFTP server ============")
    server = Server()
    server.listen()
