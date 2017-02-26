Welcome to the FreeNAS X CLI!

.. index:: table of contents
.. _Table of Contents:

Table of Contents
*****************

1. `Introduction`_
2. `Getting Started`_
3. `General Navigation TAB Autocomplete and Global commands`_
4. `Help command`_
5. `System information and configuration`_
  a. `System information`_
  b. `System configuration`_
  c. `System session commands`_
6. `Network configuration`_
  a. `Simple static IP setup`_
7. `Volume creation and management`_
8. `Sharing`_
  a. `AFP Shares`_
  b. `NFS Shares`_
9. `Account management`_
  a. `Users`_
  b. `Groups`_
10. `Containers`_
  a. `Preface`_
  b. `VMs`_
11. `Services`_
  a. `Controlling services`_
  b. `Configuring services`_

.. index:: introduction
.. _Introduction:

Introduction
************

In FreeNAS 10, we have created an entirely new CLI which is intended to
offer full feature parity with the GUI and well beyond, offering
advanced user commands which would only add complexity and confusion to
the GUI. Our goal was also to eliminate the need to use the Unix shell
for that purpose as much as possible, giving users both high-level and
more fine grained control over the appliance while still maintaining
database integrity and logging these transactions properly. This CLI
supports TAB autocompletion, inline help, and other sexy features that
we hope will encourage its use!

.. index:: getting started
.. _Getting Started:

Getting Started
***************

There are a number of different ways to access the cli:

* From the console of the physical/VM box that you installed freenas on.
  By default, the cli is directly accessible from the console.

* By sshing to the box and typing **`cli`** from the shell.

* By accessing it from the webgui's console page:
  **freenas_10_ip/console**

* By running it directly on your client machine and connecting to a
  remote FreeNAS instance (this is still an advanced class and not yet
  officially supported, though the CLI is a fairly simple python
  program)

One way or another, once you have invoked the cli, it greets you with
this text:

.. code-block:: none

   Welcome to the FreeNAS CLI! Type 'help' to get started.

   You may try the following URLs to access the web user interface:
   http://fe80::20c:29ff:fe23:3173  http://192.168.221.136
   http://192.168.221.152           http://fe80::20c:29ff:fe23:3169
   127.0.0.1:>

.. note::  There may or may not be some kind of animal ASCII art
   involved here too. Do not worry, it is for your own protection.

The urls you see here are the various interfaces's providing you access
to your freenas box's webgui.

.. note:: You may only see one (IPv4 and IPv6) pair if you just have one
   interface.

At any point, if you want to see these urls again just type
**`showurls`** on the interactive cli prompt (from anywhere in the
cli) to print them out again:

.. code-block:: none

   127.0.0.1:>showurls
   You may try the following URLs to access the web user interface:
   http://fe80::20c:29ff:fe23:3173  http://192.168.221.136
   http://192.168.221.152           http://fe80::20c:29ff:fe23:3169

If you are running the cli from the shell (post sshing into the
machine), you can exit it using **`exit`** at any time.

.. code-block:: none

   127.0.0.1:>exit
   [root@myfreenas] ~#

.. index:: general navigation, tab auto, and global commands
.. _General Navigation TAB Autocomplete and Global commands:

General Navigation, TAB Autocomplete, and Global commands
*********************************************************

At any point or place in the cli to see the list of available commands
and namespaces, one can enter :kbd:`?` (or better referenced henceforth
as the **List Command**). Also, the very top level namespace that you
are dropped into upon first invoking the cli is called as the
**RootNamespace** from here on forward for the purposes of this HOWTO
document.

Whenever in doubt, press :kb:`?` (List Command) and see the list of
avaible commands in your current namespace. For example, let us examine
the output of this **List Command** from the **RootNamespace**:

.. code-block:: none

   127.0.0.1:>?
   Builtin items:
   eval     help     saveenv  history   sort    shutdown  showurls  echo
   exclude  showips  search   printenv  limit   less      select    exit
   top      setenv   clear    source    reboot  login     shell
   Current namespace items:
   help  account  calendar          disk     service  simulator  task    volume
   ?     boot     directoryservice  network  share    system     update

.. index:: help command
.. _Help command:

Help command
************

The **`help`** command is there to assist you with commands in the
cli.  To get an overview of the available commands, simply type
**`help`**:

.. code-block:: none

   127.0.0.1:>help
       Command                               Description                         
   /                  Go to the root namespace                                   
   ..                 Go up one namespace                                        
   -                  Go back to previous namespace                              
   ?                  Provides list of commands in this namespace                
   help               Provides help on commands                                  
   share              Configure and manage shares                                
   task               Manage tasks                                               
   disk               Provides information about installed disks                 
   directoryservice   Configure and manage directory service                     
   update             System Updates and their Configuration                     
   calendar           Provides access to task scheduled on a regular basis       

