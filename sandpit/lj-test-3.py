from locallib.pyLogBeat import PyLogBeatClient

message = {'@timestamp': '2018-01-02T01:02:03',  '@version': '1', 'message': 'hello world'}
client = PyLogBeatClient('192.168.100.137', 5045, ssl_enable=False)
client.connect()
client.send([message])
client.close()

# Results in this in LogStash:
# {
#        "message" => "hello world",
#          "event" => {
#         "original" => "hello world"
#     },
#           "tags" => [
#         [0] "beats_input_codec_plain_applied"
#     ],
#       "@version" => "1",
#     "@timestamp" => 2018-01-02T01:02:03.000Z
# }