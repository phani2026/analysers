import sys
import json

from datetime import timedelta

from pyspark_cassandra import CassandraSparkContext
from pyspark import SparkConf

#Create the queries containg the results of the computations to pass to Cassandra
def createQuery(CassandraRDD, experimentID):
    from commons import computeExperimentMetrics, computeModeMinMax, computeCombinedVar
    
    queries = []
    
    combinations = CassandraRDD.map(lambda a: (a["construct_type"], a["construct_name"])).distinct().collect()
    
    #Iterate over all combinations of construct type and name
    for combs in combinations:
        consType = combs[0]
        name = combs[1]
        
        dataRDD = CassandraRDD.filter(lambda r: r['construct_name'] == name and r['construct_type'] == consType)
        
        if dataRDD.isEmpty():
            continue
        
        #Compute the metrics
        metrics = computeExperimentMetrics(dataRDD, "construct_duration")
        metrics.update(computeModeMinMax(dataRDD, "construct_duration"))
        
        combinedVar = computeCombinedVar(CassandraRDD, "construct_duration")
        
        #If type or name is None, set them as Unspecified
        if consType is None:
            consType = "Unspecified"
        if name is None:
            name = "Unspecified"
        
        #Construct the query and appends it to the list of queries
        queries.append({"experiment_id":experimentID, "construct_duration_mode_min":metrics["min"], "construct_duration_mode_max":metrics["max"], \
                        "construct_type": consType, "construct_name": name, "construct_duration_variation_coefficient":metrics["variation_coefficient"], \
                      "construct_duration_mode_min_freq":metrics["mode_min_freq"], "construct_duration_mode_max_freq":metrics["mode_max_freq"], \
                      "construct_duration_mean_min":metrics["mean_min"], "construct_duration_mean_max":metrics["mean_max"], \
                      "construct_duration_min":metrics["min"], "construct_duration_max":metrics["max"], "construct_duration_q1_min":metrics["q1_min"], \
                      "construct_duration_q1_max":metrics["q1_max"], "construct_duration_q2_min":metrics["q2_min"], "construct_duration_q2_max":metrics["q2_max"], \
                      "construct_duration_p90_max":metrics["p90_max"], "construct_duration_p90_min":metrics["p90_min"], \
                      "construct_duration_p95_max":metrics["p95_max"], "construct_duration_p95_min":metrics["p95_min"], \
                      "construct_duration_p99_max":metrics["p99_max"], "construct_duration_p99_min":metrics["p99_min"], \
                      "construct_duration_q3_min":metrics["q3_min"], "construct_duration_q3_max":metrics["q3_max"], "construct_duration_weighted_avg":metrics["weighted_avg"], \
                      "construct_duration_best": metrics["best"], "construct_duration_worst": metrics["worst"], "construct_duration_average": metrics["average"], \
                      "construct_duration_combined_variance": combinedVar})

    return queries

def main():
    # Takes arguments
    args = json.loads(sys.argv[1])
    experimentID = str(args["experiment_id"])
    configFile = str(args["config_file"])
    cassandraKeyspace = str(args["cassandra_keyspace"])
    
    # Set configuration for spark context
    conf = SparkConf().setAppName("Construct duration analyser")
    sc = CassandraSparkContext(conf=conf)

    # Source and destination tables
    srcTable = "trial_construct_duration"
    destTable = "exp_construct_duration"
    
    #Retrieve the data from Cassandra to perform computations on
    CassandraRDD = sc.cassandraTable(cassandraKeyspace, srcTable) \
        .select("construct_duration_min", "construct_duration_max", "construct_duration_q1", "construct_duration_q2", "construct_duration_q3", \
                "construct_duration_p95", "construct_duration_num_data_points", "construct_duration_mean", \
                "construct_duration_p90", "construct_duration_p99", "construct_type", "construct_name", "construct_duration_variance", \
                "construct_duration_me", "trial_id", "construct_duration_mode", "construct_duration_mode_freq") \
        .where("experiment_id=?", experimentID)
    CassandraRDD.cache()
    
    #Create the queries for Cassandra
    query = createQuery(CassandraRDD, experimentID)

    #Save to Cassandra
    sc.parallelize(query).saveToCassandra(cassandraKeyspace, destTable)
    
if __name__ == '__main__':
    main()