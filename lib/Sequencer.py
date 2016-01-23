import time
import threading
import rtmidi
from rtmidi.midiconstants import *
from lib.Track import *
from lib.LaunchPad import *
import sys
import traceback

MAX_TRACKS = 8
MODE_SESSION = 200
MODE_EDIT = 201
MODE_GLOBAL = 202
MODE_MIX = 202

BPM_OFFSET = 60
BPM_PER_BUTTON = 4

MIDDLE_C = 48

class Sequencer:

   def __init__(self, lp, conf):
      try:
         self.output = rtmidi.MidiOut() 
         self.output.open_port(int(conf['global']['midi_out']))
      except:
         print("Output Ports:\n" + str(self.output.get_ports()))
         print("Can't open main MIDI output device, run 'cat /dev/sndstat' and check config file")
         exit()  

      self.config = conf
      self.pad = lp
      self.bpm = int(conf['global']['bpm'])
      self.clock_time_div = float(conf['global']['clock_div'])
      self.clock_interval = (60.0 / self.bpm) / self.clock_time_div
      
      self.pad.btn_callback = self.buttonPressed
      self.pad.btn_long_callback = self.buttonPressedLong
      self.pad.grid_callback = self.gridPressed
      self.pad.grid_long_callback = self.gridPressedLong
      self.mode = MODE_SESSION
      self.editing_track = None
      self.editing_page = None
      self.editing_offset = MIDDLE_C
      
      self.tracks = []
      for t in range(MAX_TRACKS):
         trk = Track(self, t, self.bpm)
         self.tracks.append(trk)

      self.__quit_now = False
      threading.Timer(0, self.__mainloop).start()
      
   def buttonPressed(self, b):
      #print("   BUTTON="+str(b))
      #print("pages="+str(self.editing_track.getPlayingPattern().countPages()))
      if(b == 4): 
         self.startSessionMode()
         return
         
      if(b == 6): 
         self.startGlobalMode()
         return
         
      if(self.mode == MODE_EDIT):
         pages = self.editing_track.getPlayingPattern().countPages()
         # switch to page 0 
         if(b == 0):
            self.editPage(0, self.editing_offset)
            
         # add or switch to page 2
         if(b == 1):
            if(pages == 1):
               self.editing_track.getPlayingPattern().addPage()
               self.pad.setButton(1, AMBER_FULL)
            self.editPage(1, self.editing_offset)
            
         # add or switch to page 3
         if(b == 2):
            if(pages == 2):
               self.editing_track.getPlayingPattern().addPage()
               self.pad.setButton(2, AMBER_FULL)
               self.editPage(2, self.editing_offset)
            else: 
               if(pages >= 3): self.editPage(2, self.editing_offset)
               
         # add or switch to page 4
         if(b == 3):
            if(pages == 3):
               self.editing_track.getPlayingPattern().addPage()
               self.pad.setButton(3, AMBER_FULL)
               self.editPage(3, self.editing_offset)
            else: 
               if(pages == 4): self.editPage(3, self.editing_offset)               
            
   
   def buttonPressedLong(self, b):
      if(b == 7):                   # QUIT!
         self.quit()
         self.pad.close()
      
      if(self.mode != MODE_EDIT): return
      
      pages = self.editing_track.getPlayingPattern().countPages()
      # page 0 can't be deleted
      # delete page 1
      if(b == 1):
         if(pages == 2):
            self.editing_track.getPlayingPattern().removePage()
            self.pad.setButton(1, LED_OFF)
            self.editPage(0, self.editing_offset)
      # delete page 2
      if(b == 2):
         if(pages == 3):
            self.editing_track.getPlayingPattern().removePage()
            self.pad.setButton(2, LED_OFF)
            self.editPage(1, self.editing_offset)
      # delete page 3
      if(b == 3):
         if(pages == 4):
            self.editing_track.getPlayingPattern().removePage()
            self.pad.setButton(3, LED_OFF)
            self.editPage(2, self.editing_offset)         

               
   def gridPressed(self, b):
      x, y = LaunchPad.convertToXY(b)
      
      # side buttons are on x = 8
      if(x == 8):
         if(y == 4 and self.mode == MODE_EDIT): # snd b button on LP
            self.editing_offset -= 8
            self.editPage(self.editing_page, self.editing_offset)
            return
         if(y == 5 and self.mode == MODE_EDIT): # snd b button on LP
            self.editing_offset += 8
            self.editPage(self.editing_page, self.editing_offset)
            return
         if(y == 3): # STOP button on LP
            if(self.mode == MODE_EDIT):
               self.editing_track.stopPlaying()
               self.startSessionMode()
               return
            if(self.mode == MODE_SESSION):
               for trk in self.tracks:
                  trk.stopPlaying()
               self.startSessionMode()
         if(y == 0 and self.mode == MODE_EDIT):
            self.editing_track.getPlayingPattern().delete() #.steps = [Step() for s in range (8)]
            self.editing_track.stopPlaying()
            self.editing_track = None
            self.startSessionMode()
            
         return
         
      if(self.mode == MODE_EDIT):
         page_offset = self.editing_page * 8
         pat = self.editing_track.getPlayingPattern() #self.tracks[self.editing_track].patterns[self.tracks[self.editing_track].active_pat]
         old_note_y = (pat.steps[x + page_offset].note) - self.editing_offset
         
         # switch off note
         if(y == old_note_y):
            pat.steps[x + page_offset].note = 0
            colour = LED_OFF
            if((self.editing_offset + y) % 12 in [1, 3, 6, 8, 10]): colour = RED_DIM
            self.pad.setLED(x, y, colour)
            pat.note_count -= 1
         else:
            # monophonic so only a single note at each step
            pat.steps[x + page_offset].note = y + self.editing_offset
            pat.note_count += 1
            if(old_note_y >= 0 and old_note_y <= 7): self.pad.setLED(x, old_note_y, LED_OFF)
            self.pad.setLED(x, y, AMBER_FULL)
      
      if(self.mode == MODE_SESSION):
         pat_num = 7 - y
         trk = self.tracks[x]
         
         # if pressed empty pattern - then edit it
         if(trk.patterns[pat_num].isEmpty()):
            self.startEditMode(x, pat_num, 0)
         else:
            # if playing, turn off old light
            if(trk.isPlaying()): 
               self.pad.setLED(x, 7 - trk.getPlayingPatternNum(), AMBER_FULL)
               # if pressed playing pattern then stop it
               if(trk.getPlayingPatternNum() == pat_num): 
                  trk.stopPlaying()
                  return
            # now play selected track
            trk.playPattern(pat_num)
            self.pad.setLED(x, y, GREEN_FULL)
            
      if(self.mode == MODE_GLOBAL):
         bpm = (((y * 8) + x) * BPM_PER_BUTTON) + BPM_OFFSET
         self.setBPM( bpm )
         self.paintBPM()
         
   def gridPressedLong(self, b):
      x, y = LaunchPad.convertToXY(b)
      print("grid press long - here {} {}".format(x, y))
      if(self.mode == MODE_SESSION):
         pat_num = 7 - y
         self.startEditMode(x, pat_num, 0)
  
   def __mainloop(self):
      while not self.__quit_now:
         #pass
         time.sleep(self.clock_interval / 6) # every six beats (send clock in 1/16th time)
         self.output.send_message([TIMING_CLOCK]) 

   def startGlobalMode(self):
      print("start global mode")
      self.mode = MODE_GLOBAL
      self.pad.clear()
      self.pad.setButton(6, GREEN_FULL)
      self.paintBPM()
         
   def startEditMode(self, trk_num, pat_num, pg_num):
      print("start edit mode", trk_num, pat_num, pg_num)
      self.pad.clear()
      self.pad.setButton(5, GREEN_FULL) # turn on user 1 button on LP
      self.pad.setLED(8, 0, RED_FULL)
      self.pad.setLED(8, 3, RED_FULL)
      self.editing_offset = MIDDLE_C

      try:
         self.mode = MODE_EDIT
         self.editing_track = self.tracks[trk_num]
		   # IMPORTANT MIGHT WANT TO CHANGE THIS LATER
         self.editing_track.playPattern(pat_num)
         # set the four buttons for each page 
         for p in range(self.editing_track.getPlayingPattern().countPages()):
            self.pad.setButton(p, AMBER_FULL)
         print("# About to change page")
         self.editPage(pg_num, self.editing_offset)
      except:
         print(traceback.format_exc())

   def startSessionMode(self):
      self.pad.clear()
      self.mode = MODE_SESSION
      for p in range(8):
         self.pad.setButton(p, LED_OFF)
      self.pad.setButton(4, GREEN_FULL)
      
      # load patterns gubbins here.   
      self.pad.clearGrid()
      t = 0
      for trk in self.tracks:
         p = 0
         for pat in trk.patterns:
            if not pat.isEmpty():
               col = AMBER_FULL
               if(trk.active_pat == p): col = GREEN_FULL
               self.pad.setLED(t, 7 - p, col)
            p += 1
         t += 1

   def editPage(self, page, offset):
      #print("## CHANGE PAGE", self.editing_page , page)
      
      n = int((offset - MIDDLE_C) / 8)
      if(n == -1): 
         self.pad.setLED(8, 5, LED_OFF)
         self.pad.setLED(8, 4, GREEN_FULL)
      if(n == -2): 
         self.pad.setLED(8, 5, LED_OFF)
         self.pad.setLED(8, 4, GREEN_FULL + RED_MID)
      if(n == -3): 
         self.pad.setLED(8, 5, LED_OFF)
         self.pad.setLED(8, 4, AMBER_FULL)
      if(n == -4): 
         self.pad.setLED(8, 5, LED_OFF)
         self.pad.setLED(8, 4, GREEN_MID + RED_FULL)
      if(n <= -5): 
         self.pad.setLED(8, 5, LED_OFF)
         self.pad.setLED(8, 4, RED_FULL)
         
      if(n == 0): 
         self.pad.setLED(8, 4, LED_OFF)
         self.pad.setLED(8, 5, GREEN_FULL)
      if(n == 1): 
         self.pad.setLED(8, 4, LED_OFF)
         self.pad.setLED(8, 5, GREEN_FULL + RED_MID)
      if(n == 2): 
         self.pad.setLED(8, 4, LED_OFF)
         self.pad.setLED(8, 5, AMBER_FULL)
      if(n == 3): 
         self.pad.setLED(8, 4, LED_OFF)
         self.pad.setLED(8, 5, GREEN_MID + RED_FULL)
      if(n >= 4): 
         self.pad.setLED(8, 4, LED_OFF)
         self.pad.setLED(8, 5, RED_FULL)
         
      for p in range(self.editing_track.getPlayingPattern().countPages()):
         self.pad.setButton(p, AMBER_FULL)
      self.pad.setButton(page, RED_FULL)
      self.editing_page = page
      
      # clear grid and paint black keys as dim green
      for y in range(8):
         colour = LED_OFF
         if((offset + y) % 12 in [1, 3, 6, 8, 10]): colour = RED_DIM
         for x in range(8):
            self.pad.setLED(x, y, colour)

      # load grid for page
      x = 0 
      y = 0
      for s in range(page * 8, (page * 8) + 8):
         y = self.editing_track.getPlayingPattern().steps[s].note - offset
         if(y < 0 or y > 7): 
            x += 1
            continue
         self.pad.setLED(x, y, AMBER_FULL)
         x += 1

   def lightstep_on(self, offset, note, track):
      if(self.editing_track != track): return
      if(self.mode != MODE_EDIT): return
	  
      if(offset >= (self.editing_page * 8) and offset < ((self.editing_page + 1) * 8)): 
         x = offset % 8
         y = note - self.editing_offset
         if(y < 0 or y > 7): return
         self.pad.setLED(x, y, GREEN_FULL)
      else:
         # Pointless code but only way to get the Launchpad to light up correctly
         self.pad.setButton(int(offset/8), GREEN_FULL)

   def lightstep_off(self, offset, note, track):
      if(self.editing_track != track): return
      if(self.mode != MODE_EDIT): return
	  
      if(offset >= (self.editing_page * 8) and offset < ((self.editing_page + 1) * 8)): 
         x = offset % 8
         y = note - self.editing_offset
         if(y < 0 or y > 7): return
         self.pad.setLED(x, y, AMBER_FULL)
      else:
         # Pointless code but only way to get the Launchpad to light up correctly
         self.pad.setButton(int(offset/8), AMBER_FULL)
         
   def quit(self):
      self.__quit_now = True
      for trk in self.tracks: trk.quit()
      self.output.send_message([CONTROLLER_CHANGE, ALL_NOTES_OFF, 0])
      self.output.send_message([CONTROLLER_CHANGE, 120, 0])   
      
      self.config['global']['bpm'] = str(self.bpm)
      cfgfile = open("config.cfg", 'w')
      self.config.write(cfgfile)
      cfgfile.close()

   def setBPM(self, bpm):
      self.bpm = bpm
      self.clock_interval = (60.0 / self.bpm) / self.clock_time_div  
      for trk in self.tracks:
         trk.setBPM(bpm)
         
   def paintBPM(self):
      self.pad.clearGrid()
      for i in range(int ((self.bpm - BPM_OFFSET) / BPM_PER_BUTTON) + 1):
         self.pad.setLED(i % 8, int(i / 8), GREEN_FULL)