#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division

import os
import sys
import time
import atexit
import psutil

from pwd import getpwnam
from grp import getgrnam
from signal import SIGTERM, SIGKILL


class Daemon(object):
    """Subclass this Daemon class and override the run() method"""

    def __init__(self,
                 pid_file=None,
                 stdin='/dev/null',
                 stdout='/dev/null',
                 stderr='/dev/null'):
        if len(sys.argv) == 1:
            return self.usage()
        self.param1 = sys.argv.pop(1)

        self.stdin = os.path.abspath(stdin)
        self.stdout = os.path.abspath(stdout)
        self.stderr = os.path.abspath(stderr)
        self.config = {}
        self.load_configuration()
        self.user = self.config.get('user')
        self.group = self.config.get('group')
        if not pid_file:
            raise Exception("You did not provide a pid file")
        self.pid_file = os.path.abspath(pid_file)

    def set_gid(self):
        """Change the group of the running process"""
        if self.group:
            gid = getgrnam(self.group).gr_gid
            try:
                os.setgid(gid)
            except Exception:
                message = ("Unable to switch ownership to {0}:{1}. " +
                           "Did you start the daemon as root?")
                print(message.format(self.user, self.group))
                sys.exit(1)

    def set_uid(self):
        """Change the user of the running process"""
        if self.user:
            uid = getpwnam(self.user).pw_uid
            try:
                os.setuid(uid)
            except Exception:
                message = ('Unable to switch ownership to {0}:{1}. ' +
                           'Did you start the daemon as root?')
                print(message.format(self.user, self.group))
                sys.exit(1)

    @staticmethod
    def usage():
        sys.stdout.write("Usage: %s {start|stop|restart|status}\n" % sys.argv[0])
        return 2

    def action(self):
        if self.param1 == 'start':
            return self.start()
        elif self.param1 == 'stop':
            return self.stop()
        elif self.param1 == 'restart':
            return self.restart()
        elif self.param1 == 'status':
            return self.status()
        else:
            return self.usage()

    def load_configuration(self):
        """Set up self.config if needed"""
        pass

    def daemonize(self):
        """
        Do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write('fork #1 failed: %d (%s)\n' %
                             (e.errno, e.strerror))
            sys.exit(1)
        os.chdir('/')
        os.setsid()
        os.umask(0)
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write('fork #2 failed: %d (%s)\n' %
                             (e.errno, e.strerror))
            sys.exit(1)
        # to properly close the fd's, we need to use sys and os:
        # http://chromano.me/2011/05/23/starting-python-daemons-via-ssh.html
        sys.stdin.close()
        os.close(0)
        sys.stdout.close()
        os.close(1)
        sys.stderr.close()
        os.close(2)
        atexit.register(self.delpid)
        pid = os.getpid()
        file(self.pid_file, 'w+').write("%s\n" % pid)

    def delpid(self):
        """Remove the pid_file from filesystem"""
        os.remove(self.pid_file)

    def _already_running(self):
        try:
            self.pid = int(open(self.pid_file).read().strip())
        except IOError:
            self.pid = None
            return False
        if psutil.pid_exists(self.pid):
            return True
        return False

    def start(self):
        """Start the daemon"""
        if self._already_running():
            message = 'pid file %s already exists. Daemon already running?\n'
            sys.stderr.write(message % self.pid_file)
            return 0
        self.set_gid()
        self.set_uid()
        # Create pid file with new user/group. This ensures we will be able
        # to delete the file when shutting down.
        self.daemonize()
        try:
            self.run()
        except Exception:
            self.logger.exception('Exception while running the daemon:')
            return 1
        return 0

    def reliable_kill(self):
        # TODO: make the timeout configurable
        try:
            for count in range(100):
                os.kill(self.pid, SIGTERM)
                time.sleep(0.1)
        except OSError as err:
            err = str(err)
            if 'No such process' in err:
                if os.path.exists(self.pid_file):
                    self.delpid()
                return 0
            else:
                print(err)
                return 1

        # No 'no such process' exception -> process is still running.
        sys.stderr.write('Had to kill the process with SIGKILL')
        os.kill(self.pid, SIGKILL)
        return 0

    def stop(self):
        """Stop the daemon"""
        if self._already_running():
            return self.reliable_kill()
        else:
            # FIXME: misleading error message
            message = 'Daemon not running, nothing to do.\n'
            sys.stderr.write(message)
            return 0

    def restart(self):
        """Restart the daemon"""
        self.stop()
        self.start()

    def run(self):
        """Placeholder for later overwriting"""
        raise NotImplementedError

    def status(self):
        """Determine the status of the daemon"""
        my_name = os.path.basename(sys.argv[0])
        if self._already_running():
            message = "{0} (pid  {1}) is running...\n".format(my_name, self.pid)
            sys.stdout.write(message)
            return 0
        sys.stdout.write("{0} is stopped\n".format(my_name))
        return 3
