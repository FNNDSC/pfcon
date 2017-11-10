#!/usr/bin/env python3.5

import  sys

from    io              import  BytesIO as IO
from    http.server     import  BaseHTTPRequestHandler, HTTPServer
from    socketserver    import  ThreadingMixIn
from    webob           import  Response
import  cgi
import  json
import  urllib
import  ast
import  shutil
import  datetime
import  time
import  inspect
import  pprint

import  threading
import  platform
import  socket
import  psutil
import  os
import  multiprocessing
import  pfurl

import  pfmisc

import  pudb

# pfcon local dependencies
from    ._colors        import  Colors
from    .debug          import  debug
from   .C_snode         import *


# Horrible global var
G_b_httpResponse            = False

Gd_internalvar  = {
    'self': {
        'name':                 'pfcon',
        'version':              'undefined',
        'coordBlockSeconds':    10
    },

    'jobstatus': {
        'purpose':  'this structure keeps track of job status: pathPush/pull and compute.',
        'organization': 'the tree is /jobstatus/<someKey>/info',
        'info': {
            'pushPath': {
                'status':   '<statusString>',
                'return':   '<d_ret>'
                },
            'compute':  {
                'status':   '<statusString>',
                'return':   '<d_ret>'
                },
            'pullPath': {
                'status':   '<statusString>',
                'return':   '<d_ret>'
                }
        }
    },

    'service':  {
        'chris-docker-dev': {
            'data': {
                'addr':         '172.17.0.5:5055',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }

            },
            'compute': {
                'addr':         '172.17.0.2',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        },
        
        'moc': {
            'data': {
                'addr':         'pfioh-radiology.apps.osh.massopen.cloud',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }

            },
            'compute': {
                'addr':         'pman-radiology.apps.osh.massopen.cloud',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        },
        'gondwanaland': {
            'data': {
                'addr':         '192.168.1.189:5055',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }

            },
            'compute': {
                'addr':         '192.168.1.189:5010',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        },
        'pangea': {
            'data': {
                'addr':         '10.17.24.163:5055',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }

            },
            'compute': {
                'addr':         '10.17.24.163:5010',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        },
        'megalodon': {
            'data': {
                'addr':         '10.23.131.204:5055',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }
            },
            'compute': {
                'addr':         '10.23.131.204:5010',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        },
        'host': {
            'data': {
                'addr':         '%PFIOH_IP:5055',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }
            },
            'compute': {
                'addr':         '%PMAN_IP:5010',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        },
        'localhost': {
            'data': {
                'addr':         '127.0.0.1:5055',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined',

                'storeAccess.tokenSet':  {
                    "action":   "internalctl",
                    "meta": {
                           "var":          "key",
                           "set":          "setKeyValueHere"
                       }
                },

                'storeAccess.addrGet':  {
                    "action":   "internalctl",
                    "meta": {
                        "var":          "storeAddress",
                        "compute":      "address"
                    }
                }
            },
            'compute': {
                'addr':         '127.0.0.1:5010',
                'baseURLpath':  '/api/v1/cmd/',
                'status':       'undefined'
            }
        }        
    }
}

Gd_tree         = C_stree()


