#!/usr/bin/env python
# encoding: utf-8

############################################################################################################################################################################
#  COPYRIGHT NOTICE:                                                                                                                                                       #
#  AUTHOR:  Dave Stoll                                                                                                                                                     #
#  CONTACT: dave (dot) stoll (at) gmail (dot) com                                                                                                                          #
#  Created: 2016                                                                                                                                                           #
############################################################################################################################################################################
# The MIT License (MIT)                                                                                                                                                    #
# Copyright (c) <year> <copyright holders>                                                                                                                                 #
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the        #
# Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,  #
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:                                                                   #
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.                                           #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A        #
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF  #
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                                       #
############################################################################################################################################################################

from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from logging.handlers import RotatingFileHandler
import json, logging, syslog, signal, os, os.path, random, subprocess, sys, time, socket
from multiprocessing import Process, Queue

mp = None
_is_daemon=False

def createDaemon():
    """
        Detach a process from the controlling terminal and run it in the
        background as a daemon.
    """
    import os

    try:
        pid = os.fork()
    except OSError, e:
        raise Exception, "%s [%d]" % (e.strerror, e.errno)

    if (pid == 0):   # The first child.
        os.setsid()
        try:
            pid = os.fork()    # Fork a second child.
        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)

        if (pid == 0):    # The second child.
            pass
        else:
            os._exit(0)    # Exit parent (the first child) of the second child.
    else:
        os._exit(0)   # Exit parent of the first child.

