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














