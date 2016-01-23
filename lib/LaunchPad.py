import rtmidi
from rtmidi.midiconstants import *
import threading

LED_OFF = 4
RED_FULL = 7
RED_MID = 6
RED_DIM = 5
RED_BLINK = 11
GREEN_FULL = 52
GREEN_MID = 36
GREEN_DIM = 20
GREEN_BLINK = 56
AMBER_FULL = ((RED_FULL + GREEN_FULL) - 4)
AMBER_MID = ((RED_MID + GREEN_MID) - 4)
AMBER_DIM = ((RED_DIM + GREEN_DIM) - 4)
AMBER_BLINK = ((AMBER_FULL - 4) + 8)
LONG_PRESS = 0.6

class LaunchPad:

   def __init__(self, in_port, out_port):
      try:
         self.input = rtmidi.MidiIn() 
         self.output = rtmidi.MidiOut() 
         self.input.open_port(in_port)
         self.output.open_port(out_port)
         self.input.set_callback(self.__midi_message)
         self.last_ts = 0
         self.btn_callback = None
         self.grid_callback = None
         self.btn_long_callback = None
         self.grid_long_callback = None
      except:
         print("Can't open Launchpad MIDI device, run 'cat /dev/sndstat' and check config file")
         exit()      

   def __midi_message(self, msg, ts):
      type = msg[0][0]
      num = msg[0][1]
      val = msg[0][2]
      time = msg[1]
      if(type == CONTROLLER_CHANGE and val == 0):       # Control change = top row of buttons
         if(time > LONG_PRESS):
            if(self.btn_long_callback != None): self.btn_long_callback(num - 104)
         else:
            if(self.btn_callback != None): self.btn_callback(num - 104)

      if(type != CONTROLLER_CHANGE and val == 0):       # Note change = main grid
         if(time > LONG_PRESS):
            if(self.grid_long_callback != None): self.grid_long_callback(num)
         else:
            if(self.grid_callback != None): self.grid_callback(num)

            
   def setButton(self, b, c):
      self.output.send_message([CONTROLLER_CHANGE, 104 + b, c]) 

   def convertToXY(note):
      x = (note % 16)
      y = 7 - int((note - x) / 16)
      return x, y
   
   def close(self):
      self.clear()
      self.input.close_port()
      self.output.close_port()
      
   def setLED(self, led_x, led_y, c):
      #print(" #LED# {},{},{}".format(led_x, led_y, c))
      n = ((7 - led_y) * 16) + led_x
      self.output.send_message([NOTE_ON, n, c]) 
      
   def clear(self):
      self.output.send_message([CONTROLLER_CHANGE, 0, 0])
      
   def blinkLED(self, bx, by, c1, c2, t):
      self.setLED(bx, by, c1)
      threading.Timer(t, self.setLED, [bx, by, c2]).start()

   def blinkButton(self, b, c1, c2, t):
      self.setButton(b, c1)
      threading.Timer(t, self.setButton, [b, c2]).start()
      
   #def blinkLED_OFF(self, x, y, c1, c2, t):
   #   n = ((7 - y) * 16) + x
   #   #threading.Timer(t, self.__blinkLED_OFF).start()
      
   def clearGrid(self):
      for y in range(8):
         for x in range(8):
            self.setLED(x, y, LED_OFF)
      
   def setFlash(self, on):
      if(on):
         self.output.send_message([CONTROLLER_CHANGE, 0, 40])       
      else:
         self.output.send_message([CONTROLLER_CHANGE, 0, 32])  
      