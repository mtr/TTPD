#! /usr/bin/python
# -*- coding: latin-1 -*-
# $Id$
"""
Socket server handler implementation for the TUC Transfer Protocol
(TTP).

Copyright (C) 2004 by Martin Thorsen Ranang
"""

__version__ = "$Rev$"
__author__ = "Martin Thorsen Ranang"

import Queue
import SocketServer
import cStringIO
import re
import time
import xml.sax
#import xml.sax.saxutils
import htmlentitydefs

import Message
import EncapsulateTUC
import num_hash


class BaseHandler(SocketServer.StreamRequestHandler):

    def setup(self):
        
        """ Create an XML parser for this handler instance. """
        
        # Call the base class setup method.
        
        SocketServer.StreamRequestHandler.setup(self)
        
        # Initialize the XML parser.  We keep one parser per thread,
        # in an attempt to avoid any shared resource problems.
        
        self.xml_handler = Message.XML2Message()
        
        self.xml_error_handler = xml.sax.ErrorHandler()
        
        self.xml_parser = xml.sax.make_parser()
        self.xml_parser.setContentHandler(self.xml_handler)
        self.xml_parser.setErrorHandler(self.xml_error_handler)
        
    def handle(self):
        
        meta, body = Message.receive(self.connection, self.xml_parser)
        
        #if meta.MxHead.Len == 0:
        #    self.server.log.info('\n%s\n%s' % ('ACK', body))
        
        self.server.log.info('\n%s\n%s' % (meta, body))
        
        ack = Message.MessageAck()
        ack.MxHead.TransID = meta.MxHead.TransID
        ack.MxHead.Ref = meta.MxHead.MsgId
        Message.send(self.connection, ack)
        
    def escape(self, data):

        """ Replace special characters with escaped equivalents. """

        data = data.replace('"', '\\"')

        return data
    
    def unescape(self, data):
        
        """ Replace escaped special characters with unescaped
        equivalents. """

        data = data.replace('\\"', '"')
        
        return data

    
