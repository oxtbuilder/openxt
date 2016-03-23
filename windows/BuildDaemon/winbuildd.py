#!/usr/bin/env python

# Copyright (c) 2016 Assured Information Security, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


# Some idiot interpreters don't always set up __file__
# (I'm looking at you PythonWin)
try:
    __file__
except NameError:
    import sys
    __file__ = sys.argv[0]
    del sys

import SimpleXMLRPCServer
import os
import subprocess as subprocess_
import socket
import time
import sys
import getopt
import shutil
import ConfigParser
import tempfile

subprocess = subprocess_
linesep = '\n'
SCRIPTDIR = os.path.dirname(__file__)

def write_(*args):
  """Place-holder for print"""
  if args:
    print ' '.join(map(str, args))
  else:
    print
write = write_

def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    print "Retrying " + path + " after chmod"
    mode = os.stat(path).st_mode
    if stat.S_ISDIR(mode):
        os.system('ls -laR ' + path)
    os.chmod(path, stat.S_IWRITE)
    func(path)

class PopenWrapper(object):
  """Like popen but actually writes stuff out to a log file too."""
  class WaitWrapper(object):
    """Wraps the wait object."""
    def __init__(self, waiter, log, cmdline):
        super(PopenWrapper.WaitWrapper, self).__init__()
        self.waiter = waiter
        self.log = log
        self.cmdline = cmdline
    def __getattr__(self, name):
        return getattr(self.waiter, name)
    def wait(self, *args, **kwargs):
        cmdline = self.cmdline
        self.log.write(linesep + 'EXECUTING: ' + cmdline)
        start = time.time()
        result = self.waiter.wait(*args, **kwargs)
        end = time.time()
        self.log.write(('FINISHED EXECUTING (%.02f' % (end - start)) + '): ' + cmdline + linesep)
        return result

  def __init__(self, logfile):
    """Initialise this PopenWrapper instance.
        Parameters:
          logfile  - File to write any output to.
    """
    super(PopenWrapper, self).__init__()
    self.logfile = logfile

  def Popen(self, *unargs, **kwargs):
    """Wrapper around the real popen. Dump the command line...
        Parameters:
          cmdline  - Command line being executed.
    """
    cmdline = None
    if 'args' in kwargs:
        cmdline = kwargs['args']
    else:
      cmdline = unargs[0]
    return PopenWrapper.WaitWrapper(subprocess_.Popen(*unargs, **kwargs), self, cmdline)

  def write(self, *args):
    """Placeholder for print"""
    write_(*args) #Print in build server.
    if args:
        self.logfile.write(' '.join(map(str, args)) + linesep) #Print to log file.
        self.logfile.flush()
    else:
        self.logfile.write(linesep)
        self.logfile.flush()

