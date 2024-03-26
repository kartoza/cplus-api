#!/bin/sh

# Exit script in case of error
set -e

echo $"\n\n\n"
echo "-----------------------------------------------------"
echo "STARTING WORKER COMMAND $(date)"
echo "-----------------------------------------------------"

# remove pids
rm -f /var/run/celery/cplus.pid

# copy flower daemon script
rm -f /var/tmp/flower.pid
cp flower.sh /etc/init.d/flower
chmod +x /etc/init.d/flower
update-rc.d flower defaults
sleep 2
/etc/init.d/flower start

CPLUS_C=${CPLUS_QUEUE_CONCURRENCY:-1}

# start tile and validate workers
celery -A core multi start cplus -c:cplus $CPLUS_C -Q:cplus cplus -l INFO --logfile=/proc/1/fd/1

# start default worker
celery -A core worker -l INFO --logfile=/proc/1/fd/1
# celery -A core worker -l INFO

echo "-----------------------------------------------------"
echo "FINISHED WORKER COMMAND --------------------------"
echo "-----------------------------------------------------"
