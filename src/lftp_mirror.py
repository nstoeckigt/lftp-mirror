#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""
   lftp_mirror.py: This script mirrors a remote FTP server dir with a local dir
"""

#==============================================================================
# This Script mirrors a remote FTP server dir with a local dir (or vice versa)
# and stores a daily compressed copy of local dir
#
# The real job is done by the marvelous lftp program by Alexander V. Lukyanov
# and it's necessary to run this script
# http://lftp.yar.ru/
#
# This script can be executed in three ways:
#
#   a) shell: command line interactive
#   b) cron: as a programmed task
#   c) cfg: importing arguments from a config file
#
# In the first way, you need to give the required arguments (site, remote FTP
# directory and local directory) to the script in the command line. Optional
# arguments, obviously, are optional.
#
# As a programmed task, don't need supply the arguments in the command line.
# It takes the scripts parameters (previously defined) as default command line
# arguments. These defines the required and several optional arguments (which
# can left blank): user, password, port and options (the other). It's useful
# for set up a cron programmed task with a single command line argument, 'cron'
#
# Finally, the last way is ideal for running multiple mirror operations. With a
# one configuration file can set up various mirror actions with different sites
# or directories, and do all of them in a single script execution. Arguments
# are imported from this config file, with a section for each mirror operation,
# and there are not limits for sections.
#
# For further information visits the lftp_mirror's website:
#     http://joedicastro.com
#
#==============================================================================

#==============================================================================
#    Copyright 2010 joe di castro <joe@joedicastro.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#==============================================================================

#==============================================================================
#    Copyleft 2023 nico stöckigt <info@nstoeckigt.de>
#
#    The previous rights and legal terms still aply!
#
#    This software was rewritten for python 3.x by the author above.
#
#    Because ftp is quite dead but still has it niches this program has been
#    adopted to be used with own~/nextCloud and an ftp source.
#==============================================================================

# original:
#__author__ = "joe di castro - joe@joedicastro.com"
#__license__ = "GNU General Public License version 3"
#__date__ = "16/9/2012"
#__version__ = "0.15"

__author__ = "nico stöckigt - info@nstoeckigt.de"
__license__ = "GNU General Public License version 3"
__date__ = "06/06/2024"
__version__ = "0.16.2"

import sys
import os
from typing import Union, Iterable

try:
    import glob
    import base64
    import time
    import re
    import tarfile
    import platform
    import socket
    import smtplib
    import getpass
    import subprocess
    from argparse import ArgumentParser, SUPPRESS
    from configparser import ConfigParser
    from subprocess import Popen, PIPE, STDOUT
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.utils import COMMASPACE, formatdate
    from loguru import logger
    import snoop
except ImportError:
    # Checks the installation of the necessary python modules
    print((os.linesep * 2).join(["An error found importing one module:",
          str(sys.exc_info()[1]), "You need to install it", "Exit..."]))
    sys.exit(-2)


# Notify it's not essential and libnotify it's not always installed (in Ubuntu
# & Debian it's optional) but it's very useful to show operation's progress
TRACE = False
NOT_NOTIFY = True
NOTIFY_ERRORS = []
if os.getenv('DISPLAY', ''):
    try:
        import pynotify
        import gtk
        NOT_NOTIFY = False
    except ImportError:
        NOT_NOTIFY = True


class Logger():
    """

    Create a log object to log script messages.

    These messages can be sended via email or writed in a log file

    """

    def __init__(self):
        """Create the object Logger itself and set two variables.

        This variable is about this python file:

        __script_name = The script name
        filename = the log file's name

        """
        self.__log = ''
        self.__script_name = os.path.basename(__file__).split('.')[0]
        self.filename = f"{self.__script_name}.log"

    def __len__(self) -> int:
        return len(self.__log)

    def __format__(self, format_spec: str) -> str:
        """Format the logged content based on format_spec.

        Args:
            format_spec (str): The format specifier ('block' or 'list').

        Returns:
            str: Formatted string representation of the logged content.

        Raises:
            ValueError: If an unsupported format specifier is provided.
        """
        if format_spec == 'block':
            return f"{self.__log}{os.linesep}"
        elif format_spec == 'list':
            return f"{self.__log}{os.linesep}"
        else:
            raise ValueError("Unsupported format specifier")

    def block(self, title: str, content: Union[str, Iterable[str]]) -> None:
        """Add a block of text lines with a title and decorations.

        Args:
            title (str): The title for the block.
            content (str or iterable of str): The lines of content for the block.
        """
        if content:
            self.__log += f"{title.upper()} {'=' * (80 - len(title))}{os.linesep}"
            if isinstance(content, str):
                self.__log += f"{content}{os.linesep}"
            else:
                self.__log += os.linesep.join(content) + os.linesep
            self.__log += '=' * 80 + os.linesep

    def list(self, title: str, content: Union[str, Iterable[str]]) -> None:
        """Add a list of text lines with a title and decorations.

        Args:
            title (str): The title for the list.
            content (str or iterable of str): The lines of content for the list.
        """
        if content:
            self.__log += f"{title.upper()} {'_' * (80 - len(title))}{os.linesep}"
            if isinstance(content, str):
                self.__log += f"{content}{os.linesep}"
            elif isinstance(content, list):
                decoded_content = [line.decode('utf-8', errors='replace') for line in content]
                self.__log += os.linesep.join(decoded_content) + os.linesep
            else:
                self.__log += content.decode('utf-8', errors='replace') + os.linesep

    def free(self, content: str) -> None:
        """Add free-form text to the log.

        Args:
            content (str): The free-form text to add.
        """
        if isinstance(content, str):
            self.__log += content + os.linesep * 2

    def time(self, title):
        """A self.block() formated line with current time and date.

        (str) title -- Title for self.block()

        Looks like this, the data and time are right-justified:

        TITLE ==================================================
                                       Friday 09/10/10, 20:01:39
        ========================================================

        """
        self.block(title, f"{time.strftime('%A %x, %X'):>80}")

    def header(self, url, msg):
        """A self.block() formated header for the log info.

        (str) url -- The url of the script
        (str) msg -- Message to show into the header to Provide any useful info

        It looks like this:

        SCRIPT =================================================
        script name and version
        url

        msg
        ========================================================

        """
        script = f"{self.__script_name} (v{ __version__})"
        self.block('Script', [script, url, '', msg])

    def get(self):
        """Get the log content."""
        return self.__log

    def send(self, subject, send_from='', dest_to='', mail_server='localhost',
             server_user='', server_pass=''):
        """Send a email with the log.

        Arguments:
            (str) send_from -- a sender's email address (default '')
            (str or list) dest_to -- a list of receivers' email addresses ('')
            (str) subject -- the mail's subject
            (str) mail_server -- the smtp server (default 'localhost')
            (str) server_user -- the smtp server user (default '')
            (str) server_pass --the smtp server password (default '')

        If 'send_from' or 'dest_to' are empty or None, then script user's
        mailbox is assumed instead. Useful for loggin scripts

        """
        local_email = '@'.join([getpass.getuser(), socket.gethostname()])
        if not send_from:
            send_from = local_email
        if not dest_to:
            dest_to = [local_email]

        dest_to_addrs = COMMASPACE.join(dest_to)  # receivers mails
        message = MIMEMultipart()
        message['Subject'] = f"{subject} - {time.strftime('%A %x, %X')}"
        message['From'] = send_from
        message['To'] = dest_to_addrs
        message['Date'] = formatdate(localtime=True)
        message.preamble = "You'll not see this in a MIME-aware mail reader.\n"
        message.attach(MIMEText(self.__log))

        # initialize the mail server
        server = smtplib.SMTP()
        # Connect to mail server
        try:
            server.connect(mail_server)
        except socket.gaierror:
            self.list('mail error', 'Wrong server, are you sure is correct?')
        except socket.error:
            self.list('mail error', 'Server unavailable or connection refused')
        # Login in mail server
        if mail_server != 'localhost':
            try:
                server.login(server_user, server_pass)
            except smtplib.SMTPAuthenticationError:
                self.list('mail error', 'Authentication error')
            except smtplib.SMTPException:
                self.list('mail error', 'No suitable authentication method')
        # Send mail
        try:
            server.sendmail(send_from, dest_to_addrs, message.as_string())
        except smtplib.SMTPRecipientsRefused:
            self.list('mail error', 'All recipients were refused.'
                      'Nobody got the mail.')
        except smtplib.SMTPSenderRefused:
            self.list('mail error', 'The server didn’t accept the from_addr')
        except smtplib.SMTPDataError:
            self.list('mail error', 'An unexpected error code, Data refused')
        # Disconnect from server
        server.quit()

    def write(self, append=False):
        """Write the log to a file.

        The name of the file will be like this:

        script.log

        where 'script' is the name of the script file without extension (.py)

        (boolean) append -- If true appends log to file, else writes a new one

        """
        mode = 'ab' if append else 'wb'
        with open(self.filename, mode) as log_file:
            log_file.write(self.__log.encode('utf-8'))


@logger.catch()
def arguments():
    """Defines the command line arguments for the script."""
    main_desc = ("Mirror a remote FTP directory into a local directory or vice"
                 " versa through the lftp program")
    subs_desc = "Select a running mode from the following:"
    epilog = (f"For detailed help for each mode, select a mode followed by help option,"
              f" e.g.:{os.linesep}{os.linesep}%(prog)s shell -h")
    cron_use = "%(prog)s [-h]"
    shell_use = (f"%(prog)s site remote local [options]{os.linesep}{os.linesep}By default "
                  "downloads the changes from remote FTP directory to local "
                 f"directory.{os.linesep}To upload changes from local to remote FTP, use"
                  " the 'r, --reverse' option")
    file_use = (f"%(prog)s config_file [-h]{os.linesep}{os.linesep}The structure of the "
                f"config file (a simple text file) is as follows:{os.linesep}"
                f"{os.linesep}[section]{os.linesep}site = {{ftp server URL or IP}}"
                f"{os.linesep}port = (ftp server port){os.linesep}remote = "
                f"{{remote directory}}{os.linesep}local = {{local directory}}"
                f"{os.linesep}user = (ftp server username){os.linesep}password = "
                f"(user password encoded in base64){os.linesep}options = (other options)"
                f"{os.linesep}{os.linesep}Section is a name that defines the mirror operation. "
                 "Usually is the ftp server's name or directory' name. Useful for distinguish one "
                 "mirror operation from others. Write one section for each "
                f"mirror action with no limits in the number of sections.{os.linesep}{os.linesep}"
                 "Values between curly brackets '{{}}' are required arguments "
                 "and values between brackets '()' are optional arguments. If "
                 "don't want optional arguments, left them blank. In case you do"
                 " not specify a username and password, you must add the '-a' "
                 "option which specifies that the connection is made with the "
                f"anonymous user.{os.linesep}{os.linesep}The order of arguments doesn't matter, "
                f"but all are needed.{os.linesep}{os.linesep}")

    parser = ArgumentParser(description=main_desc, epilog=epilog)
    subparsers = parser.add_subparsers(title="running modes",
                                       description=subs_desc)

    cron = subparsers.add_parser("cron", help="ideal to run as a scheduled "
                                 "task. Takes arguments from parameters "
                                 "defined within the script", usage=cron_use)
    cron.add_argument("cron", action="store_true", help=SUPPRESS,
                      default=SUPPRESS)
    cron.add_argument("cfg", action="store_false", help=SUPPRESS,
                      default=SUPPRESS)

    cfg = subparsers.add_parser("cfg", help="ideal for mirror multiple sites/"
                                "directories. Imports the arguments from a "
                                "config file", usage=file_use)
    cfg.add_argument("cron", action="store_false", help=SUPPRESS,
                     default=SUPPRESS)
    cfg.add_argument("cfg", action="store_true", help=SUPPRESS,
                     default=SUPPRESS)
    cfg.add_argument("config_file", help="config file to import arguments")

    shell = subparsers.add_parser("shell", help="usual mode, takes arguments "
                                  "from the command line ", usage=shell_use)
    shell.add_argument("cron", action="store_false", help=SUPPRESS,
                       default=SUPPRESS)
    shell.add_argument("cfg", action="store_false", help=SUPPRESS,
                       default=SUPPRESS)
    shell.add_argument("site", help="the ftp server (URL or IP)")
    shell.add_argument("remote", help="the remote directory")
    shell.add_argument("local", help="the local directory")

    auth = shell.add_mutually_exclusive_group(required=True)
    auth.add_argument("-l", "--login", dest="login", nargs=2,
                      help="the ftp account's username and password",
                      metavar=("user", "password"))
    auth.add_argument("-a", "--anon", action="store_true", dest="anonymous",
                      help="set user as anonymous", default=False)

    shell.add_argument("-p", "--port", dest="port", default="",
                       help="the ftp server port", metavar="port")
    shell.add_argument("-s", "--secure", action="store_const", const="s",
                       dest="secure",
                       help="use the sftp protocol instead of ftp")
    shell.add_argument("--ssl-verify", action="store_const", const="yes",
                       dest="ssl_verify", default="no",
                       help="verify ssl certificates")
    shell.add_argument("-e", "--erase", action="store_const", const="e",
                       dest="erase", default="",
                       help="delete files not present at target site")
    shell.add_argument("-n", "--newer", action="store_const", const="n",
                       dest="newer", default="",
                       help="download only newer files")
    shell.add_argument("-P", "--parallel", dest="parallel", default="",
                       nargs="?", metavar="N", const=2,
                       help="download N files in parallel. N=2 if not provide "
                       "any value")
    shell.add_argument("-r", "--reverse", action="store_const", const="R",
                       dest="reverse", default="",
                       help="reverse, upload files from local to remote")
    shell.add_argument("--delete-first", action="store_const",
                       const=" --delete-first", dest="del_first", default="",
                       help="delete old files before transferring new ones")
    shell.add_argument("--depth-first", action="store_const",
                       const=" --depth-first", dest="depth_first", default="",
                       help="descend into subdirectories, before transfer "
                       "files")
    shell.add_argument("--no-empty-dirs", action="store_const",
                       const=" --no-empty-dirs", dest="no_empty_dir",
                       default="",
                       help="don't create empty dirs (needs --depth-first)")
    shell.add_argument("--no-recursion", action="store_const",
                       const=" --no-recursion", dest="no_recursion",
                       default="",
                       help="don't go to subdirectories")
    shell.add_argument("--dry-run", action="store_const",
                       const=" --dry-run", dest="dry_run", default="",
                       help="simulation, don't execute anything. Writes to "
                       "log")
    shell.add_argument("--use-cache", action="store_const",
                       const=" --use-cache", dest="use_cache", default="",
                       help="use cached directory listings")
    shell.add_argument("--update-cloud", action="store_true",
                       default="false", help="re-index new files in cloud")
    shell.add_argument("--del-source", action="store_const",
                       const=" --Remove-source-files",
                       dest="del_source", default="",
                       help="remove files (no dirs) after transfer (Caution!)")
    shell.add_argument("--only-missing", action="store_const",
                       const=" --only-missing", dest="missing", default="",
                       help="download only missing files")
    shell.add_argument("--only-existing", action="store_const",
                       const=" --only-existing", dest="existing", default="",
                       help="download only files already existing at target")
    shell.add_argument("--loop", action="store_const",
                       const=" --loop", dest="loop", default="",
                       help="loop until no changes found")
    shell.add_argument("--ignore-size", action="store_const",
                       const=" --ignore-size", dest="size", default="",
                       help="ignore size when deciding whether to download")
    shell.add_argument("--ignore-time", action="store_const",
                       const=" --ignore-time", dest="time", default="",
                       help="ignore time when deciding whether to download")
    shell.add_argument("--no-perms", action="store_const",
                       const=" --no-perms", dest="no_perms", default="",
                       help="don't set file permissions")
    shell.add_argument("--no-umask", action="store_const",
                       const=" --no-umask", dest="no_umask", default="",
                       help="don't apply umask to file modes")
    shell.add_argument("--no-symlinks", action="store_const",
                       const=" --no-symlinks", dest="no_symlinks", default="",
                       help="don't create symbolic links")
    shell.add_argument("--allow-suid", action="store_const",
                       const=" --allow-suid", dest="suid", default="",
                       help="set suid/sgid bits according to remote site")
    shell.add_argument("--allow-chown", action="store_const",
                       const=" --allow-chown",
                       dest="chown", default="",
                       help="try to set owner and group on files")
    shell.add_argument("--dereference", action="store_const",
                       const=" --dereference", dest="dereference", default="",
                       help="download symbolic links as files")
    shell.add_argument("--exclude-glob", action="append", dest="exc_glob",
                       default=[], metavar="GP",
                       help="exclude matching files. GP is a glob pattern, "
                       "e.g. '*.zip'")
    shell.add_argument("--include-glob", action="append", dest="inc_glob",
                       default=[], metavar="GP",
                       help="include matching files. GP is a glob pattern, "
                       "e.g. '*.zip'")

    shell.add_argument("-q", "--quiet", action="store_true", dest="quiet",
                       help="the detailed shell process is no "
                       "displayed, but is added to the log", default=False)
    shell.add_argument("--compress", action="store_true",
                       dest="compress", default=False,
                       help="create daily archive files")
    shell.add_argument("--to-addrs", dest="to_addrs", nargs='+',
                       metavar="<email address>",
                       help="a list of receiver(s)' email address(es)")
    shell.add_argument("--smtp-config", metavar="<config file>",
                       help="config file to import arguments")
    shell.add_argument("--smtp-server", dest="smtp_server", metavar="server",
                       help="set a smtp server")
    shell.add_argument("--smtp-user", dest="smtp_user", metavar="user",
                       help="the smtp server username")
    shell.add_argument("--smtp-pass", dest="smtp_pass", metavar="password",
                       help="the smtp server password")
    shell.add_argument("--smtp-from", dest="from_addr", metavar="<email address>",
                       help="sender's email address")

    parser.add_argument("--trace", action="store_true", dest="trace",
                        help=SUPPRESS, default=False)  # allow function snooping
    parser.add_argument("-v", "--version", action="version",
                        version="%(prog)s {__version__}",
                        help="show program's version number and exit")
    return parser


@logger.catch()
def trace(func):
    """
    conditional snoop
    """
    def wrapper(*args, **kwargs):
        if TRACE:
            return snoop(func)(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


@logger.catch()
def check_execs_posix_win(*progs):
    """Check if the programs are installed.

    Returns two values:

    (dict) windows_paths - a dictionary of executables/paths (keys/values)
    (boolean) is_windows - True it's a Windows OS, False it's a *nix OS

    """
    def not_found(app):
        """ If executable is not installed, exit and report."""
        msg = f"The {app} program is necessary to run this script"
        sys.exit(msg)

    windows_paths = {}
    is_windows = platform.system() == 'Windows'
    # get all the drive unit letters if the OS is Windows
    windows_drives = None
    if is_windows:
        with Popen('fsutil fsinfo drives', stdout=PIPE) as proc:
            windows_drives = re.findall(r'(\w:)', proc.communicate()[0].decode())

    for prog in progs:
        if is_windows:
            # Set all commands to search the executable in all drives
            win_cmds = [fr"dir /B /S {letter}\*{prog}.exe" for
                        letter in windows_drives]
            # Get the first location (usually in C:) of the all founded where
            # the executable exists
            exe_paths_list = []
            for cmd in win_cmds:
                with Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True) as proc:
                    exe_paths_list.append(proc.communicate()[0].decode())
            exe_paths = ''.join(exe_paths_list).split(os.linesep, maxsplit=1)[0]

            # Assign the path to the executable or report not found if empty
            windows_paths[prog] = exe_paths if exe_paths else not_found(prog)
        else:
            try:
                subprocess.run([prog, '--help'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        check=True)
            except (OSError, subprocess.CalledProcessError):
                not_found(prog)
    return windows_paths, is_windows


@logger.catch()
def notify(msg, status):
    """Send notification status messages through libnotify.

    Paramaters:

    (str) msg -- The message to display into notification
    (str) status -- Type of notification status (ok|info|error|warm|ask|sync)

    """
    if NOT_NOTIFY:
        return
    if not pynotify.is_initted():
        pynotify.init('lftp_mirror')
    note = pynotify.Notification("LFTP Mirror", msg)
    helper = gtk.Button()
    icons = {'ok': gtk.STOCK_YES, 'info': gtk.STOCK_DIALOG_INFO,
             'error': gtk.STOCK_DIALOG_ERROR, 'warm': gtk.STOCK_DIALOG_WARNING,
             'ask': gtk.STOCK_DIALOG_QUESTION, 'sync': gtk.STOCK_JUMP_TO}
    icon = helper.render_icon(icons[status], gtk.ICON_SIZE_BUTTON)
    note.set_icon_from_pixbuf(icon)
    try:
        note.show()
    except Exception as e:
        NOTIFY_ERRORS.append(e)


@logger.catch()
def best_unit_size(bytes_size):
    """Get a size in bytes & convert it to the best IEC prefix for readability.

    Return a dictionary with three pair of keys/values:

    's' -- (float) Size of path converted to the best unit for easy read
    'u' -- (str) The prefix (IEC) for s (from bytes(2^0) to YiB(2^80))
    'b' -- (int / long) The original size in bytes

    """
    for exp in range(0, 90, 10):
        bu_size = abs(bytes_size) / pow(2.0, exp)
        if int(bu_size) < 2 ** 10:
            unit = {0: 'bytes', 10: 'KiB', 20: 'MiB', 30: 'GiB', 40: 'TiB',
                    50: 'PiB', 60: 'EiB', 70: 'ZiB', 80: 'YiB'}[exp]
            break
    return {'s': bu_size, 'u': unit, 'b': bytes_size}


@logger.catch()
def get_path_info(the_path):
    """Get size of a directory tree or a file in bytes."""
    path_size = 0
    file_count = 0
    for path, directories, files in os.walk(the_path):
        file_count += len(files)
        for filename in files:
            path_size += os.lstat(os.path.join(path, filename)).st_size
        for directory in directories:
            path_size += os.lstat(os.path.join(path, directory)).st_size
    path_size += os.path.getsize(the_path)
    return (path_size, file_count)


@logger.catch()
@trace
def compress(path):
    """Compress a local directory into a gz file.

    Creates a file for each weekday, and removes the old files if exists"""
    dir2gz = os.path.basename(path)
    old_gzs = glob.glob(f"{dir2gz}*{time.strftime('%a')}.tar.gz")
    gz_name = f"{dir2gz}_{time.strftime('%d%b%Y_%H:%M_%a')}.tar.gz"
    with tarfile.open(gz_name, "w:gz") as gz_file:
        gz_file.add(path, arcname=dir2gz)
        gz_file.close()
    output = os.linesep.join(['Created file:', '', os.path.join(os.getcwd(),
                                                                gz_name)])
    for old_gz in old_gzs:
        os.remove(old_gz)
        output += os.linesep.join([os.linesep, 'Deleted old file:', '',
                                   old_gz])
    return output


@logger.catch()
@trace
def mirror(args, log):
    """Mirror the directories."""

    user = '' if args.anonymous else ' '.join(args.login)
    local, remote = os.path.normpath(args.local), os.path.normpath(args.remote)
    port = f"-p {args.port}" if args.port else ''
    include = ''
    include = " ".join(f" --include-glob {iglob}" for iglob in args.inc_glob)
    exclude = ''
    exclude = " ".join(f" --include-glob {eglob}" for eglob in args.exc_glob)
    parallel = f" --parallel={args.parallel}" if args.parallel else ''

    url = f"https://joedicastro.com{os.linesep}https://cloud.stephanradom.de"
    msg = (f"Connected to {args.site} as {'anonymous' if args.anonymous else args.login[0]}"
           f"{os.linesep}")
    msg += f"Mirror {local if args.reverse else remote} to {remote if args.reverse else local}"
    log.header(url, msg)
    log.time('Start time')
    notify(f"Mirroring with {args.site}...", 'sync')

    if not os.path.exists(local):
        os.mkdir(local)
        log.list('Created new directory', local)
    #os.chdir(os.path.join(os.getcwd(), local))

    # create the script file to import with lftp
    scp_args = ('-vvv' + args.erase + args.newer + args.reverse
                + args.del_first + args.depth_first + args.no_empty_dir +
                args.no_recursion + args.dry_run + args.use_cache +
                args.del_source + args.missing + args.existing + args.loop +
                args.size + args.time + args.no_perms + args.no_umask +
                args.no_symlinks + args.suid + args.chown + args.dereference +
                exclude + include + parallel)

    log.list('lftp mirror arguments', scp_args)
    secure_prefix = "s" if args.secure else ""

    with open('ftpscript', 'w', encoding='utf-8') as script:
        lines = [f"open {secure_prefix}ftp://{args.site} {port}",
                 f"user {user}",
                 f"set ssl:verify-certificate {args.ssl_verify}",
                 f"mirror {scp_args} '{local if args.reverse else remote}'"  # wrap
                 f" '{remote if args.reverse else local}'",
                 'exit']
        if args.secure and not args.ssl_verify == 'yes':
            lines.insert(3, "set sftp:auto-confirm yes")

        script.write(os.linesep.join(lines))

    # mirror
    cmd = ['lftp', '-d', '-f', script.name]
    with Popen(cmd, stdout=PIPE, stderr={True: STDOUT, False: None}[args.quiet]) as sync:
        log.list('lftp output', sync.stdout.readlines())
    # end mirroring

    if NOTIFY_ERRORS:
        log.list('Notification errors', set(NOTIFY_ERRORS))

    # compress the dir and create a .gz file with date
    if not args.reverse and args.compress:
        notify('Compressing folder...', 'info')
        log.list('Rotate compressed copies', compress(local))
    # end compress

    gz_size = sum(get_path_info(gz)[0] for gz in glob.glob(f"{local}*.gz"))
    log_size = get_path_info(log.filename)[0] if os.path.exists(log.filename) else 0
    local_size, local_fcount = get_path_info(local)
    size = best_unit_size(local_size + gz_size + log_size)
    margin = (70 - len(str(local_fcount)))
    log.block('Disk space used', f"{local_fcount} files{size['s']:>{margin}.2f} {size['u']}")
    log.time('End Time')
    log.free(os.linesep * 2)
    log.write(True)

    os.remove(script.name)

    return sync.returncode


@logger.catch()
def find_occ():
    """locate the occ binary"""
    try:
        result = subprocess.run(['locate', 'occ'], stdout=subprocess.PIPE, text=True, check=False)
        if result.returncode == 0:
            return [entry for entry in result.stdout.strip().split('\n') if entry.endswith('occ')]
    except FileNotFoundError:
        pass

    result = subprocess.run(['find', '/', '-xdev', '-type', 'f', '-name', 'occ'],
            stdout=subprocess.PIPE, text=True, check=False)
    if result.returncode == 0:
        return result.stdout.strip().split('\n')
    raise FileNotFoundError("occ not found!")


@logger.catch()
def reindex_cloud(args, log):
    """run nextcloud reindex in users files"""
    #TODO: use config for nextcloud user and storage path
    local_path = re.match(r".*files/(.*)", args.local)
    if not local_path:
        local_user = getpass.getuser()
        if local_user == 'root':
            local_user = 'stephan'
        local_path = f"/media/storage/nextcloud-data/{local_user}/files/{args.local}"

    cloud_path = re.match(r".*data/([^/]+/files/.*)", local_path).groups()[0]
    binary_path = next((entry for entry in find_occ() if re.match(r".*occ", entry)), None)
    notify(f"Re-Indexing cloud folder ${cloud_path}...", 'info')
    subprocess.run(['sudo', '-u', 'www-data', binary_path, 'files:scan',
        '--path', cloud_path], check=True)
    log.block('Reindexing cloud', f"Cloud folder ${cloud_path} fully indexed.")
    notify(f"Cloud folder ${cloud_path} fully indexed.", 'ok')


def parse_parms(*parms):
    """Parse parameters from script or config file to shell format."""
    parameters = (f"shell {parms[0]} -p {parms[1] if parms[1] else ''}"
                  f"{parms[2]} {parms[3]} -l {parms[4] if parms[4] else ''}"
                  f"{base64.b64decode(parms[5])} {parms[6]}")
    return parameters.split()


@logger.catch()
def main():
    """Main sect"""
    global TRACE

#==============================================================================
# SCRIPT PARAMATERS TO EXECUTE THE SCRIPT AS A PROGRAMMED TASK
#==============================================================================

    # ftp user name ('user' by default)
    cron_user = 'user'
    # ftp password, with a minimum security measure, encoded by base64
    # ('password' by default)
    cron_pass = 'cGFzc3dvcmQ='
    # ftp server, name or ip ('localhost' by default)
    cron_site = 'localhost'
    # ftp server port. ('' by default)
    cron_port = ''
    # ftp directory
    cron_remote = 'directory'
    # local directory
    cron_local = '/your/path/to/your/local/directory/'
    # options, same as the shell mode. See shell mode help for more info
    cron_options = ''

#==============================================================================
# END PARAMETERS
#==============================================================================

    # first, parse the arguments
    parser = arguments()
    args = parser.parse_args()
    TRACE = args.trace

    # initalize the log
    log = Logger()

    if TRACE:
        print(f"ARGS: {args!r}")

    # set the arguments depending of execution mode
    if hasattr(args, 'cron') and args.cron:
        args = parser.parse_args(parse_parms(cron_site,
                                             cron_port,
                                             cron_remote,
                                             cron_local,
                                             cron_user,
                                             cron_pass,
                                             cron_options))
        mir_res = mirror(args, log)
    elif hasattr(args, 'cfg') and  args.cfg:
        cfg = ConfigParser()
        cfg.read(args.config_file)
        for sect in cfg.sections():
            args = parser.parse_args(parse_parms(cfg.get(sect, 'site'),
                                                 cfg.get(sect, 'port'),
                                                 cfg.get(sect, 'remote'),
                                                 cfg.get(sect, 'local'),
                                                 cfg.get(sect, 'user'),
                                                 cfg.get(sect, 'password'),
                                                 cfg.get(sect, 'options')))
            mir_res = mirror(args, log)
    else:  # shell
        if args.to_addrs:
            if args.smtp_config:
                if any([args.smtp_server, args.smtp_user, args.smtp_pass, args.from_addr]):
                    print("When --smtp-config is provided, --smtp-server, --smtp-user,"
                          " --smtp-pass, and --from-addr are ignored")
            else:
                if not all([args.smtp_server, args.smtp_user, args.smtp_pass, args.from_addr]):
                    parser.error("If --smtp-config is not provided, --smtp-server,"
                                 " --smtp-user, --smtp-pass, and --from-addr must all be provided")
        else:
            if any([args.smtp_server, args.smtp_user, args.smtp_pass, args.from_addr,
                    args.smtp_config]):
                parser.error("--to-addrs must be specified if any SMTP configuration is provided")
        mir_res = mirror(args, log)

    if args.update_cloud:
        reindex_cloud(args, log)

    # send the log by mail and write the log file
    if args.to_addrs:
        if args.smtp_config:
            smtp_config = {}
            with open(args.smtp_config, 'r', encoding='utf-8') as smtp_config_file:
                for line in smtp_config_file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Split the line into key and value
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove surrounding quotes if any
                    if ((value.startswith('"') and value.endswith('"')) or
                            (value.startswith("'") and value.endswith("'"))):
                        smtp_config[key] = value[1:-1]
                    else:
                        smtp_config[key] = value

            log.send('FTP Sync', send_from=smtp_config.get('from'), dest_to=args.to_addrs,
                     mail_server=smtp_config.get('server'), server_user=smtp_config.get('user'),
                     server_pass=smtp_config.get('pass'))

        else:
            log.send('FTP Sync', send_from=args.from_addr, dest_to=args.to_addrs,
                     mail_server=args.smtp_server, server_user=args.smtp_user,
                     server_pass=args.smtp_pass)

    notify('Ended Ok', 'ok')

if __name__ == "__main__":
    check_execs_posix_win('lftp')  # Check first if lftp is installed
    main()
