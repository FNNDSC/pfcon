
import logging
logging.disable(logging.CRITICAL)

import  sys, os

from    io              import  BytesIO as IO
from    http.server     import  BaseHTTPRequestHandler, HTTPServer
from    socketserver    import  ThreadingMixIn
from    webob           import  Response
from    pathlib         import  Path
import  cgi
import  json
import  urllib
import  ast
import  datetime
import  time
import  pprint

import  threading
import  platform
import  socket
import  psutil
import  multiprocessing
import  pfurl

# debugging utilities
import  pudb

# pfcon local dependencies
import  pfmisc
from    pfmisc._colors      import  Colors
from    pfmisc.debug        import  debug
from    pfmisc.C_snode      import C_snode, C_stree

from .swiftmanager import SwiftManager


# Horrible global var
G_b_httpResponse            = False

Gd_internalvar  = {
    'self': {
        'name':                 'pfcon',
        'version':              'undefined',
        'verbosity':            1,
        'coordBlockSeconds':    10,
        'debugToDir':           '',
        'httpProxy':    {
            'use':              False,
            'httpSpec':         ''
        }
    },
    "swift": {
        "auth_url":                 "http://swift_service:8080/auth/v1.0",
        "username":                 "chris:chris1234",
        "key":                      "testing",
        "container_name":           "users",
        "auto_create_container":    True,
        "file_storage":             "swift.storage.SwiftStorage"
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
                },
            'swiftPut': {
                'status':   '<statusString>',
                'return':   '<d_ret>'
                }
        }
    },
    'service':  {
        'host': {
            'data': {
                'addr':             '%PFIOH_IP:5055',
                'baseURLpath':      'api/v1/cmd/',
                'status':           'undefined',
                'authToken':        'password'
            },
            'compute': {
                'addr':             '%PMAN_IP:5010',
                'baseURLpath':      'api/v1/cmd/',
                'status':           'undefined',
                'authToken':        'password'
            }
        },
        'localhost': {
            'data': {
                'addr':             '127.0.0.1:5055',
                'baseURLpath':      'api/v1/cmd/',
                'status':           'undefined'
            },
            'compute': {
                'addr':         '127.0.0.1:5010',
                'baseURLpath':  'api/v1/cmd/',
                'status':       'undefined'
            }
        },
        "moc": {
            "compute": {
                "addr":         "pman-radiology.k-apps.osh.massopen.cloud",
                "baseURLpath":  "api/v1/cmd/",
                "status":       "undefined"
            },
            "data": {
                "addr":         "pfioh-radiology.k-apps.osh.massopen.cloud",
                "baseURLpath":  "api/v1/cmd/",
                "status":       "undefined"
            }
        },
        "openshiftlocal": {
            "compute": {
                "addr":                         "pman-myproject.127.0.0.1.nip.io",
                "baseURLpath":                  "api/v1/cmd/",
                "status":                       "undefined",
                "authToken":                    "password"
            },
            "data": {
                "addr":                         "pfioh-myproject.127.0.0.1.nip.io",
                "baseURLpath":                  "api/v1/cmd/",
                "status":                       "undefined",
                "authToken":                    "password"
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
        self.str_debugToDir     = Gd_internalvar['self']['debugToDir']
        self.b_quiet            = True

        self.verbosity          = Gd_internalvar['self']['verbosity']
        self.dp                 = pfmisc.debug(
                                            verbosity   = self.verbosity,
                                            within      = self.__name__
                                            )
        self.pp                 = pprint.PrettyPrinter(indent=4)

        self.b_treeLocked       = False
        self.initial_wait       = 0.2
        self.max_wait           = 120

        for k,v in kwargs.items():
            if k == 'test': b_test  = True

        if not b_test:
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        d_server            = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        d_meta              = ast.literal_eval(d_server['meta'])

        d_msg               = {'action': d_server['action'], 'meta': d_meta}
        d_ret               = {}
        print("Request: " + self.headers + '\n' + d_msg)
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
        """
        hits            = 0

        def fileContentsReplaceAtPath(str_path, **kwargs):
            nonlocal    hits
            b_status        = True
            str_target      = ''
            str_value       = ''
            l_fileChanged = []

            self.dp.qprint('In dir = %s, hits = %d' % (str_path, hits))

            for k, v in kwargs.items():
                if k == 'target':   str_target  = v
                if k == 'value':    str_value   = v

            for str_hit in Gd_tree.lsf(str_path):
                str_content = Gd_tree.cat(str_hit)
                self.dp.qprint('%20s: %20s' % (str_hit, str_content))
                if str_content  == str_target:
                    self.dp.qprint('%20s: %20s' % (str_hit, str_value))
                    Gd_tree.touch(str_hit, str_value)
                    b_status    = True
                    hits        = hits + 1
                    l_fileChanged.append(str_path + '/' + str_hit)

            return {
                    'status':           b_status,
                    'l_fileChanged':    l_fileChanged
                    }

        d_meta      = {}
        d_ret       = {}
        b_status    = False

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
                b_tree          = False

                try:
                    d_set       = json.loads(d_meta['set'])
                except:
                    str_set     = json.dumps(d_meta['set'])
                    d_set       = json.loads(str_set)
                    if isinstance(d_set, dict):
                        b_tree  = True
                if b_tree:
                    D       = C_stree()
                    D.initFromDict(d_set)
                    for topDir in D.lstr_lsnode():
                        D.copy(startPath = '/'+topDir, destination = Gd_tree, pathDiskRoot = str_var)
                    d_ret           = d_set
                else:
                    Gd_tree.touch(str_var, d_meta['set'])
                    d_ret[str_var]          = Gd_tree.cat(str_var)
                b_status                = True

            if 'valueReplace' in d_meta.keys():
                # Find all the values in the internalctl tree
                # and replace the value corresponding to 'var' with
                # the field of 'valueReplace'
                #
                str_target      = d_meta['var']
                str_value       = d_meta['valueReplace']
                if str_value    == 'ENV':
                    if str_target.strip('%') in os.environ:
                        str_value   = os.environ[str_target.strip('%')]
                d_ret = Gd_tree.treeExplore(
                        f       = fileContentsReplaceAtPath,
                        target  = str_target,
                        value   = str_value
                        )
                b_status        = d_ret['status']
                d_ret['hits']   = hits

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

    def dataRequest_processPushPath(self, *args, **kwargs):
        """
        This method handles the processing of data to push out to a
        compute environment. In the JSON input specification the
        'local' denotes the source to push -- this is a path-like
        descriptor that originally denoted an actual path on the
        filesystem accessible to pfcon.

        If, however, the 'local' has a directive:

            {'storageType': 'swift'}

        then the path spec is a location in object storage.

        This method will pull from object storage all elements that
        conform to the path spec, and store on the local filesystem
        in a directory with the same name.

        Thus, this method effectively mirrors a location in object
        storage out to local storage (prepending a leading '/' to the
        local storage path).
        """
        d_ret   = {
            'status':       False,
            'd_swiftPull':  {},
            'localpath':    ""
        }
        d_meta  = {}

        for k,v in kwargs.items():
            if k == 'd_meta':   d_meta = v

        # pudb.set_trace()
        if 'local' in d_meta:
            d_local     = d_meta['local']
            if 'storageType' in d_local:
                if d_local['storageType'] == 'swift':
                    d_ret['d_swiftPull']    = SwiftManager.objPull(
                                                    fromLocation = d_local['path'],
                                                    tree = Gd_tree
                                                )
                    d_ret['status']         = True
                    d_ret['localpath']      = d_ret['d_swiftPull']['localpath']
                    d_meta['local']['path'] = d_ret['localpath']

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
        self.dp.qprint("dataRequest_process()", comms = 'status')

        d_request       = {}
        # The return from the remote call
        d_ret           = {}
        # The return from this method
        str_metaHeader  = 'meta'
        str_key         = 'none'
        str_op          = ''

        for k,v in kwargs.items():
            if k == 'request':          d_request           = v
            if k == 'metaHeader':       str_metaHeader      = v
            if k == 'key':              str_key             = v
            if k == 'op':               str_op              = v

        d_meta          = d_request[str_metaHeader]

        if str_op == 'pushPath':
            d_pushPath = self.dataRequest_processPushPath(d_meta = d_meta)

        # pudb.set_trace()
        str_remoteService       = d_meta['service']
        str_dataServiceAddr     = Gd_tree.cat('/service/%s/data/addr'       % str_remoteService)
        str_dataServiceURL      = Gd_tree.cat('/service/%s/data/baseURLpath'% str_remoteService)
        str_token               = Gd_tree.cat('/service/%s/data/authToken'  % str_remoteService)
        str_serviceMan          = Gd_tree.cat('/service/%s/data/serviceMan' % str_remoteService)
        if not str_token:
            str_token = None
        if str_serviceMan:
            d_request[str_metaHeader]['serviceMan']   = str_serviceMan

        # This dump to file is only for debugging, if tracking the actual
        # pfurl JSON payload is useful.
        # with open("/tmp/pfurl.json", "w") as f:
        #     json.dump(d_request, f, indent = 4)
        dataComs = pfurl.Pfurl(
            msg                         = json.dumps(d_request),
            verb                        = 'POST',
            http                        = '%s/%s' % (str_dataServiceAddr, str_dataServiceURL),
            b_quiet                     = False,
            b_raw                       = True,
            b_httpResponseBodyParse     = True,
            jsonwrapper                 = '',
            authToken                   = str_token,
            httpProxy                   = Gd_tree.cat('/self/httpProxy/httpSpec')
        )
        self.dp.qprint("Calling remote data service...",   comms = 'rx')
        # pudb.set_trace()
        d_dataComs          = dataComs()
        str_response        = d_dataComs.split('\n')
        str_responseStatus  = str_response[0]
        if len(str_response) > 1 and '200 OK' == str_responseStatus:
            # Unusual case caused by pfurl returning a response string,
            # during parsing of hello response, starting with "200 OK\n"
            # Isolates json payload from request headers
            d_dataComs = str_response[-1].replace('\\', '')
            if d_dataComs[-1] == '\"':
                d_dataComs = d_dataComs[:-1]

        d_dataResponse                          = json.loads(d_dataComs)
        d_ret['%s-data' % str_remoteService]    = d_dataResponse

        d_return = {
            'd_ret':        d_ret,
            'serviceName':  str_remoteService,
            'status':       d_dataResponse['stdout']['status']
        }

        self.jobStatus_do(      action      = 'set',
                                key         = str_key,
                                op          = str_op,
                                status      = True,
                                jobReturn   = d_return)
        return d_return

    def computeRequest_process(self, *args, **kwargs):
        """
        Method for talking to the data handling service.

        Return JSON information from remote process is returned directly by this method,
        and also stored in the internal key_ID tree.

        :param args:
        :param kwargs:
        :return: JSON object from the 'pman' call.
        """
        self.dp.qprint("computeRequest_process()", comms = 'status')

        d_request       = {}
        # The return from the remote call
        d_ret           = {}
        # The return from this method
        str_metaHeader  = 'meta'
        str_key         = ''
        str_op          = ''

        for k,v in kwargs.items():
            if k == 'request':          d_request           = v
            if k == 'metaHeader':       str_metaHeader      = v
            if k == 'key':              str_key             = v
            if k == 'op':               str_op              = v

        #pudb.set_trace()
        d_meta                  = d_request[str_metaHeader]
        str_remoteService       = d_meta['service']
        str_computeServiceAddr  = Gd_tree.cat('/service/%s/compute/addr'        % str_remoteService)
        str_computeServiceURL   = Gd_tree.cat('/service/%s/compute/baseURLpath' % str_remoteService)

        str_token = Gd_tree.cat('/service/%s/compute/authToken'% str_remoteService)
        if not str_token:
            str_token = None
        # Remember, 'pman' responses do NOT need to http-body parsed!
        computeComs = pfurl.Pfurl(
            msg                         = json.dumps(d_request),
            verb                        = 'POST',
            http                        = '%s/%s' % (str_computeServiceAddr, str_computeServiceURL),
            b_quiet                     = False,
            b_raw                       = True,
            b_httpResponseBodyParse     = False,
            jsonwrapper                 = 'payload',
            authToken                   = str_token,
            httpProxy                   = Gd_tree.cat('/self/httpProxy/httpSpec')
        )

        self.dp.qprint("Calling remote compute service...", comms = 'rx')
        d_computeComs                           = computeComs()
        d_computeResponse                       = json.loads(d_computeComs)
        d_ret['%s-computeRequest' % str_remoteService] = d_computeResponse

        d_return = {
            'd_ret':        d_ret,
            'serviceName':  str_remoteService,
            'status':       d_computeResponse['status']
        }

        # if there is a key associated with this request, also determine
        # the jobStatus associated with this key.
        if len(str_key):
            self.jobStatus_do(      action      = 'set',
                                    key         = str_key,
                                    op          = str_op,
                                    status      = True,
                                    jobSubmit   = d_return)
        return d_return

    def hello_process_remote(self, *args, **kwargs):
        """
        Process the 'hello' call on the remote services
        """
        self.dp.qprint("hello_process_remote()", comms = 'status')
        # pudb.set_trace()

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
        """
        self.dp.qprint("hello_process()", comms = 'status')
        b_status            = False
        d_ret               = {}
        d_request           = {}

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

        d_remote    = self.hello_process_remote(request = d_request)

        return { 'd_ret':       d_ret,
                 'd_remote':    d_remote,
                 'status':      b_status}

    def jobStatus_do(self, *args, **kwargs):
        """
        Sets/gets the status of a specific operation in a given job.
        """
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
        b_jobSubmit = False
        d_jobSubmit = {}
        b_jobSwift  = False
        d_jobSwift  = {}

        for k,v in kwargs.items():
            if k == 'key':          str_keyID   = v
            if k == 'op':           str_op      = v
            if k == 'status':       str_status  = v
            if k == 'jobSubmit':
                b_jobSubmit                     = True
                d_jobSubmit                     = v
            if k == 'jobReturn':
                b_jobReturn                     = True
                d_jobReturn                     = v
            if k == 'jobSwift':
                b_jobSwift                      = True
                d_jobSwift                      = v
            if k == 'action':       str_action  = v

        # pudb.set_trace()

        if str_keyID != 'none':
            T           = self.tree_access()
            T.cd('/jobstatus')
            b_status    = True
            if not T.exists(str_keyID):
                T.mkcd(str_keyID)
                if str_action == 'getInfo':
                    # Set the status of all job operations to 'not found'...
                    d_ret = self.jobStatus_do(      action      = 'set',
                                                    key         = str_keyID,
                                                    op          = 'all',
                                                    status      = 'not found'
                                            )
                    b_status    = False
                    d_info      = d_ret['info']
            else:
                T.cd(str_keyID)
            if T.exists('info'):
                d_info  = T.cat('info')
                # NB NB NB! DEBUGGING NOTES:
                # The following creates terminal noise that should be commented out
                # if doing debugging otherwise the pudb screen gets corrupted.
                self.dp.qprint( "d_info = %s" % self.pp.pformat(d_info).strip(),
                                comms = 'status')
                if not isinstance(d_info['compute']['status'],  bool) or \
                   not isinstance(d_info['pullPath']['status'], bool) or \
                   not isinstance(d_info['pushPath']['status'], bool) or \
                   not isinstance(d_info['swiftPut']['status'], bool):
                    b_status = False
                else:
                    b_status =  d_info['compute']['status']     and \
                                d_info['pullPath']['status']    and \
                                d_info['pullPath']['status']    and \
                                d_info['swiftPut']['status']

            if str_op != 'none':
                if str_op == 'all':
                    l_opKey = ['pushPath', 'compute', 'pullPath', 'swiftPut']
                else:
                    if str_op in ['pushPath', 'compute', 'pullPath', 'swiftPut']:
                        l_opKey = [str_op]
                for k in l_opKey:
                    if str_action == 'set':
                        if not k in d_info.keys():
                            d_info[k]           = {}
                            d_info[k]['return'] = {}
                            d_info[k]['status'] = ''
                        d_info[k]['status'] = str_status
                        b_status            = True
                        if b_jobReturn:
                            d_info[k]['return'] = d_jobReturn
                        if b_jobSubmit:
                            d_info[k]['submit'] = d_jobSubmit
                        if b_jobSwift:
                            d_info[k]           = d_jobSwift
                    T.touch('info', d_info)

        # Unlock the Tree for other threads
        self.b_treeLocked = False
        time.sleep(1)

        return {
            'status':   b_status,
            'info':     d_info
        }

    def exponential_backoff(self, attempt):
        """

        Returns exponential backoff value based on the
        number of attempts

        Useful for retrying certain operations until
        a successful state is reached
        """
        return min(self.max_wait, self.initial_wait * 2 ** attempt)

    def tree_access(self):
        """

        Return a pointer to Gd_tree if no other execution
        thread is accessing the tree

        Prevents RunTime Error when iterating through
        Gd_tree or saving it to a local path
        """
        number_attempts = 0
        while self.b_treeLocked:
            time.sleep(self.exponential_backoff(number_attempts))
            number_attempts += 1
        self.b_treeLocked = True
        return Gd_tree

    def jobOperation_computeStatusQuery(self, *args, **kwargs):
        """
        Query the remote compute job status.
        """
        d_request           = {}
        str_keyID           = 'none'

        for k,v in kwargs.items():
            if k == 'key':      str_keyID   = v
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
        str_token = Gd_tree.cat('/service/%s/compute/authToken'% str_remoteService)
        if not str_token:
            str_token = None
        computeStatus = pfurl.Pfurl(
            msg                         = json.dumps(d_remoteStatus),
            verb                        = 'POST',
            http                        = '%s/%s' % (str_computeServiceAddr, str_computeServiceURL),
            b_quiet                     = False,
            b_raw                       = True,
            b_httpResponseBodyParse     = False,
            jsonwrapper                 = 'payload',
            authToken                   = str_token,
            httpProxy                   = Gd_tree.cat('/self/httpProxy/httpSpec')
        )

        self.dp.qprint("Calling remote compute service...", comms = 'rx')
        d_computeStatus                         = computeStatus()
        d_computeResponse                       = json.loads(d_computeStatus)
        # The following is a "circumstantial" hack predicated on fixing
        # a symptom and not the underlying issue. It seems that some calls
        # to the computeStatus() in the remote environment are not properly
        # parsed on return and are not packed properly into the dictionary
        # expected here. This is mostly observed in the openshift case.
        #
        # The "hack" catches this failure and attempts to communicate this
        # to upstream processing.
        try:
            d_computeResponse['d_ret']['status']    = True
        except:
            d_origResponse                          = d_computeResponse.copy()
            d_computeResponse                       = {}
            d_computeResponse['d_ret']              = {}
            d_computeResponse['d_ret']['status']    = False
            d_computeResponse['d_ret']['response']  = d_origResponse
            d_computeResponse['status']             = False
        self.dp.qprint("d_computeResponse = %s" % self.pp.pformat(d_computeResponse).strip(), comms = 'tx')
        return d_computeResponse

    def jobOperation_blockUntil(self, *args, **kwargs):
        """
        Block until a given job operation reaches a given status,
        or optionally until a timeout has passed.
        """
        b_jobStatusCheck    = False
        # d_request is used only by the compute ops
        d_request           = {}
        str_keyID           = 'none'
        str_op              = 'none'
        str_status          = 'none'
        pollInterval        = 1

        for k,v in kwargs.items():
            if k == 'key':      str_keyID   = v
            if k == 'op':       str_op      = v
            if k == 'status':   str_status  = v
            if k == 'request':  d_request   = v

        kwargs['action']    = 'get'

        while not b_jobStatusCheck:
            if str_op == 'pushPath' or str_op == 'pullPath':
                # pudb.set_trace()
                d_jobStatus      = self.jobStatus_do(           key     = str_keyID,
                                                                action  = 'getInfo',
                                                                op      = str_op)
                str_jobStatus       = d_jobStatus['info'][str_op]['status']
                d_jobReturn         = d_jobStatus['info'][str_op]['return']
                if str_jobStatus == str_status: b_jobStatusCheck    = True

            if str_op == 'swiftPut':
                d_jobStatus      = self.jobStatus_do(           key     = str_keyID,
                                                                action  = 'getInfo',
                                                                op      = str_op)
                d_jobReturn         = d_jobStatus['info'][str_op]['return']

            if str_op == 'compute':
                d_jobStatus      = self.jobOperation_computeStatusQuery(
                                                                key     = str_keyID,
                                                                request = d_request)
                # If the status of the request to the computeStatusQuery is
                # False (which in theory it never should be, but sometimes is)
                # then handle that by setting job status to False in the else
                # condition. This has the net effect of having pfcon attempt to
                # recheck the status condition. Note the idea of "False" or "True"
                # was supposed to be a False and True on the actual call, not the
                # results of the call.
                #
                # This "fix" is mostly only applicable to the openshift case.
                if d_jobStatus['status']:
                    l_status            = d_jobStatus['d_ret']['l_status']
                    lb_status           = []
                    for job in l_status:
                        if 'finished' in job:
                            lb_status.append(True)
                            self.jobStatus_do(      action      = 'set',
                                                    key         = str_keyID,
                                                    op          = str_op,
                                                    status      = True,
                                                    jobReturn   = d_jobStatus)
                        else:
                            lb_status.append(False)
                            self.jobStatus_do(      action      = 'set',
                                                    key         = str_keyID,
                                                    op          = str_op,
                                                    status      = False,
                                                    jobReturn   = d_jobStatus)
                    b_jobStatusCheck    = lb_status[0]
                    for flag in lb_status:
                        b_jobStatusCheck    = flag and b_jobStatusCheck
                    d_jobReturn         = d_jobStatus['d_ret']
                else:
                    self.jobStatus_do(      action      = 'set',
                                            key         = str_keyID,
                                            op          = str_op,
                                            status      = False,
                                            jobReturn   = d_jobStatus)
                    d_jobReturn         = d_jobStatus['d_ret']
            # self.dp.qprint('blocking on %s' % str_op, comms = 'status')
            time.sleep(pollInterval)
        self.dp.qprint( 'return from %s' % str_op,
                        comms = 'status')
        self.dp.qprint( 'd_jobReturn = \n%s' % \
                        self.pp.pformat(d_jobReturn).strip(),
                        comms = 'status')
        return d_jobReturn

    def data_asyncHandler(self, *args, **kwargs):
        """
        The data handler. This method performs the push/pull (depending on the
        JSON input payload). Significantly, this method threads the actual data
        IO operation and thus returns to caller immediately. The data IO
        operation, which uses `pfurl`, will itself block until the data IO is
        done.

        Status of a particular data IO operation is stored in a global identifier
        which is indexed by some 'key' (typically a job id, 'jid' parameter) in
        the JSON directive supplied by the calling process.

        Downstream processing should block where appropriate based on examining
        the global status by calling jobOperation_blockUntil() -- note that
        this method will also call jobStatus_do() which is the method that
        actually "prints"/logs the call status response.
        """
        str_key     = ''
        str_op      = ''

        for k,v in kwargs.items():
            if k == 'key':      str_key     = v
            if k == 'op':       str_op      = v

        #
        # NB NB NB -- DEBUGGING NOTE:
        # If debugging the dataRequest_process, it is sometimes best to
        # call it directly instead of threading it. Breakpoints in the
        # function seem to mess up pudb keys if threaded. In such a use
        # case uncomment the following call:
        ###
        # pudb.set_trace()
        # self.dataRequest_process(**kwargs)
        ###

        t_dataSync_handler  = threading.Thread( target      = self.dataRequest_process,
                                                args        = (),
                                                kwargs      = kwargs)

        # Set the state of the actual data jobOperation being called to 'pushing'...
        self.jobStatus_do(      action      = 'set',
                                key         = str_key,
                                op          = str_op,
                                status      = 'pushing'
        )

        # and start the thread about the actual push
        # (comment the following thread start if testing in synchronous mode)
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
                            "image":            "fnndsc/pl-simpledsapp"
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
        """
        self.dp.qprint("coordinate_process()", comms = 'status')
        b_status                    = False
        d_request                   = {}
        d_dataRequestProcessPush    = {}
        d_computeRequestProcess     = {}
        d_dataRequestProcessPull    = {}

        for k,v in kwargs.items():
            if k == 'request':      d_request   = v

        str_key                     = self.key_dereference(request = d_request)['key']
        str_flatDict                = json.dumps(d_request)
        d_request                   = json.loads(str_flatDict.replace('%meta-store', str_key))
        d_metaData                  = d_request['meta-data']
        d_metaCompute               = d_request['meta-compute']

        # Set the status of all job operations to 'not started'...
        self.jobStatus_do(      action      = 'set',
                                key         = str_key,
                                op          = 'all',
                                status      = 'not started'
                            )
        d_ret = {
            'status':               b_status,
            'pushData':             d_dataRequestProcessPush,
            'compute':              d_computeRequestProcess,
            'pullData':             d_dataRequestProcessPull,
            'd_swiftstore':         {},
            'd_jobStatus':          {},
            'd_jobStatusSummary':   {}
        }

        # pudb.set_trace()

        # Stop file storage directory deletion by pfurl to prevent
        # issues where running multiple jobs in parallel results in
        # removal of files that have not been pushed to swift
        if 'threadAction' in list(d_request.keys()):
            if d_request['threadAction']:
                d_metaData['localTarget']['createDir'] = False
                FS_Directory = d_metaData['localTarget']['path']
                if not os.path.exists(FS_Directory):
                    os.makedirs(FS_Directory)

                # The Line Below is useful for Debugging FS Directory
                # d_metaData['specialHandling']['cleanup'] = False

        # Check on propagation of error message!
        # If the status is false, the client will not be notified
        b_status, d_dataRequestProcessPush = self.pushData_handler(d_metaData, str_key)
        if b_status:
            b_status, d_computeRequestProcess = self.compute_handler(d_dataRequestProcessPush,
                                                                     d_metaCompute,
                                                                     d_computeRequestProcess,
                                                                     str_key)
            if b_status:
                b_status, d_dataRequestProcessPull, str_localDestination = self.pullData_handler(d_metaData,
                                                                                                 str_key,
                                                                                                 d_dataRequestProcessPull)
                if b_status:
                    b_status = self.swift_handler(d_ret, str_localDestination, str_key)
                    if b_status:
                        self.jobStatusFiles_create(d_ret, str_localDestination, str_key)
        return d_ret

    def pushData_handler(self, d_metaData, str_key):
        """
        Handle push to remote.

        Input           -- d_dataRequestProcessPush holder
        Return: bool    -- success
        """
        # default returns
        d_dataRequestProcessPush = {}

        d_metaData['local'] = d_metaData['localSource']
        self.dp.qprint('metaData = %s' % self.pp.pformat(d_metaData).strip(),
                       comms='status')
        d_dataRequest = {
            'action': 'pushPath',
            'meta': d_metaData
        }

        self.data_asyncHandler(request=d_dataRequest,
                               key=str_key,
                               op='pushPath')
        d_jobBlock = self.jobOperation_blockUntil(
            key=str_key,
            op='pushPath',
            status=True
        )
        b_status = d_jobBlock['status']

        if not b_status:
            self.jobStatus_do(
                action='set',
                key=str_key,
                op='pushPath',
                status=False
            )
        if b_status:
            d_jobStatus = self.jobStatus_do(
                key=str_key,
                action='getInfo',
                op='pushPath')
            self.dp.qprint('d_jobStatus = %s' % self.pp.pformat(d_jobStatus).strip(),
                           comms='status')

            d_dataRequestProcessPush = d_jobStatus['info']['pushPath']['return']
            time.sleep(0.2)

        return b_status, d_dataRequestProcessPush

    def pullData_handler(self, d_metaData, str_key, d_dataRequestProcessPull):
        """
        Handle pull from remote.
        """
        str_localDestination = d_metaData['localTarget']['path']
        str_localParentPath, str_localDest = os.path.split(str_localDestination)
        d_metaData['local'] = {'path': str_localDestination}
        if 'createDir' in d_metaData['localTarget']:
            d_metaData['local']['createDir'] = d_metaData['localTarget']['createDir']
        d_metaData['transport']['compress']['name'] = str_localDest
        self.dp.qprint('metaData = %s' % self.pp.pformat(d_metaData).strip(),
                       comms='status')
        d_dataRequest = {
            'action': 'pullPath',
            'meta': d_metaData
        }
        # pudb.set_trace()
        self.data_asyncHandler(request=d_dataRequest,
                               key=str_key,
                               op='pullPath')

        d_jobBlock = self.jobOperation_blockUntil(
            key=str_key,
            op='pullPath',
            status=True
        )
        b_status = d_jobBlock['status']
        if not b_status:
            self.jobStatus_do(
                action='set',
                key=str_key,
                op='pullPath',
                status=False
            )
        if b_status:
            d_jobStatus = self.jobStatus_do(key=str_key,
                                            action='getInfo',
                                            op='pullPath')
            d_dataRequestProcessPull.update(d_jobStatus['info']['pullPath']['return'])

        return b_status, d_dataRequestProcessPull, str_localDestination

    def swift_handler(self, d_ret, str_localDestination, str_key):
        """
        Put data pulled from previous process into swift.

        This is an "internal" process, so not asynchronous and does not require
        a separate blocking method.
        """
        if Gd_tree.exists('swift', path='/'):
            # There might be a timing issue with pushing files into swift and
            # the swift container being able to report them as accessible. The
            # solution is to push objects, and then poll on calls to swift 'ls'
            # and compare results with push record.
            waitPoll = 0
            maxWaitPoll = 10
            d_ret['d_swiftstore'] = SwiftManager.createFileList(
                root=str_localDestination,
                tree=Gd_tree
            )
            filesPushed = len(d_ret['d_swiftstore']['d_put']['d_result']['l_fileStore'])
            filesAccessible = 0
            while filesAccessible < filesPushed and waitPoll < maxWaitPoll:
                d_swift_ls = SwiftManager.ls(path=str_localDestination, tree=Gd_tree)
                filesAccessible = len(d_swift_ls['lsList'])
                time.sleep(0.2)
                waitPoll += 1
            d_ret['d_swift_ls'] = d_swift_ls
            d_ret['d_swiftstore']['waitPoll'] = waitPoll
            d_ret['d_swiftstore']['filesPushed'] = filesPushed
            d_ret['d_swiftstore']['filesAccessible'] = filesAccessible
            d_swift = {}
            d_swift['useSwift'] = True
            d_swift['d_swift_ls'] = d_swift_ls
            d_swift['d_swiftstore'] = d_ret['d_swiftstore']
            d_swift['status'] = d_swift['d_swift_ls']['status'] and \
                                d_swift['d_swiftstore']['status']
            self.jobStatus_do(
                action='set',
                key=str_key,
                op='swiftPut',
                status=True,
                jobSwift=d_swift
            )

            d_internalInfo = Gd_tree.cat('/jobstatus/%s/info' % str_key)

        if len(self.str_debugToDir):
            self.dp.qprint(
                'Info: d_internalInfo = \n%s' % json.dumps(d_internalInfo, indent=4),
                comms='status',
                teeFile='%s/d_internalInfo-%s.json' % (self.str_debugToDir, str_key),
                teeMode='w+')
        return d_swift['status']

    def compute_handler(self, d_dataRequestProcessPush, d_metaCompute, d_computeRequestProcess, str_key):
        """
        Handle compute.
        """
        coordBlockSeconds = Gd_internalvar['self']['coordBlockSeconds']
        str_serviceName = d_dataRequestProcessPush['serviceName']
        str_shareDir = \
        d_dataRequestProcessPush['d_ret']['%s-data' % str_serviceName]['stdout'][
            'compress']['remoteServer']['postop'].get('shareDir')
        str_outDirPath = \
        d_dataRequestProcessPush['d_ret']['%s-data' % str_serviceName]['stdout'][
            'compress']['remoteServer']['postop'].get('outgoingPath')
        if str_outDirPath is not None:
            # This value will not be none in case of non-swift option.
            str_outDirParent, str_outDirOnly = os.path.split(str_outDirPath)
        d_metaCompute['container']['manager']['env']['shareDir'] = str_shareDir
        self.dp.qprint('metaCompute = %s' % self.pp.pformat(d_metaCompute).strip(),
                       comms='status')
        d_computeRequest = {
            'action': 'run',
            'meta': d_metaCompute
        }

        d_computeRequestProcess.update(self.computeRequest_process(
            request=d_computeRequest,
            key=str_key,
            op='compute')
        )
        # wait for processing...
        self.dp.qprint('compute job submitted... waiting %ds for transients...' % \
                       coordBlockSeconds)
        time.sleep(coordBlockSeconds)
        d_jobBlock = self.jobOperation_blockUntil(
            request=d_computeRequest,
            key=str_key,
            op='compute',
            status=True
        )
        self.dp.qprint('compute d_jobBlock = %s' % \
                       self.pp.pformat(d_jobBlock).strip(),
                       comms='status')
        b_status = d_jobBlock['status']
        if not b_status:
            self.jobStatus_do(
                action='set',
                key=str_key,
                op='compute',
                status=False
            )
        if b_status:
            d_jobStatus = self.jobStatus_do(
                key=str_key,
                action='getInfo',
                op='compute'
            )
            self.dp.qprint('d_jobStatus = %s' % \
                           self.pp.pformat(d_jobStatus).strip(),
                           comms='status')
            d_computeRequestProcess.update(d_jobStatus['info']['compute']['return'])

        return b_status, d_computeRequestProcess

    def jobStatusFiles_create(self, d_ret, str_localDestination, str_key):
        # Note a potential issue here (almost a catch-22 of sorts):
        #
        # The status and summary files can only be pushed to swift after swift
        # has completed. (since these files contain information about the swift
        # operation itself, we push them to object storage after creating them
        # in the pfcon FS).
        #
        # This means that the files may not be registered with CUBE due to the
        # "delay" inherent in swift access IO (one method might push data to
        # swift, and an immediately subsequent method that tries to access the
        # data might get a "data not present" error as swift synchronizes).
        #
        # In practice though, this rarely happens.
        d_ret['d_jobStatus'] = self.jobStatus_do(key=str_key,
                                                 action='getInfo',
                                                 op='all')
        d_ret['d_jobStatusSummary'] = self.summaryStatus_process(d_ret['d_jobStatus'])
        str_statusFile = os.path.join(str_localDestination, 'jobStatus.json')
        with open(str_statusFile, 'w') as f:
            json.dump(d_ret['d_jobStatus'], f)
        f.close()
        str_summaryFile = os.path.join(str_localDestination, 'jobStatusSummary.json')
        with open(str_summaryFile, 'w') as f:
            json.dump(d_ret['d_jobStatusSummary'], f)
        f.close()
        # Also put these two files into swift
        SwiftManager.objPut(fileList=[str_statusFile, str_summaryFile], tree=Gd_tree)
        if len(self.str_debugToDir):
            self.dp.qprint('Final return: d_ret = \n%s' % json.dumps(d_ret, indent=4),
                           comms='status',
                           teeFile='%s/d_ret-%s.json' % (self.str_debugToDir, str_key),
                           teeMode='w+')

    def filesFind(self, *args, **kwargs):
        """
        This method simply returns a list of files
        down a filesystem tree starting from the
        kwarg:

            root = <someStartPath>

        """

        d_ret      = {
            'status':   False,
            'l_fileFS': [],
            'numFiles': 0
        }
        str_rootPath    = ''
        for k,v in kwargs.items():
            if k == 'root': str_rootPath    = v
        if len(str_rootPath):
            # Create a list of all files down the <str_rootPath>
            for root, dirs, files in os.walk(str_rootPath):
                for filename in files:
                    d_ret['l_fileFS'].append(os.path.join(root, filename))
                    d_ret['status'] = True

        d_ret['numFiles']   = len(d_ret['l_fileFS'])
        return d_ret

    def summaryStatus_process(self, ad_jobStatus):
        """
        Create a summary dictionary object from the main jobStatus dictionary.abs

        PRECONDITIONS
        * A valid jobStatus dictionary.
        """

        d_jobStatusSummary                      = {
            'status':           False,
            'pushPath': {
                'status':       False
            },
            'pullPath': {
                'status':       False
            },
            'compute': {
                'status':       False,
                'submit': {
                    'status':   False
                },
                'return': {
                    'status':   False,
                    'l_status': [],
                    'l_logs':   []
                }
            },
            'swiftPut': {
                'status':       False
            }
        }

        d_jobStatusSummary['pushPath']['status']            = ad_jobStatus['info']['pushPath']['status']
        d_jobStatusSummary['pullPath']['status']            = ad_jobStatus['info']['pullPath']['status']
        d_jobStatusSummary['compute']['status']             = ad_jobStatus['info']['compute']['status']
        d_jobStatusSummary['swiftPut']['status']            = ad_jobStatus['info']['swiftPut']['status']

        if 'submit' in ad_jobStatus['info']['compute']:
            d_jobStatusSummary['compute']['submit']['status']           = ad_jobStatus['info']['compute']['submit']['status']

        if 'return' in ad_jobStatus['info']['compute']:
            if 'status' in ad_jobStatus['info']['compute']['return']:
                d_jobStatusSummary['compute']['return']['status']       = ad_jobStatus['info']['compute']['return']['status']
                d_jobStatusSummary['compute']['return']['l_status']     = ad_jobStatus['info']['compute']['return']['d_ret']['l_status']
                d_jobStatusSummary['compute']['return']['l_logs']       = ad_jobStatus['info']['compute']['return']['d_ret']['l_logs']

        if  isinstance(d_jobStatusSummary['pushPath']['status'],            bool) and \
            isinstance(d_jobStatusSummary['pullPath']['status'],            bool) and \
            isinstance(d_jobStatusSummary['compute']['status'],             bool) and \
            isinstance(d_jobStatusSummary['compute']['submit']['status'],   bool) and \
            isinstance(d_jobStatusSummary['compute']['return']['status'],   bool) and \
            isinstance(d_jobStatusSummary['swiftPut']['status'],            bool):
            d_jobStatusSummary['status'] =      d_jobStatusSummary['pushPath']['status']            and \
                                                d_jobStatusSummary['pullPath']['status']            and \
                                                d_jobStatusSummary['compute']['status']             and \
                                                d_jobStatusSummary['compute']['submit']['status']   and \
                                                d_jobStatusSummary['compute']['return']['status']   and \
                                                d_jobStatusSummary['swiftPut']['status']
        else:
            d_jobStatusSummary['status'] = False

        return d_jobStatusSummary

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

        for k,v in kwargs.items():
            if k == 'request':      d_request   = v

        d_meta      = d_request['meta']
        str_keyID   = d_meta['remote']['key']

        d_jobStatus      = self.jobStatus_do(           key     = str_keyID,
                                                        action  = 'getInfo',
                                                        op      = 'all')
        self.dp.qprint('d_status = %s' % self.pp.pformat(d_jobStatus).strip(), comms = 'status')
        d_jobStatusSummary  = self.summaryStatus_process(d_jobStatus)

        return {
            'status':               d_jobStatus['status'],
            'jobOperation':         d_jobStatus,
            'jobOperationSummary':  d_jobStatusSummary
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
        b_threaded  = False

        # pudb.set_trace()
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
        self.dp.qprint('data: %s' % data, comms = 'status')
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
            # pudb.set_trace()
            self.dp.qprint("verb: %s detected." % d_msg['action'], comms = 'status')
            str_method      = '%s_process' % d_msg['action']
            self.dp.qprint("method to call: %s(request = d_msg) " % str_method, comms = 'status')
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
            self.wfile.write(json.dumps(d_ret, indent = 4).encode())
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(Response(json.dumps(d_ret, indent=4))).encode())


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """
    Handle requests in a separate thread.
    """

    def col2_print(self, str_left, str_right, level = 1):
        self.dp.qprint(Colors.WHITE +
              ('%*s' % (self.LC, str_left)),
              end       = '',
              syslog    = False,
              level     = level)
        self.dp.qprint(Colors.LIGHT_BLUE +
              ('%*s' % (self.RC, str_right)) +
              Colors.NO_COLOUR,
              syslog    = False,
              level     = level)

    def __init__(self, *args, **kwargs):
        """

        Holder for constructor of class -- allows for explicit setting
        of member 'self' variables.

        :return:
        """
        HTTPServer.__init__(self, *args, **kwargs)
        self.LC             = 40
        self.RC             = 40
        self.args           = None
        self.str_desc       = 'pfcon'
        self.str_name       = self.str_desc
        self.str_version    = ''
        self.str_debugToDir = ''

    def leaf_process(self, **kwargs):
        """
        Process the global Gd_tree and perform possible env substitutions.
        """
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
        global Gd_internalvar
        str_defIP       = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
        str_defIPpman   = str_defIP
        str_defIPpfioh  = str_defIP

        if 'HOST_IP' in os.environ:
            str_defIPpman   = os.environ['HOST_IP']
            str_defIPpfioh  = os.environ['HOST_IP']

        # For old docker-compose
        if 'PMAN_PORT_5010_TCP_ADDR' in os.environ:
            str_defIPpman   = os.environ['PMAN_PORT_5010_TCP_ADDR']
        if 'PFIOH_PORT_5055_TCP_ADDR' in os.environ:
            str_defIPpfioh  = os.environ['PFIOH_PORT_5055_TCP_ADDR']

        # For newer docker-compose
        try:
            pman_service    = socket.gethostbyname('pman_service')
            if pman_service != "127.0.0.1":
                str_defIPpman   = pman_service
        except:
            pass
        try:
            pfioh_service   = socket.gethostbyname('pfioh_service')
            if pfioh_service != "127.0.0.1":
                str_defIPpfioh  = pfioh_service
        except:
            pass

        for k,v in kwargs.items():
            if k == 'args': self.args           = v
            if k == 'desc': self.str_desc       = v
            if k == 'ver':  self.str_version    = v

        if len(self.args['str_configFileLoad']):
            if Path(self.args['str_configFileLoad']).is_file():
                # Read configuration detail from JSON formatted file
                with open(self.args['str_configFileLoad']) as json_file:
                    Gd_internalvar  = json.load(json_file)

        G_b_httpResponse = self.args['b_httpResponse']
        if 'httpProxy' in self.args.keys():
            if len(self.args['httpProxy']):
                Gd_internalvar['self']['httpProxy']['use']          = True
                Gd_internalvar['self']['httpProxy']['httpSpec']     = self.args['httpProxy']

        # pudb.set_trace()
        Gd_internalvar['self']['name']                  = self.str_name
        Gd_internalvar['self']['version']               = self.str_version
        Gd_internalvar['self']['coordBlockSeconds']     = int(self.args['coordBlockSeconds'])
        Gd_internalvar['self']['verbosity']             = int(self.args['verbosity'])
        if len(self.args['str_debugToDir']):
            Gd_internalvar['self']['debugToDir']        = self.args['str_debugToDir']
            self.str_debugToDir                         = self.args['str_debugToDir']

        self.verbosity      = Gd_internalvar['self']['verbosity']
        self.dp             = debug(verbosity = self.verbosity)

        self.dp.qprint(self.str_desc, level = 1)

        Gd_tree.initFromDict(Gd_internalvar)

        self.leaf_process(  where   = '/service/host/data/addr',
                            replace = '%PFIOH_IP',
                            newVal  = str_defIPpfioh)
        self.leaf_process(  where   = '/service/host/compute/addr',
                            replace = '%PMAN_IP',
                            newVal  = str_defIPpman)

        self.dp.qprint(
            Colors.YELLOW + "\n\t\tInternal data tree:",
            level   = 1,
            syslog  = False)
        self.dp.qprint(
            C_snode.str_blockIndent(str(Gd_tree), 3, 8),
            level   = 1,
            syslog  = False)

        self.col2_print("Listening on address:",    self.args['ip'])
        self.col2_print("Listening on port:",       self.args['port'])
        self.col2_print("Server listen forever:",   self.args['b_forever'])
        self.col2_print("Return HTTP responses:",   G_b_httpResponse)
        self.col2_print("Internal debug dir:",      self.str_debugToDir)

        # pudb.set_trace()
        if len(self.str_debugToDir):
            if not os.path.exists(self.str_debugToDir):
                os.makedirs(self.str_debugToDir)

        self.dp.qprint(
            Colors.LIGHT_GREEN +
            "\n\n\t\t\tWaiting for incoming data...\n" +
            Colors.NO_COLOUR,
            level   = 1,
            syslog  = False)