You will be given a scrollable list of the available commands and their
descriptions in the current namespace. To escape the help command press
:kbd:`q`.  You can also get help about individual commands and
namespaces, for example:

.. code-block:: none

   127.0.0.1:>help help
   Usage: help <command> <command> ...

   Provides usage information on particular command. If command can't be
   reached directly in current namespace, may be specified as chain,
   eg: "account users show".

   Examples:
       help
       help printenv
       help account users show

   To see the properties of a given namespace, use 'help properties'

Help on a higher level command will show the commands it expands to, for
example:

.. code-block:: none

   127.0.0.1:>help account
   Command                               Description
   /         Go to the root namespace
   ..        Go up one namespace
   -         Go back to previous namespace
   ?         Provides list of commands in this namespace
   user      System users
   group     System groups

   127.0.0.1:>help account user
   Command                               Description
   /         Go to the root namespace
   ..        Go up one namespace
   -         Go back to previous namespace
   delete    Removes item
   ?         Provides list of commands in this namespace
   create    Creates new item
   show      Lists items

You can also get the properties of a namespace by adding the keyword
**properties** to your help query, for example:

.. code-block:: none

   127.0.0.1:>help account user properties
  Property                                 Usage

  uid                                    An unused number greater than 1000 and less than 65535.
  name                                   Maximum 16 characters, though a maximum of 8 is recommended for interoperability.
                                         Can not begin with a hyphen or contain a space, a tab, a double quote, or any of
                                         these characters: , : + & # % ^ & ( ) ! @ ~ * ? < > = If a $ is used, it can only be
                                         the last character.
  fullname                               Place within double quotes if contains a space.
  group                                  By default when a user is created, a primary group with the same name as the user is
                                         also created. When specifying a different group name, that group must already exist.
  groups                                 List of additional groups the user is a member of. To add the user to other groups,
                                         enclose a space delimited list between double quotes and ensure the groups already
                                         exist.
  shell                                  Default is "/bin/sh". Can be set to full path of an existing shell. Type 'shells' to
                                         see the list of available shells.
  home                                   By default when a user is created, their home directory is not created. To create
                                         one, specify the full path to an existing dataset between double quotes.
  password                               Mandatory unless "password_disabled=true" is specified when creating the user.
                                         Passwords cannot contain a question mark.
  password_disabled                      Can be set to true or false. When set to true, disables password logins and
                                         authentication to CIFS shares but still allows key-based logins.
  locked                                 Can be set to true or false. While set to true, the account is disabled.
  email                                  Specify email address, enclosed between double quotes, to send that user's
                                         notifications to.
  administrator                          Can be set to true or false. When set to true, the user is allowed to use sudo to
                                         run commands with administrative permissions.
  pubkey                                 To configure key-based authentication, use the 'set' command to paste the user's SSH
                                         public key.
  domain                                 Domain, read_only string value
  delete_own_group                       Delete own group, accepts boolean values
  delete_home_directory                  Delete home directory, accepts boolean values

.. index:: system information and configuration
.. _System information and configuration:

System information and configuration
************************************

.. index:: system information
.. _System information:

System information
==================

You can get information and change various system settings with the
**`system`** top level command.  For instance, you can see your
hardware specs with **`system info`**:

.. code-block:: none

   127.0.0.1:>system info
   cpu_cores=1         cpu_model=Intel(R) Core(TM) i5-3570 CPU @ 3.40GHz
   cpu_clockrate=3400  memory_size=6413496320

You can get information about your version of FreeNAS with
**`system version`**:

.. code-block:: none

   127.0.0.1:>system version
   FreeNAS version (freenas_version)      FreeNAS-10.2-ALPHA-201511231130
   System version (system_version)        FreeBSD freenas.local 10.2-STABLE
                                          FreeBSD 10.2-STABLE #0
                                          ab9925e(freebsd10): Sat Nov 21
                                          00:05:53 PST 2015     root@build.ixs
                                          ystems.com:/tank/home/nightlies
                                          /freenas-
                                          build/_BE/objs/tank/home/nightlies
                                          /freenas-
                                          build/_BE/trueos/sys/FreeNAS.amd64
                                          amd64

If you want to know things like system up-time and the number of things
connected to the middlware, use **`system status`**:

.. code-block:: none

   127.0.0.1:>system status
   middleware-connections=12  started-at=1448327368.791504  up-since=18 minutes ago

You can view system events with the **`system event`** top level
command:

.. code-block:: none

   127.0.0.1:>system session show
   Session ID   IP Address     User name        Started at          Ended at
   1            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago
   2            unix         task.130        4 hours ago        none
   3            unix         task.129        4 hours ago        an hour ago
   4            unix         task.132        4 hours ago        none
   5            unix         task.131        4 hours ago        none
   6            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago
   7            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago
   8            127.0.0.1    etcd            4 hours ago        none
   9            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago
   10           127.0.0.1    dispatcherctl   4 hours ago        4 hours ago
   11           127.0.0.1    dispatcherctl   4 hours ago        4 hours ago

