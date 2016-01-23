import time
import configparser 
import pprint
import rtmidi
from rtmidi.midiconstants import *
from midi_classes import *

# Load main config
config = configparser.RawConfigParser()
config.read('main.cfg')

#
# Globals / singletons 
#
midi = MidiGlobal(config)

#
# Load tracks from config file
#
for section in config.sections():
   if(section != "global"):
      track = MidiTrack(config, section, midi) #name, midi, channel, midi.master_bpm, gate, timediv, pat_len)
      
      # Load and parse note data for each pattern into track
      if config.has_option(section, 'data') and len(config[section]['data']) > 0:
         data_str = config[section]['data']
         for pat in data_str.split("|"):
            notes = [int(n) for n in pat.split(",")]
            track.patterns.append(notes)
      else:
         # If no data value present then create defaults
         print("Initialising data for track {}".format(section))
         for p in range(0, midi.MAX_PATTERNS):
            notedata = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            track.patterns.append(notedata)
         
      midi.add_track(track)
    
#
# Main global master loop
#
try:
   if(config['global'].getboolean('send_midi_song')): midi.send_message([SONG_START])
   while True:
      time.sleep(midi.clock_interval / 6) # every six beats (send clock in 1/16th time)
      if(config['global'].getboolean('clock_send')): midi.send_message([TIMING_CLOCK]) 
except KeyboardInterrupt:
   # Quit when user hits CTRL-C
   if(config['global'].getboolean('send_midi_song')): midi.send_message([SONG_STOP])
   midi.send_message([CONTROLLER_CHANGE, ALL_NOTES_OFF, 0])
   # Reset play and stop lights
   midi.send_control_change(41, 0)
   midi.send_control_change(42, 127)  
   # Send quit message to all tracks
   midi.quit()
   
   # Save config file
   config['global']['bpm'] = str(midi.master_bpm)
   with open('main.cfg', 'w') as configfile: config.write(configfile)
   


