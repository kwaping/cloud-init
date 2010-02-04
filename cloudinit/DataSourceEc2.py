import DataSource

import cloudinit
import socket
import urllib2
import time
import boto_utils

class DataSourceEc2(DataSource.DataSource):
    api_ver  = '2009-04-04'
    cachedir = cloudinit.cachedir + '/ec2'

    location_locale_map = { 
        'us' : 'en_US.UTF-8',
        'eu' : 'en_GB.UTF-8',
        'default' : 'en_US.UTF-8',
    }

    def __init__(self):
        pass

    def get_data(self):
        try:
            udf = open(self.cachedir + "/user-data.raw")
            self.userdata_raw = udf.read()
            udf.close()

            mdf = open(self.cachedir + "/meta-data.raw")
            data = mdf.read()
            self.metadata = eval(data)
            mdf.close()

            return True
        except:
            pass

        try:
            if not self.wait_for_metadata_service():
                return False
            self.userdata_raw = boto_utils.get_instance_userdata(self.api_ver)
            self.metadata = boto_utils.get_instance_metadata(self.api_ver)
            return True
        except Exception as e:
            print e
            return False

    def get_instance_id(self):
        return(self.metadata['instance-id'])

    def get_availability_zone(self):
        return(self.metadata['placement']['availability-zone'])

    def get_local_mirror(self):
        return(self.get_mirror_from_availability_zone())

    def get_locale(self):
        az = self.metadata['placement']['availability-zone']
        if self.location_locale_map.has_key(az[0:2]):
            return(self.location_locale_map[az[0:2]])
        else:
            return(self.location_locale_map["default"])

    def get_hostname(self):
        toks = self.metadata['local-hostname'].split('.')
        # if there is an ipv4 address in 'local-hostname', then
        # make up a hostname (LP: #475354)
        if len(toks) == 4:
            try:
                r = filter(lambda x: int(x) < 256 and x > 0, toks)
                if len(r) == 4:
                    return("ip-%s" % '-'.join(r))
            except: pass
        return toks[0]

    def get_mirror_from_availability_zone(self, availability_zone = None):
        # availability is like 'us-west-1b' or 'eu-west-1a'
        if availability_zone == None:
            availability_zone = self.get_availability_zone()

        try:
            host="%s.ec2.archive.ubuntu.com" % availability_zone[:-1]
            socket.getaddrinfo(host, None, 0, socket.SOCK_STREAM)
            return 'http://%s/ubuntu/' % host
        except:
            return 'http://archive.ubuntu.com/ubuntu/'

    def wait_for_metadata_service(self, sleeps = 10):
        sleeptime = 1
        for x in range(sleeps):
            s = socket.socket()
            try:
                address = '169.254.169.254'
                port = 80
                s.connect((address,port))
                s.close()
                return True
            except socket.error, e:
                print "sleeping %s" % sleeptime
                time.sleep(sleeptime)
                #timeout = timeout * 2
        return False

    def get_public_ssh_keys(self):
        keys = []
        if not self.metadata.has_key('public-keys'): return([])
        for keyname, klist in self.metadata['public-keys'].items():
            # lp:506332 uec metadata service responds with
            # data that makes boto populate a string for 'klist' rather
            # than a list.
            if isinstance(klist,str):
                klist = [ klist ]
            for pkey in klist:
                # there is an empty string at the end of the keylist, trim it
                if pkey:
                    keys.append(pkey)

        return(keys)

    def device_name_to_device(self, name):
        # consult metadata service, that has
        #  ephemeral0: sdb
        # and return 'sdb' for input 'ephemeral0'
        if not self.metadata.has_key('block-device-mapping'):
            return(None)

        for entname, device in self.metadata['block-device-mapping'].items():
            if entname == name:
                return(device)
            # LP: #513842 mapping in Euca has 'ephemeral' not 'ephemeral0'
            if entname == "ephemeral" and name == "ephemeral0":
                return(device)
        return None