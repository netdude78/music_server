# coding: utf-8
import socket, sys, ui, os
from console import alert, hud_alert

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((socket.gethostbyname('raspberrypi.local'), 9999))
#s.send(sys.argv[-1])
#alert("Command Sent", "Command has been sent to Pi.", "Quit", hide_cancel_button=True)

def _play(sender):
	s.send('play')
	hud_alert('command sent')
	
	
def _stop(sender):
	s.send('stop')
	hud_alert('command sent')
	
def _pause(sender):
	s.send('pause')
	hud_alert('command sent')
	
def _next(sender):
	s.send('next')
	hud_alert('command sent')
	
def _restart(sender):
	s.send('restart song')
	hud_alert('command sent')
	
def _resume(sender):
	s.send('resume')
	hud_alert('command sent')
	
def _previous(sender):
	s.send('previous song')
	hud_alert('command sent')
	
v = ui.load_view('play_music')

if min(ui.get_screen_size()) >= 768:
	# iPad
	v.frame = (0, 0, 320, 320)
	v.present('sheet')
else:
	# iPhone
	v.present(orientations=['portrait'])
	
if len(sys.argv) > 1:
	if len(sys.argv)==3:
		command = "%s %s" %(sys.argv[1], sys.argv[2])
	else:
		command = sys.argv[1]
	s.send(command)
	hud_alert('sent command')