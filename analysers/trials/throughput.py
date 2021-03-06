import sys
import json
import io
import gzip
import uuid
import math
import datetime 

from datetime import timedelta

from pyspark_cassandra import CassandraSparkContext
from pyspark_cassandra import RowFormat
from pyspark import SparkConf
from pyspark import SparkFiles

#Create the queries containg the results of the computations to pass to Cassandra
def createQuery(sc, cassandraKeyspace, experimentID, trialID, partitionsPerCore):
    queries = []
    
    execTimes = sc.cassandraTable(cassandraKeyspace, "trial_execution_time")\
            .select("process_definition_id", "execution_time") \
            .where("trial_id=? AND experiment_id=?", trialID, experimentID) \
            .repartition(sc.defaultParallelism * partitionsPerCore) \
            .cache()
    numProcesses = sc.cassandraTable(cassandraKeyspace, "trial_number_of_process_instances")\
            .select("process_definition_id", "number_of_process_instances") \
            .where("trial_id=? AND experiment_id=?", trialID, experimentID) \
            .repartition(sc.defaultParallelism * partitionsPerCore) \
            .cache()
    
    ex = execTimes.filter(lambda r: r["process_definition_id"] == "all").first()["execution_time"]
    npr = numProcesses.filter(lambda r: r["process_definition_id"] == "all").first()["number_of_process_instances"]
    
    if ex == 0:
        tp = None
    else:
        tp = npr/(ex*1.0)
    
    queries.append({"experiment_id":experimentID, "trial_id":trialID, "process_definition_id":"all", "throughput":tp})
    
    processes = execTimes.map(lambda a: a["process_definition_id"]).distinct().collect()
    
    #Iterate over all process definitions
    for process in processes:
        npr = numProcesses.filter(lambda r: r["process_definition_id"] == process).first()["number_of_process_instances"]
        
        if ex == 0:
            tp = None
        else:
            tp = npr/(ex*1.0)
    
        queries.append({"experiment_id":experimentID, "trial_id":trialID, "process_definition_id":process, "throughput":tp})
        
    return queries

def main():
    # Takes arguments
    args = json.loads(sys.argv[1])
    trialID = str(args["trial_id"])
    experimentID = str(args["experiment_id"])
    configFile = str(args["config_file"])
    cassandraKeyspace = str(args["cassandra_keyspace"])
    partitionsPerCore = 5
    
    # Set configuration for spark context
    conf = SparkConf().setAppName("Process throughput trial analyser")
    sc = CassandraSparkContext(conf=conf)
    
    #Destination table
    destTable = "trial_throughput"
    
    #Create Cassandra table
    query = createQuery(sc, cassandraKeyspace, experimentID, trialID, partitionsPerCore)
    
    #Save to Cassandra
    sc.parallelize(query, sc.defaultParallelism * partitionsPerCore).saveToCassandra(cassandraKeyspace, destTable)
    
if __name__ == '__main__': main()