class MPlayer:
    _media_directory = "./music"
    _media_player_command = "/usr/bin/mpg123"
    _song_list = []
    _previous_song = None
    _current_song = None
    _is_playing = False

    _loop_process = None
    q = Queue()

    global logger

    def __init__(self, mplayer = None, music_dir = None):
        if mplayer:
            self._media_player_command = mplayer
        if music_dir:
            self._media_directory = music_dir

        if not os.path.isdir(self._media_directory):
            logger.critical("Media Directory: %s does not exist or is not a directory." %self._media_directory)
            print os.listdir(self._media_directory)
            print "Critical Error.  Exiting.  Check Log for details."
            sys.exit(1)

        if not os.path.isfile(self._media_player_command):
            logger.critical("Media player command: %s does not exist or is not a regular file." %self._media_player_command)
            print "Critical Error.  Exiting.  Check Log for details."
            sys.exit(1)

    def shutdown(self):
        """
        shut down any existing processes.
        """
        logger.info("Shutdown method starting.")
        try:
            if os.path.isfile("music_server.pid"):
                logger.info("removing pid file.")
                os.remove("music_server.pid")
            #the only way to actually kill the player subprocess.
            self.q.put("STOP")
            time.sleep(2)
            self._loop_process.kill()
        except:
            pass

    def populate_song_list(self):
        """
        Find all songs in media directory and add them to the _song_list array.
        """
        logger.debug("populating song list.")
        self._song_list = os.listdir(self._media_directory)
        logger.debug("song list is %d elements long" %len(self._song_list))

    def play(self, song = None):
        """
        Wrapper function to handle stopping and starting the play_loop subprocess.
        """
        if self._loop_process:
            self.q.put("STOP")
            self._loop_process.terminate()

        self.q = Queue()
        time.sleep(2)
        self._loop_process = Process(target=self.play_loop, args=(self.q,song,))
        self._loop_process.start()

    def play_loop(self, q, song = None):
        """
        Start playing a song, when that song is finished, continue with another random song.
        args: song = song filename or absolute path and filename
        q = Queue - a message queue to handle interprocess communication (pause, fast forward, etc..)
        if no song is specified, a random song from _media_directory will be played.
        """
        ##
        ## Signal handler is needed in case autoplay is on.
        ## If autoplay is off, signals will be handled through the before_term process of twisted
        ##
        def signal_handler(signal, frame):
            logger.warn("Caught signal.  Calling shutdown method.")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGQUIT, signal_handler)

        _player_process = None
        # if there is a process already running, kill it forcibly.
        if _player_process != None and not _player_process.poll():
            logger.info("process already running.  Killing process.")
            _player_process.kill()
            _player_process = None

        while True:
            if not q.empty():
                ## message received
                msg = q.get()
                if msg == "STOP":
                    try:
                        _player_process.kill()
                    except:
                        pass
                    self._is_playing = False
                    return
                elif msg == "NEXT":
                    try:
                        _player_process.kill()
                    except:
                        pass
                    continue
                elif msg == "PAUSE":
                    try:
                        _player_process.send_signal(signal.SIGSTOP)
                    except:
                        pass
                    continue
                elif msg == "RESUME":
                    try:
                        _player_process.send_signal(signal.SIGCONT)
                    except:
                        pass
                    continue
                elif msg == "PREVIOUS":
                    try:
                        _player_process.kill()
                    except:
                        pass
                    song = self._previous_song
                    continue
                elif msg == "RESTART":
                    try:
                        _player_process.kill()
                    except:
                        pass
                    song = self._current_song
                    continue

            if not _player_process:
                # either there is no process running
                if not song:
                    logger.info("song not provided, picking random song.")
                    if not self._song_list:
                        logger.info("song list not populated, populating.")
                        self.populate_song_list()
                        if not self._song_list or len(self._song_list) < 1:
                            return "No songs to play."
                    song = os.path.join(self._media_directory, random.sample(self._song_list, 1)[0])

                if not os.path.split(song)[0]:
                    song = os.path.join(self._media_directory, song)

                # check to see if file exists
                if os.path.exists(song) and os.path.isfile(song):
                    pass
                else:
                    logger.error("File: %s missing." %song)

                if self._current_song:
                    logger.debug("logger.debug setting previous song to: %s" %self._current_song)
                    self._previous_song = self._current_song
                logger.debug("Setting current song to: %s" %os.path.split(song)[1])
                self._current_song = os.path.split(song)[1]

                logger.info("Playing song filename: %s" %song)
                    
                self._is_playing = True
                _player_process = subprocess.Popen([self._media_player_command, song], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                song = None

            elif _player_process.poll() != None:
                _player_process = None
                continue

    
    def pause_song(self):
        """
        Pause the player process if it is currently running:
        """
        self._is_playing = False
        logger.debug("Attempting to pause song.")
        self.q.put("PAUSE")

    def resume_song(self):
        """
        Un-Pause the player process if it is currently running:
        """
        self._is_playing = False
        logger.debug("Attempting to resume song.")
        self.q.put("RESUME")

    def stop_playing(self):
        """
        Stop playing
        """
        logger.debug("Stopping.")
        self.q.put("STOP")
        try:
            self._loop_process.terminate()
        except:
            pass
        self._loop_process = None
        self._is_playing=False


    def next_song(self):
        """
        Skipping to next song.
        """
        logger.debug("Skipping to next song.  Calling play_song.")
        self.q.put("NEXT")

    def previous_song(self):
        """
        Play Previous Song.
        """
        logger.debug("Skipping back one song.  Calling play_song with _previous_song")
        self.q.put("PREVIOUS")

    def restart_song(self):
        """
        Restart current song.
        """
        logger.debug("Rewinding to beginning of current song.  Calling play_song with _current_song")
        self.q.put("RESTART")

class SimpleProtocol(LineReceiver):
    _helpmsg = """
Available commands:

PLAY
    Start playing.
STOP
    Stop Playing.
NEXT
    Skip to Next Song.
    And plays, if stopped.
RESTART SONG
    Rewinds to beginning of song.
    And plays, if stopped.
PREVIOUS SONG
    Rewinds to beginning of previous song.
    And plays, if stopped.
HELP
    Returns this text."""
    global mp

    def connectionMade(self):
        logger.info('connectionMade')

    def dataReceived(self, data):
        logger.info('data received: RX: %s' %data.rstrip())

        command = data.rstrip().upper()

        if   command == 'PLAY':
            mp.play()
            response = 'Now Playing'
        elif command == 'STOP':
            mp.stop_playing()
            response = 'Stopping.'
        elif command == 'NEXT':
            mp.next_song()
            response = 'Fast Forwarding to Next Song'
        elif command == 'RESTART SONG':
            mp.restart_song()
            response = 'Playing Current Song From Beginning'
        elif command == 'PREVIOUS SONG':
            mp.previous_song()
            response = 'Rewind to Previous Song'
        elif command == "PAUSE":
            mp.pause_song()
            response = 'Paused Song'
        elif command == "RESUME":
            mp.resume_song()
            response = 'Resumed Playing Song'
        elif command == "HELP":
            response = self._helpmsg
        else:
            response = 'unknown request'

        logger.info('sending response. TX: %s' % response)
        self.sendLine(response)

class SimpleProtocolFactory(Factory):
    def buildProtocol(self, addr):
        return SimpleProtocol()

def print_help():
    """
    Function to print command line options to stdout
    """
    print """
Usage: music-server.py [args]
    -b | --background 
        Fork process into background and create .pid file with running process.
        
        Default is to run attached to tty.
    
    -d | --media-directory (dir)
        Specify path to find music.  
        
        Default is ./music
        
        This program will not recurse directories.  
        Only files in the directory specified will be added to the play queue.

    -h or --help 
        Print help message / Command Usage

    -l | --listen (IP)
        Specify address to bind to.

        Default is 0.0.0.0 (all interfaces)

    -m | --media-player (program)
        Specify command line media player to use.
        
        Default is /usr/bin/mpg123
        
        Note:  This program requires the media player to accept the music filename
        to be the first argument to the program.  IE:
            /usr/bin/mpg123 my_great_song.mp3
        mpg123 has been tested to work properly.

    -n | --disable-autoplay
        Do not start in auto-play mode.

        Default - startup and begin playing music.

    -p | --port (port)
        Specify port to listen on.
        
        Default is 9999

        Note: This port must be > 1024.

    -v
        Run program in "verbose" mode.  Sets logging level to DEBUG.

    -vv
        Runs program in "verbose" mode, also sets console logging (when not run in -d mode)
        to DEBUG.
"""

def main(m_cmd, m_dir, addr=None, port=None, autoplay=True):
    global mp
    mp = MPlayer(mplayer=m_cmd, music_dir=m_dir)

    if not addr:
        addr = '0.0.0.0'

    if not port:
        port = 9999

    if autoplay:
        mp.play()
    
    reactor.listenTCP(port, SimpleProtocolFactory(), interface=addr)
    reactor.addSystemEventTrigger('before','shutdown',mp.shutdown)
    reactor.run()

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)s - %(funcName)s() - %(levelname)s - %(message)s')
    file_log_handler = RotatingFileHandler("music_server.log", maxBytes='10M', backupCount=10)
    
    file_log_handler.setFormatter(formatter)
    logger.addHandler(file_log_handler)

    logger.debug('Command Server started.')
    
    # defaults
    media_player_command = "/usr/bin/mpg123"
    media_directory = "./music"
    port = None
    addr = None
    autoplay = True

    
    # check if the user is asking for help in the command args
    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        sys.exit(0)

    # if the user selected to detach this program, do that first.
    if '-b' in sys.argv or '--background' in sys.argv:
        if os.path.isfile("music_server.pid"):
            logger.error("PID file exists.  Process potentially running or previously abnormally exited.")
            print "PID file exists: music_server.pid.  Process may be running.  Kill process and/or delete pid file before running again."
            sys.exit(1)
        createDaemon() # fork to background
        currentPID = os.getpid()  #get new process ID
        pid_file = open("music_server.pid", 'w')
        pid_file.write("%d" %currentPID)
        logger.info('process running in background.  PID is %d' %currentPID)
        pid_file.close()
        _is_daemon=True

    # turn on debug logging
    if '-v' in sys.argv or '-vv' in sys.argv:
        logger.info("verbose option detected.  Setting logging level to DEBUG")
        logger.setLevel(logging.DEBUG)

    # disable autoplay
    if '-n' in sys.argv or '--disable-autoplay' in sys.argv:
        autoplay = False

    # check to see if the user specified a media player config in the command args
    if '-m' in sys.argv or '--media-player' in sys.argv:
        media_player_command = None
        # loop througn argv to find path (index +1)
        for i in range(0, len(sys.argv)):
            if sys.argv[i] == '-m' or sys.argv[i] == '--media-player':
                #check to make sure we don't array index out of bounds
                if i+1 > len(sys.argv)-1:
                    print "ERROR: -m or --media-player option specified but missing argument. See usage below for proper syntax.\n"
                    print_help()
                    logger.critical('-m or --media-player option passed, but missing argument. argv: %s' %str(sys.argv))
                    sys.exit(1)
                elif not os.path.isfile(sys.argv[i+1]):
                    logger.critical('-m or --media-player option passed but next argument: %s is not a regular file.' %sys.argv[i+1])
                    print 'ERROR: -m or --media-player option passed but next argument: %s is not a regular file.  See usage below for proper syntax.\n' %sys.argv[i+1]
                    print_help()
                    sys.exit(1)
                else:
                    logger.info('setting media_player_command=%s' %sys.argv[i+1])
                    media_player_command = sys.argv[i+1]
                    break
        if not media_player_command:
            logger.critical('-m or --media-player option selected on command line, but value not specified.  sys.argv: %s' %str(sys.argv))

    # check to see if the user specified a media directory config in the command args
    if '-d' in sys.argv or '--media-directory' in sys.argv:
        media_directory = None
        # loop througn argv to find path (index +1)
        for i in range(0, len(sys.argv)):
            if sys.argv[i] == '-d' or sys.argv[i] == '--media-directory':
                #check to make sure we don't array index out of bounds
                if i+1 > len(sys.argv)-1:
                    logger.critical('-d or --media-directory option passed, but missing argument. argv: %s' %str(sys.argv))
                    print 'ERROR: -d or --media-directory option passed, but missing argument.  See usage below for proper syntax.\n'
                    print_help()
                    sys.exit(1)
                elif not os.path.isdir(sys.argv[i+1]):
                    logger.critical('-d or --media-directory option passed but next argument: %s is not a directory.' %sys.argv[i+1])
                    print 'ERROR: -d or --media-directory option passed but next argument: %s is not a directory.  See usage below for proper syntax.\n' %sys.argv[i+1]
                    print_help()
                    sys.exit(1)
                else:
                    logger.info('setting media_directory=%s' %sys.argv[i+1])
                    media_directory = sys.argv[i+1]
                    break
        if not media_directory:
            logger.critical('-p or --media-directory option selected on command line, but value not specified.  sys.argv: %s' %str(sys.argv))

    # check to see if -p or --port is specified
    if '-p' in sys.argv or '--port' in sys.argv:
        # loop througn argv to find path (index +1)
        for i in range(0, len(sys.argv)):
            if sys.argv[i] == '-p' or sys.argv[i] == '--port':
                #check to make sure we don't array index out of bounds
                if i+1 > len(sys.argv)-1:
                    logger.critical('-p or --port option passed, but missing argument. argv: %s' %str(sys.argv))
                    print 'ERROR: -p or --port option passed, but missing argument.  See usage below for proper syntax.\n'
                    print_help()
                    sys.exit(1)

                try:
                    port = int(sys.argv[i+1])
                except Exception, e:
                    logger.critical("Could not convert port argument to integer.  argv: %s" %str(sys.argv))
                    sys.exit(1)

                if port <= 1024:
                    logger.critical('-p or --port option passed but next argument: %s is not an integer > 1024.' %sys.argv[i+1])
                    print 'ERROR: -p or --port option passed but next argument: %s is not an integer > 1024.  See usage below for proper syntax.\n' %sys.argv[i+1]
                    print_help()
                    sys.exit(1)
                else:
                    logger.info('setting port=%d' %port)
                    break

        if not port:
            logger.critical('-p or --port option selected on command line, but value not specified.  sys.argv: %s' %str(sys.argv))

    # check to see if -l or --listen is specified
    if '-l' in sys.argv or '--listen' in sys.argv:
        # loop througn argv to find path (index +1)
        for i in range(0, len(sys.argv)):
            if sys.argv[i] == '-l' or sys.argv[i] == '--listen':
                #check to make sure we don't array index out of bounds
                if i+1 > len(sys.argv)-1:
                    logger.critical('-l or --listen  option passed, but missing argument. argv: %s' %str(sys.argv))
                    print 'ERROR: -l or --listen  option passed, but missing argument.  See usage below for proper syntax.\n'
                    print_help()
                    sys.exit(1)
                    
                try:
                    a = socket.inet_aton(sys.argv[i+1])
                except Exception, e:
                    logger.critical("argument: %s does not appear to be a valid IPv4 address.  argv: %s, exception: %s" %(sys.argv[i+1], sys.argv, e.message))
                    print 'ERROR: %s does not appear to be a valid IPv4 address.  See usage below for proper syntax.\n' %sys.argv[i+1]
                    sys.exit(1)

                addr = sys.argv[i+1]
                logger.info('setting listen address=%s' %addr)
                break
        if not addr:
            logger.critical('-l or --listen  option selected on command line, but value not specified.  sys.argv: %s' %str(sys.argv))
            print 'ERROR: -l or --listen  option passed, but missing argument.  See usage below for proper syntax.\n'

    #start program  
    if not _is_daemon:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        if '-vv' in sys.argv:
            print "Console logging enabled, log level set to DEBUG"
            console_handler.setLevel(logging.DEBUG)
        else:
            print "Console logging enabled."
        logger.addHandler(console_handler)        
        print "Starting Music Server attached to vty.\nPress Ctrl-C to stop server and exit."  
    else:
        print "Program running in background. Check music_server.pid for running processID. Logging to ./music_server.log"

    main(media_player_command, media_directory, addr=addr, port=port, autoplay=autoplay)