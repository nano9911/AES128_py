'''
*   Author: Adnan Omar Khalaf Hleihel
*   Created at: 19/12/2020
*   Tile: AES implementation in python
'''

try:
    import Queue
except ImportError:
    import queue as Queue

from random import seed, getrandbits
import sys
import threading
from time import sleep
import AES_key_sched as aes_key
import AES_encrypt as aes_enc
import AES_decrypt as aes_dec

BUFF_SIZE = 1024
q1 = Queue.Queue(BUFF_SIZE)
q2 = Queue.Queue(BUFF_SIZE)
q1lock = threading.Lock()
q2lock = threading.Lock()

def get_file_size(fn) :
    fp = open(fn, "rb")
    fp.seek(0, 2)
    size = fp.tell()
    extra = 0

    print("\nFile size = ", size, " Bytes")
    if size%16 != 0 :
        extra = size % 16
        size = int(size/16) + 1
    else :   size = int(size / 16)
    print("File size = ", size, " Blocks")

    fp.close()
    return size, extra


def print_bytes(arg) :
    for i in range(16) :
        print("0x%02X" % arg[i], end = "\t")
    print("\n")


IV = bytearray(16)

def gen_random_iv() :
    global IV
    seed()
    for i in range(16) :
        IV[i] = getrandbits(8)


def get_iv(fn) :
    global IV
    fp = open(fn, "rb")
    IV = bytearray(fp.read(16))
    fp.close()


class read_thread (threading.Thread):
    def __init__(self, threadID, name, arg1, arg2, arg3):
        super(read_thread, self).__init__()
#        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.fn = arg1
        self.size = arg2
        self.extra = arg3

    def run(self) :
        fp = open(self.fn, "rb")
        for i in range(self.size) :
            state = bytearray(fp.read(16))
            if i == (self.size-1) :
                for i in range(self.extra, 16) :
                    state.append(0x00)

            while q1.full() :
                sleep(0.005)

            q1lock.acquire()
            q1.put(state)
            q1lock.release()

        fp.close()
        return

class operate_thread(threading.Thread) :
    def __init__(self, threadID, name, arg1) :
        super(operate_thread, self).__init__()
#        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.size = arg1
        return

    def run(self) :
        if self.name == "ecb_encrypt" :
            for i in range(self.size) :
                while q1.empty() :
                    sleep(0.005)

                q1lock.acquire()
                state = bytearray(q1.get())
                q1lock.release()

                aes_enc.encrypt_one_state(state, aes_key.key, aes_key.round_key)

                while q2.full() :
                    sleep(0.005)

                q2lock.acquire()
                q2.put(state)
                q2lock.release()

##############################################################
        elif self.name == "ecb_decrypt" :
            for i in range(self.size) :
                while q1.empty() :
                    sleep(0.005)

                q1lock.acquire()
                state = bytearray(q1.get())
                q1lock.release()

                aes_dec.decrypt_one_state(state, aes_key.key, aes_key.round_key)

                while q2.full() :
                    sleep(0.005)

                q2lock.acquire()
                q2.put(state)
                q2lock.release()

##############################################################
        elif self.name == "ctr" :
            for i in range(self.size) :
                while q1.empty() :
                    sleep(0.005)

                q1lock.acquire()
                state = bytearray(q1.get())
                q1lock.release()

                aes_enc.encrypt_one_state(IV, aes_key.key, aes_key.round_key)
            
                for e in range(16) :
                    state[e] ^= IV[e]

                for e in range(15, -1, -1) :
                    if (IV[e]+1) > 0xff :
                        IV[e] = 0x00
                        continue
                    IV[e] += 1
                    break

                while q2.full() :
                    sleep(0.005)

                q2lock.acquire()
                q2.put(state)
                q2lock.release()

        return


class write_thread (threading.Thread) :
    def __init__(self, threadID, name, arg1, arg2) :
        super(write_thread, self).__init__()
#        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.fn = arg1
        self.size = arg2
        return

    def run(self) :
        print("\t\t\t", end = "")

        fp = open(self.fn, "wb")
        for i in range(self.size) :
            while q2.empty() :
                sleep(0.005)

            q2lock.acquire()
            state = bytearray(q2.get())
            q2lock.release()

            if i == ((self.size)-1) :
                while (not state[len(state)-1]) & (len(state)>0) :
                    state.pop()

            fp.write(state)
            print("\b"*11, end = "")
            print("%010d" % i, end = " ")

        fp.close()
        print("Blocks\n\n\tFinished")
        return


def main(argv) :
    if argv[1] == 0 :
        print("Error: No iput file was given")
        return
    else :  infn = argv[1]
    size, extra = get_file_size(infn)

    operation = 0
    outfn = 0
    kfn = 0
    IVfn = 0

    if "-k" in argv :
        kfn = argv[argv.index("-k")+1]
        aes_key.get_key(kfn)
    else :
        aes_key.gen_random_key()
    print("Key : ")
    print_bytes(aes_key.key)
    aes_key.gen_round_keys()


    if "-o" in argv :
        outfn = argv[argv.index("-o")+1]
    else :
        outfn = infn + ".output"


    if ("-enc" in argv) & ("-ecb" in argv) :
        operation = "ecb_encrypt"
    elif ("-dec" in argv) & ("-ecb" in argv) :
        operation = "ecb_decrypt"

    elif "-ctr" in argv :
        IVfn = 0
        if "-iv" in argv :  
            IVfn = argv[argv.index("-iv")+1]
            get_iv(IVfn)
        else :
            gen_random_iv()
        print("IV : ")
        print_bytes(IV)
        operation = "ctr"

    if operation != 0 :
        read = read_thread(1, "read", infn, size, extra)
        operate = operate_thread(2, operation, size)
        write = write_thread(3, "write", outfn, size)

        read.start()
        operate.start()
        write.start()

#        read.join()
#        operate.join()
        write.join()

    else :
        print("No operation selected. Exiting...")


main(sys.argv)