class StoreHandler(BaseHTTPRequestHandler):

    b_quiet     = False

    def __init__(self, *args, **kwargs):
        """
        """
        b_test                  = False
        self.__name__           = 'StoreHandler'
        self.b_useDebug         = False
        self.str_debugFile      = '/tmp/pfcon-log.txt'
        self.b_quiet            = True
        self.dp                 = pfmisc.debug(    
                                            verbosity   = 0,
                                            level       = -1,
                                            within      = self.__name__
                                            )
        self.pp                 = pprint.PrettyPrinter(indent=4)

        for k,v in kwargs.items():
            if k == 'test': b_test  = True

        if not b_test:
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def qprint(self, msg, **kwargs):
        """
        Simple print function with verbosity control.
        """
        str_comms  = ""
        for k,v in kwargs.items():
            if k == 'comms':    str_comms  = v

        str_caller  = inspect.stack()[1][3]

        if not StoreHandler.b_quiet:
            if str_comms == 'status':   print(Colors.PURPLE,    end="")
            if str_comms == 'error':    print(Colors.RED,       end="")
            if str_comms == "tx":       print(Colors.YELLOW + "<----")
            if str_comms == "rx":       print(Colors.GREEN  + "---->")
            print('%s' % datetime.datetime.now() + " | "  + os.path.basename(__file__) + ':' + self.__name__ + "." + str_caller + '() | ', end="")
            print(msg)
            if str_comms == "tx":       print(Colors.YELLOW + "<----")
            if str_comms == "rx":       print(Colors.GREEN  + "---->")
            print(Colors.NO_COLOUR, end="")

    def log_message(self, format, *args):
        """
        This silences the server from spewing to stdout!
        """
        return

    def do_GET(self):

        d_server            = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        d_meta              = ast.literal_eval(d_server['meta'])

        d_msg               = {'action': d_server['action'], 'meta': d_meta}
        d_ret               = {}
        self.dp.qprint(self.path, comms = 'rx')

        return d_ret

    def form_get(self, str_verb, data):
        """
        Returns a form from cgi.FieldStorage
        """
        return cgi.FieldStorage(
            IO(data),
            headers = self.headers,
            environ =
            {
                'REQUEST_METHOD':   str_verb,
                'CONTENT_TYPE':     self.headers['Content-Type'],
            }
        )

    def internalctl_varprocess(self, *args, **kwargs):
        """

        get/set a specific variable as parsed from the meta JSON.

        :param args:
        :param kwargs:
        :return:
        """
        global Gd_internalvar
        global Gd_tree
        d_meta      = {}
        d_ret       = {}
        str_var     = ''
        b_status    = False
        b_tree      = False

        for k,v in kwargs.items():
            if k == 'd_meta':   d_meta  = v

        str_var     = d_meta['var']

        T           = C_stree()

        if d_meta:
            if 'get' in d_meta.keys():
                if Gd_tree.isdir(str_var):
                    Gd_tree.copy(startPath = str_var, destination = T)
                    d_ret                   = dict(T.snode_root)
                else:
                    d_ret[str_var]          = Gd_tree.cat(str_var)
                b_status                = True

            if 'set' in d_meta.keys():
                try:
                    d_set   = json.loads(d_meta['set'])
                    b_tree  = True
                except:
                    b_tree  = False
                if b_tree:
                    D       = C_stree()
                    D.initFromDict(d_set)
                    D.copy(startPath = '/', destination = Gd_tree, pathDiskRoot = str_var)
                    d_ret           = d_set
                else:
                    Gd_tree.touch(str_var, d_meta['set'])
                    d_ret[str_var]          = Gd_tree.cat(str_var)
                b_status                = True

        return {'d_ret':    d_ret,
                'status':   b_status}

    def internalctl_process(self, *args, **kwargs):
        """

        Process the 'internalctl' action.

             {  "action": "internalctl",
                     "meta": {
                            "var":      "/tree/path",
                            "set":     "<someValue>"
                     }
             }

             {  "action": "internalctl",
                     "meta": {
                            "var":      "/tree/path",
                            "get":      "currentPath"
                     }
             }

        :param args:
        :param kwargs:
        :return:
        """

        d_request           = {}
        b_status            = False
        d_ret               = {
            'status':   b_status
        }

        for k,v in kwargs.items():
            if k == 'request':   d_request   = v
        if d_request:
            d_meta  = d_request['meta']
            d_ret   = self.internalctl_varprocess(d_meta = d_meta)
        return d_ret

    def dataRequest_process(self, *args, **kwargs):
        """
        Method for talking to the data handling service.

        Return JSON information from remote process is returned directly by this method,
        and also stored in the internal key_ID tree.

        :param args:
        :param kwargs:
        :return: JSON object from the 'pfioh' call.
        """

        global  Gd_tree
        b_status    = False

        self.dp.qprint("dataRequest_process()", comms = 'status')

        # pudb.set_trace()

        d_request       = {}
        d_meta          = {}
        # The return from the remote call
        d_ret           = {}
        # The return from this method
        d_return        = {}
        str_metaHeader  = 'meta'
        str_key         = 'none'
        str_op          = ''
        for k,v in kwargs.items():
            if k == 'request':          d_request           = v
            if k == 'metaHeader':       str_metaHeader      = v
            if k == 'return':           d_return            = v
            if k == 'key':              str_key             = v
            if k == 'op':               str_op              = v

        d_meta                  = d_request[str_metaHeader]
        str_remoteService       = d_meta['service']
        str_dataServiceAddr     = Gd_tree.cat('/service/%s/data/addr'       % str_remoteService)
        str_dataServiceURL      = Gd_tree.cat('/service/%s/data/baseURLpath'% str_remoteService)

        dataComs = pfurl.Pfurl(
            msg                         = json.dumps(d_request),
            verb                        = 'POST',
            http                        = '%s/%s' % (str_dataServiceAddr, str_dataServiceURL),
            b_quiet                     = False,
            b_raw                       = True,
            b_httpResponseBodyParse     = True,
            jsonwrapper                 = ''
        )

        self.dp.qprint("Calling remote data service...",   comms = 'rx')
        d_dataComs                              = dataComs()
        d_dataResponse                          = json.loads(d_dataComs)
        d_ret['%s-data' % str_remoteService]    = d_dataResponse

        d_return = {
            'd_ret':        d_ret,
            'serviceName':  str_remoteService,
            'status':       d_dataResponse['stdout']['status']
        }

        self.jobOperation_do(   action      = 'set',
                                key         = str_key,
                                op          = str_op,
                                status      = 'done',
                                jobReturn   = d_return)

        return d_return

    def computeRequest_process(self, *args, **kwargs):
        """
        Method for talking to the data handling service.

        Return JSON information from remote process is returned directly by this method,
        and also stored in the internal key_ID tree.

        :param args:
        :param kwargs:
        :return: JSON object from the 'pfioh' call.
        """

        global  Gd_tree
        b_status    = False

        self.dp.qprint("computeRequest_process()", comms = 'status')

        d_request       = {}
        d_meta          = {}
        # The return from the remote call
        d_ret           = {}
        # The return from this method
        d_return        = {}
        str_metaHeader  = 'meta'
        str_key         = ''
        str_op          = ''
        for k,v in kwargs.items():
            if k == 'request':          d_request           = v
            if k == 'metaHeader':       str_metaHeader      = v
            if k == 'return':           d_return            = v
            if k == 'key':              str_key             = v
            if k == 'op':               str_op              = v

        d_meta                  = d_request[str_metaHeader]
        str_remoteService       = d_meta['service']
        str_computeServiceAddr  = Gd_tree.cat('/service/%s/compute/addr'        % str_remoteService)
        str_computeServiceURL   = Gd_tree.cat('/service/%s/compute/baseURLpath' % str_remoteService)

        # Remember, 'pman' responses do NOT need to http-body parsed!
        computeComs = pfurl.Pfurl(
            msg                         = json.dumps(d_request),
            verb                        = 'POST',
            http                        = '%s/%s' % (str_computeServiceAddr, str_computeServiceURL),
            b_quiet                     = False,
            b_raw                       = True,
            b_httpResponseBodyParse     = False,
            jsonwrapper                 = 'payload'
        )

        self.dp.qprint("Calling remote compute service...", comms = 'rx')
        d_computeComs                           = computeComs()
        d_computeResponse                       = json.loads(d_computeComs)
        d_ret['%s-compute' % str_remoteService] = d_computeResponse

        return {
            'd_ret':        d_ret,
            'serviceName':  str_remoteService,
            # 'status':       d_computeResponse['stdout']['status']
        }

    def hello_process_remote(self, *args, **kwargs):
        """
        Process the 'hello' call on the remote services

        :param args:
        :param kwargs:
        :return:
        """
        global Gd_tree
        b_status    = False

        self.dp.qprint("hello_process_remote()", comms = 'status')

        d_request   = {}
        d_ret       = {}
        for k,v in kwargs.items():
            if k == 'request':          d_request           = v

        d_dataResponse      = self.dataRequest_process(request      = d_request)
        d_ret['%s-data'     % d_dataResponse['serviceName']]        = d_dataResponse

        d_computeResponse   = self.computeRequest_process(request   = d_request)
        d_ret['%s-compute'  % d_computeResponse['serviceName']]     = d_computeResponse

        return {
            'd_ret':                d_ret,
            'serviceNameData':      d_dataResponse['serviceName'],
            'serviceNameCompute':   d_computeResponse['serviceName'],
            'status':               True
        }

    def hello_process(self, *args, **kwargs):
        """

        The 'hello' action is merely to 'speak' with the server. The server
        can return current date/time, echo back a string, query the startup
        command line args, etc.

        This method is a simple means of checking if the server is "up" and
        running.

        :param args:
        :param kwargs:
        :return:
        """
        global Gd_internalvar

        self.dp.qprint("hello_process()", comms = 'status')
        b_status            = False
        d_ret               = {}
        d_request           = {}
        d_remote            = {}
        for k, v in kwargs.items():
            if k == 'request':      d_request   = v

        d_meta  = d_request['meta']
        if 'askAbout' in d_meta.keys():
            str_askAbout    = d_meta['askAbout']
            d_ret['name']       = Gd_internalvar['self']['name']
            d_ret['version']    = Gd_internalvar['self']['version']
            if str_askAbout == 'timestamp':
                str_timeStamp   = datetime.datetime.today().strftime('%Y%m%d%H%M%S.%f')
                d_ret['timestamp']              = {}
                d_ret['timestamp']['now']       = str_timeStamp
                b_status                        = True
            if str_askAbout == 'sysinfo':
                d_ret['sysinfo']                = {}
                d_ret['sysinfo']['system']      = platform.system()
                d_ret['sysinfo']['machine']     = platform.machine()
                d_ret['sysinfo']['platform']    = platform.platform()
                d_ret['sysinfo']['uname']       = platform.uname()
                d_ret['sysinfo']['version']     = platform.version()
                d_ret['sysinfo']['memory']      = psutil.virtual_memory()
                d_ret['sysinfo']['cpucount']    = multiprocessing.cpu_count()
                d_ret['sysinfo']['loadavg']     = os.getloadavg()
                d_ret['sysinfo']['cpu_percent'] = psutil.cpu_percent()
                d_ret['sysinfo']['hostname']    = socket.gethostname()
                d_ret['sysinfo']['inet']        = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
                b_status                        = True
            if str_askAbout == 'echoBack':
                d_ret['echoBack']               = {}
                d_ret['echoBack']['msg']        = d_meta['echoBack']
                b_status                        = True

        # pudb.set_trace()
        d_remote    = self.hello_process_remote(request = d_request)

        return { 'd_ret':       d_ret,
                 'd_remote':    d_remote,
                 'status':      b_status}

    def jobOperation_do(self, *args, **kwargs):
        """
        Sets the status of a specific operation in a given job.
        """
        global  Gd_tree 
        # return status of this method
        b_status    = False
        # the info dictionary for all the jobs per key
        d_info      = {}
        str_keyID   = 'none'
        str_op      = 'none'
        str_status  = 'none'
        str_action  = 'none'
        b_jobReturn = False
        d_jobReturn = {}

        # pudb.set_trace()
        for k,v in kwargs.items():
            if k == 'key':          str_keyID   = v
            if k == 'op':           str_op      = v
            if k == 'status':       str_status  = v
            if k == 'jobReturn':
                b_jobReturn                     = True    
                d_jobReturn                     = v 
            if k == 'action':       str_action  = v

        # pudb.set_trace()
        if str_keyID != 'none':
            T           = Gd_tree
            T.cd('/jobstatus')
            b_status    = True
            if not T.exists(str_keyID):
                T.mkcd(str_keyID)
            else:
                T.cd(str_keyID)
            if T.exists('info'):
                d_info  = T.cat('info')
                # self.dp.qprint("d_info = %s" % self.pp.pformat(d_info).strip(), comms = 'status')
                if not d_info['compute']['status']  or \
                   not d_info['pullPath']['status'] or \
                   not d_info['pushPath']['status']:
                    b_status = False
            if str_op != 'none':
                if str_op == 'all':
                    l_opKey = ['pushPath', 'compute', 'pullPath']
                else:
                    if str_op in ['pushPath', 'compute', 'pullPath']:
                        l_opKey = [str_op]
                for k in l_opKey:
                    if str_action == 'set':
                        if not k in d_info.keys():
                            d_info[k]           = {}
                            d_info[k]['return'] = {}
                            d_info[k]['status'] = ''
                        d_info[k]['status'] = str_status
                        b_status            = str_status
                        if b_jobReturn:
                            d_info[k]['return'] = d_jobReturn
                    T.touch('info', d_info)
        return {
            'status':   b_status,
            'info':     d_info
        }

    def jobOperation_computeStatusQuery(self, *args, **kwargs):
        """
        Query the remote compute job status.
        """
        d_request           = {}
        d_status            = {}
        str_keyID           = 'none'
        str_op              = 'none'
        str_status          = 'none'
        str_action          = 'none'
        timeout             = 60
        pollInterval        = 1

        for k,v in kwargs.items():
            if k == 'key':      str_keyID   = v
            if k == 'op':       str_op      = v
            if k == 'status':   str_status  = v
            if k == 'timeout':  timeout     = v
            if k == 'request':  d_request   = v

        # pudb.set_trace()
        d_meta                  = d_request['meta']
        str_remoteService       = d_meta['service']
        str_computeServiceAddr  = Gd_tree.cat('/service/%s/compute/addr'        % str_remoteService)
        str_computeServiceURL   = Gd_tree.cat('/service/%s/compute/baseURLpath' % str_remoteService)

        d_remoteStatus  = {
            "action":   "status",
            "meta":     {
                            "key":      "jid",
                            "value":    str_keyID
            }
        }

        computeStatus = pfurl.Pfurl(
            msg                         = json.dumps(d_remoteStatus),
            verb                        = 'POST',
            http                        = '%s/%s' % (str_computeServiceAddr, str_computeServiceURL),
            b_quiet                     = False,
            b_raw                       = True,
            b_httpResponseBodyParse     = False,
            jsonwrapper                 = 'payload'
        )

        self.dp.qprint("Calling remote compute service...", comms = 'rx')
        d_computeStatus                         = computeStatus()
        d_computeResponse                       = json.loads(d_computeStatus)
        d_computeResponse['d_ret']['status']    = True 
        self.dp.qprint("d_computeResponse = %s" % self.pp.pformat(d_computeResponse).strip(), comms = 'tx')
        return d_computeResponse

    """
    The following method adapted from:
    https://stackoverflow.com/questions/9807634/find-all-occurrences-of-a-key-in-nested-python-dictionaries-and-lists
    """
    @staticmethod
    def gen_dict_extract(key, var):
        if hasattr(var,'items'):
            for k, v in var.items():
                if k == key:
                    yield v
                if isinstance(v, dict):
                    for result in StoreHandler.gen_dict_extract(key, v):
                        yield result
                elif isinstance(v, list):
                    for d in v:
                        for result in StoreHandler.gen_dict_extract(key, d):
                            yield result

    def jobOperation_blockUntil(self, *args, **kwargs):
        """
        Block until a given job operation reaches a given status,
        or optionally until a timeout has passed.
        """
        b_jobStatusCheck    = False
        # d_request is used only by the compute ops
        d_request           = {}
        d_status            = {}
        str_keyID           = 'none'
        str_op              = 'none'
        str_status          = 'none'
        str_action          = 'none'
        timeout             = 60
        pollInterval        = 1

        for k,v in kwargs.items():
            if k == 'key':      str_keyID   = v
            if k == 'op':       str_op      = v
            if k == 'status':   str_status  = v
            if k == 'timeout':  timeout     = v
            if k == 'request':  d_request   = v

        kwargs['action']    = 'get'

        while not b_jobStatusCheck:
            if str_op == 'pushPath' or str_op == 'pullPath':
                # pudb.set_trace()
                d_jobOperation      = self.jobOperation_do(     key     = str_keyID,
                                                                action  = 'getInfo',
                                                                op      = str_op)
                str_jobStatus       = d_jobOperation['info'][str_op]['status']
                d_jobReturn         = d_jobOperation['info'][str_op]['return']
                if str_jobStatus == str_status: b_jobStatusCheck    = True

            if str_op == 'compute':
                # pudb.set_trace()
                d_jobOperation      = self.jobOperation_computeStatusQuery(
                                                                key     = str_keyID,
                                                                request = d_request)
                # l_remoteStatus      = list(StoreHandler.gen_dict_extract('Status', d_jobOperation))
                # self.dp.qprint('remoteStatus = %s' % l_remoteStatus, comms = 'tx')
                # b_jobStatusCheck    = True
                # for hit in l_remoteStatus:
                #     b_jobStatusCheck    =   hit['Message']  == 'finished' and \
                #                             hit['State']    == 'complete' and \
                #                             b_jobStatusCheck
                #     self.dp.qprint('compute job status check = %d' % b_jobStatusCheck)
                l_status            = d_jobOperation['d_ret']['l_status']
                lb_status           = []
                for job in l_status:
                    if 'finished' in job:   lb_status.append(True)
                    else:                   lb_status.append(False)
                b_jobStatusCheck    = lb_status[0]
                for flag in lb_status:
                    b_jobStatusCheck    = flag and b_jobStatusCheck
                d_jobReturn         = d_jobOperation['d_ret']
            # self.dp.qprint('blocking on %s' % str_op, comms = 'status')
            time.sleep(pollInterval)
        self.dp.qprint('return from %s' % str_op, comms = 'status')
        self.dp.qprint('d_jobReturn = \n%s' % self.pp.pformat(d_jobReturn).strip(), comms = 'status')
        return d_jobReturn

    def data_asyncHandler(self, *args, **kwargs):
        """
        The data handler. This method performs the push/pull (depending on the 
        JSON input payload). Significantly, this method threads the actual data
        IO operation and thus returns to caller immediately.

        Status of a particular data IO operation is stored in a global identifier
        which is indexed by some 'key' (typically a job id, 'jid' parameter) in
        the JSON directive supplied by the calling process.

        Downstream processing should block where appropriate based on examining
        the global status.

        'jobstatus': {
            'purpose':  'this structure keeps track of job status: pathPush/pull and compute.',
            'organization': 'the tree is /jobstatus/<someKey>/info',
            'info': {
                'pushPath': {
                    'status':   '<statusString>',
                    'return':   <d_ret>
                    },
                'compute':  {
                    'status':   '<statusString>',
                    'return':   <d_ret>
                    },
                'pullPath': {
                    'status':   '<statusString>',
                    'return':   <d_ret>
                    }
            }store_true
        }

        """
        d_request   = {}
        d_ret       = {}
        str_key     = ''
        str_op      = ''

        for k,v in kwargs.items():
            if k == 'request':  d_request   = v
            if k == 'key':      str_key     = v
            if k == 'op':       str_op      = v

        t_dataSync_handler  = threading.Thread( target      = self.dataRequest_process,
                                                args        = (),
                                                kwargs      = kwargs)

        # Set the state of the actual data jobOperation being called to 'pushing'...
        self.jobOperation_do(   action      = 'set',
                                key         = str_key,
                                op          = str_op,
                                status      = 'pushing'
        )

        # and start the thread about the actual push
        t_dataSync_handler.start()

        # finally return a True
        return True

    def key_dereference(self, *args, **kwargs):
        """
        Given the 'coordinate' JSON payload, deference the 'key' and return
        its value in a dictionary.

        {   
            'status', <status>,
            key': <val>
        }

        """
        self.dp.qprint("key_dereference()", comms = 'status')
        
        b_status    = False
        d_request   = {}
        str_key     = ''
        for k,v in kwargs.items():
            if k == 'request':      d_request   = v

        # self.dp.qprint("d_request = %s" % d_request)

        if 'meta-store' in d_request:
            d_metaStore     = d_request['meta-store']
            if 'meta' in d_metaStore:
                str_storeMeta   = d_metaStore['meta']
                str_storeKey    = d_metaStore['key']
                if str_storeKey in d_request[str_storeMeta].keys():
                    str_key     = d_request[str_storeMeta][str_storeKey]
                    b_status    = True
                    self.dp.qprint("key = %s" % str_key, comms = 'status')
        return {
            'status':   b_status,
            'key':      str_key
        }

    def coordinate_process(self, *args, **kwargs):
        """
        The main coordination method entry point.

        This method (and sub-methods) is responsible for copying data to remote,
        calling the remote process, and copying results back.

        PRECONDITIONS:

        Input JSON is assumed to be:

        pfurl --verb POST --raw --http 10.17.24.163:5005/api/v1/cmd --httpResponseBodyParse --jsonwrapper 'payload' --msg '
        {   "action":           "coordinate",
            "threadAction":     true,
            "meta-store": {
                        "meta":         "meta-compute",
                        "key":          "jid"
            },

            "meta-data": {
                "remote": {
                        "key":          "%meta-store"
                },
                "localSource": {
                        "path":         "/home/rudolph/Pictures"
                },
                "localTarget": {
                        "path":         "/home/tmp/Pictures",
                        "createDir":    true
                },
                "specialHandling": {
                        "op":           "dsplugin",
                        "cleanup":      true
                },
                "transport": {
                    "mechanism":    "compress",
                    "compress": {
                        "encoding": "none",
                        "archive":  "zip",
                        "unpack":   true,
                        "cleanup":  true
                    }
                },
                "service":              "megalodon"
            },

            "meta-compute":  {
                "cmd":      "$execshell $selfpath/$selfexec --prefix test- --sleepLength 0 /share/incoming /share/outgoing",
                "auid":     "rudolphpienaar",
                "jid":      "simpledsapp-1",
                "threaded": true,
                "container":   {
                        "target": {
                            "image":            "fnndsc/pl-simpledsapp",
                            "cmdParse":         true
                        },
                        "manager": {
                            "image":            "fnndsc/swarm",
                            "app":              "swarm.py",
                            "env":  {
                                "meta-store":   "key",
                                "serviceType":  "docker",
                                "shareDir":     "%shareDir",
                                "serviceName":  "testService"
                            }
                        }
                },
                "service":              "megalodon"
            }
        }
        '

        :param args:
        :param kwargs:
        :return:
        """

        global Gd_internalvar

        self.dp.qprint("coordinate_process()", comms = 'status')
        b_status                    = False
        d_request                   = {}
        d_jobOperation              = {}
        d_dataRequest               = {}
        d_dataRequestProcessPush    = {}
        d_computeRequest            = {}
        d_computeRequestProcess     = {}
        d_dataRequestProcessPull    = {}
        coordBlockSeconds           = Gd_internalvar['self']['coordBlockSeconds']

        for k,v in kwargs.items():
            if k == 'request':      d_request   = v
        # self.dp.qprint("d_request = %s" % d_request)

        str_key         = self.key_dereference(request = d_request)['key']

        # pudb.set_trace()
        str_flatDict    = json.dumps(d_request)
        d_request       = json.loads(str_flatDict.replace('%meta-store', str_key))
        d_metaData      = d_request['meta-data']
        d_metaCompute   = d_request['meta-compute']

        # Set the status of all job operations to 'init'...
        self.jobOperation_do(   action      = 'set',
                                key         = str_key,
                                op          = 'all',
                                status      = 'init'
                            )
        #######
        # Push data to remote location        
        #######
        d_metaData['local'] = d_metaData['localSource']
        self.dp.qprint('metaData = %s' % self.pp.pformat(d_metaData).strip(), comms = 'status')
        d_dataRequest   = {
            'action':   'pushPath',
            'meta':     d_metaData
        }

        self.data_asyncHandler(         request = d_dataRequest, 
                                        key     = str_key,
                                        op      = 'pushPath')

        d_jobBlock                  = self.jobOperation_blockUntil(   
                                        key     = str_key,
                                        op      = 'pushPath',
                                        status  = 'done'
                                    )
        b_status                    = d_jobBlock['status']

        if not b_status:
            self.jobOperation_do(
                                        action  = 'set',
                                        key     = str_key,
                                        op      = 'pushPath',
                                        status  = False
            )

        if b_status:
            d_jobOperation          = self.jobOperation_do( 
                                        key     = str_key,
                                        action  = 'getInfo',
                                        op      = 'pushPath')
            self.dp.qprint('d_jobOperation = %s' % self.pp.pformat(d_jobOperation).strip(), comms = 'status')
                                            
            d_dataRequestProcessPush    = d_jobOperation['info']['pushPath']['return']

            #######
            # Process data at remote location
            #######
            str_serviceName = d_dataRequestProcessPush['serviceName']
            str_shareDir    = d_dataRequestProcessPush['d_ret']['%s-data' % str_serviceName]['stdout']['compress']['remoteServer']['postop']['shareDir']
            str_outDirPath  = d_dataRequestProcessPush['d_ret']['%s-data' % str_serviceName]['stdout']['compress']['remoteServer']['postop']['outgoingPath']
            str_outDirParent, str_outDirOnly = os.path.split(str_outDirPath)
            # pudb.set_trace()
            d_metaCompute['container']['manager']['env']['shareDir']    = str_shareDir
            self.dp.qprint('metaCompute = %s' % self.pp.pformat(d_metaCompute).strip(), comms = 'status')
            d_computeRequest   = {
                'action':   'run',
                'meta':     d_metaCompute
            }

            d_computeRequestProcess = self.computeRequest_process(  request     = d_computeRequest,
                                                                    key         = str_key,
                                                                    op          = 'compute')
            # wait 1s for processing...
            self.dp.qprint('compute job submitted... waiting %ds for transients...' % coordBlockSeconds)
            time.sleep(coordBlockSeconds)
            # pudb.set_trace()
            d_jobBlock                  = self.jobOperation_blockUntil(   
                                            request = d_computeRequest,
                                            key     = str_key,
                                            op      = 'compute',
                                            status  = 'done')
            self.dp.qprint('compute d_jobBlock = %s' % self.pp.pformat(d_jobBlock).strip(), comms = 'status')
            b_status                    = d_jobBlock['status']
            if not b_status:
                self.jobOperation_do(
                                            action  = 'set',
                                            key     = str_key,
                                            op      = 'compute',
                                            status  = False
                )
            if b_status:
                #######
                # Pull data from remote location
                #######                                                                
                # pudb.set_trace()
                str_localDestination                = d_metaData['localTarget']['path']
                str_localParentPath, str_localDest  = os.path.split(str_localDestination)        
                d_metaData['local']                 = {'path': str_localDestination}
                if 'createDir' in d_metaData['localTarget']:
                    d_metaData['local']['createDir'] = d_metaData['localTarget']['createDir']
                d_metaData['transport']['compress']['name']   = str_localDest
                self.dp.qprint('metaData = %s' % self.pp.pformat(d_metaData).strip(), comms = 'status')

                d_dataRequest   = {
                    'action':   'pullPath',
                    'meta':     d_metaData
                }
                self.data_asyncHandler(         request = d_dataRequest, 
                                                key     = str_key,
                                                op      = 'pullPath')

                d_jobBlock                  = self.jobOperation_blockUntil(   
                                                key     = str_key,
                                                op      = 'pullPath',
                                                status  = 'done'
                                            )
                b_status                    = d_jobBlock['status']
                if not b_status:
                    self.jobOperation_do(
                                                action  = 'set',
                                                key     = str_key,
                                                op      = 'pullPath',
                                                status  = False
                    )
                if b_status:
                    d_jobOperation              = self.jobOperation_do( key     = str_key,
                                                                        action  = 'getInfo',
                                                                        op      = 'pullPath')
                    d_dataRequestProcessPull    = d_jobOperation['info']['pullPath']['return']

        return {
            'status':   b_status,
            'pushData': d_dataRequestProcessPush,
            'compute':  d_computeRequest,
            'pullData': d_dataRequestProcessPull
        }

    def status_process(self, *args, **kwargs):
        """
        Simply returns to caller the 'info' dictionary structure for a give remote
        key store.

        JSON query:

        pfurl --verb POST --raw --http 10.17.24.163:5005/api/v1/cmd --httpResponseBodyParse --jsonwrapper 'payload' --msg '
        {   "action":           "status",
            "threadAction":     false,
            "meta": {
                "remote": {
                        "key":          "simpledsapp-1"
                }
            }
        }'

        """
        self.dp.qprint("status_process()", comms = 'status')
        d_request                   = {}
        d_meta                      = {}
        d_jobOperation              = {}
        b_status                    = False

        for k,v in kwargs.items():
            if k == 'request':      d_request   = v
        
        d_meta      = d_request['meta']
        str_keyID   = d_meta['remote']['key']

        d_jobOperation      = self.jobOperation_do(     key     = str_keyID,
                                                        action  = 'getInfo',
                                                        op      = 'all')
        self.dp.qprint('d_status = %s' % self.pp.pformat(d_jobOperation).strip(), comms = 'status')

        return {
            'status':       d_jobOperation['status'],
            'jobOperation': d_jobOperation
        }


    def do_POST(self, *args, **kwargs):
        """
        Main dispatching method for coordination service.

        The following actions are available:

            * hello
            * coordinate
            * status
            * servicectl

        :param kwargs:
        :return:
        """

        d_msg       = {}
        d_done      = {}
        b_threaded  = False

        # Parse the form data posted
        self.dp.qprint(str(self.headers), comms = 'rx')

        length              = self.headers['content-length']
        data                = self.rfile.read(int(length))
        form                = self.form_get('POST', data)
        d_form              = {}
        d_ret               = {
            'msg':      'In do_POST',
            'status':   True,
            'formsize': sys.getsizeof(form)
        }

        self.dp.qprint('data length = %d' % len(data),   comms = 'status')
        self.dp.qprint('form length = %d' % len(form), comms = 'status')

        if len(form):
            self.dp.qprint("Unpacking multi-part form message...", comms = 'status')
            for key in form:
                self.dp.qprint("\tUnpacking field '%s..." % key, comms = 'status')
                d_form[key]     = form.getvalue(key)
            d_msg               = json.loads((d_form['d_msg']))
        else:
            self.dp.qprint("Parsing JSON data...", comms = 'status')
            d_data              = json.loads(data.decode())
            d_msg               = d_data['payload']

        self.dp.qprint('d_msg = %s' % self.pp.pformat(d_msg).strip(), comms = 'status')

        if 'action' in d_msg:
            self.dp.qprint("verb: %s detected." % d_msg['action'], comms = 'status')
            str_method      = '%s_process' % d_msg['action']
            self.dp.qprint("method to call: %s(request = d_msg) " % str_method, comms = 'status')
            d_done          = {'status': False}
            try:
                pf_method   = getattr(self, str_method)
            except  AttributeError:
                raise NotImplementedError("Class `{}` does not implement `{}`".format(self.__class__.__name__, pf_method))
            
            if 'threadAction' in d_msg:
                b_threaded  = int(d_msg['threadAction'])

            if not b_threaded:
                d_done      = pf_method(request = d_msg)
                self.dp.qprint(self.pp.pformat(d_done).strip(), comms = 'tx')
                d_ret       = d_done
            else:
                t_process   = threading.Thread( target  = pf_method,
                                                args    = (),
                                                kwargs  = {'request': d_msg})
                t_process.start()
                time.sleep(0.1)

        self.ret_client(d_ret)
        return d_ret

    def do_POST_serverctl(self, d_meta):
        """
        """
        d_ctl               = d_meta['ctl']
        self.dp.qprint('Processing server ctl...', comms = 'status')
        self.dp.qprint(d_meta, comms = 'rx')
        if 'serverCmd' in d_ctl:
            if d_ctl['serverCmd'] == 'quit':
                self.dp.qprint('Shutting down server', comms = 'status')
                d_ret = {
                    'msg':      'Server shut down',
                    'status':   True
                }
                self.dp.qprint(d_ret, comms = 'tx')
                self.ret_client(d_ret)
                os._exit(0)

    def ret_client(self, d_ret):
        """
        Simply "writes" the d_ret using json and the client wfile.

        :param d_ret:
        :return:
        """
        if not G_b_httpResponse:
            self.wfile.write(json.dumps(d_ret).encode())
        else:
            self.wfile.write(str(Response(json.dumps(d_ret))).encode())


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """
    Handle requests in a separate thread.
    """

    def col2_print(self, str_left, str_right):
        print(Colors.WHITE +
              ('%*s' % (self.LC, str_left)), end='')
        print(Colors.LIGHT_BLUE +
              ('%*s' % (self.RC, str_right)) + Colors.NO_COLOUR)

    def __init__(self, *args, **kwargs):
        """

        Holder for constructor of class -- allows for explicit setting
        of member 'self' variables.

        :return:
        """
        global Gd_internalvar
        global Gd_tree
        HTTPServer.__init__(self, *args, **kwargs)
        self.LC             = 40
        self.RC             = 40
        self.args           = None
        self.str_desc       = 'pfcon'
        self.str_name       = self.str_desc
        self.str_version    = ''

        self.dp             = debug(verbosity=0, level=-1)

    def leaf_process(self, **kwargs):
        """
        Process the global Gd_tree and perform possible env substitutions.
        """
        global Gd_tree
        str_path    = ''
        str_target  = ''
        str_newVal  = ''

        for k,v in kwargs.items():
            if k == 'where':    str_path    = v
            if k == 'replace':  str_target  = v
            if k == 'newVal':   str_newVal  = v

        str_parent, str_file    = os.path.split(str_path)
        str_pwd                 = Gd_tree.cwd()
        if Gd_tree.cd(str_parent)['status']:
            str_origVal     = Gd_tree.cat(str_file)
            str_replacement = str_origVal.replace(str_target, str_newVal)
            Gd_tree.touch(str_path, str_replacement)
        Gd_tree.cd(str_pwd)

    def setup(self, **kwargs):
        global G_b_httpResponse
        global Gd_tree
        str_defIP       = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
        str_defIPpman   = str_defIP
        str_defIPpfioh  = str_defIP

        if 'HOST_IP' in os.environ:
            str_defIP       = os.environ['HOST_IP']
            str_defIPpman   = os.environ['HOST_IP']
            str_defIPpfioh  = os.environ['HOST_IP']

        if 'PMAN_PORT_5010_TCP_ADDR' in os.environ:
            str_defIPpman   = os.environ['PMAN_PORT_5010_TCP_ADDR']
        if 'PFIOH_PORT_5055_TCP_ADDR' in os.environ:
            str_defIPpfioh  = os.environ['PFIOH_PORT_5055_TCP_ADDR']

        for k,v in kwargs.items():
            if k == 'args': self.args           = v
            if k == 'desc': self.str_desc       = v
            if k == 'ver':  self.str_version    = v

        G_b_httpResponse = self.args['b_httpResponse']
        print(self.str_desc)

        Gd_internalvar['self']['name']                  = self.str_name
        Gd_internalvar['self']['version']               = self.str_version
        Gd_internalvar['self']['coordBlockSeconds']     = int(self.args['coordBlockSeconds'])

        self.col2_print("Listening on address:",    self.args['ip'])
        self.col2_print("Listening on port:",       self.args['port'])
        self.col2_print("Server listen forever:",   self.args['b_forever'])
        self.col2_print("Return HTTP responses:",   G_b_httpResponse)

        Gd_tree.initFromDict(Gd_internalvar)

        self.leaf_process(  where   = '/service/host/data/addr', 
                            replace = '%PFIOH_IP', 
                            newVal  = str_defIPpfioh)
        self.leaf_process(  where   = '/service/host/compute/addr', 
                            replace = '%PMAN_IP', 
                            newVal  = str_defIPpman)

        print(Colors.YELLOW + "\n\t\tInternal data tree:")
        print(C_snode.str_blockIndent(str(Gd_tree), 3, 8))

        print(Colors.LIGHT_GREEN + "\n\n\tWaiting for incoming data..." + Colors.NO_COLOUR)


