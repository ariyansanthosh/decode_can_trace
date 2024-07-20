#This script will take dbc file and decode can messages
#pip3 install pyyaml
#pip3 install cantools

import cantools
import os
from os.path import join as join_path
from os.path import isfile
from os.path import isdir
from pprint import pprint
import yaml


# Configurations
CONST_INPUT_DIR = join_path(os.getcwd(),"input")
CONST_CONFIG_FILE = join_path(CONST_INPUT_DIR,"configurations.yml")

# Global variables
g_dbc_file = None
g_trc_file = None
g_can_messages = {}
g_can_signals = {}
g_can_traces = {}

# Function to verify the YAML configurations
# It will check if all msgs and signals configured in YAML are defined in dbc file
# If even one of config check fails, script will exit(1)
def check_for_configurations():

	global g_dbc_file, g_trc_file, g_can_messages, g_can_signals

	if isdir(CONST_INPUT_DIR):
		if isfile(CONST_CONFIG_FILE):
			try:
				with open(CONST_CONFIG_FILE,'r') as yaml_file:
					configs = yaml.safe_load(yaml_file)
			except:
				print(e)
				print(f"Error : Reading configurations.yml (Invalid YAML file)")
				exit(1)
		else:
			print(f"Error : Reading configurations.yml (File does not exist in {CONST_INPUT_DIR})")
			exit(1)
	else:
		print(f"Error: Cannot find {CONST_INPUT_DIR}")
		exit(1)

	g_dbc_file = join_path(CONST_INPUT_DIR,configs['dbc'])
	if not isfile(g_dbc_file):
		print(f"Error: Reading dbc file (File does not exist in {CONST_INPUT_DIR})")

	g_trc_file = join_path(CONST_INPUT_DIR, configs['trace'])
	if not isfile(g_trc_file):
		print(f"Error: Reading trc file (File does not exist in {CONST_INPUT_DIR})")

	db = cantools.database.load_file(g_dbc_file)
	db_message_names = [msg.name for msg in db.messages]

	for msg in configs['Message']:

		msg_name = next(iter(msg.keys()))

		if msg_name not in db_message_names:
			print(f"Error: Rule for {msg_name} not defined in {configs['dbc']}")
			exit(1)

		msg_object = db.get_message_by_name(msg_name)
		tmp_signals = []

		for sig in msg[msg_name]['signals']:
			if sig not in msg_object.signal_tree:
				print(f"Error: Signal {sig} not defined in {configs['dbc']}")
				exit(1)
			else:
				tmp_signals.append(sig)

		g_can_messages[msg_object.frame_id] = msg_object.name
		g_can_signals[msg_name] = tmp_signals


def process_cantrc_data(cantrc_entry):

	global g_can_traces
	
	data = [val for val in cantrc_entry.split('  ') if val]
	time_stamp = data[1].strip()
	frame_id = int(data[3],16)
	hex_vals = data[5]
	frame_data = ""

	for val in hex_vals.split(' '):
		frame_data += r'\x' + val

	g_can_traces[time_stamp] = {'frame_id':frame_id, 'frame_data':frame_data.encode()}


# Main function; Start of the script
if __name__ == "__main__":

	check_for_configurations()

	#Read trc file
	with open(g_trc_file, "r") as file:
		for line in file:
			line = line.strip()
			#Ignore the comments, starts with ;
			if ';' not in line:
				process_cantrc_data(line)

	output = {}
	db = cantools.database.load_file(g_dbc_file)

	message_slot = list(g_can_messages.keys())
	flag =  True
	
	for time_stamp in g_can_traces.keys():

		frame_id = g_can_traces[time_stamp]['frame_id']

		if frame_id in g_can_messages.keys():
			db_msg_object = db.decode_message(frame_id,g_can_traces[time_stamp]['frame_data'])
			sig_values = {sig : db_msg_object[sig] for sig in g_can_signals[g_can_messages[frame_id]]}

			if flag:
				slot_ts = time_stamp
				output[slot_ts] = {}

			if frame_id in message_slot:
				message_slot.remove(frame_id)
				flag = False
				temp = output[slot_ts]
				temp.update(sig_values)
				output[slot_ts] =  temp

				if len(message_slot) == 0:
					message_slot = list(g_can_messages.keys())
					flag = True
			else:
				output[slot_ts] = sig_values
				message_slot = list(g_can_messages.keys())
				flag = True

	
	with open("Sample.txt",'w') as file:
		file.write(f"Time,")
		for msg in g_can_signals.keys():
			for sig in g_can_signals[msg]:
				file.write(f"{sig},")

		file.write("\n")
		for time_stamp in output.keys():
			file.write(f"{time_stamp},")
			for msg in g_can_signals.keys():
				for sig in g_can_signals[msg]:
					file.write(f"{output[time_stamp][sig]},")
			file.write("\n")

