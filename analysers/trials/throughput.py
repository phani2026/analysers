import sys
import json
import io
import gzip
import uuid
import math
import datetime 

from pyspark_cassandra import CassandraSparkContext
from pyspark_cassandra import RowFormat
from pyspark import SparkConf

# Takes arguments: Spark master, Cassandra host, Minio host, path of the files
sparkMaster = sys.argv[1]
cassandraHost = sys.argv[2]
trialID = sys.argv[3]
experimentID = trialID.split("_")[0]
nToIgnore = 5
cassandraKeyspace = "benchflow"
srcTable = "process"
destTable = "trial_throughput"

# Set configuration for spark context
conf = SparkConf() \
    .setAppName("Process duration analyser") \
    .setMaster(sparkMaster) \
    .set("spark.cassandra.connection.host", cassandraHost)
sc = CassandraSparkContext(conf=conf)

# TODO: Use Spark for all computations

dataRDD = sc.cassandraTable(cassandraKeyspace, srcTable)\
        .select("process_definition_id", "source_process_instance_id", "end_time", "start_time") \
        .where("trial_id=? AND experiment_id=?", trialID, experimentID) \
        .filter(lambda r: r["process_definition_id"] is not None) \
        .cache()

processes = dataRDD.map(lambda r: r["process_definition_id"]) \
        .distinct() \
        .collect()

maxTime = None
maxID = None
for p in processes:
    time = dataRDD.filter(lambda r: r["process_definition_id"] == p) \
        .map(lambda r: (r["start_time"], r["source_process_instance_id"])) \
        .sortByKey(1, 1) \
        .collect()
    if len(time) < nToIgnore:
        continue
    else:
        time = time[nToIgnore-1]
    if maxTime is None or time[0] > maxTime:
        maxTime = time[0]
        maxID = time[1]

print(maxTime)

data = dataRDD.map(lambda r: (r["start_time"], r)) \
        .sortByKey(1, 1) \
        .map(lambda r: r[1]) \
        .collect()

index = -1
if maxID is not None:
    for i in range(len(data)):
        if data[i]["source_process_instance_id"] == maxID:
            index = i
            break
    
data = sc.parallelize(data[index+1:])

data = data.map(lambda r: (r['start_time'], r['end_time'])) \
        .collect()

smallest = None
for d in data:
    t = d[0]
    if smallest == None:
        smallest = t
    elif t != None:
        if t < smallest:
            smallest = t
print(smallest)
        
largest = None
for d in data:
    t = d[1]
    if largest == None:
        largest = t
    elif t != None:
        if t > largest:
            largest = t
print(largest)
        
delta = largest - smallest
delta = delta.total_seconds()
print(delta)

tp = len(data)/float(delta)
print(tp)

# TODO: Fix this
query = [{"experiment_id":experimentID, "trial_id":trialID, "throughput":tp, "execution_time":delta}]

sc.parallelize(query).saveToCassandra(cassandraKeyspace, destTable)