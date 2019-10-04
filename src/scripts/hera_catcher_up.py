#!/usr/bin/env python

import redis
import time
import argparse
import subprocess
import numpy as np

perf_tweaker = 'tweak-perf-sn.sh'
init = 'hera_catcher_init.sh'
python_source_cmd = ['source', '~/.venv/bin/activate']
template_cmd = ['hera_make_hdf5_template.py']

def run_on_hosts(hosts, cmd, user=None, wait=True):
    if isinstance(cmd, str):
        cmd = [cmd]
    p = []
    for host in hosts:
        if user is None:
            p += [subprocess.Popen(['ssh', '%s' % (host)] + cmd)]
        else:
            p += [subprocess.Popen(['ssh', '%s@%s' % (user, host)] + cmd)]
    if wait:
        for pn in p:
            pn.wait()

parser = argparse.ArgumentParser(description='Start the HERA Catcher Machine',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('host', type=str, help='Host to intialize')
parser.add_argument('-r', dest='redishost', type=str, default='redishost', help='Host serving redis database')
parser.add_argument('-t', dest='hdf5template', type=str, default='/tmp/template.h5', 
                    help='Place to put HDF5 header template file')
parser.add_argument('-c', dest='bdaconfig', type=str, default='/tmp/bdaconfig.txt',
                    help='Place to put the BDA config file.\
                          Used only if --bda flag is used')
parser.add_argument('--bda', dest='bda', action='store_true', default=False,
                    help='Use the baseline dependent averaging version')
parser.add_argument('--runtweak', dest='runtweak', action='store_true', default=False,
                    help='Run the tweaking script %s on X-hosts prior to starting the correlator' % perf_tweaker)

args = parser.parse_args()

r = redis.Redis(args.redishost)

# Run performance tweaking script
if args.runtweak:
    run_on_hosts([args.host], perf_tweaker, user='root', wait=True)

init_args = []
if args.bda:
   init_args += ['-a']

# Start Catcher
run_on_hosts([args.host], ['cd', '/tmp;', init] + init_args + ['0'], wait=True)
time.sleep(15)

# Start hashpipe<->redis gateways
cpu_mask = '0x0004'
run_on_hosts([args.host], ['taskset', cpu_mask, 'hashpipe_redis_gateway.rb', '-g', args.host, '-i', '0'])

# Wait for the gateways to come up
time.sleep(15)

# Upload config file location
# NOTE: This has to come before template generation!
if args.bda:
   r.set('bda:config',args.bdaconfig)
time.sleep(10)

# Generate the meta-data template
if args.bda:
   run_on_hosts([args.host], python_source_cmd + [';'] + ['hera_make_hdf5_template_bda.py'] + [args.hdf5template], wait=True)
else:
   run_on_hosts([args.host], python_source_cmd + [';'] + template_cmd + ['-c', '-r', args.hdf5template], wait=True)

#Configure runtime parameters
catcher_dict = {
  'HDF5TPLT' : args.hdf5template,
  'NFILES'   : 0,
  'SYNCTIME' : r['corr:feng_sync_time'],
  'INTTIME'  : r['corr:acc_len'],
  'TRIGGER'  : 0,
}
  
# Reset various statistics counters

pubchan = 'hashpipe://%s/%d/set' % (args.host, 0)
for key, val in catcher_dict.iteritems():
   r.publish(pubchan, '%s=%s' % (key, val))
for v in ['NETWAT', 'NETREC', 'NETPRC']:
    r.publish(pubchan, '%sMN=99999' % (v))
    r.publish(pubchan, '%sMX=0' % (v))
r.publish(pubchan, 'MISSEDPK=0')

# If BDA is requested, write distribution to redis
if args.bda:
   baselines = {}
   Nants = 0
   for n in range(4):
       baselines[n] = []
   
   bdaconfig = np.loadtxt(args.bdaconfig, dtype=np.int)
   for ant0,ant1,t in bdaconfig:
       if (t==0): continue
       n = int(np.log(t)/np.log(2))
       if (n==4): n = 3
       baselines[n].append((ant0, ant1))
       if (ant0 == ant1):
          Nants += 1
   
   for i in range(4):
       r.publish(pubchan, 'NBL%dSEC=%d'  % (2**(i+1), len(baselines[i])))
   r.publish(pubchan, 'BDANANT=%d'  % Nants)
   
   time.sleep(0.1)

# Release nethread hold
r.publish(pubchan, 'CNETHOLD=0')
