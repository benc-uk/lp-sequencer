import configparser 
from lib.LaunchPad import *
from lib.Sequencer import *
import json
import pprint
import os

# Load main config
config = configparser.RawConfigParser()
config.read('config.cfg')

lp = LaunchPad(int(config['global']['lp_midi_in']), int(config['global']['lp_midi_out']))

lp.clear()
lp.setFlash(False)
seq = Sequencer(lp, config)

# load data
for t in range(8):
   # skip missing files == default data
   if(not os.path.isfile('data/track'+str(t)+'_data.json')): continue
   
   # load json data
   json_file = open('data/track'+str(t)+'_data.json')
   track_data = json.load(json_file)
   pat_num = 0
   # loop and deserialize into pattern and step data in each track
   for pat in track_data['patterns']:
      steps = pat['steps']
      # wipe steps array to empty for appending back to full size
      # steps array MUST still be 8, 16, 24 or 32 long
      seq.tracks[t].patterns[pat_num].steps = []
      for new_step in steps:
         seq.tracks[t].patterns[pat_num].steps.append(Step(new_step['note'], new_step['vel'], new_step['gate']))
         if(new_step['note'] != 0): seq.tracks[t].patterns[pat_num].note_count += 1
      pat_num += 1
      
   json_file.close()

seq.startSessionMode()
