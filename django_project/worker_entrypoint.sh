#!/bin/sh

# Exit script in case of error
set -e

echo $"\n\n\n"
echo "-----------------------------------------------------"
echo "STARTING WORKER COMMAND $(date)"
echo "-----------------------------------------------------"

CPLUS_C=${CPLUS_QUEUE_CONCURRENCY:-1}

# remove pids
rm -f /var/run/celery/cplus.pid

# start cplus workers
celery -A core multi start cplus -c:cplus $CPLUS_C -Q:cplus cplus -l INFO --logfile=/proc/1/fd/1 --statedb=/var/run/celery/%n.state

# start default worker
celery -A core worker -l INFO --logfile=/proc/1/fd/1
# celery -A core worker -l INFO

echo "-----------------------------------------------------"
echo "FINISHED WORKER COMMAND --------------------------"
echo "-----------------------------------------------------"
