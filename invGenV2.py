import json
import pickle
import sys
import random
import time
from multiprocessing import Process
import glob
import re
import urllib.parse

heads = []
with open('header.csv') as f:
  for line in f:
    line = line.strip()
    name = line.split('\t').pop()
    heads.append(name)


class DT(object):
  def __init__(self):
    self.ts = set()
    self.data = []

def makeMap(tuuid_dts, ind):
  s = pickle.dumps(tuuid_dts)
  with open('./maps/%012d.pkl'%ind, 'wb') as f:
    f.write(s)
  return None

def map1():
  maxnames = sorted(glob.glob('maps/*.pkl'))
  if maxnames == []:
    already = 0
  else:
    already = int( re.search(r"(\d{1,})", maxnames[-1]).group(1) )
  with open('../../sdb/138717728.json', 'r') as f:
    ancker = time.time()
    tuuid_dts = {}
    for ind, line in enumerate(f):
      line = line.strip()
      line = line.replace('[[', '[')
      if ind%10000 == 0:
        print('now iter {ind} {time}'.format(ind=ind, time="%04f"%(time.time() - ancker)))
        ancker = time.time()
      if ind < already:
        continue
      if ind%200000 == 0:
        print('save iter {ind} {time}'.format(ind=ind, time="%04f"%(time.time() - ancker)))
        ancker = time.time()
        p = Process(target=makeMap, args=(tuuid_dts,ind, ))
        p.start()
        tuuid_dts = {}

      if line[-1] == ',':
        raw = line[:-1]
        try:
          o = json.loads(raw)
        except json.decoder.JSONDecodeError as e:
          continue
        z = dict(zip(heads, o))
        tuuid = z['tuuid']
        dt    = z['date_time']
        if tuuid is None: 
          continue
        ru = urllib.parse.unquote(urllib.parse.unquote(z['request_uri']))
        ru = {xs[0]:xs[1] for xs in filter( lambda xs: len(xs) == 2, \
                  map(lambda x:x.split('='), ru.split('&')) ) }
        z['request_uri'] = ru
        if tuuid_dts.get(tuuid) is None: tuuid_dts[tuuid] = DT()
        tuuid_dts[tuuid].ts.add(dt)
        tuuid_dts[tuuid].data.append(z)

def makeRed1(tuuid_dts, num):
  s = pickle.dumps(tuuid_dts)
  with open('./red1/%012d.pkl'%num, 'wb') as f:
    f.write(s)
  return None

def red1():
  try:
    m = int ( sorted(map(lambda x:re.search(r"/(\d{1,}).pkl",x).group(1), \
                  glob.glob("red1/*.pkl")), key=lambda x:x)[-1] )
  except IndexError as e:
    m = 0
    print("reduce step1は今回の実行が初めてですね")
  tuuid_dts = {}
  ancker = time.time()
  for name in sorted(glob.glob("maps/*.pkl")):
    num = int(re.search(r"(\d{1,}).pkl", name).group(1))
    if int(num) < m:
      continue
    if num%2000000 == 0:
      print("dump task...", num)
      p = Process(target=makeRed1, args=(tuuid_dts,num, ))
      p.start()
      tuuid_dts = {}
       
    print(time.time() - ancker)
    print("try to collect {name}".format(name=name))
    ancker = time.time()
    try:
      t_ds = pickle.loads(open(name, 'rb').read())
    except Exception as e:
      print('cannot parse pickle...', e)
      continue
    for t, ds in t_ds.items():
      if tuuid_dts.get(t) is None : tuuid_dts[t] = DT()
      
      tuuid_dts[t].ts |= ds.ts
      tuuid_dts[t].data.extend(ds.data)

def red2():
  import plyvel
  db = plyvel.DB('red1.ldb', create_if_missing=True)
  ancker = time.time()
  for name in sorted(glob.glob("maps/*.pkl")):
    print(time.time() - ancker)
    print("try to collect {name}".format(name=name))
    ancker = time.time()
    t_ds = pickle.loads(open(name, 'rb').read())
    for t, ds in t_ds.items():
      if db.get(bytes(t, 'utf-8')) is None:
        db.put(bytes(t, 'utf-8'), pickle.dumps(ds) )
      else:
        ds_ = pickle.loads(db.get(bytes(t, 'utf-8')))
        ds_.ts |= ds.ts
        ds_.data.extend(ds.data)
        db.put(bytes(t, 'utf-8'), pickle.dumps(ds_) )

if __name__ == '__main__':
  if '--map1' in sys.argv:
    map1()
  if '--red1' in sys.argv:
    red1()