.. index:: system configuration
.. _System configuration:

System configuration
====================

The **`system`** top level command also has commands for
configuring various aspects of your system.  At the
**`system`** level you can configure things like *hostname*,
*timezone*, *syslog server*, and *language* options with
**`set`**:

.. code-block:: none

   127.0.0.1:>system set timezone=America/Los_Angeles
   127.0.0.1:>system set hostname=myfreenas.local
   127.0.0.1:>system show
   Time zone (timezone)              America/Los_Angeles
   Hostname (hostname)               myfreenas.local
   Syslog Server (syslog_server)     none
   Language (language)               en
   Console Keymap (console_keymap)   us.iso

If you need help figuring out what time zone options are available, you
can use the **`system timezones`** command, this will give you a
scrollable list of valid options.

To configure email options, use the **`system mail`** command:

.. code-block:: none

   127.0.0.1:>system mail set email=admin@foo.com 
   127.0.0.1:>system mail set server=mail.foo.com
   127.0.0.1:>system mail set username=admin@foo.com
   127.0.0.1:>system mail set password=mypassword
   127.0.0.1:>system mail show
   Email address (email)                    admin@foo.com 
   Email server (server)                    mail.foo.com
   SMTP port (port)                         25
   Authentication required (auth)           no
   Encryption type (encryption)             PLAIN
   Username for Authentication (username)   admin@foo.com

And finally for powerusers, there is a set of advanced options in
**`system advanced`**:

.. code-block:: none

   127.0.0.1:>system advanced set console_screensaver=yes
   127.0.0.1:>system advanced show
   Enable Console CLI (console_cli)       yes
   Enable Console Screensaver             yes
   (console_screensaver)
   Enable Serial Console                  no
   (serial_console)
   Serial Console Port (serial_port)      none
   Serial Port Speed (serial_speed)       none
   Enable powerd (powerd)                 no
   Default swap on drives (swapondrive)   2
   Enable Debug Kernel (debugkernel)      no
   Automatically upload crash dumps to    yes
   iXsystems (uploadcrash)
   Message of the day (motd)              FreeBSD ?.?.?  (UNKNOWN)
                                          FreeNAS (c) 2009-2015, The FreeNAS
                                          Development Team
                                          All rights reserved.
                                          FreeNAS is released under the
                                          modified BSD license.
                                          For more information, documentation,
                                          help or support, go here:
                                          http://freenas.org
   Periodic Notify User UID               0
   (periodic_notify_user)

.. index:: system session commands
.. _System session commands:

System session commands
=======================

There is also a namespace in the FreeNAS CLI specifically for dealing
with connected sessions, which administrators may find very useful.

You can view connected session information and history with the
**`session`** top level command, or limit that information to just
logged-in sessions with the **`w`** command:

.. code-block:: none

   127.0.0.1:>session show
   Session ID   IP Address     User name        Started at          Ended at     
   1            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago      
   2            unix         task.130        4 hours ago        none             
   3            unix         task.129        4 hours ago        an hour ago      
   4            unix         task.132        4 hours ago        none             
   5            unix         task.131        4 hours ago        none             
   6            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago      
   7            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago      
   8            127.0.0.1    etcd            4 hours ago        none             
   9            127.0.0.1    dispatcherctl   4 hours ago        4 hours ago      

   127.0.0.1:>w
    Session ID          User name           Address             Started at

    1978                root                unix,2133           22 hours ago
    1981                root                unix,6020           21 minutes ago

You can also use the **`session`** command to send messages to all
logged in users, e.g.

.. code-block:: none

   session wall "Hey, hosers! I'm shutting the system down in 5 minutes!"

As well as to send a message to a specific logged-in user; just get the
session ID from the **`w`** command and then
**`session id send <some text>`**.

You can also use the **`session id`** sub-namespace to query
individual attributes of a session and, in the future, to terminate a
session with great prejudice.

.. index:: network configuration
.. _Network configuration:

Network configuration
*********************

.. index:: simple static IP setup
.. _Simple static IP setup:

Simple static IP setup
======================

By default, FreeNAS is set to use a DHCP address, if you wish to set a
static IP, first turn off DHCP for your network port:

.. code-block:: none

   127.0.0.1:>network interface em0 set dhcp=false

Then create an alias with the IP you wish to set your system's IP to:

.. code-block:: none

   127.0.0.1:>network interface em0 alias create address=10.0.0.150 netmask=255.255.255.0

If you run **`network interface em0 show`**, you will see that
DHCP is disabled and it is listening on the static IP:

