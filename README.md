# Scriptable Beat
![Status](https://badgen.net/static/status/proof%20of%20concept/orange "Status")
![Docker image size](https://badgen.net/docker/size/tonymasse/scriptable_beat?icon=docker "Docker image size")
![Docker pulls](https://badgen.net/docker/pulls/tonymasse/scriptable_beat?icon=docker "Docker pulls")

A Beat that allows the user to run any arbitrary script inside of it, to do the collection of the data, and then takes care of transmitting the output to the LogRhythm Open Collector, LogRhythm System Monitor Agent or LogStash over Lumberjack.

# Key constrains and goals

- Run Python script
- Run PowerShell script
- Run Bash script
- Manage the scheduling of the script run
- Monitor the script output and push it to the OC/SMA
- Deal gracefully with errors/crashs of the script
- Manage the configuration of the script through its own configuration
- Ideally - Manage/clean the script output from the disk, preventing any unnecessary disk usage
- Ideally - Deal with (Lumberjack) back-pressure by reducing/stopping scheduling frequency

# High level architecture

### Container containing:
- Beat core code
- Interpreters for the selected supported scripts

### Configuration:

- What packages/modules are required for the scripts
- What langage/interpreter is to be used
- Content of the:
  - First Run script
  - Startup script
  - Scheduled script
- Scheduler details:
  - Run once and keep running?
  - Frequency?
  - Restart on Error?
  - Restart on Crash?
- Dictate if the log data is meant to be coming out of STDOUT or file/folder
- File/Folder path
- How to treat output:
  - JSON log as-is
  - Plain text that needs to be encoded into a JSON field
- How to handle STDERR
  - Report as error in the stream
  - Log in Beats own logs
  - All of the above
  - Ignore
- How to handle STDOUT if log data is coming out of File/Folder
  - Report as error in the stream
  - Report as log message in the stream
  - Log in Beats own logs
  - All of the above
  - Ignore
- How to handle File after read/processing
  - Leave as is
  - Delete
  - Flush to empty
- How to handle Folder left empty
  - Leave as is
  - Delete

### At startup:
- Read from the configuration the list of required packages/modules required by the script
- Download/update each of the said packages/modules
- Start run sequence (only passing to next step on success of each step):
  - Establish comms with OC/SMA and other internal Beat required prep tasks
  - Run First Run script (only once, at the very first startup)
  - Run Startup script (at each startup)
  - Run Scheduler

### At run time
Beat core to monitor:
- STDOUT
- STDERR
- File/folder specified in configuration

# Internal doc
https://logrhythm.atlassian.net/l/cp/kmMun7qV

