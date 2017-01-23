import os
from slackclient import SlackClient
import subprocess
import netifaces as ni
import time
import re
import subprocess as sp
import xml.etree.ElementTree as ET
import curses as crs
import psutil

BOT_NAME = 'gpubot'
BOT_ID = os.environ.get("BOT_ID")


AT_BOT = "<@" + BOT_ID + ">"
STATUS_COMMAND = "status"
JOBS_COMMAND = "jobs"
IP_COMMAND = "ip"
HELP_COMMAND = "help"
CPU_STATUS = "cpu"
GPU_STATUS = "gpu"
MEM_STATUS = "memory"
UPTIME_STATUS = "uptime"
NUM_USERS = "user_number"
WHO_USERS = "user_list"
POSSIBLE_COMMANDS = [STATUS_COMMAND, JOBS_COMMAND, UPTIME_STATUS, IP_COMMAND, HELP_COMMAND, CPU_STATUS, GPU_STATUS, MEM_STATUS, NUM_USERS, WHO_USERS]

# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

def get_nvidia_smi():
    i = os.popen('nvidia-smi --query-gpu=index,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv -i 0').read()
    j = os.popen('nvidia-smi --query-gpu=index,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv -i 1').read()
    r = i.split("\n")[1]
    s = j.split("\n")[1]
    r = re.sub("\s+","\t", r)
    s = re.sub("\s+", "\t", s)
    return r,s

def get_cpu():
    x = psutil.cpu_percent()
    return x
def get_ram():
    x = psutil.virtual_memory()
    return x
def get_ip():
    #ni.ifaddresses('et0')
    ip = ni.ifaddresses('eno1')[2][0]['addr']
    return ip

def display_proc_info():
    gpunum = 0
    pnum = 0
    lines1 = []
    lines2 = []
    data = sp.check_output(['nvidia-smi', '-q', '-x'])
    root = ET.fromstring(data)
    idx = 0
    for gpu in root.findall('gpu'):
        procs = gpu.find("processes")
        for proc in procs.findall("process_info"):
            pid = proc.find('pid').text
            name = proc.find('process_name').text
            memuse = proc.find('used_memory').text
            line = '%3s' % repr(pnum) + '%8s' % repr(gpunum) + '%8s' % pid + '%60s' % name + '%14s' % memuse
            if idx == 0:
                lines1.append(line)
            else:
                lines2.append(line)
	idx += 1
    return lines1, lines2

def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    commands = "\t".join(POSSIBLE_COMMANDS)
    response = "I only support the following commands:\t%s"%(commands) 
    if command.startswith(STATUS_COMMAND) or command.startswith(GPU_STATUS):
        gpu0, gpu1 = get_nvidia_smi()
        response = "GPU Index, Temperature(Celsius), Utilization GPU (Cores), Utilization VRAM, Total Memory, Free Memory, Memory Used\n%s\n%s\n"%(gpu0, gpu1)
    elif command.startswith(JOBS_COMMAND):
        line1, line2 = display_proc_info()
	lines1 = "\n".join(line1)
	lines2 = "\n".join(line2)
        response = "Process_number, GPU_ID, Process_ID, Name, Memory Usage\n%s\n%s"%(lines1, lines2)
    elif command.startswith(IP_COMMAND):
        ip = get_ip()
        response = "Current IP address is: %s"%(ip)
    elif command.startswith(HELP_COMMAND):
        response = "I support the following commands %s"%(commands)
    elif command.startswith(MEM_STATUS):
        ram = psutil.virtual_memory()
        response = "Percent RAM Used: %0.3f %% Total RAM: %i Avaliable RAM: %i Used RAM: %i"%(ram[2], ram[0], ram[1], ram[3])
    elif command.startswith(CPU_STATUS):
        response = "Percent CPU used %0.2f %%"%(get_cpu())
    elif command.startswith(NUM_USERS):
        response = os.popen("users | wc -w").read()
    elif command.startswith(WHO_USERS):
        response = os.popen("users").read()
    elif command.startswith(UPTIME_STATUS):
        response = os.popen("uptime").read()
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel'] 
    return None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