.. code-block:: none

   127.0.0.1:>network interface em0 show
   Name (name)                              em0
   Type (type)                              ETHER
   Enabled (enabled)                        yes
   DHCP (dhcp)                              no
   IPv6 autoconfiguration (ipv6_autoconf)   no
   Disable IPv6 (ipv6_disable)              no
   Link address (link_address)              08:00:27:e4:ce:17
   IP configuration (ip_config)             10.0.1.150/24
   Link state (link_state)                  up
   State (state)                            up
   -- Interface addresses --
   Address family   IP address   Netmask   Broadcast address
   INET             10.0.0.150   24        10.0.0.255

Now set the default gateway and DNS server:

.. code-block:: none

   127.0.0.1:>network config set ipv4_gateway=10.0.0.1 dns_servers=10.0.0.1
   127.0.0.1:>network config show
   IPv4 gateway (ipv4_gateway)                         10.0.0.1
   IPv6 gateway (ipv6_gateway)                         none
   DNS servers (dns_servers)                           10.0.0.1
   DNS search domains (dns_search)                     empty
   DHCP will assign default gateway (dhcp_gateway)     yes
   DHCP will assign DNS servers addresses (dhcp_dns)   yes

And finally set the default route for your network:

.. code-block:: none

   127.0.0.1:>network route create default gateway=10.0.0.1 network=10.0.0.0 netmask=255.255.255.0
   127.0.0.1:>network route show
    Name     Address family   Gateway    Network    Subnet prefix
   default   INET             10.0.0.1   10.0.0.0   24

To undo the static IP settings, go back to DHCP and reenable DHCP:

.. code-block:: none

   127.0.0.1:>network interface em0 set dhcp=yes
   127.0.0.1:>network interface em0 show
   Name (name)                              em0
   Type (type)                              ETHER
   Enabled (enabled)                        yes
   DHCP (dhcp)                              yes
   IPv6 autoconfiguration (ipv6_autoconf)   no
   Disable IPv6 (ipv6_disable)              no
   Link address (link_address)              08:00:27:e4:ce:17
   IP configuration (ip_config)             10.0.0.145/24
   Link state (link_state)                  up
   State (state)                            up
   -- Interface addresses --
   Address family   IP address   Netmask   Broadcast address

.. index:: volume creation and management
.. _Volume creation and management:

Volume creation and management
******************************

Before you create a volume, you should probably find out the names of
the disks you will be creating the volume with. You can do this by
using **`disk show`**:

.. code-block:: none

   127.0.0.1:>disk show
   Disk path   Disk name     Size      Online   Allocation
   /dev/ada0   ada0        17.18 GiB   yes      boot device
   /dev/ada5   ada5        6.44 GiB    yes      unallocated
   /dev/ada1   ada1        6.44 GiB    yes      unallocated
   /dev/ada2   ada2        6.44 GiB    yes      unallocated
   /dev/ada3   ada3        6.44 GiB    yes      unallocated
   /dev/ada4   ada4        6.44 GiB    yes      unallocated

On the left of the table you see the disk names and on the right you can
see the allocation status of these disks.  Be sure to only use
*unallocated* disks since those are ones that are not currently being
used.

The command to create a volume is **`volume create`**.  This
command takes as arguments the name of the volume, the type of volume
you are creating, and the disks you are assigning to the volume.  For
example:

.. code-block:: none

   127.0.0.1:>volume create tank type=raidz1 disks=ada1,ada2,ada3

To see the topology of the newly created volume,
use **`show_topology`**:

.. code-block:: none

   127.0.0.1:>volume tank show_topology
    +-- data
        +-- raidz1
            |-- /dev/ada1 (disk)
            |-- /dev/ada2 (disk)
            `-- /dev/ada3 (disk)

If you type **`disk show`** again you will see that these disks
are now marked as allocated to tank:

.. code-block:: none

   127.0.0.1:>disk show
   Disk path   Disk name     Size      Online       Allocation
   /dev/ada5   ada5        6.44 GiB    yes      unallocated
   /dev/ada4   ada4        6.44 GiB    yes      unallocated
   /dev/ada0   ada0        17.18 GiB   yes      boot device
   /dev/ada1   ada1        6.44 GiB    yes      part of volume tank
   /dev/ada2   ada2        6.44 GiB    yes      part of volume tank
   /dev/ada3   ada3        6.44 GiB    yes      part of volume tank

The valid types for volume create are: *disk*, *mirror*, *raidz1*,
*raidz2*, *raidz3*, and *auto*.  If you do not specify a type, *auto*
is assumed and FreeNAS will try to decide the best topology for you (if
you use a multiple of 2 disks, you will get a stripe of *mirrors* or if
you use a multiple of 3 disks you get a stripe of *raidz1*).

.. code-block:: none

   127.0.0.1:>volume create tank disks=ada1,ada2,ada3,ada4

.. code-block:: none

   127.0.0.1:>volume tank show_topology
    +-- data
        +-- mirror
            |-- /dev/ada1 (disk)
            `-- /dev/ada2 (disk)
        +-- mirror
            |-- /dev/ada3 (disk)
            `-- /dev/ada4 (disk)

If you want to make some kind of custom configuration or add disks to a
volume later you can use **`add_vdev`** to add another set of
disks. For example, we created a mirror but then wanted to have a second
mirror striped to it:

.. code-block:: none

   127.0.0.1:>volume create tank type=mirror disks=ada1,ada2
   127.0.0.1:>volume tank show_topology
    +-- data
        +-- mirror
            |-- /dev/ada1 (disk)
            `-- /dev/ada2 (disk)
   127.0.0.1:>volume tank add_vdev type=mirror disks=ada3,ada4
   127.0.0.1:>volume tank show_topology
    +-- data
        +-- mirror
            |-- /dev/ada1 (disk)
            `-- /dev/ada2 (disk)
        +-- mirror
            |-- /dev/ada3 (disk)
            `-- /dev/ada4 (disk)

