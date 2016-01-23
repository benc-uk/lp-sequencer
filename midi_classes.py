import time
import threading
import pprint
import configparser 
import rtmidi
from rtmidi.midiconstants import *

# Some readiblity consts
ON = 127
OFF = 0

###############################################################################
#
# Main global class for handling all MIDI I/O and holding all the tracks  
#
###############################################################################
class MidiGlobal:
   MAX_PATTERNS = 8
   MAX_PATTERN_LEN = 16

   midi_out      = None       # MIDI notes output - e.g. USB MIDI, chained thru
   midi_in       = None       # MIDI notes input for note editing - e.g. nanoKey2
   midi_out_ctrl = None       # MIDI control output - e.g. nanoKontrol2
   midi_in_ctrl  = None       # MIDI in output - e.g. nanoKontrol2
   master_bpm = 120.0         # default if not in config
   clock_time_div = 4.0       # 16th notes
   clock_interval = (60.0 / master_bpm) / clock_time_div
   tracks = []                # master array of tracks, loaded from config
   config = None
   active_track = 0           # which track is active for controling/editing
   
   rec_mode = False           # Record mode records notes in order
   rec_mode_step = 0          # Step counter for record mode
   rec_edit_step = -1         # Used to let user edit single note anywhere in seq
   
   # Constructor does standard stuff but also reads in defaults from config file
   def __init__(self, config):
      try:
         self.midi_in_ctrl = rtmidi.MidiIn() 
         self.midi_in = rtmidi.MidiIn() 
         self.midi_out = rtmidi.MidiOut() 
         self.midi_out_ctrl = rtmidi.MidiOut() 
         print("Output Ports:\n" + str(self.midi_out.get_ports()))
         print("\nInput Ports:\n" + str(self.midi_in_ctrl.get_ports()))
         
         self.midi_out.open_port(int(config['global']['midi_main_out']))
         self.midi_out_ctrl.open_port(int(config['global']['midi_ctrl_out']))
          
         self.midi_in_ctrl.set_callback(self.midi_event)
         self.midi_in.set_callback(self.midi_event)
         self.midi_in_ctrl.open_port(int(config['global']['midi_ctrl_in']))
         self.midi_in.open_port(int(config['global']['midi_key_in']))
         
         self.config = config
         self.master_bpm = int(config['global']['bpm'])
      except:
         print("Can't open MIDI output devices, run 'cat /dev/sndstat' and check config file")
         exit()
         
   # Main control and I/O function, set as a callback on the midi ports
   # MIDI messages get routed here, both notes and cc events
   # - Note: Lots of nanoKontrol2 specific cc numbers hard coded here, sorry!
   def midi_event(self, message, time_stamp):
      # Note or rest input (cc 46 is rest)
      if(message[0][0] == NOTE_ON or (message[0][0] == CONTROLLER_CHANGE and message[0][1] == 46)):
         note = message[0][1]
         
         # Rest is on cc 46, but only on button down (val = 127)
         if(message[0][0] == CONTROLLER_CHANGE and message[0][1] == 46): 
            if(message[0][2] == 127): note = 0
            else: return
         
         # Standard record mode
         if(self.rec_mode):
            trk = self.tracks[self.active_track]
            trk.patterns[ trk.active_pattern ][self.rec_mode_step] = note
            self.rec_mode_step += 1
            if(self.rec_mode_step >= self.MAX_PATTERN_LEN): 
               self.rec_mode = False
               self.send_control_change(45, OFF) 
               self.rec_mode_step = 0
        
         # Edit a single note mode
         if(self.rec_edit_step >= 0 and not self.rec_mode):
            # This crazy code is to cope with the nanoKontrol and the order of it's buttons and cc
            note_step = self.rec_edit_step - 32
            if(self.rec_edit_step >= 48): note_step = self.rec_edit_step - 40         
            trk = self.tracks[self.active_track]
            trk.patterns[ trk.active_pattern ][note_step] = note
      
      # Control events
      if(message[0][0] == CONTROLLER_CHANGE):
         cc = message[0][1]
         val = message[0][2]
         if(cc == 16):
            # BPM range 50 ~ 168
            val += 50
            self.set_bpm(val)
            self.tracks[self.active_track].set_bpm(val)
         if(cc == 17):
            # Gate range 0.0 ~ 1.0
            self.tracks[self.active_track].set_gate(val / 127)
         if(cc == 18):
            # Div range 1 ~ 4
            self.tracks[self.active_track].set_timediv(int(val / 32) + 1)
         if(cc == 19):
            # Pattern len
            self.tracks[self.active_track].set_length( int((val / 8) + 1) )
         if(cc == 42):
            # Stop playback
            self.send_control_change(41, OFF)
            self.send_control_change(42, ON)
            self.tracks[self.active_track].set_stop()
         if(cc == 41):
            # Start playback
            self.send_control_change(41, ON)         
            self.send_control_change(42, OFF)
            self.tracks[self.active_track].set_play()
         if(cc == 45 and val == 0):
            # Rec mode
            self.rec_mode = not self.rec_mode
            self.rec_mode_step = 0
            if self.rec_mode: 
               self.send_control_change(45, ON)
               self.rec_mode_step = 0               
            else: 
               self.send_control_change(45, OFF) 
         if((cc >= 32 and cc <= 39) or ((cc >= 48 and cc <= 55))):
            # Edit a single step, using the rows of solo and mute buttons on the nanoKontrol
            if(val == 127):
               self.rec_edit_step = cc
            else:
               self.rec_edit_step = -1
         if(cc == 43 and val == 0):
            # Change pattern next
            self.tracks[self.active_track].change_patt(-1)   
         if(cc == 44 and val == 0):
            # Change pattern prev
            self.tracks[self.active_track].change_patt(+1)     
         if((cc == 58 or cc == 59 ) and val == 0):
            # Change active track
            if(cc == 58): self.active_track -= 1              
            else: self.active_track += 1 
            if self.active_track < 0: self.active_track = len(self.tracks)-1
            if self.active_track >= len(self.tracks): self.active_track = 0
            print("Setting active track {}".format(self.active_track+1))
         
   # Set global BPM
   def set_bpm(self, b):
      print("Setting global tempo to: "+str(b))
      self.master_bpm = b
      self.clock_interval = (60.0 / self.master_bpm) / self.clock_time_div
      
   # Send note on message to the main mini note output
   def note_on(self, note, c):
      #print("N:{} ~ C:{}".format(note, c))
      self.midi_out.send_message([c | NOTE_ON, note, ON])
      
   # Send note off message to the main mini note output
   def note_off(self, note, c):
      self.midi_out.send_message([c | NOTE_OFF, note, OFF])
   
   # Send cc message to the mini control output - used to control the lights on the nanoKontrol
   def send_control_change(self, cc, val):
      self.midi_out_ctrl.send_message([CONTROLLER_CHANGE, cc, val])
      
   # Send raw message to the main mini note output
   def send_message(self, msg):
      self.midi_out.send_message(msg)   

   # Important this is called when the program exits
   def quit(self):
      # Save track data to the config
      for trk in self.tracks:
         trk.set_stop()
         trk.quit()
         trk.update_config(self.config)
         
      time.sleep(self.clock_interval * 6)
      self.midi_in.close_port()
      self.midi_out.close_port()
      self.midi_out_ctrl.close_port()
      self.midi_in_ctrl.close_port()
   
   # Add new track, called at program start, it also starts the thread for the track
   def add_track(self, t):
      self.tracks.append(t)    
      threading.Timer(0, t.mainloop).start()