class RPCInterface(object):
    def make(self,build='',branch='master',certname='',developer='false',rsyncdest='',giturl='',config='sample-config.xml'):
        """make(build,branch,certname,developer,rsyncdest,giturl,config)
           Ex: make("123456","master","developer","false","builds@192.168.0.10:/home/builds/win/","git://github.com/OpenXT","sample-config.xml")
           Call powershell scripts to do the real work
        """

        result = 'SUCCESS'

        # Create log directory/file
        try:
            os.chdir(BUILDDIR)

            if os.path.exists('output.log'):
                os.remove('output.log')
            log = open('output.log', "w")
            print "Log file created @ " + socket.gethostname() + " file: " + os.path.join(BUILDDIR, "output.log")
            subprocess = PopenWrapper(log)
            write = subprocess.write

            write("Start build, RPC input:")
            write('make(build='+repr(build)+',branch='+repr(branch)+\
                  ',certname='+repr(certname)+'developer='+repr(developer)+\
                  'rsyncdest='+repr(rsyncdest)+'giturl='+repr(giturl)+'config='+repr(config)+')')
            write('Running in dir: ' + os.getcwd())

            # Nuke existing build(s)
            if not os.path.exists('garbage'):
                os.mkdir('garbage')
            if os.path.exists('openxt'):
                grave = tempfile.mkdtemp(dir='garbage')
                os.rename('openxt', os.path.join(grave, 'openxt'))
            try:
                shutil.rmtree('garbage', onerror=onerror)
            except:
                pass

            # Clone the main OpenXT repo and checkout branch
            subprocess.Popen('git clone -b ' + branch + ' ' + giturl + '/openxt.git', shell = True, stdout = log, stderr = log, universal_newlines=True).wait()
            write("Completed cloning " + giturl + "/openxt.git")
            os.chdir(os.path.join("openxt", "windows"))

            command = 'sed -i "s/Put Your Company Name Here/OpenXT/g" config\\sample-config.xml'
            subprocess.Popen(command, shell = True, stdout = log, stderr = log, universal_newlines=True).wait()

            write("Building Windows bits...")
            command = 'powershell .\winbuild-prepare.ps1 config=' + config + ' build=' + build + ' branch=' + branch + ' certname=' + certname + ' developer=' + developer
            subprocess.Popen(command, shell = True, stdout = log, stderr = log, universal_newlines=True).wait()
            command = 'powershell .\winbuild-all.ps1'
            subprocess.Popen(command, shell = True, stdout = log, stderr = log, universal_newlines=True).wait()

            # rsync the output unless something went wrong
            os.chdir(os.path.join(BUILDDIR, "openxt", "windows", "output"))
            if os.path.exists('xctools-iso.zip') and os.path.exists('xc-wintools.iso'):
                # Save build ID
                build_id_file = open('BUILD_ID', 'w')
                build_id_file.write(str(build))
                build_id_file.write('\n')
                build_id_file.close()
                # Rsync the build output to the builder
                command = 'rsync --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r -a BUILD_ID sdk.zip win-tools.zip xctools-iso.zip xc-windows.zip xc-wintools.iso ' + rsyncdest + '\\' + branch
                child_error = subprocess.Popen(command, shell = True, stdout = log, stderr = log, universal_newlines=True).wait()
                if child_error != 0:
                    # Misery
                    write("ERROR: OpenXT Tools failed to rsync!")
                    result = 'FAILURE'
            else:
                # Misery
                write("ERROR: OpenXT Tools failed to build!")
                result = 'FAILURE'
        finally:
            if log is not None:
                log.close()

        return result
 

    def hello(self):
        return "hello back"

def main(argv):

	config = ""
	site = ""
	try:
		opts, args = getopt.getopt(argv, "hc:s:", ["help", "config=", "site="])
		for opt, arg in opts:
			if opt in ("-h", "--help"):
				usage()
				sys.exit()
			elif opt in ("-c", "--config"):
				config = arg
			elif opt in ("-s", "--site"):
				site = arg
	except getopt.GetoptError:
		usage()
		sys.exit(2)

	loadConfig(config,site)
	s = SimpleXMLRPCServer.SimpleXMLRPCServer(('', PORT))
	s.register_introspection_functions()
	s.register_instance(RPCInterface())

	try:
		print """
		 OpenXT Windows Build XMLRPC Server

		 Use Control-C to exit
		 """
		s.serve_forever()
	except KeyboardInterrupt:
		print 'Exiting'

def loadConfig(cfg,site):
	try:
		config = ConfigParser.ConfigParser()
		config.read(cfg)
	except:
		print "Configuration file cannot be read."
		sys.exit()

	if not (config.has_section(site)):
		print "Invalid site specified. Available sites are:"
		print config.sections()
		sys.exit()
	else:
		try:
			global PORT, BUILDDIR
			PORT = config.getint(site,'port')
			BUILDDIR = config.get(site,'builddir')
		except:
			print "Exception getting configuration option. Corrupt .cfg file? Missing option?"
			sys.exit()

def usage():
	print """
	 Usage:
	 > python builddaemon.py -c "config file" -s "site"
	"""

if __name__ == '__main__':
	main(sys.argv[1:])