You can use **`extend_vdev`** to add a disk to an existing mirror,
for example assume we have a tank with a single mirror that we wish to
extend:

.. code-block:: none

   127.0.0.1:>volume create tank disks=ada1,ada2
   127.0.0.1:>volume tank extend_vdev vdev=ada1 ada3
   127.0.0.1:>volume tank show_topology
    +-- data
        +-- mirror
            |-- /dev/ada1 (disk)
            |-- /dev/ada2 (disk)
            `-- /dev/ada3 (disk)

If at any time you wish to delete your volume, you can do this with
**`delete`**:

.. code-block:: none

   127.0.0.1:>volume delete tank

To offline or online a disk within a Volume you can use
**`offline`** and **`online`**:

.. code-block:: none

   127.0.0.1:>volume tank show_disks
     Name      Status
   /dev/ada1   ONLINE
   /dev/ada2   ONLINE

   127.0.0.1:>volume tank offline ada1
   127.0.0.1:>volume tank show_disks
     Name      Status
   /dev/ada1   OFFLINE
   /dev/ada2   ONLINE

   127.0.0.1:>volume tank online ada1
   127.0.0.1:>volume tank show_disks
     Name      Status
   /dev/ada1   ONLINE
   /dev/ada2   ONLINE

To run a scrub on your volume, use **`scrub`**:

.. code-block:: none

   127.0.0.1:>volume tank scrub

To detatch/export a volume, use the **`detach`** volume command.
After detaching, you will notice it is no longer visible in
**`volume show`**:

.. code-block:: none

   127.0.0.1:>volume show
   Volume name   Status   Mount point     Last scrub time     Last scrub errors
   tank          ONLINE   /mnt/tank     2015-11-10 23:04:46   0

   127.0.0.1:>volume detach tank
   ...
   127.0.0.1:>volume show
   Volume name   Status   Mount point   Last scrub time   Last scrub errors

If you wish to import your volume tank, first use **`find`** to see
if your volume is visible then use **`import`** to import it:

.. code-block:: none


   127.0.0.1:>volume find
      ID       Volume name   Status
   1.845e+19   tank          ONLINE
   127.0.0.1:>volume import tank
   127.0.0.1:>volume show
   Volume name   Status   Mount point   Last scrub time   Last scrub errors
   tank          ONLINE   /mnt/tank     none              none

.. index:: sharing
.. _Sharing:

Sharing
*******

After you have created your volume, you can now setup shares on your
volume to share files with the rest of your network. The **shares**
namespace is split into 4 sets of commands for different share types:
*NFS*, *AFP*, *SMB*, and *iSCSI* with a main **shares** namespace to
view them all from.

.. index:: AFP shares
.. _AFP shares:

AFP shares
==========

One basic type of share you can create are AFP shares. AFP is typically
used for sharing files with Macintosh computers. AFP shares are created
with **`share afp create`**. A basic AFP share can be created as
follows:

.. code-block:: none

   127.0.0.1:>share afp create foo volume=tank

When it is created, you will be able to see it in two different places:
the shares overview and the afp share namespace.

.. code-block:: none

   127.0.0.1:>share show
   Share Name   Share Type   Volume   Dataset Path   Description
   foo          afp          tank     tank/afp/foo

   127.0.0.1:>share afp show
   Share name   Target volume   Compression   Read only   Time machine
   foo          tank            lz4           no          no

To see more details on the AFP share, you can use **`show`** on the
share itself:

.. code-block:: none

   127.0.0.1:>share afp foo show
   Share name (name)                      foo
   Share type (type)                      afp
   Target volume (volume)                 tank
   Compression (compression)              lz4
   Allowed hosts/networks (hosts_allow)   none
   Denied hosts/networks (hosts_deny)     none
   Allowed users/groups (users_allow)     none
   Denied users/groups (users_deny)       none
   Read only (read_only)                  no
   Time machine (time_machine)            no

If you want to set one of these properties of your share, use
**`set`**:

.. code-block:: none

   127.0.0.1:>share afp foo set read_only=true
   127.0.0.1:>share afp foo set users_allow=tom, frank
   127.0.0.1:>share afp foo set users_deny=bob
   127.0.0.1:>share afp foo set hosts_allow=192.168.1.100,foobar.local
   127.0.0.1:>share afp foo show
   Share name (name)                      foo
   Share type (type)                      afp
   Target volume (volume)                 tank
   Compression (compression)              lz4
   Allowed hosts/networks (hosts_allow)   192.168.1.100
                                          foobar.local
   Denied hosts/networks (hosts_deny)     none
   Allowed users/groups (users_allow)     tom
                                          frank
   Denied users/groups (users_deny)       bob
   Read only (read_only)                  yes
   Time machine (time_machine)            no

Now that you have a share, you must enable the AFP service:

.. code-block:: none

   127.0.0.1:>service afp config set enable=yes
   Service name (name)   afp
   State (state)         RUNNING
   Process ID (pid)      none

You can further configure the AFP service by using **`set`**:

.. code-block:: none

   127.0.0.1:>service afp config set bind_addresses=192.168.1.50
   127.0.0.1:>service afp config set guest_enable=yes
   127.0.0.1:>service afp config show
   Enabled (enable)                        yes
   Share Home Directory (homedir_enable)   no
   Home Directory Path (homedir_path)      none
   Home Directory Name (homedir_name)      none
   Auxiliary Parameters (auxiliary)        none
   Connections limit (connections_limit)   50
   Guest user (guest_user)                 nobody
   Enable guest user (guest_enable)        yes
   Bind Addresses (bind_addresses)         192.168.1.50
   Database Path (dbpath)                  none

And finally, to delete an AFP share, simply use **`delete`**, but
be aware this will also delete the dataset that the share is on:

.. code-block:: none

   127.0.0.1:>share afp delete foo

.. index:: NFS shares
.. _NFS Shares:

NFS Shares
==========

Another basic type of share you can create are NFS shares. NFS is
typically used for sharing files with Unix systems. NFS shares are
created with **`share nfs create`**. A basic NFS share can be
created as follows:

.. code-block:: none

   127.0.0.1:>share nfs create bar volume=tank

Like AFP shares, you can also see the NFS share in the shares overview
and the NFS share namespace.

.. code-block:: none

   127.0.0.1:>share show
   Share Name   Share Type   Volume   Dataset Path   Description
   bar          nfs          tank     tank/nfs/bar
   127.0.0.1:>share nfs show
   Share name     Target     Compressio   All direct   Read only   Security
                  volume         n          ories
   bar          tank         lz4          no           no          none

To see more details on the NFS share you can use **`show`** on the
share itself:

.. code-block:: none

   127.0.0.1:>share nfs bar show
   Share name (name)                bar
   Share type (type)                nfs
   Target volume (volume)           tank
   Compression (compression)        lz4
   All directories (alldirs)        no
   Read only (read_only)            no
   Root user (root_user)            none
   Root group (root_group)          none
   All user (all_user)              none
   All group (all_group)            none
   Allowed hosts/networks (hosts)   none
   Security (security)              none

If you want to set one of these properties of your share, use
**`set`**:

.. code-block:: none

   127.0.0.1:>share nfs bar set alldirs=true
   127.0.0.1:>share nfs bar set read_only=true
   127.0.0.1:>share nfs bar set hosts=foobar.local,10.0.0.101
   127.0.0.1:>share nfs bar show
   Share name (name)                bar
   Share type (type)                nfs
   Target volume (volume)           tank
   Compression (compression)        lz4
   All directories (alldirs)        yes
   Read only (read_only)            yes
   Root user (root_user)            none
   Root group (root_group)          none
   All user (all_user)              none
   All group (all_group)            none
   Allowed hosts/networks (hosts)   foobar.local
                                    10.0.0.101
   Security (security)              none

Now that you have a share, you must enable the NFS service:

.. code-block:: none

   127.0.0.1:>service nfs config set enable=yes
   127.0.0.1:>service nfs show
   Service name (name)   nfs
   State (state)         RUNNING
   Process ID (pid)      5760

You can further configure the NFS service by using **`set`**:

.. code-block:: none

   127.0.0.1:>service nfs config set servers=3
   127.0.0.1:>service nfs config set v4=yes
   127.0.0.1:>service nfs config show
   Enabled (enable)                      yes
   Number of servers (servers)           3
   Enable UDP (udp)                      no
   Enable NFSv4 (v4)                     yes
   Enable NFSv4 Kerberos (v4_kerberos)   no
   Bind addresses (bind_addresses)       none
   Mountd port (mountd_port)             none
   RPC statd port (rpcstatd_port)        none
   RPC Lockd port (rpclockd_port)        none

And finally, to delete an NFS share, simply use **`delete`**.
Please be aware this will also delete the dataset that the share is on:

.. code-block:: none

   127.0.0.1:>share nfs delete bar

.. index:: account management
.. _Account management:

Account management
******************

FreeNAS has users and groups with various permissions similar to those
you would find on a Unix platform. In this section you will learn how to
manage users and groups using the **`account`** top level command.

.. index:: users
.. _Users:

Users
=====

Under the **`account user`** command you can create and set
properties of a user.  To create a user, use
**`account user create`**:

.. code-block:: none

   127.0.0.1:>account user create foo password=mypassword
   127.0.0.1:>account user foo show
      Property              Description             Value       Settable
  uid                 User ID                    1002           yes
  name                User name                  foo            yes
  fullname            Full name                  User &         yes
  group               Primary group              foo            yes
  groups              Auxiliary groups           <empty>        yes
  shell               Login shell                /bin/sh        yes
  home                Home directory             /nonexistent   yes
  password            Password                   none           yes
  password_disabled   Password Disabled          none           yes
  locked              Locked                     none           yes
  email               Email address              none           yes
  administrator       Administrator privileges   no             yes
  pubkey              SSH public key             none           yes
  domain              Domain                     local          no

An account must either have a password set upon creation or have the
property **password_disabled** turned on. If you do not specify a group
for your user upon creation it will attempt to create a group with the
same name as the username for that user.

If you want to change a property of a user, use **`set`**:

.. code-block:: none

   127.0.0.1:>account user foo set email=foo@foobar.com
   127.0.0.1:>account user foo show
      Property              Description              Value        Settable
  uid                 User ID                    1002             yes
  name                User name                  foo              yes
  fullname            Full name                  User &           yes
  group               Primary group              foo              yes
  groups              Auxiliary groups           <empty>          yes
  shell               Login shell                /bin/sh          yes
  home                Home directory             /nonexistent     yes
  password            Password                   none             yes
  password_disabled   Password Disabled          none             yes
  locked              Locked                     none             yes
  email               Email address              foo@foobar.com   yes
  administrator       Administrator privileges   no               yes
  pubkey              SSH public key             none             yes
  domain              Domain                     local            no

To delete a user, use **`delete`**:

.. code-block:: none

   127.0.0.1:>account user delete foo

.. index:: groups
.. _Groups:

Groups
======

Groups are managed by the **`account group`** commands. To create
a group use **`account group create`**:

.. code-block:: none

   127.0.0.1:>account group create bar
   127.0.0.1:>account group bar show
   Group name (name)         bar
   Group ID (gid)            1001
   Builtin group (builtin)   no

To change a group's name use **`set`**:

.. code-block:: none

   127.0.0.1:>account group bar set name=baz

User to group relationships are handled at the user level, so if to add
a user to a group, you must use **`account user`**. Users have 2
properties for groups, *group* and *groups*. The singular *group*
property contains the user's primary group, and *groups* is a set
property that contains the auxiliary groups.

Suppose we want to create a user named *foo* and we want to add it to
our group *baz*:

.. code-block:: none

   127.0.0.1:>account user create foo group=baz password=mypassword

Then suppose we want to give this user admin privileges so we add it to
the *wheel* group:

.. code-block:: none

   127.0.0.1:>account user foo set groups=wheel

The user should then look like this after running **`show`**:

.. code-block:: none

   127.0.0.1:>account user foo show
    Property              Description              Value        Settable
  uid                 User ID                    1002             yes
  name                User name                  foo              yes
  fullname            Full name                  User &           yes
  group               Primary group              foo              yes
  groups              Auxiliary groups           wheel            yes
  shell               Login shell                /bin/sh          yes
  home                Home directory             /nonexistent     yes
  password            Password                   none             yes
  password_disabled   Password Disabled          none             yes
  locked              Locked                     none             yes
  email               Email address              foo@foobar.com   yes
  administrator       Administrator privileges   no               yes
  pubkey              SSH public key             none             yes
  domain              Domain                     local            no

And finally, to delete a group, use **`delete`**:

.. code-block:: none

   127.0.0.1:>account group delete baz

.. index:: containers
.. _Containers:

Containers
**********

.. index:: containers preface
.. _preface:

Preface
=======

Virtual machine support is an experimental feature which is not yet
fully supported in the CLI. For example, if you want to be able to
access the Internet from your VMs, you will need to create a bridge
interface, add your main network interface to it (please refer to the
:ref:`Network configuration` section to learn how to do that), and then
issue the following command manually (for now):

.. code-block:: none

   127.0.0.1:>!dsutil config-set container.bridge '"bridgeX"'

where **bridgeX** is name of previously created bridge interface.

.. index:: VMs
.. _VMs:

VMs
===

To create a BHyVe virtual machine called *myvm* running inside FreeNAS,
use this command:

.. code-block::

   127.0.0.1:>vm create name=myvm datastore=tank bootloader=GRUB

Pass *volume name* where you want your VM data disks to be stored as a
*datastore* parameter. You also need to set the bootloader type: either
*BHYVELOAD* (if you're installing a FreeBSD VM) or *GRUB* (which is
suitable for most Linux distributions and FreeNAS).

When the VM is created, you can add data disk and CD images to the VM
by going to the **vm myvm disks** namespace:

.. code-block:: none

   127.0.0.1:>vm myvm disks create name=disk1 type=DISK size=8G
   127.0.0.1:>vm myvm disks create name=cdrom1 type=CDROM path=/mnt/tank/path/to/installer/image.iso

The last step is to set the boot device. In this example, we want to
boot off a CD image to install the operating system on the VM:

.. code-block:: none

   127.0.0.1:>vm myvm set boot_device=cdrom1

Virtual machine is ready to be started:

.. code-block:: none

   127.0.0.1:>vm myvm start

To see the virtual machine console, navigate to
`http://<freenas-ip>:8180/vm`_ and select VM from the dropdown list.

