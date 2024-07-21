#This script will take dbc file and decode can messages
#Required Modules
#pip3 install pyyaml
#pip3 install cantools

import cantools
import os
from os.path import join as join_path
from os.path import isfile
from os.path import isdir
from pprint import pprint
import yaml
import csv

# Global constants
CONST_INPUT_DIR     = join_path(os.getcwd(),"input")
CONST_CONFIG_FILE   = join_path(CONST_INPUT_DIR,"configurations.yml")
CONST_OUTPUT_FILE   = join_path(os.getcwd(), "Motor_Status_Report")

# Global variables
g_dbc_file          = None
g_trc_file          = None
g_can_messages      = {}
g_can_signals       = {}
g_can_traces        = {}
g_total_can_signals = []

# Function to verify the YAML configurations
# It will check if all msgs and signals configured in YAML are defined in dbc file
# If even one of config check fails, script will exit(1)
# 
# References :-
# https://cantools.readthedocs.io/en/latest/#
# 
def check_for_configurations():

    # Declaration of global variables inside function; Since these will be modified
    global g_dbc_file, g_trc_file, g_can_messages, g_can_signals, g_total_can_signals

    if isdir(CONST_INPUT_DIR):
        if isfile(CONST_CONFIG_FILE):
            try:
                #Extract YAML file contents and store it as a dict - 'configs'
                with open(CONST_CONFIG_FILE,'r') as yaml_file:
                    configs = yaml.safe_load(yaml_file)
            except:
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

    try:
        # Read the CAN-DBC file and create a list of message names
        db = cantools.database.load_file(g_dbc_file)
        db_message_names = [msg.name for msg in db.messages]
    except:
        print(f"Error: Reading CAN-DBC file (Invalid CAN-DBC file)")


    # Read messages cofigured in the YAML file
    # Check if these message names have a rule in the CAN-DBC file
    for msg in configs['Message']:

        msg_name = next(iter(msg.keys()))

        if msg_name not in db_message_names:
            print(f"Error: Rule for {msg_name} not defined in {configs['dbc']}")
            exit(1)

        msg_object = db.get_message_by_name(msg_name)
        tmp_signals = []

        # Read signals configured for each message in YAML file
        # Check if these signal names have a rule in the CAN-DBC file
        for sig in msg[msg_name]['signals']:
            # .signal_tree is a list of signals for each message objects read from CAN-DBC
            if sig not in msg_object.signal_tree:      
                print(f"Error: Signal {sig} not defined in {configs['dbc']}")
                exit(1)
            else:
                tmp_signals.append(sig)
                g_total_can_signals.append(sig)   # List of all vaild signals

        # g_can_messages consits of {frame_id : name} pair
        # Only user configured messages appear in this dict
        # frame_id will be in integer fmt
        g_can_messages[msg_object.frame_id] = msg_object.name
        
        # g_can_signals consists of {msg_name : signals_list}
        # For each message there could be multiple signals
        # Only user configured signals appear in the list
        g_can_signals[msg_name] = tmp_signals


# Function to process each line from the CANtrc file
# It extracts the time stamp, frame_id and data (8 bytes hex value) from each CAN frame
# Example CANtrc entries :-
#     1)        85.3  Rx         018C  8  09 00 F6 FF 13 02 00 00
#     2)        87.3  Rx         028C  8  59 54 08 01 A1 03 C8 01
def process_cantrc_data(cantrc_entry):

    global g_can_traces
    
    data = [val for val in cantrc_entry.split('  ') if val] # Split with '  ' (double spaces)
    time_stamp = data[1].strip()                            # 1st index is time
    frame_id = int(data[3],16)                              # 3rd index is frame_id (convert hex to int)
    hex_vals = data[5]                                      # 5th index is hex data
    frame_data = ""

    # cantools module expect the hex data as a byte string in this fmt
    # b"\x90\x00\xF6\xFF\x13\x02\x00\x00"
    for val in hex_vals.split(' '):
        frame_data += r'\x' + val

    g_can_traces[time_stamp] = {'frame_id':frame_id, 'frame_data':frame_data.encode()}


# Main function; Start of the script
if __name__ == "__main__":

    check_for_configurations()

    # Read trc file
    with open(g_trc_file, "r") as file:
        for line in file:
            line = line.strip()
            # Ignore the comments, starts with ;
            if ';' not in line:
                process_cantrc_data(line)

    
    # Message slot 
    message_slot = list(g_can_messages.keys())
    first_frame = True
    index = 0
    output = []

    db = cantools.database.load_file(g_dbc_file)
    
    for time_stamp in g_can_traces.keys():

        frame_id = g_can_traces[time_stamp]['frame_id']
        frame_data = g_can_traces[time_stamp]['frame_data']
        sig_values = {}

        if frame_id in g_can_messages.keys():
            
            db_msg_object = db.decode_message(frame_id,frame_data)
            
            if first_frame:
                sig_values['Time'] = time_stamp
                output.insert(index,{})
                first_frame = False

            temp_dict = {sig : db_msg_object[sig] for sig in g_can_signals[g_can_messages[frame_id]]}
            sig_values.update(temp_dict)


            if frame_id in message_slot:
                message_slot.remove(frame_id)
                output[index].update(sig_values)

                if len(message_slot) == 0:
                    message_slot = list(g_can_messages.keys())
                    first_frame = True
                    index += 1


    feilds = ['Time'] + g_total_can_signals
    
    # Generate CSV report
    with open(CONST_OUTPUT_FILE+".csv", 'w') as csvfile:
        writer = csv.DictWriter(csvfile,fieldnames=feilds)
        writer.writeheader()
        writer.writerows(output)

        print(f"Report generated : {CONST_OUTPUT_FILE}.csv")