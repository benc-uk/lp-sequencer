import threading
import time
import rtmidi
from rtmidi.midiconstants import *
from lib.LaunchPad import *
import json

MAX_PATTERNS = 8

class Pattern:
   def __init__(self):
      self.empty = True
      self.active = False
      #self.editing = False
      self.steps = [Step(0, 127, 0.9) for s in range (8)]
      self.note_count = 0
   
   def addPage(self):
      for s in range(8):
         stp = Step(0, 127, 0.9)
         self.steps.append(stp)
         
   #def editPattern(self):
   #   self.editing = True

   #def editPatternStop(self):
   #   self.editing = False
      
   def removePage(self):
      new_len = len(self.steps) - 8
      self.steps = self.steps[:new_len]
      
   def countPages(self):
      #print("len="+str(len(self.steps)))
      return int(len(self.steps) / 8)
      
   def isEmpty(self):
      return self.note_count <= 0
         
   def delete(self):
      self.empty = True
      self.active = False      
      self.steps = [Step(0, 127, 0.9) for s in range (8)]
      self.note_count = 0
      
      
      
class Step:
   def __init__(self, n, v, g):
      self.note = n
      self.vel  = v
      self.gate = g
      self.active = True
  

class Track:
   def __init__(self, seq, midi_channel, bpm):
      self.channel = midi_channel
      self.tracknum = midi_channel
      self.seq = seq
      self.patterns = [Pattern() for p in range(MAX_PATTERNS)]
      self.active_pat = None
      
      self.timediv = 4.0
      self.bpm = bpm
      self.interval = (60.0 / self.bpm) / self.timediv
      
      self.__quit_now = False
      threading.Timer(0, self.__mainloop).start()
      
   def __mainloop(self):
      while not self.__quit_now:
         if(self.active_pat == None):          
            time.sleep(self.interval)
            continue
         offset = 0
         interval_t = self.interval # take copy outside of loop in case of user changes
         for step in self.patterns[self.active_pat].steps: 
            note = step.note
            velo = step.vel
            notetime = step.gate * interval_t

            #if(self.patterns[self.active_pat].editing):
            self.seq.lightstep_on(offset, note, self)            
            
            if(note <= 0):
               time.sleep(interval_t)
            else:
               #print("##NOTE## {}:{} ({})".format(self.channel, note, offset))
               self.seq.output.send_message([self.channel | NOTE_ON, note, velo]) 
               time.sleep(notetime)
               self.seq.output.send_message([self.channel | NOTE_OFF, note, 0])
               time.sleep(interval_t - notetime)
            
            self.seq.lightstep_off(offset, note, self)
            offset = offset + 1
   
   def setBPM(self, bpm):
      self.bpm = bpm
      self.interval = (60.0 / self.bpm) / self.timediv
      
   def playPattern(self, p):
      self.active_pat = p

   def stopPlaying(self):
      self.active_pat = None
      
   def isPlaying(self):
      return self.active_pat != None
            
   def getPlayingPattern(self):
      return self.patterns[self.active_pat]
      
   def getPlayingPatternNum(self):
      return self.active_pat
   
   def quit(self):
      self.__quit_now = True
      dict = {"patterns":[]}
      for p in range(len(self.patterns)):
         dict['patterns'].append({"steps":[]})
         for s in range(len(self.patterns[p].steps)):
            dict['patterns'][p]['steps'].append(self.patterns[p].steps[s].__dict__)
      with open('data/track'+str(self.tracknum)+'_data.json', 'w') as outfile:
         json.dump(dict, outfile)
      