.. index:: services
.. _Services:

Services
********

FreeNAS has various services that run on it for sharing files,
monitoring your NAS, and other purposes. In this section, you will learn
how to configure and control these services through the CLI.

.. index:: controlling services
.. _Controlling Services:

Controlling Services
====================

The **`service show`** command gives you a list of all the
currently running services:

.. code-block:: none

   127.0.0.1:>service show
   Service name    State    Process ID
   smartd         STOPPED   none
   afp            STOPPED   none
   haproxy        STOPPED   none
   lldp           STOPPED   none
   sshd           RUNNING   1054
   tftpd          STOPPED   none

To view the status of an individual service, use
**`service <service name> show`**. For example:

.. code-block:: none

   127.0.0.1:>service ftp show
   Service name (name)   ftp
   State (state)         STOPPED
   Process ID (pid)      none

To enable the service, use
**`service <service name> config set enable=true`**. For exmaple:

.. code-block:: none

   127.0.0.1:>service ftp config set enable=true
   127.0.0.1:>service ftp show
   Service name (name)   ftp
   State (state)         RUNNING
   Process ID (pid)      3959

Notice when the service is enabled, it is also started. If you want to
stop the service but leave it enabled upon reboot, use
**`service <service name> stop`**. For example:

.. code-block:: none

   127.0.0.1:>service ftp stop
   127.0.0.1:>service ftp show
   Service name (name)   ftp
   State (state)         STOPPED
   Process ID (pid)      none