###############################################################################
#
# Main track class - track/device specific code here  
#
###############################################################################
class MidiTrack:
   name = "No Name"     # Name
   midi = None          # Pointer to global MIDI object
   quitit = False       # Control for main loop, used to exit infinite loop
   play = False         # Control for main loop, used to play notes or just loop in silence
   channel = 0          # MIDI channel number
   interval = 0         # Note interval timing in seconds
   bpm = 0              # BPM, same as global BPM, each track does not have independent BPM!
   timediv = 4.0        # Time division 4 = 1/16, 2 = 1/8, 1 = 1/4
   notetime = 0         # Note duration in seconds, a function of gate time and interval
   gate = 0             # Note gate, Range: 0.0~1.0
   pattern_len = 0      # When playing pattern, you can shorten the loop to less than the full 16
   active_pattern = 0   # Which pattern is active
   patterns = []        # Main array of patterns and note data
   tick = 0 
   def __init__(self, config, section, midi):
      # Load from config or if no config - set to defaults
      self.name = config[section].name
      self.channel = int(config[section]['channel']) - 1 # rtmidi is dumb, channels are 0-15 instead of 1-16
      self.gate = float (config[section]['gate'] if config.has_option(section, 'gate') else 0.5)
      self.timediv = int (config[section]['timediv'] if config.has_option(section, 'timediv') else 4)
      self.pattern_len = int (config[section]['pattern_len'] if config.has_option(section, 'pattern_len') else midi.MAX_PATTERN_LEN)  

      # Get handle on global stuff
      self.midi = midi
      self.bpm = midi.master_bpm

      # Inital maths for note timings
      self.interval = (60.0 / self.bpm) / self.timediv
      self.notetime = self.interval *  self.gate

      # Set basic vars to defaults
      self.quitit = False
      self.play = False
      self.patterns = []
      self.tick = 0

   # The heart of the sequencer is here
   # Infinite loop which interates through the note data in the active pattern
   # sleeps are designed to send notes at correct intervals for note gate and overall bpm
   def mainloop(self):
      while not self.quitit:
         for self.tick in range(0, self.pattern_len):
            note = self.patterns[self.active_pattern][self.tick % self.pattern_len]
            #next_note = self.patterns[self.active_pattern][(self.tick + 1) % self.pattern_len]      
            do_play = self.play        # Take a copy of the play boolean in case user hits stop inbetween note on & off         
            if(do_play):
               #if(note > 0): print("{} {} {} ".format(note, self.notetime, self.interval))
               # Only play notes on if user has hit play, also send pretty lights to nanoKontrol
               light = 32 + self.tick
               if(self.tick > 7): light += 9
               #self.midi.send_control_change(light, ON)
               if(note > 0): self.midi.note_on(note, self.channel)    
            time.sleep(self.notetime) # Sleep between note on and note off
            if(do_play):
               # Only play notes off if user has hit play, also send pretty lights to nanoKontrol
               light = 32 + self.tick
               if(self.tick > 7): light += 9
               #self.midi.send_control_change(light, OFF)
               if(note > 0): self.midi.note_off(note, self.channel)
            time.sleep(self.interval - self.notetime)  # Remained of sleep until next BPM tick, allows for gated notes
         
   # Set note gate percentage for this track (0.0 ~ 1.0)
   def set_gate(self, gate):
      print("Setting '{}' to gate: {}".format(self.name, round(gate, 2)))
      self.gate = gate
      self.notetime = self.interval * self.gate
      
   # Set BPM - controlled globally
   def set_bpm(self, b):
      self.bpm = b
      self.interval = (60.0 / self.bpm) / self.timediv
      self.notetime = self.interval * self.gate
      
   # Change time division (1, 2 or 4)
   def set_timediv(self, div):
      if(div == 3): return
      print("Setting '{}' step div to: {}".format(self.name, self.timediv))
      self.timediv = div
      self.interval = (60.0 / self.bpm) / self.timediv
      
   # Change the pattern len (1 ~ 16)
   def set_length(self, len):
      self.pattern_len = len
      print("Setting '{}' to length: {}".format(self.name, self.pattern_len))
      
   # Quit the main loop to exit
   def quit(self):
      self.quitit = True
      
   # User has hit stop
   def set_stop(self):
      self.play = False      
      
   # User has hit play
   def set_play(self):
      self.play = True
      
   # Change active pattern, loop from 8 back to 0
   def change_patt(self, offset):
      self.active_pattern += offset
      if self.active_pattern < 0: self.active_pattern = 7
      if self.active_pattern > 7: self.active_pattern = 0
      print("Setting '{}' to pattern: {}".format(self.name, self.active_pattern+1))
      
   # Used to store everything back into the config ready to be writen to file
   def update_config(self, config):
      config[self.name]['gate'] = str(self.gate)
      config[self.name]['timediv'] = str(self.timediv)
      config[self.name]['pattern_len'] = str(self.pattern_len)
      config[self.name]['active_pattern'] = str(self.active_pattern)      
      data_str = ""
      for pat in self.patterns:
         pat_str = ','.join(str(n) for n in pat)
         infix = ('' if len(data_str) == 0 else '|') # voodoo
         data_str = data_str + infix + pat_str 
            
      config[self.name]['data'] = data_str
      