# Welcome to FreeNAS X CLI!

## Introduction

With FreeNAS 10 we completely redisgned the CLI such that it should be at full feature parity with the GUI (and even more to include advance user commands). It was our goal to eliminate the need to use the shell as much as possible, by giving the user a much fine grained control over the appliance while still maintaining the transactions in the database. It supports TAB autocompletion and other sexy features!

## Getting Started

**Ways to get to the cli:**

* From the console of the physical/VM box that you installed freenas on. By default the cli would be accessible directly from there.

* By sshing to the box and typing `cli` from the shell

* By accessing it from the webgui's console page: freenas_10_ip/console

Ok so now that you have reached the cli it will greet you with the following:

```
Welcome to the FreeNAS CLI! Type 'help' to get started.

You may try the following URLs to access the web user interface:
http://fe80::20c:29ff:fe23:3173  http://192.168.221.136
http://192.168.221.152           http://fe80::20c:29ff:fe23:3169
127.0.0.1:>
```

The urls you see here are the various interfaces's providing you access to your freenas box's webgui.
(Note: You may only see one (IPv4 and IPv6) pair if you just have one interface.)

At any point if you want to see these urls again just type `showurls` on the interactive cli prompt (from anywhere in the cli) to print them out again.

```
127.0.0.1:>showurls
You may try the following URLs to access the web user interface:
http://fe80::20c:29ff:fe23:3173  http://192.168.221.136
http://192.168.221.152           http://fe80::20c:29ff:fe23:3169
```

If you are running the cli from the shell (post sshing into the machine) you can exit it using the `exit` command at any time.

```
127.0.0.1:>exit
[root@myfreenas] ~# 
```

## General Navigation, TAB Autocomplete and Global Commands

At any point or place in the cli to see the list of available commands and namespaces, one can enter the `?` character (or better referenced henceforth as the List Command). Also the very top level namespace that you are dropped into upon first invoking the cli is called as the RootNamespace from here on forward for purpose of this HOWTO document.

Whenever in doubt, press the `?` character (List Command) and see the list of avaible commands in your current namespace. For example let us examine the out of this List Command from the RootNamespace:

```
127.0.0.1:>?
Builtin items:
eval     help     saveenv  history   sort    shutdown  showurls  echo
exclude  showips  search   printenv  limit   less      select    exit
top      setenv   clear    source    reboot  login     shell
Current namespace items:
help  account  calendar          disk     service  simulator  task    volume
?     boot     directoryservice  network  share    system     update
```

## Help command

The help command is there to assist you with commands in the cli.  To get an overview of the available commands, simply type `help`.

```
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
...
```

You will be given a scrollable list of the available commands and their descriptions in the current namespace.  To escape the help command press q.  You can also get help about individual commands and namespaces, for example:

```
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
```

Help on a higher level command will show the commands it expands to, for example:


```
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
```

You can also get the properties of a namespace by adding the keyword "properties" to your help query, for example:

```
127.0.0.1:>help account user properties
    Property           Description             Type        
uid                 User ID             number (read only) 
username            User name           string             
fullname            Full name           string             
group               Primary group       string             
groups              Auxilliary groups   set                
shell               Login shell         string             
home                Home directory      string             
password            Password            string             
password_disabled   Password Disabled   boolean            
locked              Locked              boolean            
email               Email address       string             
sudo                Sudo allowed        boolean            
pubkey              SSH public key      string             
```

## Network configuration

### Simple static IP setup

By default FreeNAS is set to use a DHCP address, if you wish to set a static IP, first turn off DHCP for your network port:

```
127.0.0.1:>network interface em0 set dhcp=false
```

Then create an alias with the IP you wish to set your system's IP to:

```
127.0.0.1:>network interface em0 create 10.0.0.150 netmask=255.255.255.0
```

If you do network interface em0 show, you will see that DHCP is disabled and it is listening on the static IP:

```
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
```

Now set the default gateway and DNS server:

```
127.0.0.1:>network config ipv4_gateway=10.0.0.1 dns_servers=10.0.0.1
127.0.0.1:>network config show
IPv4 gateway (ipv4_gateway)                         10.0.0.1 
IPv6 gateway (ipv6_gateway)                         none     
DNS servers (dns_servers)                           10.0.0.1 
DNS search domains (dns_search)                     empty    
DHCP will assign default gateway (dhcp_gateway)     yes      
DHCP will assign DNS servers addresses (dhcp_dns)   yes  
```

And finally set the default route for your network:

```
127.0.0.1:>network route create default gateway=10.0.0.1 network=10.0.0.0 netmask=255.255.255.0
127.0.0.1:>network route show
 Name     Address family   Gateway    Network    Subnet prefix 
default   INET             10.0.0.1   10.0.0.0   24      
```

To undo the static IP settings go back to DHCP, just reenable DHCP:

```
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
```

## Volume creation and management

Before you create a volume you should probably find out the names of the disks you will be creating the volume with.  You can do this by using the command `disk show`:

```
127.0.0.1:>disk show
Disk path   Disk name     Size      Online   Allocation  
/dev/ada0   ada0        17.18 GiB   yes      boot device 
/dev/ada5   ada5        6.44 GiB    yes      unallocated 
/dev/ada1   ada1        6.44 GiB    yes      unallocated 
/dev/ada2   ada2        6.44 GiB    yes      unallocated 
/dev/ada3   ada3        6.44 GiB    yes      unallocated 
/dev/ada4   ada4        6.44 GiB    yes      unallocated
```

On the left of the table you see the disk names and on the right you can see the allocation status of these disks.  Be sure to only use "unallocated" disks since those are ones that are not currently being used.

The command to create a volume is `volume create`.  This command takes as arguments the name of the volume, the type of volume you are creating and the disks you are assigning to the volume.  For example:

```
127.0.0.1:>volume create tank type=raidz1 disks=ada1,ada2,ada3
```

To see the topology of the newly created volume, use the command `show_topology`:

```
127.0.0.1:>volume tank show_topology  
 +-- data
     +-- raidz1
         |-- /dev/ada1 (disk)
         |-- /dev/ada2 (disk)
         `-- /dev/ada3 (disk)
```

If you type `disk show` again you will see that these disks are now marked as allocated to tank:

```
127.0.0.1:>disk show
Disk path   Disk name     Size      Online       Allocation      
/dev/ada5   ada5        6.44 GiB    yes      unallocated         
/dev/ada4   ada4        6.44 GiB    yes      unallocated         
/dev/ada0   ada0        17.18 GiB   yes      boot device         
/dev/ada1   ada1        6.44 GiB    yes      part of volume tank 
/dev/ada2   ada2        6.44 GiB    yes      part of volume tank 
/dev/ada3   ada3        6.44 GiB    yes      part of volume tank 
```

The valid types for volume create are: disk, mirror, raidz1, raidz2, raidz3 and auto.  If you do not specify a type `auto` is assumed and FreeNAS will try to decide the best topology for you (if you use a multiple of 2 disks, you will get a stripe of mirrors or if you use a multiple of 3 disks you get a stripe of raidz1).


```
127.0.0.1:>volume create tank disks=ada1,ada2,ada3,ada4
...
127.0.0.1:>volume tank show_topology                          
 +-- data
     +-- mirror
         |-- /dev/ada1 (disk)
         `-- /dev/ada2 (disk)
     +-- mirror
         |-- /dev/ada3 (disk)
         `-- /dev/ada4 (disk)
```

If you want to make some kind of custom configuration or add disks to a volume later you can use the `add_vdev` command to add another set of disks.  For example we created a mirror but then wanted to have a second mirror striped to it:

```
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
```

You can use the `extend_vdev` command to add a disk to an existing mirror, for example assume we have a tank with a single mirror that we wish to extend:

```
127.0.0.1:>volume create tank disks=ada1,ada2
127.0.0.1:>volume tank extend_vdev vdev=ada1 ada3
127.0.0.1:>volume tank show_topology 
 +-- data
     +-- mirror
         |-- /dev/ada1 (disk)
         |-- /dev/ada2 (disk)
         `-- /dev/ada3 (disk)
```