class Handler(BaseHandler):
    
    """ A handler class for request received over the TUC Transfer
    Protocol. """
    
    result_separator = '~' * 80
    
    prices = {'+': 'BILLING',
              '-': 'FREE',
              '!': 'VARSEL'}
    
    # According to "Online Interface EAS Message Switch 2.4", a
    # billing value of 1 == 0.5 NOK.
    
    billings = {'BILLING': 2,
                'FREE': 0,
                'VARSEL': 2,
                'AVBEST': 2}
    
    whitespace_replace_re = re.compile('\s+', re.MULTILINE)
    dangerous_removes_re = re.compile('[\\\�`\'"]', re.MULTILINE)
    
    sms_trans_id = 'LINGSMSOUT'
    
    service_name = 'TEAM'
    service_re = re.compile('^(?P<service>%s) (?P<body>.*)$' % (service_name),
                            re.IGNORECASE)
    
    cancel_command_info = 'Avbestill ved � sende ' \
                          '%s AVBEST %%s til 1939.' % (service_name)
    
    command = 'avbestill'
    command_misspellings = [command[:i + 1] for i in range(1,len(command))]
    cancel_command_re = re.compile(#'^(?P<service>%s) ' \
                                   '^(?P<command>%s) ' \
                                   '(?P<ext_id>\S+)' %
                                   '|'.join(command_misspellings),
                                   re.IGNORECASE)
    
    def handle(self):

        """ Handles a query received by the socket server.
        
        The incoming data is available through self.rfile and feedback
        to the client should be written to self.wfile.  The query is
        first classified.  If it is not a cancelation of an alert, the
        natural language query is 'piped' through TUC.
        
        Depending on the nature of the TUC results, the appropriate
        action is taken.  If it is an alert canelation, the request
        will be handled in another method.  """
        
        self.server.log.debug('Connection from %s:%d.' %
                              (self.client_address[0], self.client_address[1]))
        
        # Retrieve incoming request.
        
        meta, body = Message.receive(self.connection, self.xml_parser)

        # Remove "dangerous" tokens from the request.

        body = self.dangerous_removes_re.sub('', body)
        
        if meta.MxHead.TransID[:len(self.sms_trans_id)] == self.sms_trans_id:
            
            is_sms_request = True
            
            # Since it is a SMS request, send an ACK.
            
            ack = Message.MessageAck()
            ack.MxHead.TransID = meta.MxHead.TransID
            Message.send(self.connection, ack)
            
        else:
            
            is_sms_request = False
            
        # The preprocessing returns a method and some arguments.  The
        # method should be applied on the arguments.
        
        method, args = self.preprocess(body, is_sms_request)
        
        self.server.log.debug('"%s"' % body)
        
        # Apply method to args.
        
        cost, pre_answer, answer, extra = method(args)

        # Some special considerations to make when we answer an SMS
        # request.
        
        if is_sms_request:
            
            if cost == 'VARSEL':
                alert_date = extra
                
                # Insert the alert into the TAD scheduler.
                
                id = self.server.tad.insert_alert(time.mktime(alert_date),
                                                  answer, meta.MxHead.ORName)
                ext_id = num_hash.num2alpha(id)
                
                answer = 'Du vil bli varslet %s. %s %s' % \
                         (time.strftime('%X, %x', alert_date),
                          self.cancel_command_info % ext_id.upper(), answer)
                
            elif cost == 'AVBEST':
                ext_id = extra
            else:
                ext_id = ''
        else:
            
            # Non-SMS request for SMS-only services.
            
            if cost in ['VARSEL', 'AVBEST']:
                answer = 'Beklager, %s av varsel er ' \
                         'kun mulig via SMS.' % \
                         ({'VARSEL': 'bestilling',
                           'AVBEST': 'avbestilling'}[cost])
                cost = 'FREE'
                
            ext_id = ''
            
        # Hide "machinery" error messages from the user, but log them
        # for internal use.
        
        if cost == 'FREE' and (not answer) or answer[0] == '%':
            self.server.log.error('"%s"' % answer)
            answer = 'Foresp�rselen ble avbrutt.  Vennligst pr�v igjen senere.'
            
        # Send the answer to the client.
        
        ans = Message.MessageResult()
        ans.MxHead.TransID = meta.MxHead.TransID
        
        # Again, if it is an SMS request we're handling, take special
        # care.
        
        if is_sms_request:
            
            ans._setMessage(answer)
            
            ans.MxHead.ORName = meta.MxHead.ORName
            ans.MxHead.Aux.Billing = self.billings[cost]
            
            try:
                Message.communicate(ans,
                                    self.server.remote_server_address,
                                    self.xml_parser)
            except:
                
                self.server.log.error("Couldn't connect to " \
                                      "remote server (%s, %s)." % \
                                      (self.server.remote_server_address))
                answer = 'Fikk ikke sendt svaret. ' \
                         'Det opprinnelige svaret var %s' % (answer)
                cost = 'FREE'
        else:
            
            tuc_ans = Message.Message()
            
            tuc_ans.TUCAns.Technical = pre_answer,
            tuc_ans.TUCAns.NaturalLanguage = answer
            
            ans._setMessage('<?xml version="1.0" encoding="iso-8859-1"?>' \
                            '%s' % (tuc_ans._xmlify()))
            
            Message.send(self.connection, ans)
            
        # Log any interesting information.
        
        self.server.log.info('billing =%d\n%s %s\n"%s"\n"%s"\n-'
                             % (self.billings[cost], cost, ext_id, body,
                                answer.replace('\n', ' ')))

        # Close the socket.
        
        self.request.close()
   
    def parse_result(self, data):

        """ Parse the result received from TUC. """

        self.server.log.debug('Parsing result: "%s".' % data)
        
        if data.find(self.result_separator) != -1:
            
            # Split the output from TUC according to its "block
            # separators".
            
            pre, main, post = [x.strip() for x in
                               data.split(self.result_separator)]
            
            # The first line of the main block should contain billing
            # and timing information.
            
            if main[0] in self.prices:
                
                meta, answer = main.split('\n', 1)
                
                # The first character of meta may not be a cost
                # identifyer.
                
                cost = self.prices[meta[0]]
            else:
                cost, answer = self.prices['-'], main
        else:
            
            # If no block separators where found, consider the answer
            # from TUC as a "simple answer" or an error message (like
            # "% Execution aborted").
            
            self.server.log.debug('Found no separator.')
            
            pre, cost, alert_date, answer = (None, self.prices['-'],
                                             None,
                                             data.rstrip('\nno\n').strip())
            
        answer = self.whitespace_replace_re.sub(' ', answer)
        
        if cost == 'VARSEL':
            alert_date = time.strptime(meta[2:], '%Y%m%d%H%M%S')
        else:
            alert_date = None
            
        # POST is deliberately not returned.
        
        return pre, cost, alert_date, answer
    
    def cancel_alert(self, ext_id):
        
        """ Cancel the alert signified by ext_id. """
        
        if self.server.tad.cancel_alert(num_hash.alpha2num(ext_id)):
            return ('AVBEST', None, 'Varsling med referanse ' \
                    '%s ble avbestilt.' % (ext_id), ext_id)
        else:
            return ('FREE', None,
                    'Kunne ikke avbestille.  Fant ikke bestilling %s.'
                    % (ext_id), ext_id)
        
    def tuc_query(self, data):
        
        """ Pipe request through TUC and parse the result. """
        
        # Create a thread safe FIFO with a length of 1.  It will only
        # be used to receive the results produced by an encapsulated
        # TUC process (in a thread-safe manner).
        
        result_queue = Queue.Queue(1)
        
        # Because only the thread that picks up _this_task_ will know
        # about this particular result_queue, we don't need to supply
        # any id with the task.
        
        self.server.tuc_pool.queue_task((EncapsulateTUC.TYPE_NORMAL, data),
                                        result_queue)

        # Possibly wait some time and retrieve the result from the
        # result_queue.
        
        result = result_queue.get()
        if not result:
            self.server.log.error('Received empty result from TUC process')
            result = 'Foresp�rselen ble avbrutt.  Vennligst pr�v igjen senere.'
            
        # self.server.log.debug('result = "%s"' % result)
        
        try:
            pre, cost, alert_date, answer = self.parse_result(result)
        except:
            self.server.log.exception('There was a problem handling ' \
                                      'the result:\n%s\nInput: "%s"'
                                      % (result, data))
            pre, cost, alert_date, answer = None, 'FREE', \
                                            None, 'Beklager, ' \
                                            'det oppstod en feil.'
        return cost, pre, answer, alert_date
        
    def preprocess(self, request, is_sms_request = False):
        
        """ Perform pre-processing of the request. """
        
        # Check for (and handle) "TEAM ..." in start of message.
        
        m = self.service_re.match(request)
        if m:
            
            # Service should become 'TEAM' here.
            
            service, body = m.groups()
            
            m = self.cancel_command_re.match(body)
            if m and is_sms_request:
                ext_id = m.group('ext_id').lower()
                return self.cancel_alert, ext_id
            elif m:

                # Return a function that always returns _one_
                # particular result, regardless of its input.  The
                # return values should match those of self.tuc_query
                # and self.cancel_alert.
                
                return (lambda x: ('AVBEST', None, None)), None
            
            else:
                return self.tuc_query, body
        else:
            return self.tuc_query, request

def main():
    
    """ Module mainline (for standalone execution). """

    return

if __name__ == "__main__":
    main()
