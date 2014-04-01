# -*- coding: utf-8 -*-

import socket
import struct
import datetime
from StringIO import StringIO

import tornado.ioloop
import tornado.iostream
from tornado.options import define, options


class LampProtocol:
    
    def __init__(self, stream):
        self.stream = stream
        self.init()
        
    def init(self):
        try:
            self.stream.read_bytes_with_timeout(3, self.on_got_tl)
        except tornado.iostream.StreamClosedError:
            pass
        self.type = None
        self.length = 0
        
    def __check_length(self, length):
        if self.length != length:
            raise ValueError('Wrong value size. Need %d, got %d' % (length, self.length))
        
    def on_got_tl(self, data):
        self.type, self.length = struct.unpack('!BH', data)
        if self.length > 0:
            self.stream.read_bytes_with_timeout(self.length, self.on_got_value)
        else:
            self.on_got_value()
        
    def on_got_value(self, data=None):
        try:
            if self.type == 0x12:
                self.__check_length(0)
                print 'LAMP ON'
            elif self.type == 0x13:
                self.__check_length(0)
                print 'LAMP OFF'
                # uncomment if need to stop client
                # self.stream.close()
            elif self.type == 0x20:
                self.__check_length(3)
                R, G, B = struct.unpack('!BBB', data)
                print 'LAMP COLOUR', R, G, B
        except Exception, e:
            print 'on_got_value', e
        finally:
            self.init()


class ReadTimeoutException(Exception):
    pass


class LampIOStream(tornado.iostream.IOStream):

    def __init__(self, addr, reconnect, read_timeout=None):
        '''
        tuple addr is (host, port)
        bool reconnect means the stream has to be reconnected when lose connection
        float read_timeout - timeout on each read iteration.
        '''
        tornado.iostream.IOStream.__init__(self, socket.socket())
        
        self.reconnect = reconnect
        self.addr = addr
        self._read_timeout = read_timeout
        self._read_timeout_handle = None
        
        self.buf = ''
        self.set_close_callback(self.handle_disconnect)
        self.connect(addr, self.handle_connect)
        
    def handle_disconnect(self):
        if self._read_timeout_handle:
            self.io_loop.remove_timeout(self._read_timeout_handle)
        if self.error:
            print 'Disconnected with error.', self.error
        else:
            print 'Disconnected cleanly'
        if self.reconnect:
            self.__init__(self.addr, self.reconnect, self._read_timeout)
        else:
            self.io_loop.stop()

    def handle_connect(self):
        print 'Connected to %s:%d' % self.addr
        LampProtocol(self)
        
    def read_bytes_with_timeout(self, num_bytes, when_done):
        
        def handle_timeout():
            self.buf = ''
            try:
                raise ReadTimeoutException('Reading timeout')
            except:
                self.close(True)
            
        def handle_data(data):
            if self._read_timeout:
                self.io_loop.remove_timeout(self._read_timeout_handle)
                self._read_timeout_handle = self.io_loop.add_timeout(datetime.timedelta(seconds=self._read_timeout), handle_timeout)
            self.buf += data
            
        def handle_done(data):
            if self._read_timeout:
                self.io_loop.remove_timeout(self._read_timeout_handle)
                self._read_timeout_handle = None
            buf = self.buf[:]
            self.buf = ''
            when_done(buf)
        
        if self._read_timeout and not self._read_timeout_handle:
            # start timer
            self._read_timeout_handle = self.io_loop.add_timeout(datetime.timedelta(seconds=self._read_timeout), handle_timeout)
        self.read_bytes(num_bytes, handle_done, handle_data)

if __name__ == '__main__':
    define('addr', '127.0.0.1:9999', help='Must look like host:port', metavar='remote host address')
    options.parse_command_line()
    sp = options.addr.split(':')
    if len(sp) == 2 and sp[1].isdigit():
        addr = (sp[0], int(sp[1]))
    else:
        raise ValueError('Wrong addr value: %s' % options.addr)
    
    LampIOStream(addr, False, None)
    tornado.ioloop.IOLoop.instance().start()