If at any time you wish to delete your volume, you can do this with the 'delete' command:

```
127.0.0.1:>volume delete tank
```

To offline or online a disk within a Volume you can use the `offline` and `online` commands:

```
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

```

To run a scrub on your volume, use the `scrub` command:

```
127.0.0.1:>volume tank scrub
```

To detatch/export a volume, use the 'detach' volume command.  After detaching you will notice it is no longer visible in volume show:

```
127.0.0.1:>volume show
Volume name   Status   Mount point     Last scrub time     Last scrub errors 
tank          ONLINE   /mnt/tank     2015-11-10 23:04:46   0                 

127.0.0.1:>volume detach tank
...
127.0.0.1:>volume show
Volume name   Status   Mount point   Last scrub time   Last scrub errors 
```

If you wish to import your volume tank, first use `find` to see if your volume is visible then use `import` to import it:

```
127.0.0.1:>volume find       
   ID       Volume name   Status 
1.845e+19   tank          ONLINE 
127.0.0.1:>volume import tank
127.0.0.1:>volume show
Volume name   Status   Mount point   Last scrub time   Last scrub errors 
tank          ONLINE   /mnt/tank     none              none           
```

## Sharing

After you have created your volume, you can now setup shares on your volume to share files with the rest of your network.  The shares namespace is split into 4 sets of commands for different share types, NFS, AFP, SMB and iSCSI with a main `shares` namespace to view them all from.

### AFP shares

One basic type of share you can create are AFP shares.  AFP is typically used for sharing files with Macintosh computers.  AFP shares are created with the command `share afp create`.  A basic AFP share can be created as follows:

```
127.0.0.1:>share afp create foo volume=tank
```

When it is created you will be able to see it in two different places, the shares overview and the afp share namespace.

```
127.0.0.1:>share show
Share Name   Share Type   Volume   Dataset Path   Description 
foo          afp          tank     tank/afp/foo       

127.0.0.1:>share afp show
Share name   Target volume   Compression   Read only   Time machine 
foo          tank            lz4           no          no           
```

To see more details on the AFP share you can use the show command on the share itself:

```
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
```

If you want to set one of these properties of your share, use the `set` command:

```
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
```

Now that you have a share, you must enable the AFP service:

```
127.0.0.1:>service afp config set enable=yes
Service name (name)   afp     
State (state)         RUNNING 
Process ID (pid)      none 
```

You can further configure the AFP service by using the set command:

```
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
```

And finally, to delete an AFP share, simply use the `delete` command, be aware this will also delete the dataset that the share is on:

```
127.0.0.1:>share afp delete foo
```

### NFS Shares

Another basic type of share you can create are NFS shares.  NFS is typically used for sharing files with Unix systems.  NFS shares are created with the command `share nfs create`.  A basic NFS share can be created as follows:

```
127.0.0.1:>share nfs create bar volume=tank
```

Like AFP shares, you can also see the NFS share in the shares overview and the NFS share namespace.

```
127.0.0.1:>share show
Share Name   Share Type   Volume   Dataset Path   Description 
bar          nfs          tank     tank/nfs/bar       
127.0.0.1:>share nfs show
Share name     Target     Compressio   All direct   Read only   Security 
               volume         n          ories                           
bar          tank         lz4          no           no          none    
```

To see more details on the NFS share you can use the show command on the share itself:

```
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
```

If you want to set one of these properties of your share, use the `set` command:

```
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
```

Now that you have a share, you must enable the NFS service:
```
127.0.0.1:>service nfs config set enable=yes
127.0.0.1:>service nfs show
Service name (name)   nfs     
State (state)         RUNNING 
Process ID (pid)      5760   
```

You can further configure the NFS service by using the set command:

```
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
```

And finally, to delete an NFS share, simply use the `delete` command, be aware this will also delete the dataset that the share is on:

```
127.0.0.1:>share nfs delete bar
```

