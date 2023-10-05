# Testing logstash docker image
# Helps debug Lumberjack messages being sent from ScriptableBeat

# docker run --rm -it --name logstash -p 5045:5044 docker.elastic.co/logstash/logstash:8.9.1
docker run --rm -it --name logstash -p 5045:5044 docker.elastic.co/logstash/logstash:8.9.1 | grep -v "logstash.licensechecker.licensereader"