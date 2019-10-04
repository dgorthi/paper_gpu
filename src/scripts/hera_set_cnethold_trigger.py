import numpy as np
import redis
import time

r = redis.Redis('redishost')
pubchan = 'hashpipe://%s/%d/set' %('px1',0)

#Configure runtime parameters
catcher_dict = {
  'HDF5TPLT' : '/tmp/template.h5',
  'NFILES'   : 0,
  'SYNCTIME' : r['corr:feng_sync_time'],
  'INTTIME'  : r['corr:acc_len'],
  'TRIGGER'  : 0,
}
  
# Reset various statistics counters

for key, val in catcher_dict.iteritems():
   r.publish(pubchan, '%s=%s' % (key, val))
for v in ['NETWAT', 'NETREC', 'NETPRC']:
    r.publish(pubchan, '%sMN=99999' % (v))
    r.publish(pubchan, '%sMX=0' % (v))
r.publish(pubchan, 'MISSEDPK=0')

# If BDA is requested, write distribution to redis
baselines = {}
Nants = 0
for n in range(4):
    baselines[n] = []

bdaconfig = np.loadtxt('../bdaconfig/test_bda_192ants_nobda.txt', dtype=np.int)
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
r.publish(pubchan,'TRIGGER=1')
r.publish(pubchan, 'NFILES=10')

