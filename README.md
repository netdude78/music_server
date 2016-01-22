# music_server

A simple jukebox with network control.

## Background
This project was created to fill the need for an autonomous jukebox that would run on a Raspberry Pi and could be
simply remote controllable over an IP network.  In the creator's environment, that Pi would be installed in a cabinent
with sound equipment and would feed an Aux input on his sound board.  During equipment changes at a gig, a midi command
would unmute the auxillary channel and mute all other inputs.  

Remote control could easily be achieved using Pythonista on an iPhone, iPod touch or iPad and optionally Launch Center Pro
to make launching commands a two-click operation.  See the extras/ directory for Pythonista source and Launch Center Pro
actions.

## Features

* Continually randomly plays tracks from a specified directory.
* Listens on network socket to allow control from a remote machine
* Available network commands:
** Play
** Stop
** Pause
** Resume (un-pause)
** Next (skip to next randomly selected track)
** Restart Song (replay current song from the beginning)
** Previous Song (play previous song)
* Auto-play when program starts for unattended use

## Requirements

You must have installed a command-line media player compatible with the audio format you wish to play.  This
program has been tested with mpg123.  Others may work without program modification, but some may require tweaks.
Any program that allows you to play a file through the CLI with the filename as the first and only command argument
should work just fine.  If you need to make changes, look for the subprocess.Popen command at the end of MPlayer.play_loop

The network socket functionality is provided through the twisted API.  You can download that API using pip.  Follow instructions
on the twisted website: https://pypi.python.org/pypi/Twisted or: https://twistedmatrix.com/

## Usage

Start up music_server through the cli:
./music_server.py

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

## Network Client

Any network client may be used to control this software.  The program is simply listening for 
any of the following case insensitive commands:

	Available Commands:
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
	    Returns available commands.

Testing can be accomplished with any simple TCP connection.  Netcat / telnet can be used from
any machine.  A simple Python socket program could also be used, or executed in the interactive shell.

	Test:
	To test operation with netcat:
	
	nc localhost 9999
	play
	Now Playing
	stop
	Stopping.
	play
	Now Playing
	dmac:music_server dstoll$ nc localhost 9999
	play
	Now Playing
	next
	Fast Forwarding to Next Song
	pause
	Paused Song
	resume
	Resumed Playing Song
	stop
	Stopping.

A sample pythonista (http://omz-software.com/pythonista/) control app is included in the extras/ directory.

## Contribution

Anyone who would like to contribute to the project is more than welcome.
Basically there's just a few steps to getting started:

1. Fork this repo
2. Make your changes and write a test for them
3. Add yourself to the AUTHORS file and submit a pull request!

## Copyright and License

music_server is Copyright (c) 2016 Dave Stoll and licensed under the MIT license.
See the LICENSE file for full details.