"""
Swift storage manager module.
"""

import logging
import os
import swiftclient


class SwiftManager(object):

    @staticmethod
    def connect(*args, **kwargs):
        """
        Connect to swift storage and return the connection object,
        as well an optional "prepend" string to fully qualify
        object location in swift storage.

        The 'prependBucketPath' is somewhat 'legacy' to a similar
        method in charm.py and included here with the idea
        to eventually converge on a single swift-based intermediary
        library for both pfcon and CUBE.
        """

        b_status                = True
        str_prependBucketPath = ''

        for k,v in kwargs.items():
            if k == 'prependBucketPath':    str_prependBucketPath = v
            if k == 'tree':    Gd_tree = v

        d_ret       = {
            'status':               b_status,
            'conn':                 None,
            'prependBucketPath':    str_prependBucketPath,
            'user':                 Gd_tree.cat('/swift/username'),
            'key':                  Gd_tree.cat('/swift/key'),
            'authurl':              Gd_tree.cat('/swift/auth_url'),
            'container_name':       Gd_tree.cat('/swift/container_name')
        }

        # initiate a swift service connection, based on internal
        # settings already available in the django variable space.
        try:
            d_ret['conn'] = swiftclient.Connection(
                user    = d_ret['user'],
                key     = d_ret['key'],
                authurl = d_ret['authurl']
            )
        except:
            d_ret['status'] = False

        return d_ret

    @staticmethod
    def ls(*args, **kwargs):
        """
        Return a list of objects in the swiftstorage
        """
        l_ls                    = []    # The listing of names to return
        ld_obj                  = {}    # List of dictionary objects in swift
        str_path                = '/'
        str_fullPath            = ''
        b_prependBucketPath     = False
        b_status                = False

        for k,v in kwargs.items():
            if k == 'path':                 str_path            = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        # Remove any leading noise on the str_path, specifically
        # any leading '.' characters.
        # This is probably not very robust!
        while str_path[:1] == '.':  str_path    = str_path[1:]

        d_conn          = SwiftManager.connect(**kwargs)
        if d_conn['status']:
            conn        = d_conn['conn']
            if b_prependBucketPath:
                str_fullPath    = '%s%s' % (d_conn['prependBucketPath'], str_path)
            else:
                str_fullPath    = str_path

            # get the full list of objects in Swift storage with given prefix
            try:
                ld_obj = conn.get_container(
                            d_conn['container_name'],
                            prefix          = str_fullPath,
                            full_listing    = True)[1]

                for d_obj in ld_obj:
                    l_ls.append(d_obj['name'])
                    b_status    = True
            except:
                b_status    = False
                logging.error( "Could not get a list of objects in Swift")
        return {
            'status':       b_status,
            'objectDict':   ld_obj,
            'lsList':       l_ls,
            'fullPath':     str_fullPath
        }

    @staticmethod
    def objExists(*args, **kwargs):
        """
        Return True/False if passed object exists in swift storage
        """
        b_exists    = False
        str_obj     = ''

        for k,v in kwargs.items():
            if k == 'obj':                  str_obj             = v
            if k == 'prependBucketPath':    b_prependBucketPath = v

        kwargs['path']  = str_obj
        d_swift_ls  = SwiftManager.ls(*args, **kwargs)
        str_obj     = d_swift_ls['fullPath']

        if d_swift_ls['status']:
            for obj in d_swift_ls['lsList']:
                if obj == str_obj:
                    b_exists = True

        return {
            'status':   b_exists,
            'objPath':  str_obj
        }

    @staticmethod
    def objPut(*args, **kwargs):
        """
        Put an object (or list of objects) into swift storage.

        This method also "maps" tree locations in the local storage
        to new locations in the object storage. For example, assume
        a list of local locations starting with:

                    /home/user/project/data/ ...

        and we want to pack everything in the 'data' dir to
        object storage, at location '/storage'. In this case, the
        pattern of kwargs specifying this would be:

                    fileList = ['/home/user/project/data/file1',
                                '/home/user/project/data/dir1/file_d1',
                                '/home/user/project/data/dir2/file_d2'],
                    inLocation      = '/storage',
                    mapLocationOver = '/home/user/project/data'

        will replace, for each file in <fileList>, the <mapLocationOver> with
        <inLocation>, resulting in a new list

                    '/storage/file1',
                    '/storage/dir1/file_d1',
                    '/storage/dir2/file_d2'

        Note that the <inLocation> is subject to <b_prependBucketPath>!

        """
        b_status                = True
        l_localfile             = []    # Name on the local file system
        l_objectfile            = []    # Name in the object storage
        str_swiftLocation       = ''
        str_mapLocationOver     = ''
        str_localfilename       = ''
        str_storagefilename     = ''
        str_prependBucketPath   = ''
        d_ret                   = {
            'status':           b_status,
            'localFileList':    [],
            'objectFileList':   [],
            'localpath':        ''
        }

        d_conn  = SwiftManager.connect(*args, **kwargs)
        if d_conn['status']:
            str_prependBucketPath       = d_conn['prependBucketPath']

        str_swiftLocation               = str_prependBucketPath

        for k,v in kwargs.items():
            if k == 'file':             l_localfile.append(v)
            if k == 'fileList':         l_localfile         = v
            if k == 'inLocation':       str_swiftLocation   = '%s%s' % (str_prependBucketPath, v)
            if k == 'mapLocationOver':  str_mapLocationOver = v

        if len(str_mapLocationOver):
            # replace the local file path with object store path
            l_objectfile    = [w.replace(str_mapLocationOver, str_swiftLocation) \
                                for w in l_localfile]
        else:
            # Prepend the swiftlocation to each element in the localfile list:
            l_objectfile    = [str_swiftLocation + '{0}'.format(i) for i in l_localfile]

        d_ret['localpath']  = os.path.dirname(l_localfile[0])

        if d_conn['status']:
            for str_localfilename, str_storagefilename in zip(l_localfile, l_objectfile):
                try:
                    d_ret['status'] = True and d_ret['status']
                    with open(str_localfilename, 'rb') as fp:
                        d_conn['conn'].put_object(
                            d_conn['container_name'],
                            str_storagefilename,
                            contents=fp.read()
                        )
                except Exception as e:
                    d_ret['error']  = e
                    d_ret['status'] = False
                d_ret['localFileList'].append(str_localfilename)
                d_ret['objectFileList'].append(str_storagefilename)
        return d_ret

    @staticmethod
    def objPull(*args, **kwargs):
        """
        Pull an object (or set of objects) from swift storage and
        onto the local filesystem.

        This method can also "map" locations in the object storage
        to new locations in the filesystem storage. For example, assume
        a list of object locations starting with:

                user/someuser/uploads/project/data ...

        and we want to pack everything from 'data' to the local filesystem
        to, for example,

                /some/dir/data

        In this case, the pattern of kwargs specifying this would be:

                    fromLocation    = user/someuser/uploads/project/data
                    mapLocationOver = /some/dir/data

        if 'mapLocationOver' is not specified, then the local file system
        location will be the 'inLocation' prefixed with a '/'.

        """
        b_status                = True
        l_localfile             = []    # Name on the local file system
        l_objectfile            = []    # Name in the object storage
        str_swiftLocation       = ''
        str_mapLocationOver     = ''
        str_localfilename       = ''
        str_storagefilename     = ''
        str_prependBucketPath   = ''
        d_ret                   = {
            'status':           b_status,
            'localFileList':    [],
            'objectFileList':   [],
            'localpath':        ''
        }

        d_conn  = SwiftManager.connect(*args, **kwargs)
        if d_conn['status']:
            str_prependBucketPath       = d_conn['prependBucketPath']

        str_swiftLocation               = str_prependBucketPath

        for k,v in kwargs.items():
            if k == 'fromLocation':     str_swiftLocation   = '%s%s' % (str_prependBucketPath, v)
            if k == 'mapLocationOver':  str_mapLocationOver = v
            if k == 'tree':    Gd_tree = v

        # Get dictionary of objects in storage
        d_lsSwift       = SwiftManager.ls(path = str_swiftLocation, tree = Gd_tree)

        # List of objects in storage
        l_objectfile    = d_lsSwift['lsList']

        if len(str_mapLocationOver):
            # replace the local file path with object store path
            l_localfile         = [w.replace(str_swiftLocation, str_mapLocationOver) \
                                    for w in l_objectfile]
        else:
            # Prepend a '/' to each element in the l_objectfile:
            l_localfile         = ['/' + '{0}'.format(i) for i in l_objectfile]
            str_mapLocationOver =  '/' + str_swiftLocation

        d_ret['localpath']      = str_mapLocationOver

        if d_conn['status']:
            for str_localfilename, str_storagefilename in zip(l_localfile, l_objectfile):
                try:
                    d_ret['status'] = True and d_ret['status']
                    obj_tuple       = d_conn['conn'].get_object(
                                                    d_conn['container_name'],
                                                    str_storagefilename
                                                )
                    str_parentDir   = os.path.dirname(str_localfilename)
                    os.makedirs(str_parentDir, exist_ok = True)
                    with open(str_localfilename, 'wb') as fp:
                        # fp.write(str(obj_tuple[1], 'utf-8'))
                        fp.write(obj_tuple[1])
                except Exception as e:
                    d_ret['error']  = str(e)
                    d_ret['status'] = False
                d_ret['localFileList'].append(str_localfilename)
                d_ret['objectFileList'].append(str_storagefilename)
        return d_ret

    @staticmethod
    def putObjects(*args, **kwargs):
        """
        """
        d_ret = {
            'status': True,
            'd_result': {
                'l_fileStore':  []
            }
        }
        l_files     = []
        for k,v in kwargs.items():
            if k == 'fileObjectList':   l_files = v
            if k == 'tree':    Gd_tree = v

        # initiate a swift service connection
        conn = swiftclient.Connection(
            user    = Gd_tree.cat('/swift/username'),
            key     = Gd_tree.cat('/swift/key'),
            authurl = Gd_tree.cat('/swift/auth_url')
        )

        # create container in case it doesn't already exist
        conn.put_container(Gd_tree.cat('/swift/container_name'))

        # put files into storage
        for filename in l_files:
            try:
                d_ret['status'] = True and d_ret['status']
                with open(filename, 'rb') as fp:
                    conn.put_object(
                        Gd_tree.cat('/swift/container_name'),
                        filename,
                        contents=fp.read()
                    )
            except:
                d_ret['status'] = False
            d_ret['d_result']['l_fileStore'].append(filename)

        return d_ret

    @staticmethod
    def createFileList(*args, **kwargs):
        """
        Initial entry point for swift storage processing.

        This method determines a list of files to put into
        swift storage.
        """

        d_create   = {
            'status': True,
            'd_result': {
                'l_fileFS': []
            }
        }
        logging.info("starting...")
        str_rootPath    = ''
        for k,v in kwargs.items():
            if k == 'root': str_rootPath = v
            if k == 'tree':    Gd_tree = v

        if len(str_rootPath):
            # Create a list of all files down the <str_rootPath>
            for root, dirs, files in os.walk(str_rootPath):
                for filename in files:
                    d_create['d_result']['l_fileFS'].append(os.path.join(root, filename))
            d_swiftPut = SwiftManager.putObjects(
                fileObjectList = d_create['d_result']['l_fileFS'],
                tree = Gd_tree
            )
        return {
            'status':   True,
            'd_create': d_create,
            'd_put':    d_swiftPut
        }