To start the service back up, use
**`service <service name> start`**:

.. code-block:: none

   127.0.0.1:>service ftp start
   127.0.0.1:>service ftp show
   Service name (name)   ftp
   State (state)         RUNNING
   Process ID (pid)      4218

To restart a servce, use **`service <service name> restart`**:

.. code-block:: none

   127.0.0.1:>service ftp restart
   127.0.0.1:>service ftp show
   Service name (name)   ftp
   State (state)         RUNNING
   Process ID (pid)      4457

Notice that it has a different *pid* since the service was restarted.
To have a service do a graceful reload, use
**`service <service name> reload`**:

.. code-block:: none

   127.0.0.1:>service ftp reload
   Service name (name)   ftp
   State (state)         RUNNING
   Process ID (pid)      4457

.. index:: configuring services
.. _Configuring Services:

Configuring Services
====================

To view the configuration of a service, use
**`service <service name> config show`**:

.. code-block:: none

   127.0.0.1:>service sshd config show
   Enabled (enable)                                      yes
   sftp log facility (sftp_log_facility)                 AUTH
   Allow public key authentication (allow_pubkey_auth)   yes
   Enable compression (compression)                      no
   Allow password authentication (allow_password_auth)   yes
   Allow port forwarding (allow_port_forwarding)         no
   Permit root login (permit_root_login)                 yes
   sftp log level (sftp_log_level)                       ERROR
   Port (port)                                           22

Along with being able to enable a service from this namespace, you are
also able to set various properties of the service with
**`service <service name> config set`**:

.. code-block:: none

   127.0.0.1:>service sshd config set allow_port_forwarding=true
   127.0.0.1:>service sshd config show
   Enabled (enable)                                      yes
   sftp log facility (sftp_log_facility)                 AUTH
   Allow public key authentication (allow_pubkey_auth)   yes
   Enable compression (compression)                      no
   Allow password authentication (allow_password_auth)   yes
   Allow port forwarding (allow_port_forwarding)         yes
   Permit root login (permit_root_login)                 yes
   sftp log level (sftp_log_level)                       ERROR
   Port (port)                                           22

.. note:: Some services like *sshd* restart upon setting a property,
   while others will do a graceful reload, depending on what the service
   supports.
